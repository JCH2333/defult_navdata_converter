from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.package_reader import PackageReaderResult
from fenix_default_navdata.route_fragment_probe import (
    default_route_fragment_scenarios,
    read_route_fragment_probe_airways,
    run_route_fragment_probe,
    write_route_fragment_probe_xml,
)


def test_default_scenarios_cover_the_fragment_contrasts() -> None:
    scenarios = default_route_fragment_scenarios()

    assert [scenario.identifier for scenario in scenarios] == [
        "same_name_type_continuous",
        "same_name_type_disconnected",
        "same_name_cross_region_continuous",
        "same_name_route_type_switch_continuous",
    ]
    assert [scenario.airway_name for scenario in scenarios] == [
        "CONT",
        "DISC",
        "XREG",
        "SWCH",
    ]


def test_probe_xml_is_deterministic_and_preserves_the_type_switch(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"

    write_route_fragment_probe_xml(first)
    write_route_fragment_probe_xml(second)

    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    continuous_middle = root.find(
        "Waypoint[@waypointRegion='ZB'][@waypointIdent='CTB']"
    )
    assert continuous_middle is not None
    continuous_route = continuous_middle.find("Route[@name='CONT']")
    assert continuous_route is not None
    assert [child.tag for child in continuous_route] == ["Previous", "Next"]

    switch_middle = root.find(
        "Waypoint[@waypointRegion='ZB'][@waypointIdent='SWB']"
    )
    assert switch_middle is not None
    assert [
        (route.attrib["name"], route.attrib["routeType"])
        for route in switch_middle.findall("Route")
    ] == [("SWCH", "BOTH"), ("SWCH", "VICTOR")]


def test_reader_rows_are_limited_to_fragment_fields(tmp_path: Path) -> None:
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
                from_lonx REAL,
                to_lonx REAL
            )
            """
        )
        connection.executemany(
            "INSERT INTO airway VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("XREG", "B", 1, 2, 100.2, 100.4),
                ("CONT", "B", 1, 1, 100.0, 100.2),
                ("CONT", "B", 1, 2, 100.2, 100.4),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    assert read_route_fragment_probe_airways(database) == [
        {
            "airway_name": "CONT",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 1,
        },
        {
            "airway_name": "CONT",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 2,
        },
        {
            "airway_name": "XREG",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 2,
        },
    ]


def test_run_probe_uses_single_enroute_bgl_and_writes_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def compile_project(project_path: Path, *_args, **_kwargs) -> dict[str, object]:
        package = project_path.parent / "_compiled" / "route-fragment-probe"
        package.mkdir(parents=True)
        return {"package_root": str(package), "bgls": [str(package / "00_enroute.bgl")]}

    def read_project(package: Path, output: Path, **kwargs) -> PackageReaderResult:
        assert package.name == "route-fragment-probe"
        assert kwargs["filename_patterns"] == ("00_enroute.bgl",)
        assert kwargs.get("object_filter") is None
        connection = sqlite3.connect(output)
        try:
            connection.execute(
                """
                CREATE TABLE airway (
                    airway_name TEXT NOT NULL,
                    airway_type TEXT NOT NULL,
                    airway_fragment_no INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO airway VALUES ('CONT', 'B', 1, 1)"
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
        "fenix_default_navdata.route_fragment_probe.compile_package",
        compile_project,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.route_fragment_probe.read_package",
        read_project,
    )

    report = run_route_fragment_probe(
        tmp_path / "probe",
        compiler=CompilerInfo(tmp_path / "fspackagetool.exe", "PackageTool", "test"),
    )

    assert report["contract"]["bgl_filename_pattern"] == "00_enroute.bgl"
    assert report["contract"]["object_filter"] == "disabled"
    assert report["airway_rows"] == [
        {
            "airway_name": "CONT",
            "airway_type": "B",
            "airway_fragment_no": 1,
            "sequence_no": 1,
        }
    ]
    assert (tmp_path / "probe" / "probe-report.json").is_file()
