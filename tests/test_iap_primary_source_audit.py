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
