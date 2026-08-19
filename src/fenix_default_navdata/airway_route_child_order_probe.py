from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .bgl import CompilerInfo, compile_package, write_package_project
from .package_reader import (
    DEFAULT_READER_TIMEOUT_SECONDS,
    PackageReaderResult,
    read_package,
)
from .profile import DEFAULT_CYCLE


_PACKAGE_NAME = "airway-route-child-order-probe"
_SCENERY_DIR = "Scenery/airway-route-child-order-probe"
_AIRWAY_COLUMNS = (
    "airway_name",
    "airway_type",
    "airway_fragment_no",
    "sequence_no",
    "left_lonx",
    "top_laty",
    "right_lonx",
    "bottom_laty",
    "from_lonx",
    "from_laty",
    "to_lonx",
    "to_laty",
)


@dataclass(frozen=True)
class RouteChildOrderScenario:
    identifier: str
    airway_name: str
    middle_child_order: tuple[str, ...]


def default_airway_route_child_order_scenarios() -> tuple[RouteChildOrderScenario, ...]:
    """Return XSD-valid linear, converging, and branching Route scenarios."""

    return (
        RouteChildOrderScenario(
            "previous_then_next",
            "ORDPA",
            ("Previous", "Next"),
        ),
        RouteChildOrderScenario(
            "two_previous_then_next",
            "ORDPB",
            ("Previous", "Previous", "Next"),
        ),
        RouteChildOrderScenario(
            "previous_then_two_next",
            "ORDPC",
            ("Previous", "Next", "Next"),
        ),
    )


def _validate_scenarios(
    scenarios: tuple[RouteChildOrderScenario, ...],
) -> None:
    identifiers = [item.identifier for item in scenarios]
    names = [item.airway_name for item in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("航路子节点顺序探针场景标识必须唯一")
    if len(names) != len(set(names)):
        raise ValueError("航路子节点顺序探针航路名必须唯一")
    for scenario in scenarios:
        if not scenario.airway_name or len(scenario.airway_name) > 5:
            raise ValueError("航路子节点顺序探针航路名必须为 1 到 5 个字符")
        seen_next = False
        previous_count = 0
        next_count = 0
        for direction in scenario.middle_child_order:
            if direction == "Next":
                seen_next = True
                next_count += 1
            elif direction == "Previous":
                if seen_next:
                    raise ValueError(
                        "中间 Route 子节点必须遵守 Previous* 后 Next* 的 XSD 顺序"
                    )
                previous_count += 1
            else:
                raise ValueError("中间 Route 子节点只能是 Previous 或 Next")
        if previous_count < 1 or next_count < 1:
            raise ValueError("中间 Route 子节点必须至少包含一个 Previous 和一个 Next")


def _route_child(
    route: ET.Element,
    direction: str,
    *,
    region: str,
    ident: str,
) -> None:
    ET.SubElement(route, direction, {
        "waypointRegion": region,
        "waypointIdent": ident,
        "waypointType": "NAMED",
        "altitudeMinimum": "0F",
    })


def write_airway_route_child_order_probe_xml(
    output: Path,
    *,
    scenarios: tuple[RouteChildOrderScenario, ...] | None = None,
) -> tuple[RouteChildOrderScenario, ...]:
    """Write deterministic XML with a single controlled Route-child variable."""

    selected = scenarios or default_airway_route_child_order_scenarios()
    _validate_scenarios(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "default_navdata_converter_airway_route_child_order_probe",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": DEFAULT_CYCLE.begin,
        "cycleEnd": DEFAULT_CYCLE.end,
        "cycleNumber": DEFAULT_CYCLE.number[-2:],
    })
    for index, scenario in enumerate(selected):
        latitude = 20.0 + index * 5
        middle_ident = f"{scenario.airway_name}B"
        previous_idents = [
            f"{scenario.airway_name}P{position}"
            for position, direction in enumerate(scenario.middle_child_order, start=1)
            if direction == "Previous"
        ]
        next_idents = [
            f"{scenario.airway_name}N{position}"
            for position, direction in enumerate(scenario.middle_child_order, start=1)
            if direction == "Next"
        ]
        waypoints: dict[str, ET.Element] = {}
        point_idents = (*previous_idents, middle_ident, *next_idents)
        for position, ident in enumerate(point_idents):
            waypoints[ident] = ET.SubElement(root, "Waypoint", {
                "lat": f"{latitude:.12f}".rstrip("0").rstrip("."),
                "lon": f"{100.0 + position * 0.2:.12f}".rstrip("0").rstrip("."),
                "waypointType": "NAMED",
                "waypointRegion": "ZB",
                "waypointIdent": ident,
            })
        for ident in previous_idents:
            previous_route = ET.SubElement(waypoints[ident], "Route", {
                "name": scenario.airway_name,
                "routeType": "BOTH",
            })
            _route_child(previous_route, "Next", region="ZB", ident=middle_ident)
        middle_route = ET.SubElement(waypoints[middle_ident], "Route", {
            "name": scenario.airway_name,
            "routeType": "BOTH",
        })
        previous_iter = iter(previous_idents)
        next_iter = iter(next_idents)
        for direction in scenario.middle_child_order:
            _route_child(
                middle_route,
                direction,
                region="ZB",
                ident=(
                    next(previous_iter)
                    if direction == "Previous"
                    else next(next_iter)
                ),
            )
        for ident in next_idents:
            next_route = ET.SubElement(waypoints[ident], "Route", {
                "name": scenario.airway_name,
                "routeType": "BOTH",
            })
            _route_child(next_route, "Previous", region="ZB", ident=middle_ident)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return selected


def read_airway_route_child_order_rows(database: Path) -> list[dict[str, object]]:
    """Read only the fragment and geometry fields affected by this probe."""

    path = database.expanduser().resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = [
            str(row[0]).lower()
            for row in connection.execute("PRAGMA integrity_check")
        ]
        if integrity != ["ok"]:
            raise RuntimeError(f"探针读取器 SQLite 完整性检查失败: {path}")
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(airway)")
        }
        missing = set(_AIRWAY_COLUMNS) - columns
        if missing:
            raise RuntimeError(
                f"探针读取器 SQLite 缺少航路列: {', '.join(sorted(missing))}"
            )
        rows = connection.execute(
            """
            SELECT airway_name, airway_type, airway_fragment_no, sequence_no,
                   left_lonx, top_laty, right_lonx, bottom_laty,
                   from_lonx, from_laty, to_lonx, to_laty
            FROM airway
            ORDER BY airway_name, airway_type, airway_fragment_no, sequence_no
            """
        ).fetchall()
    finally:
        connection.close()
    result = []
    for row in rows:
        values = dict(zip(_AIRWAY_COLUMNS, row, strict=True))
        for field in ("airway_fragment_no", "sequence_no"):
            values[field] = int(values[field])
        for field in _AIRWAY_COLUMNS[4:]:
            values[field] = float(values[field]) if values[field] is not None else None
        values["airway_name"] = str(values["airway_name"])
        values["airway_type"] = str(values["airway_type"])
        result.append(values)
    return result


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_airway_route_child_order_probe(
    output: Path,
    *,
    compiler: CompilerInfo,
    reader: Path | None = None,
    cache_root: Path | None = None,
    build_timeout_seconds: int = 3600,
    reader_timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Compile and read the controlled Route-child order scenarios."""

    destination = output.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"航路子节点顺序探针输出目录已存在: {destination}")
    destination.mkdir(parents=True)
    xml_path = destination / "00_enroute.xml"
    scenarios = write_airway_route_child_order_probe_xml(xml_path)
    project_path = write_package_project(
        destination / "project",
        package_name=_PACKAGE_NAME,
        title="SDK Airway Route Child Order Probe",
        output_dir=_SCENERY_DIR,
        source_xmls=(xml_path,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    report: dict[str, object] = {
        "schema_version": 1,
        "probe": "sdk_airway_route_child_order",
        "status": "running",
        "contract": {
            "package_name": _PACKAGE_NAME,
            "bgl_filename_pattern": "00_enroute.bgl",
            "single_variable": "middle Route child order",
            "recorded_airway_fields": list(_AIRWAY_COLUMNS),
        },
        "scenarios": [
            {
                "identifier": item.identifier,
                "airway_name": item.airway_name,
                "middle_child_order": list(item.middle_child_order),
            }
            for item in scenarios
        ],
        "xml": str(xml_path),
        "project": str(project_path),
    }
    try:
        compilation = compile_package(
            project_path,
            compiler,
            package_name=_PACKAGE_NAME,
            timeout_seconds=build_timeout_seconds,
        )
    except Exception as error:
        report.update({
            "status": "failed",
            "failure_stage": "compile",
            "error": str(error),
        })
        _write_report(destination / "probe-report.json", report)
        raise
    report["compilation"] = compilation
    package_root = Path(str(compilation["package_root"]))
    try:
        reader_result: PackageReaderResult = read_package(
            package_root,
            destination / "reader.sqlite",
            reader=reader,
            cache_root=cache_root,
            filename_patterns=("00_enroute.bgl",),
            timeout_seconds=reader_timeout_seconds,
            failure_artifacts=destination / "reader-failure",
        )
        report["reader"] = reader_result.to_report()
        report["airway_rows"] = read_airway_route_child_order_rows(
            reader_result.database
        )
    except Exception as error:
        report.update({
            "status": "failed",
            "failure_stage": "reader",
            "error": str(error),
        })
        _write_report(destination / "probe-report.json", report)
        raise
    report["status"] = "passed"
    _write_report(destination / "probe-report.json", report)
    return report
