from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from fenix_default_navdata.airway_connection_shape_probe import (
    default_airway_connection_shape_scenarios,
    read_airway_connection_shape_rows,
    run_airway_connection_shape_probe,
    write_airway_connection_shape_probe_xml,
)
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.package_reader import PackageReaderResult


def test_default_scenarios_cover_route_child_and_connection_contrasts() -> None:
    scenarios = default_airway_connection_shape_scenarios()

    assert [scenario.identifier for scenario in scenarios] == [
        "next_and_previous",
        "next_only",
        "previous_only",
        "continuous_two_links",
        "split_two_links",
    ]
    assert [scenario.airway_name for scenario in scenarios] == [
        "BOTH",
        "NEXT",
        "PREV",
        "CONT",
        "SPLT",
    ]


def test_probe_xml_is_deterministic_and_preserves_route_child_forms(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"

    write_airway_connection_shape_probe_xml(first)
    write_airway_connection_shape_probe_xml(second)

    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    assert [
        child.tag
        for child in root.find(
            "Waypoint[@waypointRegion='ZB'][@waypointIdent='BTA']"
        ).find("Route[@name='BOTH']")
    ] == ["Next"]
    assert [
        child.tag
        for child in root.find(
            "Waypoint[@waypointRegion='ZB'][@waypointIdent='BTB']"
        ).find("Route[@name='BOTH']")
    ] == ["Previous"]
    assert root.find(
        "Waypoint[@waypointRegion='ZB'][@waypointIdent='NXB']"
    ) is None


def test_reader_rows_are_limited_to_geometry_fields(tmp_path: Path) -> None:
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
        connection.execute(
            "INSERT INTO airway VALUES "
            "('BOTH', 'B', 1, 1, 100.0, 20.2, 100.2, 20.0, "
            "100.0, 20.0, 100.2, 20.2, NULL)"
        )
        connection.commit()
    finally:
        connection.close()

    assert read_airway_connection_shape_rows(database) == [
        {
            "airway_name": "BOTH",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 1,
            "left_lonx": 100.0,
            "top_laty": 20.2,
            "right_lonx": 100.2,
            "bottom_laty": 20.0,
            "from_lonx": 100.0,
            "from_laty": 20.0,
            "to_lonx": 100.2,
            "to_laty": 20.2,
        }
    ]


def test_run_probe_uses_single_enroute_bgl_and_writes_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def compile_project(project_path: Path, *_args, **_kwargs) -> dict[str, object]:
        package = project_path.parent / "_compiled" / "airway-connection-shape-probe"
        package.mkdir(parents=True)
        return {"package_root": str(package), "bgls": [str(package / "00_enroute.bgl")]}

    def read_project(package: Path, output: Path, **kwargs) -> PackageReaderResult:
        assert package.name == "airway-connection-shape-probe"
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
                "INSERT INTO airway VALUES "
                "('BOTH', 'B', 1, 1, 100.0, 20.2, 100.2, 20.0, "
                "100.0, 20.0, 100.2, 20.2)"
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
        "fenix_default_navdata.airway_connection_shape_probe.compile_package",
        compile_project,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.airway_connection_shape_probe.read_package",
        read_project,
    )

    report = run_airway_connection_shape_probe(
        tmp_path / "probe",
        compiler=CompilerInfo(tmp_path / "fspackagetool.exe", "PackageTool", "test"),
    )

    assert report["contract"]["recorded_airway_fields"][-2:] == [
        "to_lonx",
        "to_laty",
    ]
    assert report["airway_rows"][0]["from_lonx"] == 100.0
    assert (tmp_path / "probe" / "probe-report.json").is_file()
