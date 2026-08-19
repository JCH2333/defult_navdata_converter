from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .bgl_format import BglFormatError, BglHeader, parse_bgl_file
from .model import NavModel, is_china_icao

_REGIONAL_AIRPORT_BGL = re.compile(r"^(?P<region>Z[A-Z])_airports\.bgl$", re.IGNORECASE)
_TERMINAL_SOURCE_AIRPORT = re.compile(r"(?:^|[\\/])Terminal[\\/](Z[A-Z]{3})(?:[\\/]|$)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _section_rows(header: BglHeader) -> list[dict[str, int | str]]:
    return [
        {
            "type": f"{section.type:#x}",
            "count": section.count,
            "size": section.size,
        }
        for section in header.sections
    ]


def _section_types(header: BglHeader) -> set[int]:
    return {section.type for section in header.sections}


def _airport_bgl_files(
    root: Path,
    *,
    package_roots: set[str] | None = None,
) -> tuple[dict[str, Path], dict[str, int]]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"BGL 包根目录不存在: {root}")
    files: dict[str, Path] = {}
    excluded = {"sdk_work_bgl_files": 0, "support_package_bgl_files": 0}
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
        if _REGIONAL_AIRPORT_BGL.match(path.name) is None:
            continue
        files[relative.as_posix().lower()] = path
    return files, excluded


def _region_from_bgl_path(relative_path: str) -> str:
    match = _REGIONAL_AIRPORT_BGL.match(Path(relative_path).name)
    if match is None:
        raise ValueError(f"不是区域机场 BGL: {relative_path}")
    return match.group("region").upper()


def _terminal_source_region(source_file: str) -> str:
    match = _TERMINAL_SOURCE_AIRPORT.search(source_file or "")
    return match.group(1)[:2] if match else ""


def source_counts_by_region(model: NavModel) -> dict[str, dict[str, int]]:
    """Count source-backed model objects by MSFS airport BGL region key."""

    airport_regions = {
        airport.icao: airport.icao[:2]
        for airport in model.airports.values()
        if is_china_icao(airport.icao)
    }
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for airport in model.airports.values():
        if is_china_icao(airport.icao):
            counts[airport.icao[:2]]["airports"] += 1
    for runway in model.runways:
        airport = model.airports.get(runway.airport_key)
        if airport is not None and is_china_icao(airport.icao):
            counts[airport.icao[:2]]["runway_directions"] += 1
    for waypoint in model.terminal_waypoints:
        region = airport_regions.get(waypoint.airport, waypoint.airport[:2])
        if region in {"ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"}:
            counts[region]["terminal_waypoints"] += 1
    for ils in model.ilses:
        region = airport_regions.get(ils.airport, ils.airport[:2])
        if not region:
            region = _terminal_source_region(ils.source.file)
        if region:
            counts[region]["ilses"] += 1
    for segment in model.procedure_segments:
        region = airport_regions.get(segment.airport, segment.airport[:2])
        if region in {"ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"}:
            counts[region]["procedure_segments"] += 1
            kind = (segment.kind or "").strip() or "unclassified"
            counts[region][f"procedure_segments_{kind}"] += 1
    for holding in model.holdings:
        region = (holding.fix_region or "")[:2]
        if region in {"ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"}:
            counts[region]["holdings"] += 1

    fields = (
        "airports",
        "runway_directions",
        "terminal_waypoints",
        "ilses",
        "procedure_segments",
        "holdings",
    )
    result: dict[str, dict[str, int]] = {}
    for region in sorted(counts):
        row = {field: counts[region][field] for field in fields}
        row.update({
            key: value
            for key, value in sorted(counts[region].items())
            if key.startswith("procedure_segments_")
        })
        result[region] = row
    return result


def _header_row(path: Path) -> dict[str, object]:
    header = parse_bgl_file(path)
    return {
        "size": path.stat().st_size,
        "version": f"{header.version:#x}",
        "section_count": header.section_count,
        "sections": _section_rows(header),
    }


def _section_presence(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    candidate_total: Counter[str] = Counter()
    reference_total: Counter[str] = Counter()
    candidate_only: Counter[str] = Counter()
    reference_only: Counter[str] = Counter()
    for row in rows:
        candidate = row.get("candidate")
        reference = row.get("reference")
        candidate_types = {
            section["type"] for section in candidate.get("sections", [])
        } if isinstance(candidate, dict) else set()
        reference_types = {
            section["type"] for section in reference.get("sections", [])
        } if isinstance(reference, dict) else set()
        candidate_total.update(candidate_types)
        reference_total.update(reference_types)
        candidate_only.update(candidate_types - reference_types)
        reference_only.update(reference_types - candidate_types)
    all_types = sorted(
        set(candidate_total) | set(reference_total),
        key=lambda value: int(value, 16),
    )
    return [
        {
            "type": type_id,
            "candidate_file_total": candidate_total[type_id],
            "reference_file_total": reference_total[type_id],
            "candidate_only_file_total": candidate_only[type_id],
            "reference_only_file_total": reference_only[type_id],
        }
        for type_id in all_types
    ]


def audit_airport_bgl_cardinality(
    model: NavModel,
    candidate_root: Path,
    reference_root: Path,
    *,
    model_path: Path | None = None,
) -> dict[str, object]:
    """Compare airport BGL header cardinality without reading BGL payloads."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    reference_files, reference_excluded = _airport_bgl_files(reference_root)
    package_roots = {path.split("/", 1)[0] for path in reference_files}
    candidate_files, candidate_excluded = _airport_bgl_files(
        candidate_root,
        package_roots=package_roots or None,
    )
    source_counts = source_counts_by_region(model)
    rows: list[dict[str, object]] = []

    for relative_path in sorted(set(candidate_files) | set(reference_files)):
        region = _region_from_bgl_path(relative_path)
        row: dict[str, object] = {
            "path": relative_path,
            "region": region,
            "source_counts": source_counts.get(region, {
                "airports": 0,
                "runway_directions": 0,
                "terminal_waypoints": 0,
                "ilses": 0,
                "procedure_segments": 0,
                "holdings": 0,
            }),
        }
        candidate = candidate_files.get(relative_path)
        reference = reference_files.get(relative_path)
        if candidate is not None:
            try:
                row["candidate"] = _header_row(candidate)
            except BglFormatError as error:
                row["candidate_header_error"] = str(error)
        if reference is not None:
            try:
                row["reference"] = _header_row(reference)
            except BglFormatError as error:
                row["reference_header_error"] = str(error)
        candidate_header = row.get("candidate")
        reference_header = row.get("reference")
        if isinstance(candidate_header, dict) and isinstance(reference_header, dict):
            candidate_types = {
                int(section["type"], 16) for section in candidate_header["sections"]
            }
            reference_types = {
                int(section["type"], 16) for section in reference_header["sections"]
            }
            row["candidate_only_section_types"] = [
                f"{value:#x}" for value in sorted(candidate_types - reference_types)
            ]
            row["reference_only_section_types"] = [
                f"{value:#x}" for value in sorted(reference_types - candidate_types)
            ]
        rows.append(row)

    presence = _section_presence(rows)
    common_rows = [
        row for row in rows if isinstance(row.get("candidate"), dict) and isinstance(row.get("reference"), dict)
    ]
    return {
        "diagnostic": "airport-bgl-cardinality-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "reference_payload_read": False,
        "section_type_semantics_inferred": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "model_path": str(model_path.expanduser().resolve()) if model_path else None,
        "model_sha256": _sha256(model_path) if model_path else None,
        "scope": {
            "reference_package_roots": sorted(package_roots),
            "candidate_excluded_sdk_work_bgl_files": candidate_excluded["sdk_work_bgl_files"],
            "candidate_excluded_support_package_bgl_files": candidate_excluded["support_package_bgl_files"],
            "reference_excluded_sdk_work_bgl_files": reference_excluded["sdk_work_bgl_files"],
        },
        "summary": {
            "candidate_airport_bgl_files": len(candidate_files),
            "reference_airport_bgl_files": len(reference_files),
            "common_airport_bgl_files": len(common_rows),
            "all_reference_has_0x17": bool(common_rows) and all(
                "0x17" in {section["type"] for section in row["reference"]["sections"]}
                for row in common_rows
            ),
            "all_candidate_lacks_0x17": bool(common_rows) and all(
                "0x17" not in {section["type"] for section in row["candidate"]["sections"]}
                for row in common_rows
            ),
            "all_reference_has_0x33": bool(common_rows) and all(
                "0x33" in {section["type"] for section in row["reference"]["sections"]}
                for row in common_rows
            ),
            "all_candidate_lacks_0x33": bool(common_rows) and all(
                "0x33" not in {section["type"] for section in row["candidate"]["sections"]}
                for row in common_rows
            ),
        },
        "section_presence": presence,
        "files": rows,
        "conclusion": (
            "本报告只定位 BGL 节表基数差异；在取得独立的 424 来源对象到单变量 SDK "
            "探针证据前，禁止根据参考节表推断对象类型或修改正式投影。"
        ),
    }


def write_airport_bgl_cardinality_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
