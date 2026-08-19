import json
from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.default_gap_cards import (
    DefaultGapCardAuditError,
    audit_default_gap_cards,
)
from fenix_default_navdata.model import (
    AirwayLeg,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    RejectedProcedure,
    SourceRef,
    Waypoint,
)


def _model(root: Path) -> NavModel:
    source = SourceRef("RTE_SEG.csv", row=4, sha256="source")
    iap_source = SourceRef("Terminal/ZTEST/ZTEST-4Z01.pdf", page=1, sha256="iap")
    model = NavModel(
        root,
        waypoints=[
            Waypoint("missing", "GAP", "", 30.0, 100.0, source, ""),
        ],
        airway_legs=[
            AirwayLeg(
                "A1",
                2,
                "START",
                "GAP",
                source,
                start_country="ZB",
                end_country="",
            ),
        ],
        rejected_procedures=[
            RejectedProcedure("ZTEST", "R01", "no unique primary", iap_source),
        ],
        iap_coverage={
            "unresolved_groups": [{
                "airport": "ZTEST",
                "label": "R01",
                "runway": "01",
                "source": {"file": iap_source.file, "page": 1, "sha256": "iap"},
            }],
        },
    )
    model.procedure_charts.append(ProcedureChart(
        "ZTEST",
        "ZTEST-4Z01.pdf",
        1,
        "terminal-database-coding",
        "DATABASE CODING",
        "iap",
        ("EO-01",),
        ("01",),
        (),
        (),
        (),
        iap_source,
    ))
    model.procedure_segments.append(ProcedureSegment(
        "ZTEST", "EO-01", "", "01", "", (), iap_source,
    ))
    return model


def _candidate_report(path: Path, *, waypoint_count: int = 1) -> Path:
    report = {
        "status": "candidate",
        "projection": {
            "skipped_enroute_waypoints": waypoint_count,
            "skipped_airway_legs": 1,
            "skipped_airway_leg_details": [{
                "airway": "A1",
                "sequence": 2,
                "reasons": ["missing_end_region"],
                "start": {"ident": "START", "type": "VORDME", "region": "ZB"},
                "end": {"ident": "GAP", "type": "DESIGNATED_POINT", "region": ""},
            }],
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_gap_cards_keep_all_open_default_gaps_source_linked(tmp_path: Path) -> None:
    result = audit_default_gap_cards(
        _model(tmp_path / "raw"),
        _candidate_report(tmp_path / "candidate.json"),
    )

    assert result["diagnostic"] == "default-source-gap-cards-v1"
    assert result["reference_records_read"] is False
    assert result["fenix_records_read"] is False
    assert result["summary"] == {
        "total": 4,
        "by_kind": {
            "airway_endpoint_region": 1,
            "enroute_waypoint_region": 1,
            "iap_primary_selection": 1,
            "unclassified_procedure": 1,
        },
        "all_cards_rejected_or_blocked": True,
    }
    airway = result["cards"]["airway_endpoint_region"][0]
    assert airway["source"]["file"] == "RTE_SEG.csv"
    assert airway["disposition"] == "blocked_missing_endpoint_region"
    assert result["cards"]["enroute_waypoint_region"][0]["key"] == "GAP"
    assert result["cards"]["iap_primary_selection"][0]["disposition"] == (
        "rejected_no_unique_primary"
    )
    assert result["cards"]["unclassified_procedure"][0]["label_family"] == "eo_numeric"


def test_gap_cards_reject_report_model_projection_mismatch(tmp_path: Path) -> None:
    with pytest.raises(DefaultGapCardAuditError, match="数量不一致"):
        audit_default_gap_cards(
            _model(tmp_path / "raw"),
            _candidate_report(tmp_path / "candidate.json", waypoint_count=2),
        )


def test_cli_writes_default_gap_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cards.json"
    candidate = _candidate_report(tmp_path / "candidate.json")
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: _model(tmp_path / "raw"),
    )

    exit_code = main([
        "default-gap-cards-audit",
        "--model", str(tmp_path / "model.json.gz"),
        "--candidate-report", str(candidate),
        "--output", str(output),
    ])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["total"] == 4
    assert json.loads(capsys.readouterr().out)["read_only"] is True
