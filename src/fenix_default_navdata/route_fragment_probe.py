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


_PACKAGE_NAME = "route-fragment-probe"
_SCENERY_DIR = "Scenery/route-fragment-probe"
_ROUTE_TYPES = frozenset({"BOTH", "JET", "VICTOR"})
_AIRWAY_COLUMNS = (
    "airway_name",
    "airway_type",
    "airway_fragment_no",
    "sequence_no",
)


@dataclass(frozen=True)
class ProbeWaypoint:
    ident: str
    region: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ProbeLink:
    start: ProbeWaypoint
    end: ProbeWaypoint
    route_type: str


@dataclass(frozen=True)
class RouteFragmentScenario:
    identifier: str
    airway_name: str
    description: str
    links: tuple[ProbeLink, ...]


def default_route_fragment_scenarios() -> tuple[RouteFragmentScenario, ...]:
    """Return stable, synthetic inputs for the SDK route-fragment experiment."""

    continuous_a = ProbeWaypoint("CTA", "ZB", 20.0, 100.0)
    continuous_b = ProbeWaypoint("CTB", "ZB", 20.2, 100.2)
    continuous_c = ProbeWaypoint("CTC", "ZB", 20.4, 100.4)

    disconnected_a = ProbeWaypoint("DIA", "ZB", 24.0, 100.0)
    disconnected_b = ProbeWaypoint("DIB", "ZB", 24.2, 100.2)
    disconnected_c = ProbeWaypoint("DIC", "ZB", 25.0, 100.0)
    disconnected_d = ProbeWaypoint("DID", "ZB", 25.2, 100.2)

    cross_region_a = ProbeWaypoint("XRA", "ZB", 28.0, 100.0)
    cross_region_b = ProbeWaypoint("XRB", "ZG", 28.2, 100.2)
    cross_region_c = ProbeWaypoint("XRC", "ZG", 28.4, 100.4)

    switch_a = ProbeWaypoint("SWA", "ZB", 32.0, 100.0)
    switch_b = ProbeWaypoint("SWB", "ZB", 32.2, 100.2)
    switch_c = ProbeWaypoint("SWC", "ZB", 32.4, 100.4)

    return (
        RouteFragmentScenario(
            identifier="same_name_type_continuous",
            airway_name="CONT",
            description="同名同类型、端点连续的双航段航路",
            links=(
                ProbeLink(continuous_a, continuous_b, "BOTH"),
                ProbeLink(continuous_b, continuous_c, "BOTH"),
            ),
        ),
        RouteFragmentScenario(
            identifier="same_name_type_disconnected",
            airway_name="DISC",
            description="同名同类型、端点不连通的两组航段",
            links=(
                ProbeLink(disconnected_a, disconnected_b, "BOTH"),
                ProbeLink(disconnected_c, disconnected_d, "BOTH"),
            ),
        ),
        RouteFragmentScenario(
            identifier="same_name_cross_region_continuous",
            airway_name="XREG",
            description="同名同类型、跨 waypointRegion 且端点连续的双航段航路",
            links=(
                ProbeLink(cross_region_a, cross_region_b, "BOTH"),
                ProbeLink(cross_region_b, cross_region_c, "BOTH"),
            ),
        ),
        RouteFragmentScenario(
            identifier="same_name_route_type_switch_continuous",
            airway_name="SWCH",
            description="同名、端点连续、但中途切换 routeType 的双航段航路",
            links=(
                ProbeLink(switch_a, switch_b, "BOTH"),
                ProbeLink(switch_b, switch_c, "VICTOR"),
            ),
        ),
    )


def _validate_scenarios(
    scenarios: tuple[RouteFragmentScenario, ...],
) -> None:
    identifiers = [scenario.identifier for scenario in scenarios]
    names = [scenario.airway_name for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("航路片段探针场景标识必须唯一")
    if len(names) != len(set(names)):
        raise ValueError("航路片段探针航路名必须唯一")
    for scenario in scenarios:
        if not scenario.airway_name or len(scenario.airway_name) > 5:
            raise ValueError("探针航路名必须为 1 到 5 个字符")
        if not scenario.links:
            raise ValueError(f"探针场景没有航段: {scenario.identifier}")
        for link in scenario.links:
            if link.route_type not in _ROUTE_TYPES:
                raise ValueError(
                    f"探针 routeType 不支持: {scenario.identifier}: {link.route_type}"
                )
            for point in (link.start, link.end):
                if (
                    not point.ident
                    or len(point.region) != 2
                    or point.region != point.region.upper()
                ):
                    raise ValueError(
                        f"探针航点身份无效: {scenario.identifier}: {point}"
                    )


def _scenario_report(
    scenarios: tuple[RouteFragmentScenario, ...],
) -> list[dict[str, object]]:
    return [
        {
            "identifier": scenario.identifier,
            "airway_name": scenario.airway_name,
            "description": scenario.description,
            "route_types": sorted({link.route_type for link in scenario.links}),
            "link_count": len(scenario.links),
        }
        for scenario in scenarios
    ]


def write_route_fragment_probe_xml(
    output: Path,
    *,
    scenarios: tuple[RouteFragmentScenario, ...] | None = None,
) -> tuple[RouteFragmentScenario, ...]:
    """Write a deterministic SDK BGLComp XML input for fragment experiments."""

    selected = scenarios or default_route_fragment_scenarios()
    _validate_scenarios(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "default_navdata_converter_route_fragment_probe",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": DEFAULT_CYCLE.begin,
        "cycleEnd": DEFAULT_CYCLE.end,
        "cycleNumber": DEFAULT_CYCLE.number[-2:],
    })
    route_elements: dict[tuple[str, str, str], ET.Element] = {}
    waypoint_elements: dict[tuple[str, str], ET.Element] = {}
    waypoint_coordinates: dict[tuple[str, str], tuple[float, float]] = {}

    def waypoint(point: ProbeWaypoint) -> ET.Element:
        identity = (point.region, point.ident)
        coordinates = (point.latitude, point.longitude)
        previous = waypoint_coordinates.setdefault(identity, coordinates)
        if previous != coordinates:
            raise ValueError(
                "同一探针 waypointRegion/waypointIdent 不能使用不同坐标: "
                f"{identity}"
            )
        if identity not in waypoint_elements:
            waypoint_elements[identity] = ET.SubElement(root, "Waypoint", {
                "lat": str(point.latitude),
                "lon": str(point.longitude),
                "waypointType": "NAMED",
                "waypointRegion": point.region,
                "waypointIdent": point.ident,
            })
        return waypoint_elements[identity]

    def route(
        point: ProbeWaypoint,
        scenario: RouteFragmentScenario,
        route_type: str,
    ) -> ET.Element:
        key = (point.region, point.ident, f"{scenario.airway_name}:{route_type}")
        if key not in route_elements:
            route_elements[key] = ET.SubElement(
                waypoint(point),
                "Route",
                {"name": scenario.airway_name, "routeType": route_type},
            )
        return route_elements[key]

    for scenario in selected:
        for link in scenario.links:
            ET.SubElement(route(link.start, scenario, link.route_type), "Next", {
                "waypointRegion": link.end.region,
                "waypointIdent": link.end.ident,
                "waypointType": "NAMED",
                "altitudeMinimum": "0F",
            })
            ET.SubElement(route(link.end, scenario, link.route_type), "Previous", {
                "waypointRegion": link.start.region,
                "waypointIdent": link.start.ident,
                "waypointType": "NAMED",
                "altitudeMinimum": "0F",
            })

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return selected


def read_route_fragment_probe_airways(database: Path) -> list[dict[str, object]]:
    """Read only the synthetic fragment fields needed by this experiment."""

    path = database.expanduser().resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = [str(row[0]).lower() for row in connection.execute(
            "PRAGMA integrity_check"
        )]
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
            SELECT airway_name, airway_type, airway_fragment_no, sequence_no
            FROM airway
            ORDER BY airway_name, airway_type, airway_fragment_no, sequence_no
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "airway_name": str(name),
            "airway_type": str(airway_type),
            "airway_fragment_no": int(fragment),
            "sequence_no": int(sequence),
        }
        for name, airway_type, fragment, sequence in rows
    ]


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_route_fragment_probe(
    output: Path,
    *,
    compiler: CompilerInfo,
    reader: Path | None = None,
    cache_root: Path | None = None,
    build_timeout_seconds: int = 3600,
    reader_timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Compile and read the controlled fragment scenarios with real SDK tools."""

    destination = output.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"航路片段探针输出目录已存在: {destination}")
    destination.mkdir(parents=True)
    xml_path = destination / "00_enroute.xml"
    scenarios = write_route_fragment_probe_xml(xml_path)
    project_root = destination / "project"
    project_path = write_package_project(
        project_root,
        package_name=_PACKAGE_NAME,
        title="SDK Route Fragment Probe",
        output_dir=_SCENERY_DIR,
        source_xmls=(xml_path,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    compilation = compile_package(
        project_path,
        compiler,
        package_name=_PACKAGE_NAME,
        timeout_seconds=build_timeout_seconds,
    )
    package_root = Path(str(compilation["package_root"]))
    reader_result: PackageReaderResult = read_package(
        package_root,
        destination / "reader.sqlite",
        reader=reader,
        cache_root=cache_root,
        filename_patterns=("00_enroute.bgl",),
        timeout_seconds=reader_timeout_seconds,
        failure_artifacts=destination / "reader-failure",
    )
    airway_rows = read_route_fragment_probe_airways(reader_result.database)
    report = {
        "schema_version": 1,
        "probe": "sdk_route_fragment",
        "contract": {
            "package_name": _PACKAGE_NAME,
            "bgl_filename_pattern": "00_enroute.bgl",
            "object_filter": "disabled",
            "recorded_airway_fields": list(_AIRWAY_COLUMNS),
        },
        "scenarios": _scenario_report(scenarios),
        "xml": str(xml_path),
        "compilation": compilation,
        "reader": reader_result.to_report(),
        "airway_rows": airway_rows,
    }
    _write_report(destination / "probe-report.json", report)
    return report
