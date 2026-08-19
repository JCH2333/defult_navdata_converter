from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from fenix_default_navdata.airway_route_child_order_probe import (
    default_airway_route_child_order_scenarios,
    read_airway_route_child_order_rows,
    run_airway_route_child_order_probe,
    write_airway_route_child_order_probe_xml,
)
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.package_reader import PackageReaderResult


def test_probe_xml_is_deterministic_and_covers_valid_route_child_shapes(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one.xml"
    second = tmp_path / "two.xml"
    scenarios = default_airway_route_child_order_scenarios()

    write_airway_route_child_order_probe_xml(first, scenarios=scenarios)
    write_airway_route_child_order_probe_xml(second, scenarios=scenarios)

    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    orders = []
    for scenario in scenarios:
        middle = root.find(
            f"./Waypoint[@waypointIdent='{scenario.airway_name}B']/Route"
        )
        assert middle is not None
        orders.append([child.tag for child in middle])
    assert orders == [
        ["Previous", "Next"],
        ["Previous", "Previous", "Next"],
        ["Previous", "Next", "Next"],
    ]


def test_read_probe_rows(tmp_path: Path) -> None:
    database = tmp_path / "reader.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE airway ("
            "airway_name TEXT, airway_type TEXT, airway_fragment_no INTEGER, "
            "sequence_no INTEGER, left_lonx REAL, top_laty REAL, right_lonx REAL, "
            "bottom_laty REAL, from_lonx REAL, from_laty REAL, to_lonx REAL, "
            "to_laty REAL)"
        )
        connection.execute(
            "INSERT INTO airway VALUES "
            "('ORDPA', 'B', 1, 1, 100, 20, 100.2, 20, 100, 20, 100.2, 20)"
        )
        connection.commit()
    finally:
        connection.close()

    assert read_airway_route_child_order_rows(database) == [{
        "airway_name": "ORDPA",
        "airway_type": "B",
        "airway_fragment_no": 1,
        "sequence_no": 1,
        "left_lonx": 100.0,
        "top_laty": 20.0,
        "right_lonx": 100.2,
        "bottom_laty": 20.0,
        "from_lonx": 100.0,
        "from_laty": 20.0,
        "to_lonx": 100.2,
        "to_laty": 20.0,
    }]


def test_run_probe_writes_report(tmp_path: Path, monkeypatch) -> None:
    def fake_compile(project_path: Path, compiler: CompilerInfo, **kwargs: object):
        package = project_path.parent / "_compiled" / "airway-route-child-order-probe"
        package.mkdir(parents=True)
        (package / "00_enroute.bgl").write_bytes(b"BGL")
        return {"package_root": str(package)}

    def fake_read(package: Path, output: Path, **kwargs: object):
        database = output
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE airway ("
                "airway_name TEXT, airway_type TEXT, airway_fragment_no INTEGER, "
                "sequence_no INTEGER, left_lonx REAL, top_laty REAL, right_lonx REAL, "
                "bottom_laty REAL, from_lonx REAL, from_laty REAL, to_lonx REAL, "
                "to_laty REAL)"
            )
            connection.execute(
                "INSERT INTO airway VALUES "
                "('ORDPA', 'B', 1, 1, 100, 20, 100.2, 20, 100, 20, 100.2, 20)"
            )
            connection.commit()
        finally:
            connection.close()
        return PackageReaderResult(
            database=database,
            package={"path": str(package)},
            reader={"returncode": 0},
            scan={"expected_bgl_count": 1, "bgl_file_rows": 1},
        )

    monkeypatch.setattr(
        "fenix_default_navdata.airway_route_child_order_probe.compile_package",
        fake_compile,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.airway_route_child_order_probe.read_package",
        fake_read,
    )

    report = run_airway_route_child_order_probe(
        tmp_path / "probe",
        compiler=CompilerInfo(None, "test", "test"),
    )

    assert report["probe"] == "sdk_airway_route_child_order"
    assert report["status"] == "passed"
    assert report["contract"]["single_variable"] == "middle Route child order"
    assert (tmp_path / "probe" / "probe-report.json").is_file()


def test_run_probe_writes_compile_failure_report(tmp_path: Path, monkeypatch) -> None:
    def fail_compile(*args: object, **kwargs: object):
        raise RuntimeError("模拟器仍在运行")

    monkeypatch.setattr(
        "fenix_default_navdata.airway_route_child_order_probe.compile_package",
        fail_compile,
    )

    with pytest.raises(RuntimeError, match="模拟器仍在运行"):
        run_airway_route_child_order_probe(
            tmp_path / "probe",
            compiler=CompilerInfo(None, "test", "test"),
        )

    report_path = tmp_path / "probe" / "probe-report.json"
    assert report_path.is_file()
    assert '"status": "failed"' in report_path.read_text(encoding="utf-8")
    assert '"failure_stage": "compile"' in report_path.read_text(encoding="utf-8")
