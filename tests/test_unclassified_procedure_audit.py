import hashlib
from dataclasses import replace
from pathlib import Path

from fenix_default_navdata.model import (
    ChartTerminalLeg,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    SourceRef,
)
from fenix_default_navdata.unclassified_procedure_audit import (
    audit_unclassified_procedures,
)
from fenix_default_navdata import unclassified_procedure_card_audit


def _model(root: Path) -> NavModel:
    model = NavModel(root)
    source = SourceRef("Terminal/ZTEST/ZTEST-4Z01.pdf", row=1, page=1, sha256="abc")
    chart = ProcedureChart(
        airport="ZTEST",
        filename="ZTEST-4Z01.pdf",
        page=1,
        chart_type="terminal-database-coding",
        chart_name="DATABASE CODING",
        text_sha256="abc",
        procedure_labels=("EO-15", "CC3-09", "RNP-0"),
        runways=("15",),
        waypoints=(),
        terminal_legs=(),
        fix_coordinates=(),
        source=source,
    )
    model.procedure_charts.append(chart)
    for label in ("EO-15", "CC3-09", "RNP-0"):
        model.procedure_segments.append(
            ProcedureSegment(
                "ZTEST",
                label,
                "",
                "15",
                "",
                (
                    ChartTerminalLeg(
                        label,
                        "15",
                        "TF",
                        "FIX1",
                        "fixture",
                        sequence=1,
                    ),
                ),
                source,
            )
        )
    model.procedure_segments.append(
        ProcedureSegment("ZTEST", "SID1", "离场", "15", "", (), source)
    )
    return model


def test_audit_reports_direct_source_and_rejects_label_only_mapping(tmp_path: Path) -> None:
    report = audit_unclassified_procedures(_model(tmp_path / "raw"))

    assert report["diagnostic"] == "unclassified-procedure-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_read"] is False
    assert report["fenix_records_read"] is False
    assert report["summary"]["unclassified_procedure_segment_total"] == 3
    assert report["summary"]["label_family_counts"] == {
        "cc_numeric": 1,
        "eo_numeric": 1,
        "rnp_numeric": 1,
    }
    eo = next(item for item in report["items"] if item["label"] == "EO-15")
    assert eo["source_chart_status"] == "terminal_database_coding"
    assert eo["source_chart_evidence"][0]["chart_type"] == "terminal-database-coding"
    assert eo["target_mapping_allowed"] is False
    assert eo["source_proven_kind"] is None


def test_audit_marks_missing_direct_chart_evidence(tmp_path: Path) -> None:
    model = _model(tmp_path / "raw")
    model.procedure_charts.clear()

    report = audit_unclassified_procedures(model)

    assert report["summary"]["source_chart_status_counts"] == {
        "missing_matching_terminal_database_chart": 3,
    }


def _card_model(root: Path) -> NavModel:
    pdf = root / "Terminal" / "ZTEST" / "ZTEST-4Z01.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"fixture-pdf")
    model = _model(root)
    source = SourceRef(
        "Terminal/ZTEST/ZTEST-4Z01.pdf",
        row=1,
        page=1,
        sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
    )
    model.procedure_segments = [
        ProcedureSegment(
            "ZTEST",
            "RNP-0",
            "",
            "15",
            "",
            (),
            source,
        )
    ]
    model.procedure_charts[0] = replace(model.procedure_charts[0], source=source)
    return model


def test_card_audit_rejects_nearby_heading_without_direct_label_anchor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        unclassified_procedure_card_audit,
        "_read_source_page_text",
        lambda path, page: "RWY15 进近及复飞\nCF FIX1\n",
    )

    report = unclassified_procedure_card_audit.audit_unclassified_procedure_card(
        _card_model(tmp_path / "raw"),
        "ZTEST:RNP-0:15:0",
    )

    assert report["read_only"] is True
    assert report["direct_text"]["label_match_count"] == 0
    assert report["direct_text"]["category_heading_matches"][0]["kinds"] == ["进近", "复飞"]
    assert report["source_proven_kind"] is None
    assert report["target_mapping_allowed"] is False
    assert report["disposition"] == "rejected_missing_direct_label_anchor"


def test_card_audit_accepts_unique_same_line_direct_label_kind_link(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        unclassified_procedure_card_audit,
        "_read_source_page_text",
        lambda path, page: "RNP-0 进近\n",
    )

    report = unclassified_procedure_card_audit.audit_unclassified_procedure_card(
        _card_model(tmp_path / "raw"),
        "ZTEST:RNP-0:15:0",
    )

    assert report["direct_text"]["label_match_count"] == 1
    assert report["source_proven_kind"] == "进近"
    assert report["target_mapping_allowed"] is True
    assert report["disposition"] == "direct_label_kind_link_confirmed"


def test_batch_card_audit_reuses_exact_card_gate_and_summarizes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        unclassified_procedure_card_audit,
        "_read_source_page_text",
        lambda path, page: "RNP-0 进近\n",
    )

    report = unclassified_procedure_card_audit.audit_unclassified_procedure_cards(
        _card_model(tmp_path / "raw"),
    )

    assert report["diagnostic"] == "unclassified-procedure-cards-audit-v1"
    assert report["summary"] == {
        "card_total": 1,
        "target_mapping_allowed_total": 1,
        "disposition_counts": {"direct_label_kind_link_confirmed": 1},
        "source_proven_kind_counts": {"进近": 1},
    }
    assert report["items"][0]["card_key"] == "ZTEST:RNP-0:15:0"
