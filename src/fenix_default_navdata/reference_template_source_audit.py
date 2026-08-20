from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping


class ReferenceTemplateSourceAuditError(RuntimeError):
    """参考包与官方模板来源审计失败。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path) -> dict[str, Path]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ReferenceTemplateSourceAuditError(f"目录不存在: {root}")
    return {
        path.relative_to(root).as_posix().lower(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "_work" not in {part.casefold() for part in path.relative_to(root).parts}
    }


def _role(relative_path: str) -> str:
    name = relative_path.rsplit("/", 1)[-1]
    suffix = Path(name).suffix.casefold()
    if suffix == ".bgl":
        return "navigation_bgl"
    if name == "bglindex.bout":
        return "derived_bgl_index"
    if name == "layout.json":
        return "package_layout"
    if name == "manifest.json":
        return "package_manifest"
    if name.endswith(".json") and "/contentinfo/" in f"/{relative_path}":
        return "contentinfo_json"
    if suffix in {".jpg", ".jpeg", ".png"}:
        return "package_media"
    return "other"


def _metadata(path: Path, relative_path: str) -> dict[str, object]:
    return {
        "path": relative_path,
        "role": _role(relative_path),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _template_index(
    template_roots: Mapping[str, Path],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, list[dict[str, object]]]]:
    by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, object]]] = defaultdict(list)
    for template_name, root in template_roots.items():
        for relative_path, path in _files(root).items():
            item = _metadata(path, relative_path)
            item["template"] = template_name
            by_hash[str(item["sha256"])].append(item)
            by_name[relative_path.rsplit("/", 1)[-1]].append(item)
    return dict(by_hash), dict(by_name)


def audit_reference_template_sources(
    reference_root: Path,
    template_roots: Mapping[str, Path],
) -> dict[str, object]:
    """审计参考包文件是否能在官方模板中找到同一文件或同一角色文件。

    该审计只读取文件元数据和 SHA-256。它不解析 BGL，也不导出导航记录或载荷。
    """

    reference_root = reference_root.expanduser().resolve()
    if not template_roots:
        raise ReferenceTemplateSourceAuditError("至少需要一个官方模板目录")
    normalized_templates = {
        str(name): path.expanduser().resolve()
        for name, path in template_roots.items()
    }
    reference_files = _files(reference_root)
    template_files = {
        name: _files(path)
        for name, path in normalized_templates.items()
    }
    by_hash, by_name = _template_index(normalized_templates)

    rows: list[dict[str, object]] = []
    status_counts: dict[str, int] = defaultdict(int)
    role_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for relative_path, path in reference_files.items():
        reference = _metadata(path, relative_path)
        exact_path_matches = [
            {
                "template": name,
                "path": relative_path,
                "size": template_files[name][relative_path].stat().st_size,
                "sha256": _sha256(template_files[name][relative_path]),
            }
            for name in sorted(template_files)
            if relative_path in template_files[name]
        ]
        hash_matches = [
            {
                "template": item["template"],
                "path": item["path"],
                "role": item["role"],
                "size": item["size"],
            }
            for item in by_hash.get(str(reference["sha256"]), [])
        ]
        basename = relative_path.rsplit("/", 1)[-1]
        basename_matches = [
            {
                "template": item["template"],
                "path": item["path"],
                "role": item["role"],
                "size": item["size"],
                "sha256_equal": item["sha256"] == reference["sha256"],
            }
            for item in by_name.get(basename, [])
        ]
        if hash_matches:
            status = "exact_template_file_match"
        elif exact_path_matches:
            status = "same_relative_path_changed"
        elif basename_matches:
            status = "same_basename_changed"
        else:
            status = "no_template_file_match"
        row = {
            "reference": reference,
            "status": status,
            "exact_relative_path_matches": exact_path_matches,
            "same_hash_template_files": hash_matches,
            "same_basename_template_files": basename_matches,
        }
        rows.append(row)
        status_counts[status] += 1
        role_counts[str(reference["role"])][status] += 1

    return {
        "diagnostic": "reference-template-source-audit-v1",
        "read_only": True,
        "navigation_records_read": False,
        "reference_payload_exported": False,
        "reference_root": str(reference_root),
        "template_roots": {
            name: str(path) for name, path in normalized_templates.items()
        },
        "scope": {
            "reference_files": len(reference_files),
            "template_files": {
                name: len(files) for name, files in template_files.items()
            },
            "excluded_sdk_work_files": True,
        },
        "summary": {
            "reference_files": len(reference_files),
            "status_counts": dict(sorted(status_counts.items())),
            "role_status_counts": {
                role: dict(sorted(counts.items()))
                for role, counts in sorted(role_counts.items())
            },
            "exact_template_file_matches": status_counts[
                "exact_template_file_match"
            ],
            "direct_copy_path_proven": False,
        },
        "decision": {
            "status": "metadata_source_boundary_only",
            "content_projection_authorized": False,
            "reason": (
                "文件元数据匹配只能说明派生文件或包装资源的可能来源，"
                "不能授权复制参考导航 BGL 或任何参考 payload。"
            ),
        },
        "files": rows,
    }


def write_reference_template_source_audit(
    path: Path,
    report: Mapping[str, object],
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
