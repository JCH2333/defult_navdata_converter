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
                start_type="VORDME",
                end_type="DESIGNATED_POINT",
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


def _iap_primary_source_audit(path: Path) -> Path:
    iap_source = SourceRef("Terminal/ZTEST/ZTEST-4Z01.pdf", page=1, sha256="iap")
    path.write_text(json.dumps({
        "diagnostic": "iap-primary-source-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "model_mutated": False,
        "projection_changed": False,
        "items": [{
            "airport": "ZTEST",
            "label": "R01",
            "source": {
                "file": iap_source.file,
                "row": iap_source.row,
                "page": iap_source.page,
                "sha256": iap_source.sha256,
            },
            "disposition": "rejected_transition_and_missed_without_primary",
            "model_sections": {
                "approach": 0,
                "approach_transition": 1,
                "missed": 1,
            },
            "direct_database_sections": {
                "approach": 0,
                "approach_transition": 2,
                "missed": 2,
            },
            "evidence_pages": [],
            "projection_allowed": False,
        }],
    }), encoding="utf-8")
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
    assert airway["unresolved_endpoint_evidence"] == [{
        "side": "end",
        "category": "designated_point_identity_not_found",
        "reason": "RTE_SEG 端点不能唯一回链到 DESIGNATED_POINT.csv",
        "neighbor_regions": ["ZB"],
        "acc_names": [],
    }]
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


def test_gap_cards_bind_exact_iap_primary_source_rejection(
    tmp_path: Path,
) -> None:
    result = audit_default_gap_cards(
        _model(tmp_path / "raw"),
        _candidate_report(tmp_path / "candidate.json"),
        iap_primary_source_audit_path=_iap_primary_source_audit(
            tmp_path / "iap-primary-source-audit.json",
        ),
    )

    card = result["cards"]["iap_primary_selection"][0]
    assert card["disposition"] == "rejected_transition_and_missed_without_primary"
    assert card["primary_source_audit"]["direct_database_sections"] == {
        "approach": 0,
        "approach_transition": 2,
        "missed": 2,
    }
    assert result["source"]["iap_primary_source_audit"].endswith(
        "iap-primary-source-audit.json",
    )


def test_gap_cards_reject_iap_source_audit_with_wrong_source(
    tmp_path: Path,
) -> None:
    audit = _iap_primary_source_audit(tmp_path / "iap-primary-source-audit.json")
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["items"][0]["source"]["sha256"] = "wrong"
    audit.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DefaultGapCardAuditError, match="来源不一致"):
        audit_default_gap_cards(
            _model(tmp_path / "raw"),
            _candidate_report(tmp_path / "candidate.json"),
            iap_primary_source_audit_path=audit,
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


def test_cli_binds_iap_primary_source_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "cards.json"
    candidate = _candidate_report(tmp_path / "candidate.json")
    audit = _iap_primary_source_audit(tmp_path / "iap-primary-source-audit.json")
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: _model(tmp_path / "raw"),
    )

    exit_code = main([
        "default-gap-cards-audit",
        "--model", str(tmp_path / "model.json.gz"),
        "--candidate-report", str(candidate),
        "--iap-primary-source-audit", str(audit),
        "--output", str(output),
    ])

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["cards"]["iap_primary_selection"][0]["disposition"] == (
        "rejected_transition_and_missed_without_primary"
    )
