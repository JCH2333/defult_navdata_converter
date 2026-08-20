from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.procedure_source_audit import (
    audit_procedure_source_model,
    write_procedure_source_audit,
)
from fenix_default_navdata.model import (
    ChartTerminalLeg,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    SourceRef,
)


def test_procedure_source_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    model = NavModel(raw)
    leg = ChartTerminalLeg(
        procedure_label="TEST-1",
        runway="01",
        leg_type="TF",
        fix_ident="FIX1",
        raw="TF FIX1",
    )
    seg = ProcedureSegment(
        airport="ZBAA",
        label="TEST-1",
        kind="进场",
        runway="01",
        transition="",
        legs=(leg,),
        source=SourceRef("Terminal/ZBAA/test.pdf", 1),
    )
    chart = ProcedureChart(
        airport="ZBAA",
        filename="test.pdf",
        page=1,
        chart_type="standard-terminal-procedure",
        chart_name="TEST",
        text_sha256="abc123",
        procedure_labels=("TEST-1",),
        runways=("01",),
        waypoints=("FIX1",),
        terminal_legs=(leg,),
        fix_coordinates=(),
        source=SourceRef("Terminal/ZBAA/test.pdf", 1),
    )

    model.procedure_segments = [seg]
    model.procedure_charts = [chart]
    model.rejected_procedures = []
    model.ilses = []
    model.holdings = []

    report = audit_procedure_source_model(model)

    assert report["diagnostic"] == "procedure-source-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["total_procedure_segments"] == 1
    assert report["summary"]["total_procedure_charts"] == 1
    assert report["summary"]["total_terminal_legs"] == 1
    assert report["summary"]["airports_with_procedures_total"] == 1
    assert report["summary"]["terminal_leg_type_counts"]["TF"] == 1

    out_file = tmp_path / "out.json"
    write_procedure_source_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
