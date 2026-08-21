from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class SdkSectionClosureAuditError(RuntimeError):
    """Raised when the SDK Section closure inputs are incomplete."""


def _load(path: Path, diagnostic: str) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkSectionClosureAuditError(f"cannot read report: {path}") from error
    if not isinstance(value, dict) or value.get("diagnostic") != diagnostic:
        raise SdkSectionClosureAuditError(f"unexpected diagnostic: {path}")
    return value


def _section_effects(provenance: Mapping[str, object]) -> Mapping[str, object]:
    summary = provenance.get("summary")
    if not isinstance(summary, Mapping):
        raise SdkSectionClosureAuditError("provenance report lacks summary")
    effects = summary.get("section_effects")
    if not isinstance(effects, Mapping):
        raise SdkSectionClosureAuditError("provenance report lacks section effects")
    return effects


def audit_sdk_section_closure(
    provenance_path: Path,
    expression_matrix_path: Path,
    completeness_path: Path,
    inventory_path: Path,
) -> dict[str, object]:
    """Close SDK Section hypotheses without inferring navigation semantics.

    The report intentionally separates reproducible SDK effects from source and
    target-contract authorization. It is reusable for future target adapters.
    """

    provenance = _load(provenance_path, "sdk-section-provenance-audit-v1")
    matrix = _load(expression_matrix_path, "sdk-bgl-expression-matrix-v1")
    completeness = _load(completeness_path, "source-model-completeness-audit-v1")
    inventory = _load(inventory_path, "airport-source-inventory-v2")

    effects = _section_effects(provenance)
    matrix_value = matrix.get("matrix")
    if not isinstance(matrix_value, Mapping):
        raise SdkSectionClosureAuditError("expression matrix lacks matrix")
    next_action = matrix_value.get("next_action")
    if not isinstance(next_action, Mapping):
        raise SdkSectionClosureAuditError("expression matrix lacks next action")

    completeness_summary = completeness.get("summary")
    if not isinstance(completeness_summary, Mapping):
        raise SdkSectionClosureAuditError("completeness report lacks summary")
    inventory_candidates = inventory.get("sdk_probe_candidates")
    if not isinstance(inventory_candidates, Mapping):
        raise SdkSectionClosureAuditError("inventory lacks SDK candidates")

    source_complete_candidates = completeness_summary.get(
        "source_complete_sdk_probe_candidates"
    )
    if not isinstance(source_complete_candidates, list):
        raise SdkSectionClosureAuditError(
            "completeness report lacks source-complete candidate list"
        )

    ndb_category = inventory.get("categories", {})
    if not isinstance(ndb_category, Mapping):
        raise SdkSectionClosureAuditError("inventory lacks categories")
    ndb = ndb_category.get("ndb")
    if not isinstance(ndb, Mapping):
        raise SdkSectionClosureAuditError("inventory lacks ndb category")
    ndb_records = ndb.get("source_records")
    if not isinstance(ndb_records, int):
        raise SdkSectionClosureAuditError("inventory lacks NDB source record count")

    observed_effects = {
        section: effects.get(section)
        for section in ("0x13", "0x17", "0x33", "0x35")
        if section in effects
    }
    rejected: list[dict[str, object]] = []
    ndb_effect = observed_effects.get("0x17")
    ndb_effect_33 = observed_effects.get("0x33")
    if ndb_effect or ndb_effect_33:
        rejected.append({
            "hypothesis": "airport_navaid_index_sections_from_ndb",
            "sections": ["0x17", "0x33"],
            "status": "rejected",
            "reason": (
                "Ndb can reproduce the Section effect in isolation, but the "
                f"424 NDB source has only {ndb_records} records and the inventory "
                "keeps airport-associated navaids out of airport-child projection; "
                "the observed airport Section cardinality and target scope remain "
                "unexplained."
            ),
        })

    if "0x35" in observed_effects:
        rejected.append({
            "hypothesis": "airport_section_0x35_is_missing_navigation_object",
            "sections": ["0x35"],
            "status": "rejected",
            "reason": (
                "0x35 is a candidate-only baseline/layout effect; Section "
                "presence cannot identify a missing 424 navigation object."
            ),
        })

    if not source_complete_candidates:
        rejected.append({
            "hypothesis": "untested_source_complete_sdk_expression",
            "status": "closed",
            "reason": (
                "The source completeness audit reports no source-complete, "
                "untested SDK probe candidate."
            ),
        })

    authorized = bool(
        source_complete_candidates
        and next_action.get("status") != "blocked_on_machine_readable_target_evidence"
    )
    return {
        "diagnostic": "sdk-section-closure-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "model_or_adapter_modified": False,
        "inputs": {
            "provenance": str(provenance_path.expanduser().resolve()),
            "expression_matrix": str(expression_matrix_path.expanduser().resolve()),
            "source_completeness": str(completeness_path.expanduser().resolve()),
            "airport_inventory": str(inventory_path.expanduser().resolve()),
        },
        "summary": {
            "observed_effect_sections": sorted(observed_effects),
            "source_complete_sdk_probe_candidates": source_complete_candidates,
            "ndb_source_records": ndb_records,
            "projection_authorized": authorized,
            "closure_status": "closed_without_adapter_change",
        },
        "reproducible_sdk_effects": observed_effects,
        "rejected_hypotheses": rejected,
        "decision": {
            "projection_authorized": authorized,
            "reason": (
                "No Section effect has both a source-complete 424 mapping and a "
                "target loading contract that explains its scope and cardinality."
            ),
        },
    }


def write_sdk_section_closure_audit(
    path: Path, report: Mapping[str, object]
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
