from __future__ import annotations

import sqlite3
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from fenix_default_navdata.airway_coordinate_precision_probe import (
    audit_source_airway_coordinate_precision,
    default_airway_coordinate_precision_scenarios,
    read_airway_coordinate_precision_rows,
    run_airway_coordinate_precision_probe,
    write_airway_coordinate_precision_probe_xml,
)
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.package_reader import PackageReaderResult


def test_default_scenarios_cover_coordinate_precision_levels() -> None:
    scenarios = default_airway_coordinate_precision_scenarios()

    assert [scenario.decimal_places for scenario in scenarios] == [6, 9, 12]
    assert [scenario.airway_name for scenario in scenarios] == ["P06", "P09", "P12"]


def test_probe_xml_is_deterministic_and_preserves_coordinate_text(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"

    write_airway_coordinate_precision_probe_xml(first)
    write_airway_coordinate_precision_probe_xml(second)

    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    waypoint = root.find(
        "Waypoint[@waypointRegion='ZB'][@waypointIdent='P12A']"
    )
    assert waypoint is not None
    assert waypoint.attrib["lat"] == "20.123456789123"
    assert waypoint.attrib["lon"] == "100.654321987321"


def test_source_audit_detects_legacy_six_decimal_float32_loss(
    tmp_path: Path,
) -> None:
    (tmp_path / "RTE_SEG.csv").write_text(
        "\n".join((
            "GEO_LONG_START_ACCURACY,GEO_LAT_START_ACCURACY,"
            "GEO_LONG_END_ACCURACY,GEO_LAT_END_ACCURACY",
            "E1171655,N404250,E1161936,N400839",
        )),
        encoding="utf-8",
    )

    report = audit_source_airway_coordinate_precision(tmp_path)

    assert report["rows"] == {
        "complete": 1,
        "changed_by_legacy_format": 1,
    }
    assert report["coordinates"]["total"] == 4
    assert report["coordinates"]["changed_by_legacy_format"] > 0


def test_twelve_decimal_coordinate_text_preserves_dms_float32_value() -> None:
    source = 40 + 8 / 60 + 39 / 3600
    text = f"{source:.12f}".rstrip("0").rstrip(".")
    exact = struct.unpack("<f", struct.pack("<f", source))[0]
    projected = struct.unpack("<f", struct.pack("<f", float(text)))[0]

    assert projected == exact


def test_reader_rows_are_limited_to_coordinate_fields(tmp_path: Path) -> None:
    database = tmp_path / "reader.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE airway (
                airway_name TEXT NOT NULL,
                airway_type TEXT NOT NULL,
                airway_fragment_no INTEGER NOT NULL,
                sequence_no INTEGER NOT NULL,
                left_lonx REAL,
                top_laty REAL,
                right_lonx REAL,
                bottom_laty REAL,
                from_lonx REAL,
                from_laty REAL,
                to_lonx REAL,
                to_laty REAL,
                route_type TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO airway VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "P12", "B", 1, 1, 108.6, 28.3, 108.8, 28.1,
                    108.654321987, 28.123456789, 108.765432198, 28.234567891,
                    None,
                ),
                (
                    "P06", "B", 1, 1, 100.6, 20.3, 100.8, 20.1,
                    100.654321, 20.123456, 100.765432, 20.234567,
                    None,
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    assert read_airway_coordinate_precision_rows(database) == [
        {
            "airway_name": "P06",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 1,
            "left_lonx": 100.6,
            "top_laty": 20.3,
            "right_lonx": 100.8,
            "bottom_laty": 20.1,
            "from_lonx": 100.654321,
            "from_laty": 20.123456,
            "to_lonx": 100.765432,
            "to_laty": 20.234567,
        },
        {
            "airway_name": "P12",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 1,
            "left_lonx": 108.6,
            "top_laty": 28.3,
            "right_lonx": 108.8,
            "bottom_laty": 28.1,
            "from_lonx": 108.654321987,
            "from_laty": 28.123456789,
            "to_lonx": 108.765432198,
            "to_laty": 28.234567891,
        },
    ]


def test_run_probe_writes_full_coordinate_report(tmp_path: Path, monkeypatch) -> None:
    def compile_project(project_path: Path, *_args, **_kwargs) -> dict[str, object]:
        package = project_path.parent / "_compiled" / "airway-coordinate-precision-probe"
        package.mkdir(parents=True)
        return {"package_root": str(package), "bgls": [str(package / "00_enroute.bgl")]}

    def read_project(package: Path, output: Path, **kwargs) -> PackageReaderResult:
        assert package.name == "airway-coordinate-precision-probe"
        assert kwargs["filename_patterns"] == ("00_enroute.bgl",)
        connection = sqlite3.connect(output)
        try:
            connection.execute(
                """
                CREATE TABLE airway (
                    airway_name TEXT NOT NULL,
                    airway_type TEXT NOT NULL,
                    airway_fragment_no INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    left_lonx REAL,
                    top_laty REAL,
                    right_lonx REAL,
                    bottom_laty REAL,
                    from_lonx REAL,
                    from_laty REAL,
                    to_lonx REAL,
                    to_laty REAL
                )
                """
            )
            connection.execute(
                "INSERT INTO airway VALUES ('P06', 'B', 1, 1, 100.6, 20.3, "
                "100.8, 20.1, 100.654321, 20.123456, 100.765432, 20.234567)"
            )
            connection.commit()
        finally:
            connection.close()
        return PackageReaderResult(
            database=output.resolve(),
            package={"matched_bgl_count": 1},
            reader={"returncode": 0},
            scan={"bgl_file_rows": 1},
        )

    monkeypatch.setattr(
        "fenix_default_navdata.airway_coordinate_precision_probe.compile_package",
        compile_project,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.airway_coordinate_precision_probe.read_package",
        read_project,
    )

    report = run_airway_coordinate_precision_probe(
        tmp_path / "probe",
        compiler=CompilerInfo(tmp_path / "fspackagetool.exe", "PackageTool", "test"),
    )

    assert report["contract"]["input_coordinate_precisions"] == [6, 9, 12]
    assert report["airway_rows"][0]["from_lonx"] == 100.654321
    assert (tmp_path / "probe" / "probe-report.json").is_file()
