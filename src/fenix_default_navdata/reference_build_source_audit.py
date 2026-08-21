from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


class ReferenceBuildSourceAuditError(RuntimeError):
    """参考包生成来源审计失败。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(
    root: Path,
    *,
    suffixes: set[str] | None = None,
    exclude_work: bool = True,
) -> list[Path]:
    if not root.is_dir():
        raise ReferenceBuildSourceAuditError(f"目录不存在: {root}")
    normalized = {suffix.casefold() for suffix in suffixes} if suffixes else None
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and (
            not exclude_work
            or "_work" not in {
                part.casefold() for part in path.relative_to(root).parts
            }
        )
        and (normalized is None or path.suffix.casefold() in normalized)
    ]


def _artifact(path: Path, root: Path, *, role: str) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "role": role,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _manifest_metadata(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in _files(root, suffixes={".json"}):
        if path.name.casefold() != "manifest.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "creator": payload.get("creator"),
            "package_name": payload.get("package_name"),
            "content_type": payload.get("content_type"),
            "minimum_game_version": payload.get("minimum_game_version"),
            "package_version": payload.get("package_version"),
        })
    return rows


def _sdk_artifacts(root: Path) -> list[dict[str, object]]:
    bin_root = root / "Tools" / "bin"
    if not bin_root.is_dir():
        return []
    names = {
        "fspackagetool.exe": "sdk_package_tool",
        "bglcomp.exe": "bgl_generator",
        "bglcomp.xsd": "bgl_schema",
    }
    return [
        _artifact(path, root, role=role)
        for name, role in sorted(names.items())
        for path in [bin_root / name]
        if path.is_file()
    ]


def audit_reference_build_sources(
    reference_root: Path,
    *,
    candidate_root: Path | None = None,
    sdk_roots: Iterable[Path] = (),
) -> dict[str, object]:
    sdk_roots = tuple(sdk_roots)
    reference = reference_root.expanduser().resolve()
    if not reference.is_dir():
        raise ReferenceBuildSourceAuditError(f"参考包目录不存在: {reference}")

    candidate = candidate_root.expanduser().resolve() if candidate_root else None
    if candidate is not None and not candidate.is_dir():
        raise ReferenceBuildSourceAuditError(f"候选目录不存在: {candidate}")

    reference_xml = [
        _artifact(path, reference, role="reference_source_xml")
        for path in _files(reference, suffixes={".xml"})
    ]
    reference_executable = [
        _artifact(path, reference, role="reference_generator")
        for path in _files(reference, suffixes={".exe", ".dll", ".pye"})
    ]
    candidate_xml = (
        [
            _artifact(path, candidate, role="candidate_source_xml")
            for path in _files(
                candidate,
                suffixes={".xml"},
                exclude_work=False,
            )
        ]
        if candidate is not None
        else []
    )
    sdk_artifacts = [
        {
            "sdk_root": str(root.expanduser().resolve()),
            "artifacts": _sdk_artifacts(root.expanduser().resolve()),
        }
        for root in sdk_roots
    ]
    sdk_roles = Counter(
        str(item["role"])
        for group in sdk_artifacts
        for item in group["artifacts"]
    )
    reference_files = _files(reference)
    navigation_files = [
        path for path in reference_files if path.suffix.casefold() == ".bgl"
    ]
    generator_found = bool(reference_executable) or bool(sdk_roles["bgl_generator"])
    source_inputs_found = bool(reference_xml) or bool(candidate_xml)

    if reference_xml or reference_executable:
        status = "reference_source_artifacts_present"
    elif not generator_found and not source_inputs_found:
        status = "no_reference_generator_or_source_input"
    else:
        status = "source_boundary_only"

    return {
        "diagnostic": "reference-build-source-audit-v1",
        "read_only": True,
        "reference_payload_read": False,
        "reference_navigation_payload_read": False,
        "reference_root": str(reference),
        "candidate_root": str(candidate) if candidate else None,
        "sdk_roots": [
            str(root.expanduser().resolve()) for root in sdk_roots
        ],
        "reference_manifests": _manifest_metadata(reference),
        "reference_artifacts": {
            "navigation_bgl_files": len(navigation_files),
            "source_xml_files": reference_xml,
            "generator_binaries": reference_executable,
        },
        "candidate_artifacts": {
            "source_xml_files": candidate_xml,
        },
        "sdk_artifacts": sdk_artifacts,
        "summary": {
            "reference_file_total": len(reference_files),
            "reference_source_xml_total": len(reference_xml),
            "reference_generator_total": len(reference_executable),
            "candidate_source_xml_total": len(candidate_xml),
            "sdk_package_tool_total": sdk_roles["sdk_package_tool"],
            "sdk_bgl_generator_total": sdk_roles["bgl_generator"],
            "sdk_bgl_schema_total": sdk_roles["bgl_schema"],
        },
        "decision": {
            "status": status,
            "adapter_change_authorized": False,
            "reason": (
                "仅记录生成输入和工具边界；没有参考 payload、导航记录或 BGL 语义被读取，"
                "因此不能授权复制参考内容或修改 NavModel/adapter。"
            ),
        },
    }


def write_reference_build_source_audit(
    path: Path,
    report: dict[str, object],
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
