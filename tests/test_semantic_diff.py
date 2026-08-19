from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.semantic_diff import (
    TABLE_SPECS,
    SemanticDiffError,
    semantic_diff,
    semantic_reproducibility_audit,
)


def _default_value(field: str) -> object:
    values = {
        "ident": "BASE",
        "name": "CANDIDATE NAME",
        "region": "ZB",
        "airport_ident": None,
        "type": "H",
        "frequency": 112300,
        "channel": None,
        "range": 125,
        "mag_var": 1.25,
        "dme_only": 0,
        "dme_altitude": 100,
        "dme_lonx": 105.0,
        "dme_laty": 35.0,
        "altitude": 100,
        "lonx": 105.0,
        "laty": 35.0,
        "artificial": 0,
        "arinc_type": "EA",
        "num_victor_airway": 1,
        "num_jet_airway": 2,
        "airway_name": "A1",
        "airway_type": "B",
        "route_type": None,
        "airway_fragment_no": 1,
        "sequence_no": 1,
        "direction": "F",
        "minimum_altitude": 8000,
        "maximum_altitude": 12000,
        "left_lonx": 104.9,
        "top_laty": 35.1,
        "right_lonx": 105.1,
        "bottom_laty": 34.9,
        "from_lonx": 104.9,
        "from_laty": 34.9,
        "to_lonx": 105.1,
        "to_laty": 35.1,
    }
    return values[field]


def _write_database(
    path: Path,
    rows: dict[str, list[dict[str, object]]],
    *,
    bgl_file_rows: int = 1,
) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE bgl_file (bgl_file_id INTEGER PRIMARY KEY, filepath TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO bgl_file(bgl_file_id, filepath) VALUES (?, ?)",
            ((index, f"source-{index}.bgl") for index in range(1, bgl_file_rows + 1)),
        )
        for spec in TABLE_SPECS:
            columns = ", ".join(f'"{field}" BLOB' for field in spec.semantic_fields)
            connection.execute(f'CREATE TABLE "{spec.table}" ({columns})')
            for row in rows.get(spec.table, []):
                values = {field: _default_value(field) for field in spec.semantic_fields}
                values.update(row)
                fields = ", ".join(f'"{field}"' for field in spec.semantic_fields)
                placeholders = ", ".join("?" for _ in spec.semantic_fields)
                connection.execute(
                    f'INSERT INTO "{spec.table}" ({fields}) VALUES ({placeholders})',
                    tuple(values[field] for field in spec.semantic_fields),
                )
        connection.commit()
    finally:
        connection.close()
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_semantic_diff_reports_field_names_and_redacts_reference_values(tmp_path: Path):
    candidate = _write_database(
        tmp_path / "candidate.sqlite",
        {
            "vor": [
                {"ident": "SAME", "name": "CANDIDATE NAME", "altitude": 100},
                {"ident": "EXTRA", "name": "SOURCE BACKED EXTRA"},
            ],
        },
    )
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {
            "vor": [
                {
                    "ident": "SAME",
                    "name": "REFERENCE SECRET NAME",
                    "altitude": 9999,
                    "frequency": 119950,
                    "lonx": 12.345678,
                },
                {"ident": "MISSING", "name": "REFERENCE ONLY NAME", "frequency": 118765},
            ],
        },
    )
    before = _digest(candidate)
    reference_before = _digest(reference)

    report = semantic_diff(
        candidate,
        reference,
        expected_candidate_bgl_count=1,
        expected_reference_bgl_count=1,
        tables=("vor",),
        sample_limit=10,
    )

    assert _digest(candidate) == before
    assert _digest(reference) == reference_before
    table = report["tables"]["vor"]
    assert table["candidate_rows"] == 2
    assert table["reference_rows"] == 2
    assert table["candidate_only_logical_keys"] == 1
    assert table["reference_only_logical_keys"] == 1
    assert table["candidate_only_strict_rows"] == 2
    assert table["reference_only_strict_rows"] == 2
    assert table["field_delta_rows"] == 1
    assert table["candidate_only_samples"] == [{
        "logical_key": {"ident": "EXTRA", "region": "ZB", "airport_ident": None},
        "candidate_rows": 1,
    }]
    assert table["reference_only_samples"] == [{
        "logical_key": {"ident": "MISSING", "region": "ZB", "airport_ident": None},
        "reference_rows": 1,
    }]
    assert table["field_delta_samples"] == [{
        "logical_key": {"ident": "SAME", "region": "ZB", "airport_ident": None},
        "fields": ["name", "frequency", "altitude", "lonx"],
    }]
    payload = json.dumps(report, ensure_ascii=False)
    assert "REFERENCE SECRET NAME" not in payload
    assert "REFERENCE ONLY NAME" not in payload
    assert "119950" not in payload
    assert "12.345678" not in payload


def test_semantic_diff_samples_are_stable_and_limited(tmp_path: Path):
    candidate = _write_database(
        tmp_path / "candidate.sqlite",
        {"vor": [{"ident": "ZED"}, {"ident": "ALFA"}, {"ident": "BRAVO"}]},
    )
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {"vor": [], "ndb": [{"ident": "REFERENCE-SEED"}]},
    )

    report = semantic_diff(
        candidate,
        reference,
        expected_candidate_bgl_count=1,
        expected_reference_bgl_count=1,
        tables=("vor",),
        sample_limit=2,
    )

    table = report["tables"]["vor"]
    assert [item["logical_key"]["ident"] for item in table["candidate_only_samples"]] == [
        "ALFA", "BRAVO",
    ]
    assert table["candidate_only_samples_omitted"] == 1


def test_semantic_diff_sorts_nullable_logical_keys_deterministically(tmp_path: Path):
    candidate = _write_database(
        tmp_path / "candidate.sqlite",
        {
            "vor": [
                {"ident": "DUP", "airport_ident": "ZBAA"},
                {"ident": "DUP", "airport_ident": None},
            ],
        },
    )
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {"vor": [], "ndb": [{"ident": "REFERENCE-SEED"}]},
    )

    report = semantic_diff(
        candidate,
        reference,
        expected_candidate_bgl_count=1,
        expected_reference_bgl_count=1,
        tables=("vor",),
        sample_limit=10,
    )

    assert [item["logical_key"]["airport_ident"] for item in report["tables"]["vor"]["candidate_only_samples"]] == [
        None,
        "ZBAA",
    ]


def test_semantic_diff_reports_ambiguous_logical_keys_without_pairing_rows(tmp_path: Path):
    candidate = _write_database(
        tmp_path / "candidate.sqlite",
        {
            "waypoint": [
                {"ident": "DUP", "lonx": 100.0},
                {"ident": "DUP", "lonx": 101.0},
            ],
        },
    )
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {"waypoint": [{"ident": "DUP", "lonx": 100.5}]},
    )

    report = semantic_diff(
        candidate,
        reference,
        expected_candidate_bgl_count=1,
        expected_reference_bgl_count=1,
        tables=("waypoint",),
    )

    table = report["tables"]["waypoint"]
    assert table["ambiguous_logical_keys"] == 1
    assert table["field_delta_rows"] == 0
    assert table["ambiguous_logical_key_samples"] == [{
        "logical_key": {"ident": "DUP", "region": "ZB", "airport_ident": None},
        "candidate_rows": 2,
        "reference_rows": 1,
    }]


def test_semantic_diff_requires_the_selected_reader_table_contract(tmp_path: Path):
    candidate = tmp_path / "candidate.sqlite"
    reference = tmp_path / "reference.sqlite"
    _write_database(candidate, {"ndb": [{"ident": "CANDIDATE-SEED"}]})
    _write_database(reference, {"ndb": [{"ident": "REFERENCE-SEED"}]})
    for path in (candidate, reference):
        connection = sqlite3.connect(path)
        connection.execute('DROP TABLE "vor"')
        connection.commit()
        connection.close()

    with pytest.raises(SemanticDiffError, match="vor"):
        semantic_diff(
            candidate,
            reference,
            expected_candidate_bgl_count=1,
            expected_reference_bgl_count=1,
            tables=("vor",),
        )


def test_semantic_diff_rejects_empty_bgl_file_output(tmp_path: Path):
    candidate = _write_database(
        tmp_path / "candidate.sqlite",
        {"vor": [{"ident": "CANDIDATE"}]},
        bgl_file_rows=0,
    )
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {"vor": [{"ident": "REFERENCE"}]},
    )

    with pytest.raises(SemanticDiffError, match="bgl_file.*为空"):
        semantic_diff(
            candidate,
            reference,
            expected_candidate_bgl_count=1,
            expected_reference_bgl_count=1,
            tables=("vor",),
        )


def test_semantic_diff_rejects_reader_output_without_any_target_records(tmp_path: Path):
    candidate = _write_database(tmp_path / "candidate.sqlite", {})
    reference = _write_database(
        tmp_path / "reference.sqlite",
        {"vor": [{"ident": "REFERENCE"}]},
    )

    with pytest.raises(SemanticDiffError, match="目标设施表均为空"):
        semantic_diff(
            candidate,
            reference,
            expected_candidate_bgl_count=1,
            expected_reference_bgl_count=1,
        )


def test_cli_writes_semantic_diff_report(tmp_path: Path, capsys):
    candidate = _write_database(tmp_path / "candidate.sqlite", {"ndb": [{"ident": "A"}]})
    reference = _write_database(tmp_path / "reference.sqlite", {"ndb": [{"ident": "B"}]})
    output = tmp_path / "diagnostic.json"

    exit_code = main([
        "semantic-diff",
        "--candidate-db", str(candidate),
        "--reference-db", str(reference),
        "--candidate-bgl-count", "1",
        "--reference-bgl-count", "1",
        "--tables", "ndb",
        "--sample-limit", "1",
        "--output", str(output),
    ])

    assert exit_code == 0
    assert output.is_file()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["read_only"] is True
    assert saved["output"] == str(output.resolve())
    assert saved["reader_output"]["candidate"]["bgl_file_rows"] == 1
    assert saved["reader_output"]["candidate"]["expected_bgl_count"] == 1
    assert saved["reader_output"]["reference"]["target_rows"]["ndb"] == 1
    assert json.loads(capsys.readouterr().out)["summary"]["candidate_only_logical_keys"] == 1


def test_semantic_diff_rejects_partial_requested_bgl_scan(tmp_path: Path):
    candidate = _write_database(tmp_path / "candidate.sqlite", {"vor": [{"ident": "A"}]})
    reference = _write_database(tmp_path / "reference.sqlite", {"vor": [{"ident": "B"}]})

    with pytest.raises(SemanticDiffError, match="候选 SQLite 仅登记了 1/2 个请求的 BGL"):
        semantic_diff(
            candidate,
            reference,
            expected_candidate_bgl_count=2,
            expected_reference_bgl_count=1,
            tables=("vor",),
        )


def test_semantic_reproducibility_audit_hashes_normalized_rows_without_values(
    tmp_path: Path,
):
    first = _write_database(
        tmp_path / "first.sqlite",
        {"airway": [{"airway_name": "A1", "from_lonx": 100.0}]},
    )
    second = _write_database(
        tmp_path / "second.sqlite",
        {"airway": [{"airway_name": "A1", "from_lonx": 100.0}]},
    )
    changed = _write_database(
        tmp_path / "changed.sqlite",
        {"airway": [{"airway_name": "A1", "from_lonx": 100.5}]},
    )

    stable = semantic_reproducibility_audit(
        [first, second],
        expected_bgl_count=1,
        tables=("airway",),
    )
    assert stable["reproducible"] is True
    assert stable["tables"]["airway"] == {
        "input_rows": [1, 1],
        "distinct_semantic_fingerprints": 1,
        "reproducible": True,
    }
    assert "100.0" not in json.dumps(stable)

    unstable = semantic_reproducibility_audit(
        [first, changed],
        expected_bgl_count=1,
        tables=("airway",),
    )
    assert unstable["reproducible"] is False
    assert unstable["tables"]["airway"]["distinct_semantic_fingerprints"] == 2


def test_semantic_reproducibility_audit_requires_two_inputs(tmp_path: Path):
    database = _write_database(tmp_path / "one.sqlite", {"vor": [{"ident": "A"}]})

    with pytest.raises(ValueError, match="至少需要两个"):
        semantic_reproducibility_audit(
            [database],
            expected_bgl_count=1,
            tables=("vor",),
        )


def test_cli_writes_semantic_reproducibility_audit(tmp_path: Path, capsys):
    first = _write_database(tmp_path / "first.sqlite", {"ndb": [{"ident": "A"}]})
    second = _write_database(tmp_path / "second.sqlite", {"ndb": [{"ident": "A"}]})
    output = tmp_path / "reproducibility.json"

    exit_code = main([
        "semantic-reproducibility-audit",
        "--databases", str(first), str(second),
        "--bgl-count", "1",
        "--tables", "ndb",
        "--output", str(output),
    ])

    assert exit_code == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["reproducible"] is True
    assert saved["tables"]["ndb"]["distinct_semantic_fingerprints"] == 1
    assert json.loads(capsys.readouterr().out)["input_count"] == 2
