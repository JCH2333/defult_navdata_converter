from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenix_default_navdata.airway_diff_audit import (
    AirwayDiffAuditError,
    audit_airway_differences,
)
from fenix_default_navdata.cli import main
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("RTE_SEG.csv", 2)
    return NavModel(
        tmp_path,
        airway_legs=[
            AirwayLeg(
                "A1",
                1,
                "START",
                "END",
                source,
                start_country="ZU",
                end_country="ZB",
            ),
            AirwayLeg(
                "A1",
                2,
                "END",
                "NEXT",
                source,
                start_country="ZB",
                end_country="ZG",
            ),
        ],
    )


def _semantic_report(
    deltas: list[dict[str, object]],
    *,
    omitted: int = 0,
) -> dict[str, object]:
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
                "field_delta_rows": len(deltas) + omitted,
                "field_delta_samples": deltas,
                "field_delta_samples_omitted": omitted,
            },
        },
    }


def test_airway_diff_audit_classifies_groups_and_hashes_source_mapping(
    tmp_path: Path,
) -> None:
    report = audit_airway_differences(
        _model(tmp_path),
        _semantic_report([
            {
                "logical_key": {
                    "airway_name": "A1",
                    "airway_type": "B",
                    "route_type": None,
                    "airway_fragment_no": 7,
                    "sequence_no": 1,
                },
                "fields": ["from_laty", "minimum_altitude"],
            },
            {
                "logical_key": {
                    "airway_name": "A1",
                    "airway_type": "B",
                    "route_type": None,
                    "airway_fragment_no": 7,
                    "sequence_no": 9,
                },
                "fields": ["airway_fragment_no", "sequence_no"],
            },
            {
                "logical_key": {
                    "airway_name": "A2",
                    "airway_type": "B",
                    "route_type": None,
                    "airway_fragment_no": 1,
                    "sequence_no": 1,
                },
                "fields": ["to_lonx"],
            },
        ]),
        association_sample_limit=10,
    )

    assert report["diagnostic"] == "airway-diff-audit-v1"
    assert report["field_group_row_counts"] == {
        "altitude": 1,
        "geometry": 2,
        "topology": 1,
    }
    assert report["exclusive_classification_counts"] == {
        "geometry": 1,
        "mixed": 1,
        "topology": 1,
    }
    assert report["source_category_counts"] == {
        "absent_from_rte_seg": 1,
        "same_source_airway_and_sequence": 1,
        "source_airway_name_with_different_sequence": 1,
    }
    serialized = json.dumps(report, ensure_ascii=False)
    for value in ("A1", "A2", "START", "END", "NEXT"):
        assert value not in serialized
    assert report["association_summary"]["samples_omitted"] == 0
    assert len(report["association_summary"]["samples"]) == 3


def test_airway_diff_audit_rejects_truncated_or_unredacted_report(
    tmp_path: Path,
) -> None:
    with pytest.raises(AirwayDiffAuditError, match="不完整"):
        audit_airway_differences(
            _model(tmp_path),
            _semantic_report([], omitted=1),
        )

    report = _semantic_report([])
    report["reference_values_redacted"] = False
    with pytest.raises(AirwayDiffAuditError, match="reference_values_redacted"):
        audit_airway_differences(_model(tmp_path), report)


def test_airway_diff_audit_rejects_unknown_field(tmp_path: Path) -> None:
    with pytest.raises(AirwayDiffAuditError, match="未知字段"):
        audit_airway_differences(
            _model(tmp_path),
            _semantic_report([{
                "logical_key": {
                    "airway_name": "A1",
                    "airway_type": "B",
                    "route_type": None,
                    "airway_fragment_no": 1,
                    "sequence_no": 1,
                },
                "fields": ["reference_value"],
            }]),
        )


def test_cli_writes_airway_diff_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    semantic = tmp_path / "semantic.json"
    semantic.write_text(
        json.dumps(_semantic_report([{
            "logical_key": {
                "airway_name": "A1",
                "airway_type": "B",
                "route_type": None,
                "airway_fragment_no": 1,
                "sequence_no": 1,
            },
            "fields": ["from_laty"],
        }])),
        encoding="utf-8",
    )
    model_path = tmp_path / "model.json.gz"
    output = tmp_path / "audit.json"
    observed: dict[str, object] = {}

    def fake_load_model(path: Path) -> NavModel:
        observed["path"] = path
        return _model(tmp_path)

    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        fake_load_model,
    )

    exit_code = main([
        "airway-diff-audit",
        "--model",
        str(model_path),
        "--semantic-diff",
        str(semantic),
        "--output",
        str(output),
    ])

    assert exit_code == 0
    assert observed["path"] == model_path
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostic"] == (
        "airway-diff-audit-v1"
    )
    assert json.loads(capsys.readouterr().out)["read_only"] is True
