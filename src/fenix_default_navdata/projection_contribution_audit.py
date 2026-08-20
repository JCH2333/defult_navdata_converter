from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .bgl import write_bglcomp_xml
from .bgl_format import BglFormatError, parse_bgl_file
from .model import NavModel
from .model_io import model_counts
from .profile import DEFAULT_CYCLE

_REGIONS = ("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY")


class ProjectionContributionAuditError(RuntimeError):
    """Raised when the source-to-projection contribution matrix cannot close."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _xml_tag_counts(path: Path) -> dict[str, int]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ProjectionContributionAuditError(
            f"generated projection XML is malformed: {path}"
        ) from error
    counts = Counter(_tag(element) for element in root.iter())
    return dict(sorted(counts.items()))


def _source_refs(values: object) -> dict[str, object]:
    rows: set[tuple[str, int | None, int | None]] = set()
    files: Counter[str] = Counter()
    for value in values:
        source = getattr(value, "source", None)
        if source is None:
            continue
        rows.add((source.file, source.row, source.page))
        files[source.file] += 1
    return {
        "referenced_source_record_count": len(rows),
        "model_entities_by_source_file": dict(sorted(files.items())),
    }


def _model_values(values: object) -> object:
    return values.values() if isinstance(values, dict) else values


def _model_entity_counts(model: NavModel) -> dict[str, dict[str, object]]:
    return {
        "airports": _source_refs(model.airports.values()),
        "runway_directions": _source_refs(_model_values(model.runways)),
        "navaids": _source_refs(model.navaids),
        "ilses": _source_refs(model.ilses),
        "terminal_waypoints": _source_refs(model.terminal_waypoints),
        "global_waypoints": _source_refs(model.waypoints),
        "airway_legs": _source_refs(model.airway_legs),
        "procedure_segments": _source_refs(model.procedure_segments),
        "holdings": _source_refs(model.holdings),
        "rejected_records": _source_refs(model.rejected_records),
        "rejected_procedures": _source_refs(model.rejected_procedures),
    }


def _candidate_bgl_headers(candidate_root: Path) -> list[dict[str, object]]:
    root = candidate_root.expanduser().resolve()
    if not root.is_dir():
        raise ProjectionContributionAuditError(
            f"candidate package root does not exist: {root}"
        )
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*.bgl")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0].casefold() == "_work":
            continue
        lowered_name = path.name.casefold()
        if lowered_name != "00_enroute.bgl" and not (
            lowered_name.endswith("_airports.bgl")
            and path.name[:2].upper() in _REGIONS
        ):
            continue
        try:
            header = parse_bgl_file(path)
        except BglFormatError as error:
            rows.append({
                "path": relative.as_posix().lower(),
                "header_error": str(error),
            })
            continue
        rows.append({
            "path": relative.as_posix().lower(),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
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
        })
    return rows


def _write_projection_xmls(model: NavModel, root: Path) -> list[dict[str, object]]:
    output_root = root.expanduser().resolve()
    if output_root.exists():
        raise ProjectionContributionAuditError(
            f"projection XML output already exists: {output_root}"
        )
    output_root.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for name, scope, region in (
        ("00_enroute.xml", "enroute", None),
        *((f"{region}_airports.xml", "airports", region) for region in _REGIONS),
    ):
        path = output_root / name
        projection = write_bglcomp_xml(
            model,
            DEFAULT_CYCLE,
            path,
            scope=scope,
            airport_prefix=region,
        )
        projection_summary = asdict(projection)
        projection_summary["path"] = str(projection.path)
        rows.append({
            "path": path.relative_to(output_root).as_posix(),
            "scope": scope,
            "region": region,
            "sha256": _sha256(path),
            "projection": projection_summary,
            "xml_tag_counts": _xml_tag_counts(path),
        })
    return rows


def audit_projection_contributions(
    model: NavModel,
    candidate_root: Path,
    projection_xml_root: Path,
    *,
    model_path: Path | None = None,
) -> dict[str, object]:
    """Quantify source model, generated XML, and candidate BGL header scale."""

    projection_rows = _write_projection_xmls(model, projection_xml_root)
    candidate_headers = _candidate_bgl_headers(candidate_root)
    return {
        "diagnostic": "projection-contribution-audit-v1",
        "read_only_source_model": True,
        "candidate_modified": False,
        "reference_payload_read": False,
        "section_type_semantics_inferred": False,
        "model_path": str(model_path.expanduser().resolve()) if model_path else None,
        "model_sha256": _sha256(model_path) if model_path else None,
        "candidate_root": str(candidate_root.expanduser().resolve()),
        "projection_xml_root": str(projection_xml_root.expanduser().resolve()),
        "source_model": {
            "entity_counts": model_counts(model),
            "source_references": _model_entity_counts(model),
        },
        "generated_projection_xml": projection_rows,
        "candidate_bgl_headers": candidate_headers,
        "conclusion": (
            "本报告只量化 424 来源模型、诊断投影 XML 与候选 BGL 节表的规模。"
            "Section 类型和计数不表示实体语义或一一映射，禁止据此读取参考记录、"
            "伪造对象或修改正式适配器。"
        ),
    }


def write_projection_contribution_audit(
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
