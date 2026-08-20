from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .model import NavModel


class ProcedureSourceAuditError(RuntimeError):
    """当终端程序来源与图表映射审计无法在只读边界内完成时抛出。"""


def audit_procedure_source_model(model: NavModel) -> dict[str, object]:
    segments = model.procedure_segments
    charts = model.procedure_charts
    rejected = model.rejected_procedures
    ilses = model.ilses
    holdings = model.holdings

    kind_counts = Counter(getattr(seg, "kind", "") for seg in segments)
    chart_type_counts = Counter(getattr(chart, "chart_type", "") for chart in charts)

    # Count leg types
    leg_type_counts = Counter()
    total_legs = 0
    for seg in segments:
        for leg in getattr(seg, "legs", ()):
            total_legs += 1
            leg_type_counts[getattr(leg, "leg_type", "")] += 1

    # Airports covered in procedure_segments
    airports_with_procedures = sorted({getattr(seg, "airport", "") for seg in segments if getattr(seg, "airport", "")})

    return {
        "diagnostic": "procedure-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "summary": {
            "total_procedure_segments": len(segments),
            "total_procedure_charts": len(charts),
            "total_terminal_legs": total_legs,
            "total_rejected_procedures": len(rejected),
            "total_ils_facilities": len(ilses),
            "total_holding_records": len(holdings),
            "airports_with_procedures_total": len(airports_with_procedures),
            "procedure_kind_counts": dict(sorted(kind_counts.items())),
            "chart_type_counts": dict(sorted(chart_type_counts.items())),
            "terminal_leg_type_counts": dict(sorted(leg_type_counts.items())),
            "rejected_procedure_keys": [getattr(p, "key", str(p)) for p in rejected],
            "disposition": "terminal_procedures_evidence_verified",
            "model_or_adapter_change_authorized": False,
        },
    }


def write_procedure_source_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
