from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class SdkBglExpressionMatrixError(RuntimeError):
    pass


def _has_reference_gap_sections(value: object) -> bool:
    """Normalize legacy text and current structured gap indicators."""

    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, Mapping)):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().casefold() not in {
            "false",
            "none",
            "[]",
            "{}",
        }
    return bool(value)


def _load(path: Path, diagnostic: str) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkBglExpressionMatrixError(f"cannot read report: {path}") from error
    if not isinstance(value, dict) or (
        value.get("diagnostic") != diagnostic and value.get("probe") != diagnostic
    ):
        raise SdkBglExpressionMatrixError(f"unexpected diagnostic: {path}")
    return value


def audit_sdk_bgl_expression_matrix(
    inventory_path: Path,
    projection_matrix_path: Path,
    enroute_cardinality_path: Path,
    connection_probe_path: Path,
    child_order_probe_path: Path,
    offset_threshold_matrix_path: Path | None = None,
) -> dict[str, object]:
    """Summarize only reusable, machine-readable SDK evidence."""

    inventory = _load(inventory_path, "airport-source-inventory-v2")
    projection = _load(projection_matrix_path, "airway-projection-matrix-audit-v1")
    cardinality = _load(enroute_cardinality_path, "enroute-bgl-cardinality-audit-v1")
    connection = _load(connection_probe_path, "sdk_airway_connection_shape")
    child_order = _load(child_order_probe_path, "sdk_airway_route_child_order")
    offset_threshold = (
        _load(offset_threshold_matrix_path, "offset-threshold-matrix-v1")
        if offset_threshold_matrix_path is not None
        else None
    )
    classifications = projection.get("classification_counts")
    if not isinstance(classifications, Mapping):
        raise SdkBglExpressionMatrixError("projection matrix lacks classifications")
    complete = (
        not classifications.get("missing_from_xml")
        and not classifications.get("ambiguous_output_match")
        and projection.get("candidate_connections_without_source_owner") == 0
    )
    if not complete:
        raise SdkBglExpressionMatrixError("candidate airway serialization is incomplete")
    probe_rows = connection.get("airway_rows")
    order_rows = child_order.get("airway_rows")
    if not isinstance(probe_rows, list) or not isinstance(order_rows, list):
        raise SdkBglExpressionMatrixError("route probes lack reader rows")
    candidates = inventory.get("sdk_probe_candidates")
    if not isinstance(candidates, Mapping):
        raise SdkBglExpressionMatrixError("inventory lacks SDK candidates")
    sections = []
    for file in cardinality.get("files", []):
        if isinstance(file, Mapping):
            sections.extend(file.get("section_deltas", []))
    airport_candidates = {
        key: value.get("disposition")
        for key, value in sorted(candidates.items())
        if isinstance(value, Mapping)
    }
    offset_threshold_evidence: dict[str, object] | None = None
    if offset_threshold is not None:
        source_records = offset_threshold.get("source_records")
        builds = offset_threshold.get("builds")
        observed = offset_threshold.get("bgl_section_types_observed")
        offset_threshold_evidence = {
            "source_records": source_records,
            "builds": builds,
            "bgl_section_types_observed": observed,
            "contains_reference_gap_sections": _has_reference_gap_sections(
                offset_threshold.get("contains_reference_gap_sections")
            ),
            "candidate_or_model_modified": bool(
                offset_threshold.get("candidate_or_model_modified")
            ),
            "disposition": (
                "tested_no_reference_convergence_and_rejected"
                if (
                    isinstance(source_records, int)
                    and isinstance(builds, Mapping)
                    and builds.get("total") == source_records
                    and builds.get("successful") == source_records
                    and not offset_threshold.get("candidate_or_model_modified")
                )
                else "evidence_incomplete"
            ),
        }
        if offset_threshold_evidence["disposition"] == (
            "tested_no_reference_convergence_and_rejected"
        ):
            airport_candidates["runway_offset_thresholds"] = (
                "rejected_after_probe"
            )
    return {
        "diagnostic": "sdk-bgl-expression-matrix-v1",
        "read_only": True,
        "reference_payload_read": False,
        "matrix": {
            "enroute_route_serialization": {
                "status": "verified_no_new_single_variable",
                "source_xml_complete": complete,
                "connection_probe_airway_rows": len(probe_rows),
                "child_order_probe_airway_rows": len(order_rows),
                "section_deltas_without_semantics": sections,
            },
            "airport_expression_candidates": {
                **airport_candidates,
            },
            "airport_expression_evidence": {
                "runway_offset_thresholds": offset_threshold_evidence,
            },
            "next_action": {
                "status": "blocked_on_machine_readable_target_evidence",
                "reason": (
                    "No source-complete, untested XML expression remains in the "
                    "provided reports; historical probe conclusions must be "
                    "standardized before they can select another variable."
                ),
            },
        },
    }


def write_sdk_bgl_expression_matrix(path: Path, report: Mapping[str, object]) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
