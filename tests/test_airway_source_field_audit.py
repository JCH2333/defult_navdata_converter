from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fenix_default_navdata.airway_source_field_audit import (
    audit_airway_source_fields,
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
                source_route_minimum_crossing_altitude="2000",
                source_segment_minimum_crossing_altitude="2000",
            ),
            AirwayLeg(
                "A1",
                2,
                "END",
                "NEXT",
                source,
                source_route_minimum_crossing_altitude="600",
                source_segment_minimum_crossing_altitude="650",
            ),
            AirwayLeg(
                "A2",
                1,
                "A",
                "B",
                source,
                source_route_minimum_crossing_altitude="",
                source_segment_minimum_crossing_altitude="bad",
            ),
        ],
    )


def _semantic(*keys: dict[str, object]) -> dict[str, object]:
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
                "reference_only_logical_keys": 0,
                "reference_only_samples": [],
                "reference_only_samples_omitted": 0,
                "field_delta_rows": len(keys),
                "field_delta_samples": [
                    {"logical_key": key, "fields": ["minimum_altitude"]}
                    for key in keys
                ],
                "field_delta_samples_omitted": 0,
            }
        },
    }


def _key(name: str, sequence: int) -> dict[str, object]:
    return {
        "airway_name": name,
        "airway_type": "B",
        "route_type": None,
        "airway_fragment_no": 1,
        "sequence_no": sequence,
    }


def _database(path: Path, rows: list[tuple[object, ...]]) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE airway (
            airway_name TEXT,
            airway_type TEXT,
            route_type TEXT,
            airway_fragment_no INTEGER,
            sequence_no INTEGER,
            minimum_altitude INTEGER
        )
        """
    )
    connection.executemany("INSERT INTO airway VALUES (?, ?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()


def _rows(*altitudes: int) -> list[tuple[object, ...]]:
    return [
        ("A1", "B", None, 1, index, altitude)
        for index, altitude in enumerate(altitudes, start=1)
    ]


def test_source_field_audit_classifies_conflict_and_unit_matches(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.sqlite"
    reference = tmp_path / "reference.sqlite"
    _database(candidate, _rows(0, 0))
    _database(reference, _rows(2000, 2000))

    report = audit_airway_source_fields(
        _model(tmp_path),
        _semantic(_key("A1", 1), _key("A1", 2)),
        candidate,
        reference,
    )

    assert report["diagnostic"] == "airway-source-field-audit-v1"
    assert report["source_val_mtca"]["evidence_categories"] == {
        "both_different": 1,
        "both_same": 1,
    }
    assert report["source_val_mtca"]["invalid_value_rows"] == 0
    assert report["reference_altitude"]["nonzero_rows"] == 2
    assert report["reference_altitude"]["nonzero_rows_with_source_value"] == 2
    assert report["reference_altitude"][
        "nonzero_rows_with_source_transform_match"
    ] == 1
    assert report["evidence_status"] == (
        "source_transform_partially_covers_reference_nonzero_rows"
    )
    serialized = json.dumps(report, ensure_ascii=False)
    assert "A1" not in serialized
    assert "2000" not in serialized


def test_source_field_audit_does_not_count_invalid_or_missing_source(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.sqlite"
    reference = tmp_path / "reference.sqlite"
    _database(candidate, [("A2", "B", None, 1, 1, 0)])
    _database(reference, [("A2", "B", None, 1, 1, 3000)])

    report = audit_airway_source_fields(
        _model(tmp_path),
        _semantic(_key("A2", 1)),
        candidate,
        reference,
    )

    assert report["source_val_mtca"]["evidence_categories"] == {
        "both_empty": 1,
    }
    assert report["source_val_mtca"]["invalid_value_rows"] == 1
    assert report["reference_altitude"]["nonzero_rows_with_source_value"] == 0
    assert report["evidence_status"] == "no_source_transform_match"
    assert report["adapter_change_authorized"] is False


def test_cli_writes_airway_source_field_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = tmp_path / "candidate.sqlite"
    reference = tmp_path / "reference.sqlite"
    semantic = tmp_path / "semantic.json"
    output = tmp_path / "audit.json"
    _database(candidate, _rows(0))
    _database(reference, _rows(2000))
    semantic.write_text(
        json.dumps(_semantic(_key("A1", 1))),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: _model(tmp_path),
    )

    assert main([
        "airway-source-field-audit",
        "--model", str(tmp_path / "model.json.gz"),
        "--semantic-diff", str(semantic),
        "--candidate-database", str(candidate),
        "--reference-database", str(reference),
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostic"] == (
        "airway-source-field-audit-v1"
    )
