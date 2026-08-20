from __future__ import annotations

import sqlite3
from pathlib import Path

from fenix_default_navdata.package_reader import PackageReaderResult
from fenix_default_navdata.reader_repeatability_audit import (
    audit_reader_repeatability,
)


def _database(path: Path, fragment: int) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE airway (airway_name TEXT, fragment INTEGER)"
        )
        connection.execute("INSERT INTO airway VALUES ('TEST', ?)", (fragment,))
        connection.commit()
    finally:
        connection.close()
    return path


def test_repeatability_audit_blocks_unstable_reader(monkeypatch, tmp_path: Path) -> None:
    calls = 0

    def fake_read_package(package, output, **kwargs):
        nonlocal calls
        calls += 1
        database = _database(output, calls)
        return PackageReaderResult(
            database=database,
            package={"matched_bgl_count": 1},
            reader={"returncode": 0},
            scan={"bgl_file_rows": 1, "target_rows": {"airway": 1}},
        )

    monkeypatch.setattr(
        "fenix_default_navdata.reader_repeatability_audit.read_package",
        fake_read_package,
    )

    report = audit_reader_repeatability(
        tmp_path / "package",
        reader=tmp_path / "reader.exe",
        output_directory=tmp_path / "runs",
        repeats=3,
        tables=("airway",),
    )

    assert report["comparison"]["scan_equal"] is True
    assert report["comparison"]["table_snapshots_equal"] is False
    assert report["comparison"]["repeatable"] is False
    assert report["decision"]["status"] == "reader_output_not_repeatable"
    assert report["decision"]["projection_evidence_allowed"] is False


def test_repeatability_audit_accepts_stable_reader(monkeypatch, tmp_path: Path) -> None:
    def fake_read_package(package, output, **kwargs):
        database = _database(output, 1)
        return PackageReaderResult(
            database=database,
            package={"matched_bgl_count": 1},
            reader={"returncode": 0},
            scan={"bgl_file_rows": 1, "target_rows": {"airway": 1}},
        )

    monkeypatch.setattr(
        "fenix_default_navdata.reader_repeatability_audit.read_package",
        fake_read_package,
    )

    report = audit_reader_repeatability(
        tmp_path / "package",
        reader=tmp_path / "reader.exe",
        output_directory=tmp_path / "runs",
        repeats=2,
        tables=("airway",),
    )

    assert report["comparison"]["table_snapshots_equal"] is True
    assert report["comparison"]["repeatable"] is True
    assert report["decision"]["status"] == "reader_repeatable"
