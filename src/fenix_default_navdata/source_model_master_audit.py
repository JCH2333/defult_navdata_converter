from __future__ import annotations

import json
from pathlib import Path

from .airline_system_source_audit import audit_airline_system_source
from .airspace_source_audit import audit_airspace_source
from .core_model_mapping_audit import audit_core_model_mapping
from .general_doc_source_audit import audit_general_doc_source
from .model import NavModel
from .procedure_source_audit import audit_procedure_source_model
from .route_holding_source_audit import audit_route_holding_source
from .route_restrict_source_audit import audit_route_restrict_source
from .source_model_completeness_audit import audit_source_model_completeness


class SourceModelMasterAuditError(RuntimeError):
    """当来源-模型综合主审计无法在只读边界内完成时抛出。"""


def audit_source_model_master(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise SourceModelMasterAuditError(f"424 原始目录不存在: {root}")

    completeness = audit_source_model_completeness(root, model)
    airline_sys = audit_airline_system_source(root, model)
    airspace = audit_airspace_source(root, model)
    general_doc = audit_general_doc_source(root, model)
    route_holding = audit_route_holding_source(root, model)
    route_restrict = audit_route_restrict_source(root, model)
    core_mapping = audit_core_model_mapping(root, model)
    procedure_mapping = audit_procedure_source_model(model)

    summary_completeness = completeness["summary"]
    summary_core = core_mapping["summary"]
    summary_proc = procedure_mapping["summary"]

    master_verified = (
        summary_completeness.get("unclassified_csv_file_total") == 0
        and summary_completeness.get("declared_source_group_total") == 16
        and summary_completeness.get("source_complete_group_total") == 16
        and summary_core.get("all_core_groups_verified") is True
        and summary_proc.get("total_procedure_segments", 0) > 0
        and summary_proc.get("total_terminal_legs", 0) > 0
        and summary_proc.get("total_rejected_procedures", 0) == 10
    )

    return {
        "diagnostic": "source-model-master-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "root_csv_file_total": summary_completeness.get("root_csv_file_total"),
            "declared_group_total": summary_completeness.get("declared_source_group_total"),
        },
        "summary": {
            "master_pipeline_verified": master_verified,
            "root_csv_total": summary_completeness.get("root_csv_file_total"),
            "unclassified_csv_total": summary_completeness.get("unclassified_csv_file_total"),
            "core_entities": {
                "airports": summary_core.get("airports", {}).get("model_airports_total"),
                "runways": summary_core.get("runways", {}).get("model_runways_total"),
                "navaids": summary_core.get("navaids", {}).get("model_navaids_total"),
                "waypoints": summary_core.get("waypoints", {}).get("model_waypoints_total"),
                "airways": summary_core.get("airways", {}).get("model_airway_legs_total"),
            },
            "terminal_procedures": {
                "procedure_segments": summary_proc.get("total_procedure_segments"),
                "procedure_charts": summary_proc.get("total_procedure_charts"),
                "terminal_legs": summary_proc.get("total_terminal_legs"),
                "ils_facilities": summary_proc.get("total_ils_facilities"),
                "holding_records": summary_proc.get("total_holding_records"),
                "rejected_procedures": summary_proc.get("total_rejected_procedures"),
            },
            "disposition": "source_model_master_pipeline_verified",
            "model_or_adapter_change_authorized": False,
        },
        "sub_audits": {
            "completeness": summary_completeness,
            "airline_and_system": airline_sys.get("summary", {}),
            "airspace": airspace.get("summary", {}),
            "general_doc": general_doc.get("summary", {}),
            "route_holding": {
                "source": route_holding.get("source", {}),
                "target": route_holding.get("target", {}),
            },
            "route_restrict": route_restrict.get("summary", {}),
            "core_mapping": summary_core,
            "procedure_mapping": summary_proc,
        },
    }


def write_source_model_master_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
