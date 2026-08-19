from __future__ import annotations

import csv
import json
import re
import sqlite3
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .bgl import CompilerInfo, compile_package, write_package_project
from .package_reader import (
    DEFAULT_READER_TIMEOUT_SECONDS,
    PackageReaderResult,
    read_package,
)
from .profile import DEFAULT_CYCLE
from .source import parse_dms


_PACKAGE_NAME = "airway-coordinate-precision-probe"
_SCENERY_DIR = "Scenery/airway-coordinate-precision-probe"
_COORDINATE_PATTERN = re.compile(r"^-?\d+\.\d+$")
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
class PrecisionWaypoint:
    ident: str
    region: str
    latitude: str
    longitude: str


@dataclass(frozen=True)
class AirwayCoordinatePrecisionScenario:
    identifier: str
    airway_name: str
    decimal_places: int
    start: PrecisionWaypoint
    end: PrecisionWaypoint


def default_airway_coordinate_precision_scenarios(
) -> tuple[AirwayCoordinatePrecisionScenario, ...]:
    """Return controlled route endpoints that differ only in coordinate precision."""

    return (
        AirwayCoordinatePrecisionScenario(
            identifier="six_decimal_places",
            airway_name="P06",
            decimal_places=6,
            start=PrecisionWaypoint("P06A", "ZB", "20.123457", "100.654322"),
            end=PrecisionWaypoint("P06B", "ZB", "20.234568", "100.765432"),
        ),
        AirwayCoordinatePrecisionScenario(
            identifier="nine_decimal_places",
            airway_name="P09",
            decimal_places=9,
            start=PrecisionWaypoint(
                "P09A", "ZB", "20.123456789", "100.654321987"
            ),
            end=PrecisionWaypoint(
                "P09B", "ZB", "20.234567891", "100.765432198"
            ),
        ),
        AirwayCoordinatePrecisionScenario(
            identifier="twelve_decimal_places",
            airway_name="P12",
            decimal_places=12,
            start=PrecisionWaypoint(
                "P12A", "ZB", "20.123456789123", "100.654321987321"
            ),
            end=PrecisionWaypoint(
                "P12B", "ZB", "20.234567891234", "100.765432198432"
            ),
        ),
    )


def _decimal_places(value: str) -> int:
    if not _COORDINATE_PATTERN.fullmatch(value):
        raise ValueError(f"探针坐标必须是带小数点的十进制字符串: {value}")
    try:
        Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"探针坐标不是有效十进制数: {value}") from error
    return len(value.partition(".")[2])


def _validate_scenarios(
    scenarios: tuple[AirwayCoordinatePrecisionScenario, ...],
) -> None:
    identifiers = [scenario.identifier for scenario in scenarios]
    airway_names = [scenario.airway_name for scenario in scenarios]
    precisions = [scenario.decimal_places for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("航路坐标精度探针场景标识必须唯一")
    if len(airway_names) != len(set(airway_names)):
        raise ValueError("航路坐标精度探针航路名必须唯一")
    if len(precisions) != len(set(precisions)):
        raise ValueError("航路坐标精度探针小数位数必须唯一")
    for scenario in scenarios:
        if not scenario.airway_name or len(scenario.airway_name) > 5:
            raise ValueError("探针航路名必须为 1 到 5 个字符")
        for point in (scenario.start, scenario.end):
            if (
                not point.ident
                or len(point.region) != 2
                or point.region != point.region.upper()
            ):
                raise ValueError(f"探针航点身份无效: {scenario.identifier}: {point}")
            if (
                _decimal_places(point.latitude) != scenario.decimal_places
                or _decimal_places(point.longitude) != scenario.decimal_places
            ):
                raise ValueError(
                    "探针坐标小数位数与场景不一致: "
                    f"{scenario.identifier}: {point}"
                )


def _scenario_report(
    scenarios: tuple[AirwayCoordinatePrecisionScenario, ...],
) -> list[dict[str, object]]:
    return [
        {
            "identifier": scenario.identifier,
            "airway_name": scenario.airway_name,
            "decimal_places": scenario.decimal_places,
            "start": {
                "ident": scenario.start.ident,
                "region": scenario.start.region,
                "latitude": scenario.start.latitude,
                "longitude": scenario.start.longitude,
            },
            "end": {
                "ident": scenario.end.ident,
                "region": scenario.end.region,
                "latitude": scenario.end.latitude,
                "longitude": scenario.end.longitude,
            },
        }
        for scenario in scenarios
    ]


def write_airway_coordinate_precision_probe_xml(
    output: Path,
    *,
    scenarios: tuple[AirwayCoordinatePrecisionScenario, ...] | None = None,
) -> tuple[AirwayCoordinatePrecisionScenario, ...]:
    """Write deterministic SDK XML without normalizing coordinate text."""

    selected = scenarios or default_airway_coordinate_precision_scenarios()
    _validate_scenarios(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "default_navdata_converter_airway_coordinate_precision_probe",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": DEFAULT_CYCLE.begin,
        "cycleEnd": DEFAULT_CYCLE.end,
        "cycleNumber": DEFAULT_CYCLE.number[-2:],
    })

    for scenario in selected:
        start = ET.SubElement(root, "Waypoint", {
            "lat": scenario.start.latitude,
            "lon": scenario.start.longitude,
            "waypointType": "NAMED",
            "waypointRegion": scenario.start.region,
            "waypointIdent": scenario.start.ident,
        })
        end = ET.SubElement(root, "Waypoint", {
            "lat": scenario.end.latitude,
            "lon": scenario.end.longitude,
            "waypointType": "NAMED",
            "waypointRegion": scenario.end.region,
            "waypointIdent": scenario.end.ident,
        })
        start_route = ET.SubElement(start, "Route", {
            "name": scenario.airway_name,
            "routeType": "BOTH",
        })
        ET.SubElement(start_route, "Next", {
            "waypointRegion": scenario.end.region,
            "waypointIdent": scenario.end.ident,
            "waypointType": "NAMED",
            "altitudeMinimum": "0F",
        })
        end_route = ET.SubElement(end, "Route", {
            "name": scenario.airway_name,
            "routeType": "BOTH",
        })
        ET.SubElement(end_route, "Previous", {
            "waypointRegion": scenario.start.region,
            "waypointIdent": scenario.start.ident,
            "waypointType": "NAMED",
            "altitudeMinimum": "0F",
        })

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return selected


def read_airway_coordinate_precision_rows(database: Path) -> list[dict[str, object]]:
    """Read only endpoint and bounding-box fields from synthetic airway rows."""

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


def _float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _legacy_six_decimal_coordinate(value: float) -> float:
    return float(f"{value:.6f}".rstrip("0").rstrip("."))


def _source_rows(path: Path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - both supported encodings failed
        raise UnicodeDecodeError("naip", raw, 0, len(raw), "unsupported CSV encoding")
    yield from csv.DictReader(text.splitlines())


def audit_source_airway_coordinate_precision(raw_root: Path) -> dict[str, object]:
    """Measure whether six-decimal XML text changes source DMS float32 values."""

    source = raw_root.expanduser().resolve() / "RTE_SEG.csv"
    if not source.is_file():
        raise FileNotFoundError(f"未找到航路源表: {source}")
    fields = (
        "GEO_LONG_START_ACCURACY",
        "GEO_LAT_START_ACCURACY",
        "GEO_LONG_END_ACCURACY",
        "GEO_LAT_END_ACCURACY",
    )
    changed_by_field = {field: 0 for field in fields}
    complete_rows = 0
    changed_rows = 0
    total_coordinates = 0
    for row in _source_rows(source):
        values = [parse_dms(row.get(field) or "") for field in fields]
        complete_rows += 1
        row_changed = False
        for field, value in zip(fields, values, strict=True):
            total_coordinates += 1
            if _float32(value) != _float32(_legacy_six_decimal_coordinate(value)):
                changed_by_field[field] += 1
                row_changed = True
        changed_rows += int(row_changed)
    return {
        "schema_version": 1,
        "audit": "source_airway_coordinate_precision",
        "source": {
            "file": "RTE_SEG.csv",
            "coordinate_encoding": "NAIP DMS",
        },
        "adapter_coordinate_text": {
            "legacy_decimal_places": 6,
            "current_decimal_places": 12,
        },
        "sdk_reader_representation": "IEEE-754 float32",
        "rows": {
            "complete": complete_rows,
            "changed_by_legacy_format": changed_rows,
        },
        "coordinates": {
            "total": total_coordinates,
            "changed_by_legacy_format": sum(changed_by_field.values()),
            "changed_by_field": changed_by_field,
        },
    }


def write_source_airway_coordinate_precision_audit(
    raw_root: Path,
    output: Path,
) -> dict[str, object]:
    report = audit_source_airway_coordinate_precision(raw_root)
    destination = output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_report(destination, report)
    return report


def run_airway_coordinate_precision_probe(
    output: Path,
    *,
    compiler: CompilerInfo,
    reader: Path | None = None,
    cache_root: Path | None = None,
    build_timeout_seconds: int = 3600,
    reader_timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Compile coordinate-precision controls and record SDK reader output."""

    destination = output.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"航路坐标精度探针输出目录已存在: {destination}")
    destination.mkdir(parents=True)
    xml_path = destination / "00_enroute.xml"
    scenarios = write_airway_coordinate_precision_probe_xml(xml_path)
    project_root = destination / "project"
    project_path = write_package_project(
        project_root,
        package_name=_PACKAGE_NAME,
        title="SDK Airway Coordinate Precision Probe",
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
        "probe": "sdk_airway_coordinate_precision",
        "contract": {
            "package_name": _PACKAGE_NAME,
            "bgl_filename_pattern": "00_enroute.bgl",
            "object_filter": "disabled",
            "input_coordinate_precisions": [scenario.decimal_places for scenario in scenarios],
            "recorded_airway_fields": list(_AIRWAY_COLUMNS),
        },
        "scenarios": _scenario_report(scenarios),
        "xml": str(xml_path),
        "compilation": compilation,
        "reader": reader_result.to_report(),
        "airway_rows": read_airway_coordinate_precision_rows(reader_result.database),
    }
    _write_report(destination / "probe-report.json", report)
    return report
