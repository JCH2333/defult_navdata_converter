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


_PACKAGE_NAME = "airway-connection-shape-probe"
_SCENERY_DIR = "Scenery/airway-connection-shape-probe"
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
class ConnectionWaypoint:
    ident: str
    region: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ConnectionLink:
    start: ConnectionWaypoint
    end: ConnectionWaypoint
    start_direction: str | None
    end_direction: str | None


@dataclass(frozen=True)
class AirwayConnectionShapeScenario:
    identifier: str
    airway_name: str
    description: str
    links: tuple[ConnectionLink, ...]


def default_airway_connection_shape_scenarios(
) -> tuple[AirwayConnectionShapeScenario, ...]:
    """Return stable, isolated Route child combinations for SDK experiments."""

    both_a = ConnectionWaypoint("BTA", "ZB", 20.0, 100.0)
    both_b = ConnectionWaypoint("BTB", "ZB", 20.2, 100.2)
    next_a = ConnectionWaypoint("NXA", "ZB", 24.0, 100.0)
    next_b = ConnectionWaypoint("NXB", "ZB", 24.2, 100.2)
    previous_a = ConnectionWaypoint("PVA", "ZB", 28.0, 100.0)
    previous_b = ConnectionWaypoint("PVB", "ZB", 28.2, 100.2)
    continuous_a = ConnectionWaypoint("CNA", "ZB", 32.0, 100.0)
    continuous_b = ConnectionWaypoint("CNB", "ZB", 32.2, 100.2)
    continuous_c = ConnectionWaypoint("CNC", "ZB", 32.4, 100.4)
    split_a = ConnectionWaypoint("SPA", "ZB", 36.0, 100.0)
    split_b = ConnectionWaypoint("SPB", "ZB", 36.2, 100.2)
    split_c = ConnectionWaypoint("SPC", "ZB", 37.0, 100.0)
    split_d = ConnectionWaypoint("SPD", "ZB", 37.2, 100.2)

    return (
        AirwayConnectionShapeScenario(
            identifier="next_and_previous",
            airway_name="BOTH",
            description="same link declared by Next and Previous",
            links=(ConnectionLink(both_a, both_b, "Next", "Previous"),),
        ),
        AirwayConnectionShapeScenario(
            identifier="next_only",
            airway_name="NEXT",
            description="same link declared only by Next",
            links=(ConnectionLink(next_a, next_b, "Next", None),),
        ),
        AirwayConnectionShapeScenario(
            identifier="previous_only",
            airway_name="PREV",
            description="same link declared only by Previous",
            links=(ConnectionLink(previous_a, previous_b, None, "Previous"),),
        ),
        AirwayConnectionShapeScenario(
            identifier="continuous_two_links",
            airway_name="CONT",
            description="two connected links with a shared middle waypoint",
            links=(
                ConnectionLink(continuous_a, continuous_b, "Next", "Previous"),
                ConnectionLink(continuous_b, continuous_c, "Next", "Previous"),
            ),
        ),
        AirwayConnectionShapeScenario(
            identifier="split_two_links",
            airway_name="SPLT",
            description="two disconnected links sharing an airway name",
            links=(
                ConnectionLink(split_a, split_b, "Next", "Previous"),
                ConnectionLink(split_c, split_d, "Next", "Previous"),
            ),
        ),
    )


def _validate_scenarios(
    scenarios: tuple[AirwayConnectionShapeScenario, ...],
) -> None:
    identifiers = [scenario.identifier for scenario in scenarios]
    airway_names = [scenario.airway_name for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("connection shape scenario identifiers must be unique")
    if len(airway_names) != len(set(airway_names)):
        raise ValueError("connection shape airway names must be unique")
    for scenario in scenarios:
        if not scenario.airway_name or len(scenario.airway_name) > 5:
            raise ValueError("connection shape airway name must be 1 to 5 characters")
        if not scenario.links:
            raise ValueError(f"connection shape scenario has no links: {scenario.identifier}")
        for link in scenario.links:
            if link.start_direction not in {None, "Next"}:
                raise ValueError(f"unsupported start direction: {link.start_direction}")
            if link.end_direction not in {None, "Previous"}:
                raise ValueError(f"unsupported end direction: {link.end_direction}")
            if link.start_direction is None and link.end_direction is None:
                raise ValueError(f"connection shape link has no Route child: {scenario.identifier}")
            for point in (link.start, link.end):
                if (
                    not point.ident
                    or len(point.region) != 2
                    or point.region != point.region.upper()
                ):
                    raise ValueError(
                        f"connection shape waypoint identity is invalid: {scenario.identifier}: {point}"
                    )


def _scenario_report(
    scenarios: tuple[AirwayConnectionShapeScenario, ...],
) -> list[dict[str, object]]:
    return [
        {
            "identifier": scenario.identifier,
            "airway_name": scenario.airway_name,
            "description": scenario.description,
            "link_count": len(scenario.links),
            "connection_forms": sorted({
                "+".join(
                    direction
                    for direction in (link.start_direction, link.end_direction)
                    if direction
                )
                for link in scenario.links
            }),
        }
        for scenario in scenarios
    ]


def write_airway_connection_shape_probe_xml(
    output: Path,
    *,
    scenarios: tuple[AirwayConnectionShapeScenario, ...] | None = None,
) -> tuple[AirwayConnectionShapeScenario, ...]:
    """Write deterministic BGLComp XML without using converter output."""

    selected = scenarios or default_airway_connection_shape_scenarios()
    _validate_scenarios(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "default_navdata_converter_airway_connection_shape_probe",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": DEFAULT_CYCLE.begin,
        "cycleEnd": DEFAULT_CYCLE.end,
        "cycleNumber": DEFAULT_CYCLE.number[-2:],
    })
    waypoint_elements: dict[tuple[str, str], ET.Element] = {}
    waypoint_coordinates: dict[tuple[str, str], tuple[float, float]] = {}
    route_elements: dict[tuple[str, str, str], ET.Element] = {}

    def route(point: ConnectionWaypoint, airway_name: str) -> ET.Element:
        identity = (point.region, point.ident)
        coordinates = (point.latitude, point.longitude)
        previous = waypoint_coordinates.setdefault(identity, coordinates)
        if previous != coordinates:
            raise ValueError(
                "same waypointRegion/waypointIdent cannot have different coordinates: "
                f"{identity}"
            )
        waypoint = waypoint_elements.get(identity)
        if waypoint is None:
            waypoint = ET.SubElement(root, "Waypoint", {
                "lat": f"{point.latitude:.12f}".rstrip("0").rstrip("."),
                "lon": f"{point.longitude:.12f}".rstrip("0").rstrip("."),
                "waypointType": "NAMED",
                "waypointRegion": point.region,
                "waypointIdent": point.ident,
            })
            waypoint_elements[identity] = waypoint
        key = (*identity, airway_name)
        return route_elements.setdefault(key, ET.SubElement(waypoint, "Route", {
            "name": airway_name,
            "routeType": "BOTH",
        }))

    for scenario in selected:
        for link in scenario.links:
            if link.start_direction:
                ET.SubElement(route(link.start, scenario.airway_name), "Next", {
                    "waypointRegion": link.end.region,
                    "waypointIdent": link.end.ident,
                    "waypointType": "NAMED",
                    "altitudeMinimum": "0F",
                })
            if link.end_direction:
                ET.SubElement(route(link.end, scenario.airway_name), "Previous", {
                    "waypointRegion": link.start.region,
                    "waypointIdent": link.start.ident,
                    "waypointType": "NAMED",
                    "altitudeMinimum": "0F",
                })

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return selected


def read_airway_connection_shape_rows(database: Path) -> list[dict[str, object]]:
    """Read only the SDK-derived geometry and fragment fields under test."""

    path = database.expanduser().resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = [str(row[0]).lower() for row in connection.execute(
            "PRAGMA integrity_check"
        )]
        if integrity != ["ok"]:
            raise RuntimeError(f"connection shape reader integrity check failed: {path}")
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(airway)")
        }
        missing = set(_AIRWAY_COLUMNS) - columns
        if missing:
            raise RuntimeError(
                "connection shape reader missing airway columns: "
                f"{', '.join(sorted(missing))}"
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

    result: list[dict[str, object]] = []
    for row in rows:
        values = dict(zip(_AIRWAY_COLUMNS, row, strict=True))
        for field in ("airway_fragment_no", "sequence_no"):
            values[field] = int(values[field])
        for field in _AIRWAY_COLUMNS[4:]:
            values[field] = (
                float(values[field]) if values[field] is not None else None
            )
        values["airway_name"] = str(values["airway_name"])
        values["airway_type"] = str(values["airway_type"])
        result.append(values)
    return result


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_airway_connection_shape_probe(
    output: Path,
    *,
    compiler: CompilerInfo,
    reader: Path | None = None,
    cache_root: Path | None = None,
    build_timeout_seconds: int = 3600,
    reader_timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Compile and read the controlled Route connection-shape scenarios."""

    destination = output.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(
            f"airway connection shape probe output already exists: {destination}"
        )
    destination.mkdir(parents=True)
    xml_path = destination / "00_enroute.xml"
    scenarios = write_airway_connection_shape_probe_xml(xml_path)
    project_root = destination / "project"
    project_path = write_package_project(
        project_root,
        package_name=_PACKAGE_NAME,
        title="SDK Airway Connection Shape Probe",
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
    report = {
        "schema_version": 1,
        "probe": "sdk_airway_connection_shape",
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
        "airway_rows": read_airway_connection_shape_rows(reader_result.database),
    }
    _write_report(destination / "probe-report.json", report)
    return report
