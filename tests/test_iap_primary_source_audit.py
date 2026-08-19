import json
from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.iap_primary_source_audit import (
    IapPrimarySourceAuditError,
    audit_iap_primary_sources,
)
from fenix_default_navdata.model import (
    ChartTerminalLeg,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    RejectedProcedure,
    SourceRef,
)


def _model(root: Path) -> tuple[NavModel, SourceRef]:
    source = SourceRef(
        "Terminal/ZTEST/ZTEST-0C-19.pdf",
        page=1,
        sha256="database-hash",
    )
    model = NavModel(root)
    model.procedure_segments.extend([
        ProcedureSegment(
            "ZTEST",
            "R29R",
            "进近过渡",
            "29R",
            "AD521",
            (
                ChartTerminalLeg(
                    "R29R", "29R", "IF", "AD521", "fixture", sequence=1,
                ),
                ChartTerminalLeg(
                    "R29R", "29R", "TF", "AD790", "fixture", sequence=2,
                ),
            ),
            source,
        ),
        ProcedureSegment(
            "ZTEST",
            "R29R",
            "复飞",
            "29R",
            "",
            (
                ChartTerminalLeg(
                    "R29R", "29R", "CA", None, "fixture", sequence=1,
                ),
                ChartTerminalLeg(
                    "R29R", "29R", "DF", "AD521", "fixture", sequence=2,
                ),
            ),
            source,
        ),
    ])
    model.rejected_procedures.append(
        RejectedProcedure("ZTEST", "R29R", "no unique primary", source),
    )
    model.iap_coverage = {
        "unresolved_groups": [{
            "airport": "ZTEST",
            "label": "R29R",
            "runway": "29R",
            "status": "no_unique_primary",
            "source": {
                "file": source.file,
                "page": source.page,
                "sha256": source.sha256,
            },
        }],
    }
    return model, source


def _cache(
    path: Path,
    source: SourceRef,
    *,
    include_primary: bool = False,
) -> Path:
    legs = [
        {
            "procedure_kind": "进近过渡",
            "procedure_label": "R29R",
            "runway": "29R",
            "transition": "AD521",
            "leg_type": "IF",
            "fix_ident": "AD521",
        },
        {
            "procedure_kind": "复飞",
            "procedure_label": "R29R",
            "runway": "29R",
            "transition": "",
            "leg_type": "CA",
            "fix_ident": None,
        },
    ]
    if include_primary:
        legs.append({
            "procedure_kind": "进近",
            "procedure_label": "R29R",
            "runway": "29R",
            "transition": "",
            "leg_type": "TF",
            "fix_ident": "RW29R",
        })
    path.write_text(json.dumps({
        "charts": [{
            "airport": "ZTEST",
            "chart_name": "数据库编码",
            "chart_type": "terminal-database-coding",
            "filename": "ZTEST-0C-19.pdf",
            "source": {
                "file": source.file,
                "page": source.page,
                "sha256": source.sha256,
            },
            "terminal_legs": legs,
        }],
    }), encoding="utf-8")
    return path


def _related_label_model(root: Path) -> tuple[NavModel, SourceRef]:
    source = SourceRef(
        "Terminal/ZYDD/ZYDD-0C-2.pdf",
        page=1,
        sha256="related-database-hash",
    )
    model = NavModel(root)
    model.procedure_segments.extend([
        ProcedureSegment(
            "ZYDD",
            "R01",
            "进近过渡",
            "01",
            "DD505",
            (
                ChartTerminalLeg(
                    "R01", "01", "IF", "DD505", "fixture", sequence=1,
                ),
            ),
            source,
        ),
        ProcedureSegment(
            "ZYDD",
            "R01-Y",
            "复飞",
            "01",
            "",
            (
                ChartTerminalLeg(
                    "R01-Y", "01", "DF", "DD503", "fixture", sequence=1,
                ),
            ),
            source,
        ),
    ])
    model.rejected_procedures.extend([
        RejectedProcedure("ZYDD", "R01", "no unique primary", source),
        RejectedProcedure("ZYDD", "R01-Y", "no unique primary", source),
    ])
    model.iap_coverage = {
        "unresolved_groups": [
            {
                "airport": "ZYDD",
                "label": "R01",
                "runway": "01",
                "status": "no_unique_primary",
                "source": {
                    "file": source.file,
                    "page": source.page,
                    "sha256": source.sha256,
                },
            },
            {
                "airport": "ZYDD",
                "label": "R01-Y",
                "runway": "01",
                "status": "no_unique_primary",
                "source": {
                    "file": source.file,
                    "page": source.page,
                    "sha256": source.sha256,
                },
            },
        ],
    }
    return model, source


def _related_label_cache(
    path: Path,
    source: SourceRef,
    *,
    include_primary: bool = False,
) -> Path:
    legs = [
        {
            "procedure_kind": "进近过渡",
            "procedure_label": "R01",
            "runway": "01",
            "transition": "DD505",
            "leg_type": "IF",
            "fix_ident": "DD505",
        },
        {
            "procedure_kind": "复飞",
            "procedure_label": "R01-Y",
            "runway": "01",
            "transition": "",
            "leg_type": "DF",
            "fix_ident": "DD503",
        },
    ]
    if include_primary:
        legs.append({
            "procedure_kind": "进近",
            "procedure_label": "R01",
            "runway": "01",
            "transition": "",
            "leg_type": "TF",
            "fix_ident": "RW01",
        })
    path.write_text(json.dumps({
        "charts": [{
            "airport": "ZYDD",
            "chart_name": "数据库编码",
            "chart_type": "terminal-database-coding",
            "filename": "ZYDD-0C-2.pdf",
            "source": {
                "file": source.file,
                "page": source.page,
                "sha256": source.sha256,
            },
            "terminal_legs": legs,
        }],
    }), encoding="utf-8")
    return path


def test_audit_rejects_transition_and_missed_without_primary(
    tmp_path: Path,
) -> None:
    model, source = _model(tmp_path / "raw")

    report = audit_iap_primary_sources(
        model,
        [_cache(tmp_path / "evidence.json", source)],
    )

    assert report["reference_records_read"] is False
    assert report["fenix_records_read"] is False
    assert report["model_mutated"] is False
    assert report["projection_changed"] is False
    assert report["summary"] == {
        "unresolved_group_total": 1,
        "by_disposition": {
            "rejected_transition_and_missed_without_primary": 1,
        },
    }
    item = report["items"][0]
    assert item["disposition"] == "rejected_transition_and_missed_without_primary"
    assert item["model_sections"] == {
        "approach": 0,
        "approach_transition": 1,
        "missed": 1,
    }
    assert item["direct_database_sections"] == {
        "approach": 0,
        "approach_transition": 1,
        "missed": 1,
    }
    assert item["same_page_iap_labels"] == [{
        "label": "R29R",
        "runway": "29R",
        "sections": {
            "approach": 0,
            "approach_transition": 1,
            "missed": 1,
        },
    }]
    assert item["projection_allowed"] is False


def test_audit_rejects_related_same_page_base_and_variant_without_primary(
    tmp_path: Path,
) -> None:
    model, source = _related_label_model(tmp_path / "raw")

    report = audit_iap_primary_sources(
        model,
        [_related_label_cache(tmp_path / "evidence.json", source)],
    )

    assert report["summary"] == {
        "unresolved_group_total": 2,
        "by_disposition": {
            "rejected_related_same_page_sections_without_primary": 2,
        },
    }
    for item in report["items"]:
        assert item["disposition"] == (
            "rejected_related_same_page_sections_without_primary"
        )
        assert item["related_same_page_sections"] == {
            "base_label": "R01",
            "members": [
                {
                    "label": "R01",
                    "runway": "01",
                    "sections": {
                        "approach": 0,
                        "approach_transition": 1,
                        "missed": 0,
                    },
                },
                {
                    "label": "R01-Y",
                    "runway": "01",
                    "sections": {
                        "approach": 0,
                        "approach_transition": 0,
                        "missed": 1,
                    },
                },
            ],
            "sections": {
                "approach": 0,
                "approach_transition": 1,
                "missed": 1,
            },
        }
        assert item["projection_allowed"] is False


def test_audit_keeps_related_same_page_labels_unresolved_when_primary_exists(
    tmp_path: Path,
) -> None:
    model, source = _related_label_model(tmp_path / "raw")

    report = audit_iap_primary_sources(
        model,
        [_related_label_cache(
            tmp_path / "evidence.json",
            source,
            include_primary=True,
        )],
    )

    assert {
        item["disposition"] for item in report["items"]
    } == {"unresolved_direct_database_evidence_inconclusive"}


def test_audit_keeps_related_same_page_labels_unresolved_when_model_has_primary(
    tmp_path: Path,
) -> None:
    model, source = _related_label_model(tmp_path / "raw")
    model.procedure_segments.append(
        ProcedureSegment(
            "ZYDD",
            "R01",
            "进近",
            "01",
            "",
            (
                ChartTerminalLeg(
                    "R01", "01", "TF", "RW01", "fixture", sequence=1,
                ),
            ),
            SourceRef(
                "Terminal/ZYDD/ZYDD-0C-3.pdf",
                page=1,
                sha256="other-page-hash",
            ),
        ),
    )

    report = audit_iap_primary_sources(
        model,
        [_related_label_cache(tmp_path / "evidence.json", source)],
    )

    assert {
        item["disposition"] for item in report["items"]
    } == {"unresolved_direct_database_evidence_inconclusive"}


def test_audit_does_not_reject_when_direct_database_evidence_has_primary(
    tmp_path: Path,
) -> None:
    model, source = _model(tmp_path / "raw")

    report = audit_iap_primary_sources(
        model,
        [_cache(tmp_path / "evidence.json", source, include_primary=True)],
    )

    item = report["items"][0]
    assert item["disposition"] == "unresolved_direct_database_evidence_inconclusive"
    assert item["direct_database_sections"]["approach"] == 1
    assert item["projection_allowed"] is False


def test_audit_reports_title_match_without_creating_missing_primary(
    tmp_path: Path,
) -> None:
    model, source = _model(tmp_path / "raw")
    chart_source = SourceRef(
        "Terminal/ZTEST/ZTEST-5A.pdf",
        page=1,
        sha256="chart-hash",
    )
    model.procedure_charts.append(
        ProcedureChart(
            "ZTEST",
            "ZTEST-5A.pdf",
            1,
            "instrument-approach-index",
            "RNP ILS/DME z RWY29R",
            "fixture",
            (),
            ("29R",),
            (),
            (),
            (),
            chart_source,
        ),
    )

    report = audit_iap_primary_sources(
        model,
        [_cache(tmp_path / "evidence.json", source)],
    )

    item = report["items"][0]
    assert item["disposition"] == "rejected_transition_and_missed_without_primary"
    assert item["model_sections"]["approach"] == 0
    assert item["instrument_chart_title_candidates"] == [{
        "filename": "ZTEST-5A.pdf",
        "chart_name": "RNP ILS/DME z RWY29R",
        "source": {
            "file": chart_source.file,
            "page": chart_source.page,
            "row": chart_source.row,
            "sha256": chart_source.sha256,
        },
        "title_label_candidates": ["I29R", "R29R", "I29RZ", "I29R-Z", "R29R-Z"],
        "direct_label_match": True,
    }]
    assert item["projection_allowed"] is False


def test_audit_requires_at_least_one_evidence_cache(tmp_path: Path) -> None:
    model, _ = _model(tmp_path / "raw")

    with pytest.raises(IapPrimarySourceAuditError, match="至少需要"):
        audit_iap_primary_sources(model, [])


def test_cli_writes_iap_primary_source_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model, source = _model(tmp_path / "raw")
    cache = _cache(tmp_path / "evidence.json", source)
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: model,
    )

    exit_code = main([
        "iap-primary-source-audit",
        "--model", str(tmp_path / "model.json.gz"),
        "--pdf-evidence-cache", str(cache),
        "--output", str(output),
    ])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["items"][0]["key"] == (
        "ZTEST:R29R"
    )
    assert json.loads(capsys.readouterr().out)["read_only"] is True
