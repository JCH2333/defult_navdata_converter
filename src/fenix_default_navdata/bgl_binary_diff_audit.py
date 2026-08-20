from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .bgl_format import BglFormatError, BglSection, parse_bgl_file


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bgl_files(
    root: Path,
    *,
    package_roots: set[str] | None = None,
) -> tuple[dict[str, Path], dict[str, int]]:
    if not root.is_dir():
        raise FileNotFoundError(f"BGL 包根目录不存在: {root}")
    files: dict[str, Path] = {}
    excluded = {
        "sdk_work_bgl_files": 0,
        "support_package_bgl_files": 0,
    }
    for path in sorted(root.rglob("*.bgl")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        top_level = relative.parts[0].casefold()
        if top_level == "_work":
            excluded["sdk_work_bgl_files"] += 1
            continue
        if package_roots is not None and top_level not in package_roots:
            excluded["support_package_bgl_files"] += 1
            continue
        files[relative.as_posix().lower()] = path
    return files, excluded


def _section_dict(section: BglSection) -> dict[str, int]:
    return {
        "type": section.type,
        "field_a": section.field_a,
        "count": section.count,
        "offset": section.offset,
        "size": section.size,
    }


def _header_dict(path: Path) -> dict[str, object]:
    header = parse_bgl_file(path)
    return {
        "version": header.version,
        "section_count": header.section_count,
        "qmid_tiles": list(header.qmid_tiles),
        "sections": [_section_dict(section) for section in header.sections],
    }


def _first_diff_offset(candidate: bytes, reference: bytes) -> int | None:
    common_length = min(len(candidate), len(reference))
    for offset in range(common_length):
        if candidate[offset] != reference[offset]:
            return offset
    if len(candidate) != len(reference):
        return common_length
    return None


def _different_byte_count(candidate: bytes, reference: bytes) -> int:
    common_length = min(len(candidate), len(reference))
    return sum(
        left != right
        for left, right in zip(candidate[:common_length], reference[:common_length])
    ) + abs(len(candidate) - len(reference))


def _section_groups(sections: Iterable[BglSection]) -> dict[tuple[int, int], BglSection]:
    occurrences: dict[int, int] = {}
    result: dict[tuple[int, int], BglSection] = {}
    for section in sections:
        occurrence = occurrences.get(section.type, 0)
        occurrences[section.type] = occurrence + 1
        result[(section.type, occurrence)] = section
    return result


def _section_diff(
    candidate_data: bytes,
    reference_data: bytes,
    candidate_sections: tuple[BglSection, ...],
    reference_sections: tuple[BglSection, ...],
) -> list[dict[str, object]]:
    candidate_groups = _section_groups(candidate_sections)
    reference_groups = _section_groups(reference_sections)
    rows: list[dict[str, object]] = []
    for match_key in sorted(set(candidate_groups) | set(reference_groups)):
        candidate = candidate_groups.get(match_key)
        reference = reference_groups.get(match_key)
        row: dict[str, object] = {
            "section_type": match_key[0],
            "occurrence": match_key[1],
        }
        if candidate is None:
            row.update({
                "status": "missing_candidate",
                "reference": _section_dict(reference),
            })
            rows.append(row)
            continue
        if reference is None:
            row.update({
                "status": "missing_reference",
                "candidate": _section_dict(candidate),
            })
            rows.append(row)
            continue

        candidate_payload = candidate_data[
            candidate.offset : candidate.offset + candidate.size
        ]
        reference_payload = reference_data[
            reference.offset : reference.offset + reference.size
        ]
        candidate_meta = _section_dict(candidate)
        reference_meta = _section_dict(reference)
        row.update({
            "status": "equal"
            if candidate_payload == reference_payload
            and candidate_meta == reference_meta
            else "changed",
            "candidate": candidate_meta,
            "reference": reference_meta,
            "header_equal": candidate_meta == reference_meta,
            "payload_size_delta": len(candidate_payload) - len(reference_payload),
            "payload_first_diff": _first_diff_offset(
                candidate_payload,
                reference_payload,
            ),
            "payload_different_byte_count": _different_byte_count(
                candidate_payload,
                reference_payload,
            ),
        })
        rows.append(row)
    return rows


def _diff_file(candidate: Path, reference: Path, relative_path: str) -> dict[str, object]:
    candidate_data = candidate.read_bytes()
    reference_data = reference.read_bytes()
    row: dict[str, object] = {
        "path": relative_path,
        "candidate_size": len(candidate_data),
        "reference_size": len(reference_data),
        "size_delta": len(candidate_data) - len(reference_data),
        "candidate_sha256": _sha256(candidate),
        "reference_sha256": _sha256(reference),
        "sha256_equal": candidate_data == reference_data,
        "first_diff_offset": _first_diff_offset(candidate_data, reference_data),
        "different_byte_count": _different_byte_count(
            candidate_data,
            reference_data,
        ),
    }
    try:
        candidate_header = parse_bgl_file(candidate)
        row["candidate_header"] = _header_dict(candidate)
    except BglFormatError as error:
        row["candidate_header_error"] = str(error)
        candidate_header = None
    try:
        reference_header = parse_bgl_file(reference)
        row["reference_header"] = _header_dict(reference)
    except BglFormatError as error:
        row["reference_header_error"] = str(error)
        reference_header = None

    if candidate_header is not None and reference_header is not None:
        candidate_header_dict = _header_dict(candidate)
        reference_header_dict = _header_dict(reference)
        row["header_metadata_equal"] = candidate_header_dict == reference_header_dict
        row["section_diffs"] = _section_diff(
            candidate_data,
            reference_data,
            candidate_header.sections,
            reference_header.sections,
        )
    return row


def audit_bgl_binary_differences(
    candidate_root: Path,
    reference_root: Path,
    *,
    relative_paths: Iterable[str] | None = None,
) -> dict[str, object]:
    """Compare BGL bytes and section metadata without exporting navigation records."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    reference_files, reference_excluded = _bgl_files(reference_root)
    reference_package_roots = {
        relative_path.split("/", 1)[0]
        for relative_path in reference_files
    }
    candidate_files, candidate_excluded = _bgl_files(
        candidate_root,
        package_roots=reference_package_roots or None,
    )
    selected = (
        sorted(
            {
                str(relative_path).replace("\\", "/").lower()
                for relative_path in relative_paths
            }
        )
        if relative_paths is not None
        else sorted(set(candidate_files) | set(reference_files))
    )

    rows: list[dict[str, object]] = []
    equal_files = 0
    equal_headers = 0
    for relative_path in selected:
        candidate = candidate_files.get(relative_path)
        reference = reference_files.get(relative_path)
        if candidate is None:
            rows.append({
                "path": relative_path,
                "status": "missing_candidate",
                "reference_size": reference.stat().st_size if reference else None,
            })
            continue
        if reference is None:
            rows.append({
                "path": relative_path,
                "status": "missing_reference",
                "candidate_size": candidate.stat().st_size,
            })
            continue
        row = _diff_file(candidate, reference, relative_path)
        row["status"] = "equal" if row["sha256_equal"] else "changed"
        equal_files += row["status"] == "equal"
        equal_headers += row.get("header_metadata_equal") is True
        rows.append(row)

    return {
        "diagnostic": "bgl-binary-diff-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "reference_payload_exported": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "scope": {
            "reference_package_roots": sorted(reference_package_roots),
            "candidate_excluded_sdk_work_bgl_files": candidate_excluded[
                "sdk_work_bgl_files"
            ],
            "candidate_excluded_support_package_bgl_files": candidate_excluded[
                "support_package_bgl_files"
            ],
            "reference_excluded_sdk_work_bgl_files": reference_excluded[
                "sdk_work_bgl_files"
            ],
        },
        "summary": {
            "candidate_bgl_files": len(candidate_files),
            "reference_bgl_files": len(reference_files),
            "selected_files": len(selected),
            "equal_files": equal_files,
            "equal_header_metadata": equal_headers,
            "changed_or_missing": len(rows) - equal_files,
        },
        "files": rows,
    }


def write_bgl_binary_diff_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
