from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from .bgl_format import BglFormatError, parse_bgl_file
from .model import NavModel

_ENROUTE_FILENAME = "00_enroute.bgl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _enroute_files(root: Path) -> tuple[dict[str, Path], dict[str, int]]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"BGL 包根目录不存在: {root}")
    files: dict[str, Path] = {}
    excluded = {"sdk_work_bgl_files": 0}
    for path in sorted(root.rglob(_ENROUTE_FILENAME)):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts[0].casefold() == "_work":
            excluded["sdk_work_bgl_files"] += 1
            continue
        files[relative.as_posix().lower()] = path
    return files, excluded


def _header_summary(path: Path) -> dict[str, object]:
    header = parse_bgl_file(path)
    return {
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "version": f"{header.version:#x}",
        "qmid_tiles": [f"{tile:#x}" for tile in header.qmid_tiles],
        "sections": [
            {
                "type": f"{section.type:#x}",
                "count": section.count,
                "size": section.size,
            }
            for section in header.sections
        ],
    }


def source_counts(model: NavModel) -> dict[str, object]:
    navaids = Counter((navaid.kind or "unknown").upper() for navaid in model.navaids)
    return {
        "navaids_by_kind": dict(sorted(navaids.items())),
        "global_waypoints": len(model.waypoints),
        "airway_legs": len(model.airway_legs),
        "airway_legs_with_resolved_regions": sum(
            bool(leg.start_country and leg.end_country) for leg in model.airway_legs
        ),
        "airway_legs_with_missing_region": sum(
            not (leg.start_country and leg.end_country) for leg in model.airway_legs
        ),
        "enroute_navaid_evidence": len(model.enroute_navaid_evidence),
        "enroute_airway_minimum_altitude_evidence": len(
            model.enroute_airway_minimum_altitude_evidence
        ),
        "rejected_records_by_kind": dict(sorted(
            Counter(record.kind for record in model.rejected_records).items()
        )),
    }


def _section_deltas(
    candidate: dict[str, object] | None,
    reference: dict[str, object] | None,
) -> list[dict[str, object]]:
    candidate_sections = {
        section["type"]: section for section in candidate.get("sections", [])
    } if candidate else {}
    reference_sections = {
        section["type"]: section for section in reference.get("sections", [])
    } if reference else {}
    type_ids = sorted(
        set(candidate_sections) | set(reference_sections),
        key=lambda value: int(value, 16),
    )
    rows = []
    for type_id in type_ids:
        left = candidate_sections.get(type_id)
        right = reference_sections.get(type_id)
        rows.append({
            "type": type_id,
            "candidate_count": left["count"] if left else None,
            "reference_count": right["count"] if right else None,
            "count_delta": (left["count"] - right["count"]) if left and right else None,
            "candidate_size": left["size"] if left else None,
            "reference_size": right["size"] if right else None,
            "size_delta": (left["size"] - right["size"]) if left and right else None,
        })
    return rows


def audit_enroute_bgl_cardinality(
    model: NavModel,
    candidate_root: Path,
    reference_root: Path,
    *,
    model_path: Path | None = None,
) -> dict[str, object]:
    """Compare final enroute BGL headers with source model cardinality only."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    candidate_files, candidate_excluded = _enroute_files(candidate_root)
    reference_files, reference_excluded = _enroute_files(reference_root)
    rows: list[dict[str, object]] = []
    for relative_path in sorted(set(candidate_files) | set(reference_files)):
        row: dict[str, object] = {"path": relative_path}
        candidate = candidate_files.get(relative_path)
        reference = reference_files.get(relative_path)
        if candidate:
            try:
                row["candidate"] = _header_summary(candidate)
            except BglFormatError as error:
                row["candidate_header_error"] = str(error)
        if reference:
            try:
                row["reference"] = _header_summary(reference)
            except BglFormatError as error:
                row["reference_header_error"] = str(error)
        row["section_deltas"] = _section_deltas(
            row.get("candidate") if isinstance(row.get("candidate"), dict) else None,
            row.get("reference") if isinstance(row.get("reference"), dict) else None,
        )
        rows.append(row)

    return {
        "diagnostic": "enroute-bgl-cardinality-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "reference_payload_read": False,
        "section_type_semantics_inferred": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "model_path": str(model_path.expanduser().resolve()) if model_path else None,
        "model_sha256": _sha256(model_path) if model_path else None,
        "scope": {
            "candidate_excluded_sdk_work_bgl_files": candidate_excluded["sdk_work_bgl_files"],
            "reference_excluded_sdk_work_bgl_files": reference_excluded["sdk_work_bgl_files"],
        },
        "source_counts": source_counts(model),
        "summary": {
            "candidate_enroute_bgl_files": len(candidate_files),
            "reference_enroute_bgl_files": len(reference_files),
            "common_enroute_bgl_files": len(set(candidate_files) & set(reference_files)),
        },
        "files": rows,
        "conclusion": (
            "本报告仅并列来源对象规模与 BGL 节表基数差异；在取得独立 424 来源和 "
            "单变量 SDK 证据前，禁止把任何节类型映射为对象或修改正式投影。"
        ),
    }


def write_enroute_bgl_cardinality_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
