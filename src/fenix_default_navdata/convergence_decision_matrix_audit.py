from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .bgl_format import audit_file_convergence


class ConvergenceDecisionMatrixError(RuntimeError):
    """Raised when convergence decision matrix audit cannot be built."""


def _categorize_file_decision(
    path: str,
    role: str,
    cand_summary: Mapping[str, object],
    ref_summary: Mapping[str, object],
) -> dict[str, object]:
    """Derive deterministic decision item for each of the 29 reference package files."""
    cand_size = cand_summary.get("size", 0)
    ref_size = ref_summary.get("size", 0)
    
    if role in ("package_manifest", "content_history", "package_layout", "package_index"):
        target_layer = "package_metadata_and_index"
        disposition = "controlled_by_content_and_project_definition"
        source_evidence = "package_tool_layout_filetimes_and_manifest_definitions"
        next_action = "derive_from_compiled_payload_without_direct_reference_copy"
    elif role == "enroute_bgl":
        target_layer = "enroute_navigation_data"
        disposition = "semantic_diff_and_endpoint_boundary_blocked"
        source_evidence = "424_RTE_SEG_DESIGNATED_POINT_and_general_doc_keypoints"
        next_action = "resolve_airway_geometry_and_non_designated_boundaries"
    elif role in ("regional_airport_bgl", "airport_patch_bgl"):
        target_layer = "airport_terminal_procedures_and_navaids"
        disposition = "section_cardinality_and_iap_primary_source_blocked"
        source_evidence = "424_AD_HP_runways_ils_procedures_and_terminal_database_charts"
        next_action = "audit_airport_scope_and_contract_proven_sdk_structures"
    else:
        target_layer = "unknown"
        disposition = "unclassified"
        source_evidence = "none"
        next_action = "inspect_file_role"

    return {
        "path": path,
        "role": role,
        "target_layer": target_layer,
        "candidate_size": cand_size,
        "reference_size": ref_size,
        "size_delta": cand_size - ref_size,
        "disposition": disposition,
        "source_evidence_boundary": source_evidence,
        "next_action": next_action,
        "authorized_for_adapter_change": False,
    }


def audit_convergence_decision_matrix(
    candidate_root: Path,
    reference_root: Path,
    *,
    repeat_candidate_root: Path | None = None,
) -> dict[str, object]:
    """Audit the full 29-file convergence decision matrix without reading reference records."""
    file_conv = audit_file_convergence(
        candidate_root,
        reference_root,
        repeat_candidate_root=repeat_candidate_root,
    )
    
    files = file_conv.get("files", [])
    matrix_items: list[dict[str, object]] = []
    layer_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    
    for f in files:
        path = str(f.get("path", ""))
        role = str(f.get("role", "unknown"))
        cand_summary = f.get("candidate", {}) or {}
        ref_summary = f.get("reference", {}) or {}
        
        item = _categorize_file_decision(path, role, cand_summary, ref_summary)
        matrix_items.append(item)
        
        layer = item["target_layer"]
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        "diagnostic": "convergence-decision-matrix-v1",
        "read_only": True,
        "reference_records_exported": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "summary": {
            "total_files": len(matrix_items),
            "files_equal_reference": file_conv.get("summary", {}).get("reference_equal_files", 0),
            "files_changed_or_missing": file_conv.get("summary", {}).get("reference_changed_or_missing_files", 0),
            "layer_counts": layer_counts,
            "role_counts": role_counts,
            "adapter_change_authorized_total": 0,
        },
        "items": matrix_items,
    }


def write_convergence_decision_matrix(path: Path, report: Mapping[str, object]) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )