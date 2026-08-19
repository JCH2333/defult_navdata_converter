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
