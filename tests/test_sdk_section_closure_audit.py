from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.sdk_section_closure_audit import (
    audit_sdk_section_closure,
    write_sdk_section_closure_audit,
)


def _write(path: Path, diagnostic: str, **values: object) -> Path:
    path.write_text(
        json.dumps({"diagnostic": diagnostic, **values}),
        encoding="utf-8",
    )
    return path


def test_section_closure_rejects_reproducible_ndb_effect_without_projection(
    tmp_path: Path,
) -> None:
    provenance = _write(
        tmp_path / "provenance.json",
        "sdk-section-provenance-audit-v1",
        summary={"section_effects": {
            "0x17": {"added_or_increased": ["case:ndb"]},
            "0x33": {"added_or_increased": ["case:ndb"]},
            "0x35": {"removed_or_decreased": ["case:ndb"]},
        }},
    )
    matrix = _write(
        tmp_path / "matrix.json",
        "sdk-bgl-expression-matrix-v1",
        matrix={"next_action": {
            "status": "blocked_on_machine_readable_target_evidence"
        }},
    )
    completeness = _write(
        tmp_path / "completeness.json",
        "source-model-completeness-audit-v1",
        summary={"source_complete_sdk_probe_candidates": []},
    )
    inventory = _write(
        tmp_path / "inventory.json",
        "airport-source-inventory-v2",
        categories={"ndb": {"source_records": 41}},
        sdk_probe_candidates={},
    )

    report = audit_sdk_section_closure(
        provenance, matrix, completeness, inventory
    )

    assert report["diagnostic"] == "sdk-section-closure-audit-v1"
    assert report["summary"]["projection_authorized"] is False
    assert report["summary"]["ndb_source_records"] == 41
    assert len(report["rejected_hypotheses"]) == 3
    output = tmp_path / "closure.json"
    write_sdk_section_closure_audit(output, report)
    assert json.loads(output.read_text(encoding="utf-8"))["read_only"] is True
