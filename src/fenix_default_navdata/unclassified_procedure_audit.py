from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .model import NavModel, ProcedureChart, ProcedureSegment, SourceRef


_PROJECTED_KINDS = frozenset({"离场", "进场", "进近过渡", "进近", "复飞"})
_EO_LABEL = re.compile(r"^EO-\d{2}$", re.IGNORECASE)
_CC_LABEL = re.compile(r"^CC\d+-\d{2}$", re.IGNORECASE)
_RNP_LABEL = re.compile(r"^RNP-\d+$", re.IGNORECASE)


def _source_payload(source: SourceRef) -> dict[str, object]:
    return {
        "file": source.file,
        "row": source.row,
        "page": source.page,
        "sha256": source.sha256,
    }


def _label_family(label: str) -> str:
    normalized = (label or "").strip().upper()
    if _EO_LABEL.fullmatch(normalized):
        return "eo_numeric"
    if _CC_LABEL.fullmatch(normalized):
        return "cc_numeric"
    if _RNP_LABEL.fullmatch(normalized):
        return "rnp_numeric"
    return "other"


def _charts_by_source(model: NavModel) -> dict[tuple[str, int | None], list[ProcedureChart]]:
    result: dict[tuple[str, int | None], list[ProcedureChart]] = {}
    for chart in model.procedure_charts:
        key = (chart.source.file, chart.source.page)
        result.setdefault(key, []).append(chart)
    return result


def _matching_charts(
    segment: ProcedureSegment,
    *,
    charts: dict[tuple[str, int | None], list[ProcedureChart]],
) -> list[ProcedureChart]:
    candidates = charts.get((segment.source.file, segment.source.page), [])
    return [
        chart
        for chart in candidates
        if chart.airport.upper() == segment.airport.upper()
        and chart.chart_type == "terminal-database-coding"
    ]


def _chart_payload(chart: ProcedureChart) -> dict[str, object]:
    return {
        "filename": chart.filename,
        "page": chart.page,
        "chart_type": chart.chart_type,
        "chart_name": chart.chart_name,
        "procedure_labels": list(chart.procedure_labels),
        "runways": list(chart.runways),
        "source": _source_payload(chart.source),
    }


def _segment_payload(
    segment: ProcedureSegment,
    *,
    charts: dict[tuple[str, int | None], list[ProcedureChart]],
) -> dict[str, object]:
    matching_charts = _matching_charts(segment, charts=charts)
    label_family = _label_family(segment.label)
    reason = (
        "程序段 kind 为空或不在已验证枚举中；标签形态本身不是目标程序类型证据"
    )
    return {
        "airport": segment.airport,
        "label": segment.label,
        "label_family": label_family,
        "runway": segment.runway,
        "transition": segment.transition,
        "approach_family": segment.approach_family,
        "source": _source_payload(segment.source),
        "source_chart_evidence": [_chart_payload(chart) for chart in matching_charts],
        "source_chart_status": (
            "terminal_database_coding"
            if matching_charts
            else "missing_matching_terminal_database_chart"
        ),
        "legs": [
            {
                "sequence": leg.sequence,
                "leg_type": leg.leg_type,
                "fix_ident": leg.fix_ident,
                "procedure_kind": leg.procedure_kind,
                "transition": leg.transition,
                "approach_family": leg.approach_family,
            }
            for leg in segment.legs
        ],
        "source_proven_kind": None,
        "target_mapping_allowed": False,
        "disposition": "rejected_for_target_mapping",
        "reason": reason,
    }


def audit_unclassified_procedures(model: NavModel) -> dict[str, object]:
    """Audit unprojected procedure segments without inferring target semantics.

    The report is deliberately source-only: it consumes the normalized 424
    model and its direct terminal-database chart evidence, never the reference
    BGL, Fenix data, or target projection.  A label such as ``EO-15`` remains
    unclassified until a later rule has direct, reproducible source evidence.
    """

    records = sorted(
        (
            segment
            for segment in model.procedure_segments
            if segment.kind not in _PROJECTED_KINDS
        ),
        key=lambda segment: (
            segment.airport,
            segment.label,
            segment.runway,
            segment.transition,
            segment.source.file,
            segment.source.page or 0,
        ),
    )
    charts = _charts_by_source(model)
    items = [_segment_payload(segment, charts=charts) for segment in records]
    by_family = Counter(item["label_family"] for item in items)
    source_chart_status = Counter(item["source_chart_status"] for item in items)
    return {
        "diagnostic": "unclassified-procedure-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "source": {
            "model_root": str(model.root),
            "input": "NavModel procedure_segments and procedure_charts",
        },
        "summary": {
            "unclassified_procedure_segment_total": len(items),
            "target_mapping_allowed_total": 0,
            "label_family_counts": dict(sorted(by_family.items())),
            "source_chart_status_counts": dict(sorted(source_chart_status.items())),
        },
        "items": items,
    }


def write_unclassified_procedure_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
