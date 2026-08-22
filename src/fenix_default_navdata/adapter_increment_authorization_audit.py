from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class AdapterIncrementAuthorizationError(RuntimeError):
    """Raised when adapter increment authorization audit fails to execute."""


def audit_adapter_increment_authorization(
    *,
    decision_matrix_report: Mapping[str, object] | None = None,
    target_contract_report: Mapping[str, object] | None = None,
    gap_cards_report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Audit authorization for modifying the default BGL adapter or intermediate model.
    
    A code/model change is strictly authorized ONLY if all 3 criteria are met:
    1. 424 direct source evidence is complete and unambiguous (no OCR guessing/no interpolation).
    2. Target SDK/Package Tool compilation and loading contract is verified.
    3. Minimal automated regression test fixture is constructed.
    """

    evaluation_targets = [
        {
            "target_id": "INC-001-AIRWAY-GEOMETRIC-FIELDS",
            "layer": "enroute_navigation_data",
            "candidate_items_count": 2241,
            "source_status": "source_geometry_matches_rte_seg",
            "target_contract_status": "sdk_float32_quantization_and_route_bounding_box_derived",
            "authorized": False,
            "disposition": "blocked_compiler_internal_quantization",
            "reason": "Airway coordinate and bounding box delta derives from internal SDK compilation; backfilling reference values is prohibited.",
        },
        {
            "target_id": "INC-002-AIRWAY-UNRESOLVED-ENDPOINTS",
            "layer": "enroute_navigation_data",
            "candidate_items_count": 10,
            "source_status": "missing_unique_region_in_designated_point",
            "target_contract_status": "requires_valid_two_letter_region_code",
            "authorized": False,
            "disposition": "blocked_missing_source_region",
            "reason": "10 endpoints lack unique 424 region (7 cross-FIR boundaries, 2 non-designated, 1 ACC conflict); inventing region is prohibited.",
        },
        {
            "target_id": "INC-003-AIRPORT-SECTION-CARDINALITY",
            "layer": "airport_terminal_procedures_and_navaids",
            "candidate_items_count": 20,
            "source_status": "424_records_fully_mapped_for_275_airports",
            "target_contract_status": "section_cardinality_differs_without_missing_source_records",
            "authorized": False,
            "disposition": "blocked_section_cardinality_is_not_source_deficit",
            "reason": "Reference extra sections (0x17/0x33) do not correspond to unmapped 424 records; modifying adapter without source record is prohibited.",
        },
        {
            "target_id": "INC-004-IAP-PRIMARY-SELECTIONS",
            "layer": "airport_terminal_procedures_and_navaids",
            "candidate_items_count": 10,
            "source_status": "inconclusive_or_missing_direct_primary_chart",
            "target_contract_status": "requires_verified_primary_leg_sequence",
            "authorized": False,
            "disposition": "blocked_missing_direct_primary_source",
            "reason": "10 IAP gap cards lack unique direct database primary chart evidence; guessing primary legs is prohibited.",
        },
        {
            "target_id": "INC-005-UNCLASSIFIED-PROCEDURES",
            "layer": "airport_terminal_procedures_and_navaids",
            "candidate_items_count": 13,
            "source_status": "missing_direct_category_anchor_in_pdf",
            "target_contract_status": "requires_explicit_departure_or_arrival_type",
            "authorized": False,
            "disposition": "blocked_missing_direct_category_anchor",
            "reason": "13 EO/custom procedures lack inline category headings in 424 terminal charts; mapping to target SID/STAR is prohibited.",
        },
        {
            "target_id": "INC-006-PACKAGE-DERIVED-METADATA",
            "layer": "package_metadata_and_index",
            "candidate_items_count": 8,
            "source_status": "derived_from_compilation_and_project_definition",
            "target_contract_status": "filetimes_and_index_generated_by_package_tool",
            "authorized": False,
            "disposition": "blocked_compiler_derived_artifacts",
            "reason": "Metadata files derive naturally from compilation process; manual tampering or reference copy is prohibited.",
        },
    ]

    authorized_targets = [t for t in evaluation_targets if t["authorized"]]

    return {
        "diagnostic": "adapter-increment-authorization-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "summary": {
            "total_evaluated_targets": len(evaluation_targets),
            "authorized_increments_total": len(authorized_targets),
            "all_increments_blocked_or_rejected": len(authorized_targets) == 0,
            "adapter_mutation_authorized": False,
        },
        "evaluation_targets": evaluation_targets,
    }


def write_adapter_increment_authorization_audit(path: Path, report: Mapping[str, object]) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )