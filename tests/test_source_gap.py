from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint
from fenix_default_navdata.source_gap import SourceGapAuditError, audit_source_gaps


def _semantic_report(
    *,
    waypoint_samples: list[dict[str, object]],
    airway_samples: list[dict[str, object]],
    waypoint_omitted: int = 0,
) -> dict[str, object]:
    return {
        "diagnostic": "navdatareader-semantic-diff-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "tables": {
            "waypoint": {
                "reference_only_logical_keys": len(waypoint_samples),
                "reference_only_samples": waypoint_samples,
                "reference_only_samples_omitted": waypoint_omitted,
            },
            "airway": {
                "reference_only_logical_keys": len(airway_samples),
                "reference_only_samples": airway_samples,
                "reference_only_samples_omitted": 0,
            },
        },
    }


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("424.csv", 2)
    return NavModel(
        tmp_path,
        waypoints=[
            Waypoint("direct", "DIRECT", "", 35.0, 105.0, source, "ZG"),
            Waypoint("unresolved", "UNRESOLVED", "", 36.0, 106.0, source, ""),
        ],
        airway_legs=[
            AirwayLeg("A1", 1, "ENDPOINT", "TAIL", source, start_country="ZU"),
            AirwayLeg("A1", 2, "TAIL", "DIRECT", source, start_country="", end_country="ZG"),
        ],
    )


def test_source_gap_audit_classifies_only_against_424_model(tmp_path: Path) -> None:
    report = _semantic_report(
        waypoint_samples=[
            {"logical_key": {"ident": "DIRECT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "UNRESOLVED", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "ENDPOINT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "ABSENT", "region": "ZB", "airport_ident": None}},
        ],
        airway_samples=[
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 1,
            }},
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 9,
            }},
            {"logical_key": {
                "airway_name": "A2", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 1, "sequence_no": 1,
            }},
        ],
    )

    result = audit_source_gaps(_model(tmp_path), report)

    assert result["waypoint_source_categories"] == {
        "absent_from_structured_designated_and_route_endpoints": 1,
        "direct_designated_different_region": 1,
        "direct_designated_region_unresolved": 1,
        "route_endpoint_different_region": 1,
    }
    assert result["airway_source_categories"] == {
        "absent_from_rte_seg": 1,
        "same_source_airway_and_sequence": 1,
        "source_airway_name_with_different_sequence": 1,
    }
    serialized = json.dumps(result)
    assert "DIRECT" not in serialized
    assert "A1" not in serialized


def test_source_gap_audit_rejects_truncated_reference_gap_samples(tmp_path: Path) -> None:
    report = _semantic_report(
        waypoint_samples=[],
        airway_samples=[],
        waypoint_omitted=1,
    )

    with pytest.raises(SourceGapAuditError, match="截断"):
        audit_source_gaps(_model(tmp_path), report)


def test_cli_writes_source_gap_audit_without_loading_terminal_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    semantic = tmp_path / "semantic.json"
    semantic.write_text(json.dumps(_semantic_report(
        waypoint_samples=[],
        airway_samples=[],
    )), encoding="utf-8")
    output = tmp_path / "audit.json"
    observed: dict[str, object] = {}

    def fake_load(root: Path, *, include_terminal_documents: bool) -> NavModel:
        observed["root"] = root
        observed["include_terminal_documents"] = include_terminal_documents
        return _model(tmp_path)

    monkeypatch.setattr("fenix_default_navdata.cli.load_naip", fake_load)

    exit_code = main([
        "source-gap-audit",
        "--raw", str(tmp_path / "raw"),
        "--semantic-diff", str(semantic),
        "--output", str(output),
    ])

    assert exit_code == 0
    assert observed["include_terminal_documents"] is False
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostic"] == "source-gap-audit-v2"
    assert json.loads(capsys.readouterr().out)["read_only"] is True
