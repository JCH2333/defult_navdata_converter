from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef
from fenix_default_navdata.route_type_source_audit import (
    RouteTypeSourceAuditError,
    audit_route_type_source,
)


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("RTE_SEG.csv", 2)
    return NavModel(
        tmp_path,
        airway_legs=[
            AirwayLeg(
                "A1", 1, "START", "END", source,
                start_country="ZU", end_country="ZB",
                source_enroute_location_type="LOC-A",
                source_code_type="RNAV2",
                direction="X",
            ),
            AirwayLeg(
                "A1", 2, "END", "NEXT", source,
                start_country="ZB", end_country="ZG",
                source_enroute_location_type="LOC-A",
                source_code_type="RNAV2",
                direction="X",
            ),
            AirwayLeg(
                "A2", 1, "A", "B", source,
                start_country="ZU", end_country="ZB",
                source_enroute_location_type="LOC-B",
                source_code_type="RNP4",
                direction="F",
            ),
        ],
    )


def _report(
    *,
    reference_keys: list[dict[str, object]],
    delta_keys: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    delta_keys = delta_keys or []
    return {
        "diagnostic": "navdatareader-semantic-diff-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "reader_output": {
            "candidate": {"bgl_file_rows": 1, "expected_bgl_count": 1},
            "reference": {"bgl_file_rows": 1, "expected_bgl_count": 1},
        },
        "tables": {
            "airway": {
                "reference_only_logical_keys": len(reference_keys),
                "reference_only_samples": [
                    {"logical_key": key} for key in reference_keys
                ],
                "reference_only_samples_omitted": 0,
                "field_delta_rows": len(delta_keys),
                "field_delta_samples": [
                    {"logical_key": key, "fields": ["from_lonx"]}
                    for key in delta_keys
                ],
                "field_delta_samples_omitted": 0,
            },
        },
    }


def _key(name: str, route_type: str, sequence: int) -> dict[str, object]:
    return {
        "airway_name": name,
        "airway_type": route_type,
        "route_type": None,
        "airway_fragment_no": 1,
        "sequence_no": sequence,
    }


def test_route_type_source_audit_reports_conflict_and_unmatched(
    tmp_path: Path,
) -> None:
    report = audit_route_type_source(
        _model(tmp_path),
        _report(
            reference_keys=[
                _key("A1", "J", 1),
                _key("A1", "V", 2),
                _key("A9", "J", 1),
            ],
            delta_keys=[_key("A2", "J", 1)],
        ),
    )

    assert report["diagnostic"] == "route-type-source-audit-v1"
    assert report["target_type_counts"] == {"J": 3, "V": 1}
    assert report["source_match_counts"] == {
        "unique": 3,
        "unmatched": 1,
    }
    assert report["conflicting_source_metadata_combinations"] == 1
    assert report["evidence_status"] == "insufficient_for_adapter_rule"


def test_route_type_source_audit_rejects_truncated_report(
    tmp_path: Path,
) -> None:
    report = _report(reference_keys=[_key("A1", "J", 1)])
    report["tables"]["airway"]["reference_only_samples_omitted"] = 1
    with pytest.raises(RouteTypeSourceAuditError):
        audit_route_type_source(_model(tmp_path), report)


def test_cli_writes_route_type_source_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic = tmp_path / "semantic.json"
    semantic.write_text(
        json.dumps(_report(reference_keys=[_key("A1", "J", 1)])),
        encoding="utf-8",
    )
    model_path = tmp_path / "model.json.gz"
    output = tmp_path / "route-type.json"
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: _model(tmp_path),
    )

    assert main([
        "route-type-source-audit",
        "--model", str(model_path),
        "--semantic-diff", str(semantic),
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostic"] == (
        "route-type-source-audit-v1"
    )
