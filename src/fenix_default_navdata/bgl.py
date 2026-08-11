from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .model import NavModel, Runway, is_china_icao
from .profile import Cycle


class CompilerUnavailable(RuntimeError):
    """本机没有可调用的合法 BGL 编译器。"""


@dataclass(frozen=True)
class CompilerInfo:
    path: Path | None
    kind: str
    reason: str


@dataclass(frozen=True)
class XmlProjection:
    path: Path
    airports: int
    runways: int
    waypoints: int
    navaids: int
    airway_routes: int
    procedure_segments: int
    rejected_records: int
    rejected_procedures: int


@dataclass(frozen=True)
class _PhysicalRunway:
    primary: Runway | None
    secondary: Runway | None
    number: str
    primary_designator: str
    secondary_designator: str
    latitude: float
    longitude: float
    elevation_ft: float
    true_heading: float
    length_ft: int
    width_ft: int
    surface: str


def _simulator_pids() -> set[int]:
    result = subprocess.run(
        [
            "tasklist",
            "/FI",
            "IMAGENAME eq FlightSimulator2024.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        encoding="cp936",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].lower() == "flightsimulator2024.exe":
            try:
                pids.add(int(row[1]))
            except ValueError:
                continue
    return pids


def _wait_for_package_tool_process(
    previous_pids: set[int],
    *,
    start_timeout: int = 45,
    build_timeout: int = 3600,
) -> bool:
    start_deadline = time.monotonic() + start_timeout
    launched: set[int] = set()
    while time.monotonic() < start_deadline:
        launched = _simulator_pids() - previous_pids
        if launched:
            break
        time.sleep(0.5)
    if not launched:
        return False
    build_deadline = time.monotonic() + build_timeout
    while time.monotonic() < build_deadline:
        if not (_simulator_pids() & launched):
            return True
        time.sleep(1)
    raise TimeoutError(f"MSFS Package Tool 构建超过 {build_timeout} 秒")


def find_compiler(explicit: Path | None = None) -> CompilerInfo:
    if explicit:
        path = explicit.expanduser()
        if not path.is_file():
            return CompilerInfo(None, "none", f"指定的编译器不存在: {path}")
        kind = "PackageTool" if path.name.lower() == "fspackagetool.exe" else "BglComp"
        return CompilerInfo(path.resolve(), kind, "found")
    candidates = []
    if os.environ.get("FSPACKAGETOOL"):
        candidates.append((Path(os.environ["FSPACKAGETOOL"]), "PackageTool"))
    if os.environ.get("BGLCOMP"):
        candidates.append((Path(os.environ["BGLCOMP"]), "BglComp"))
    candidates.extend([
        (Path(r"C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe"), "PackageTool"),
        (Path(r"F:\games\MSF tools\MSFS2024_SDK_Core_Installer_1.5.3\SDK\Tools\bin\fspackagetool.exe"), "PackageTool"),
        (Path(r"F:\games\MSF tools\MSFS2024_SDK_Core_Installer_1.5.3\SDK\Tools\bin\BglComp.exe"), "BglComp"),
        (Path(r"F:\SteamLibrary\steamapps\common\MSFS2024\BglComp.exe"), "BglComp"),
        (Path(r"C:\MSFS SDK\Tools\bin\BglComp.exe"), "BglComp"),
    ])
    for path, kind in candidates:
        if path.is_file():
            return CompilerInfo(path.resolve(), kind, "found")
    return CompilerInfo(
        None,
        "none",
        "未找到 MSFS 2024 SDK fspackagetool.exe 或兼容的 BglComp.exe",
    )


def _number_designator(ident: str) -> tuple[str, str]:
    value = re.sub(r"^RWY", "", (ident or "").upper().replace(" ", ""))
    match = re.fullmatch(r"(\d{1,2})([LRC]?)", value)
    if not match:
        raise ValueError(f"无法规范化跑道标识: {ident!r}")
    return match.group(1).zfill(2), match.group(2)


def _float(value: object, digits: int = 6) -> str:
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")


def _attrs(**values: object) -> dict[str, str]:
    return {key: str(value) for key, value in values.items() if value is not None and value != ""}


def _waypoint_type(ident: str) -> str:
    return "NAMED" if ident else "UNNAMED"


def _surface(value: str) -> str:
    return {
        "ASP": "ASPHALT",
        "CON": "CONCRETE",
        "GRE": "GRASS",
        "WAT": "WATER",
        "U": "UNKNOWN",
    }.get((value or "").upper(), "UNKNOWN")


def _feet(value: object) -> str:
    return f"{_float(value)}F"


def _nautical_miles(value: object) -> str:
    return f"{_float(value, 3)}N"


def _runway_parts(ident: str) -> tuple[str, str]:
    number, designator = _number_designator(ident)
    return number, designator or "NONE"


def _reciprocal_runway_ident(ident: str) -> str:
    number, designator = _number_designator(ident)
    reciprocal_number = ((int(number) + 17) % 36) + 1
    reciprocal_designator = {
        "": "",
        "L": "R",
        "R": "L",
        "C": "C",
    }[designator]
    return f"{reciprocal_number:02d}{reciprocal_designator}"


def _destination(
    latitude: float,
    longitude: float,
    heading: float,
    distance_ft: float,
) -> tuple[float, float]:
    angular_distance = distance_ft * 0.3048 / 6_371_000
    latitude_radians = math.radians(latitude)
    longitude_radians = math.radians(longitude)
    heading_radians = math.radians(heading)
    destination_latitude = math.asin(
        math.sin(latitude_radians) * math.cos(angular_distance)
        + math.cos(latitude_radians)
        * math.sin(angular_distance)
        * math.cos(heading_radians)
    )
    destination_longitude = longitude_radians + math.atan2(
        math.sin(heading_radians)
        * math.sin(angular_distance)
        * math.cos(latitude_radians),
        math.cos(angular_distance)
        - math.sin(latitude_radians) * math.sin(destination_latitude),
    )
    return (
        math.degrees(destination_latitude),
        ((math.degrees(destination_longitude) + 540) % 360) - 180,
    )


def _geographic_midpoint(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> tuple[float, float]:
    first_latitude_radians = math.radians(first_latitude)
    second_latitude_radians = math.radians(second_latitude)
    longitude_delta = math.radians(second_longitude - first_longitude)
    x = math.cos(second_latitude_radians) * math.cos(longitude_delta)
    y = math.cos(second_latitude_radians) * math.sin(longitude_delta)
    latitude = math.atan2(
        math.sin(first_latitude_radians) + math.sin(second_latitude_radians),
        math.sqrt(
            (math.cos(first_latitude_radians) + x) ** 2
            + y ** 2
        ),
    )
    longitude = math.radians(first_longitude) + math.atan2(
        y,
        math.cos(first_latitude_radians) + x,
    )
    return math.degrees(latitude), ((math.degrees(longitude) + 540) % 360) - 180


def _physical_runways(runways: list[Runway]) -> list[_PhysicalRunway]:
    by_ident: dict[str, Runway] = {}
    for runway in sorted(runways, key=lambda item: (item.ident, item.key)):
        by_ident.setdefault(runway.ident, runway)

    result: list[_PhysicalRunway] = []
    consumed: set[str] = set()
    for ident in sorted(by_ident):
        if ident in consumed:
            continue
        runway = by_ident[ident]
        number, _ = _number_designator(ident)
        reciprocal_ident = _reciprocal_runway_ident(ident)
        reciprocal = by_ident.get(reciprocal_ident)
        if int(number) <= 18:
            primary = runway
            secondary = reciprocal
        elif reciprocal is not None:
            primary = reciprocal
            secondary = runway
        else:
            primary = None
            secondary = runway
        consumed.add(ident)
        if reciprocal is not None:
            consumed.add(reciprocal_ident)

        source = primary or secondary
        assert source is not None
        primary_ident = primary.ident if primary is not None else reciprocal_ident
        primary_number, primary_designator = _number_designator(primary_ident)
        secondary_ident = (
            secondary.ident
            if secondary is not None
            else _reciprocal_runway_ident(primary_ident)
        )
        _, secondary_designator = _number_designator(secondary_ident)
        true_heading = (
            primary.true_heading
            if primary is not None
            else (secondary.true_heading + 180) % 360
        )
        if (
            primary is not None
            and secondary is not None
            and primary.latitude is not None
            and primary.longitude is not None
            and secondary.latitude is not None
            and secondary.longitude is not None
        ):
            latitude, longitude = _geographic_midpoint(
                primary.latitude,
                primary.longitude,
                secondary.latitude,
                secondary.longitude,
            )
            elevation_ft = (primary.elevation_ft + secondary.elevation_ft) / 2
        else:
            threshold = primary or secondary
            assert threshold is not None
            threshold_heading = (
                threshold.true_heading
                if primary is not None
                else secondary.true_heading
            )
            latitude, longitude = _destination(
                threshold.latitude or 0,
                threshold.longitude or 0,
                threshold_heading,
                threshold.length_ft / 2,
            )
            elevation_ft = threshold.elevation_ft
        result.append(_PhysicalRunway(
            primary=primary,
            secondary=secondary,
            number=primary_number,
            primary_designator=primary_designator or "NONE",
            secondary_designator=secondary_designator or "NONE",
            latitude=latitude,
            longitude=longitude,
            elevation_ft=elevation_ft,
            true_heading=true_heading,
            length_ft=source.length_ft,
            width_ft=source.width_ft,
            surface=source.surface,
        ))
    return result


def _route_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized in {"L", "V", "VICTOR"}:
        return "VICTOR"
    if normalized in {"H", "J", "JET"}:
        return "JET"
    return "BOTH"


def _route_point_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if "VOR" in normalized:
        return "VOR"
    if "NDB" in normalized:
        return "NDB"
    return "NAMED"


def _ils_category(value: str | None) -> str | None:
    return {
        "0": "LOCALIZER",
        "1": "CAT1",
        "2": "CAT2",
        "3": "CAT3",
        "I": "IGS",
    }.get(str(value or "").strip().upper())


def _angle_delta(true_heading: float, magnetic_heading: float | None) -> float:
    if magnetic_heading is None:
        return 0.0
    return ((float(true_heading) - float(magnetic_heading) + 180.0) % 360.0) - 180.0


def _great_circle_distance_nm(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    first_latitude_radians = math.radians(first_latitude)
    second_latitude_radians = math.radians(second_latitude)
    latitude_delta = second_latitude_radians - first_latitude_radians
    longitude_delta = math.radians(second_longitude - first_longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude_radians)
        * math.cos(second_latitude_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 3440.065 * 2 * math.asin(min(1.0, math.sqrt(haversine)))


def _runway_ilses(runway: Runway, ilses: list) -> list:
    if runway.latitude is None or runway.longitude is None:
        return []
    candidates = [
        ils
        for ils in ilses
        if ils.runway == runway.ident
        and _great_circle_distance_nm(
            runway.latitude,
            runway.longitude,
            ils.localizer_latitude,
            ils.localizer_longitude,
        ) <= 5
    ]
    return sorted(
        candidates,
        key=lambda ils: (
            _great_circle_distance_nm(
                runway.latitude,
                runway.longitude,
                ils.localizer_latitude,
                ils.localizer_longitude,
            ),
            ils.ident,
            ils.frequency_mhz,
        ),
    )[:1]


def _append_ils(
    runway_element: ET.Element,
    runway: Runway,
    ilses: list,
    *,
    end: str,
) -> None:
    for ils in sorted(ilses, key=lambda item: (item.ident, item.frequency_mhz)):
        heading = ils.localizer_course_magnetic
        ils_element = ET.SubElement(runway_element, "Ils", _attrs(
            lat=_float(ils.localizer_latitude),
            lon=_float(ils.localizer_longitude),
            alt=_feet(runway.elevation_ft),
            heading=_float(heading if heading is not None else runway.true_heading, 3),
            frequency=_float(ils.frequency_mhz, 3),
            end=end,
            range=_nautical_miles(27),
            magvar=_float(_angle_delta(runway.true_heading, heading), 3),
            ident=ils.ident[:8],
            width=_float(3.95, 3),
            name=ils.ident[:48],
            backCourse="FALSE",
            lsCategory=_ils_category(ils.category),
        ))
        if ils.glide_slope_degrees is not None:
            ET.SubElement(ils_element, "GlideSlope", _attrs(
                lat=_float(ils.glide_slope_latitude or ils.localizer_latitude),
                lon=_float(ils.glide_slope_longitude or ils.localizer_longitude),
                alt=_feet(runway.elevation_ft),
                pitch=_float(ils.glide_slope_degrees, 3),
                range=_nautical_miles(10),
            ))
        if ils.dme_latitude is not None and ils.dme_longitude is not None:
            dme_altitude_ft = (
                float(ils.dme_elevation_meters) / 0.3048
                if ils.dme_elevation_meters is not None
                else runway.elevation_ft
            )
            ET.SubElement(ils_element, "Dme", _attrs(
                lat=_float(ils.dme_latitude),
                lon=_float(ils.dme_longitude),
                alt=_feet(dme_altitude_ft),
                range=_nautical_miles(125),
            ))


def _speed_descriptor(value: str | None) -> str | None:
    return {"A": "+", "B": "-", "+": "+", "-": "-", "@": "@"}.get(
        str(value or "").strip().upper()
    )


_FIX_LEG_TYPES = {
    "AF", "CF", "DF", "FA", "FC", "FD", "FM", "HA", "HF", "HM", "IF", "PI",
    "RF", "TF", "VM",
}
_FLY_OVER_LEG_TYPES = {
    "AF", "CF", "CI", "CR", "DF", "FC", "FD", "RF", "TF", "VI", "VR",
}
_TURN_LEG_TYPES = {
    "AF", "CA", "CD", "CF", "CI", "CR", "DF", "FA", "FC", "FD", "FM", "HA",
    "HF", "HM", "RF", "TF", "VA", "VD", "VI", "VM", "VR",
}
_REQUIRED_TURN_LEG_TYPES = {"AF", "RF", "TF"}
_RECOMMENDED_LEG_TYPES = {
    "AF", "CD", "CF", "CI", "CR", "DF", "FA", "FC", "FD", "FM", "HA", "HF",
    "HM", "IF", "PI", "RF", "TF", "VD", "VI", "VR",
}
_REQUIRED_RECOMMENDED_LEG_TYPES = {
    "AF", "CD", "CF", "CR", "FA", "FC", "FD", "FM", "PI", "VD", "VR",
}
_THETA_LEG_TYPES = {
    "AF", "CF", "CR", "DF", "FA", "FC", "FD", "FM", "HA", "HF", "HM", "IF",
    "PI", "RF", "TF", "VR",
}
_REQUIRED_THETA_LEG_TYPES = {
    "AF", "CF", "CR", "FA", "FC", "FD", "FM", "PI", "VR",
}
_RHO_LEG_TYPES = {
    "AF", "CF", "DF", "FA", "FC", "FD", "FM", "HA", "HF", "HM", "IF", "PI",
    "TF",
}
_REQUIRED_RHO_LEG_TYPES = {"AF", "CF", "FA", "FC", "FD", "FM", "PI"}
_COURSE_LEG_TYPES = {
    "AF", "CA", "CD", "CF", "CI", "CR", "FA", "FC", "FD", "FM", "HA", "HF",
    "HM", "PI", "RF", "TF", "VA", "VD", "VI", "VM", "VR",
}
_REQUIRED_COURSE_LEG_TYPES = _COURSE_LEG_TYPES - {"VA"}
_DISTANCE_LEG_TYPES = {
    "CD", "CF", "CI", "CR", "FC", "FD", "HA", "HF", "HM", "PI", "RF", "TF",
    "VD",
}
_REQUIRED_DISTANCE_LEG_TYPES = {
    "CD", "CF", "CI", "CR", "FC", "FD", "HA", "HF", "HM", "PI", "RF",
}


def _initial_bearing(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> float:
    start_lat = math.radians(float(start_latitude))
    end_lat = math.radians(float(end_latitude))
    delta_lon = math.radians(float(end_longitude) - float(start_longitude))
    y = math.sin(delta_lon) * math.cos(end_lat)
    x = (
        math.cos(start_lat) * math.sin(end_lat)
        - math.sin(start_lat) * math.cos(end_lat) * math.cos(delta_lon)
    )
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _fallback_true_course(legs, index: int) -> float | None:
    leg = legs[index]
    if leg.fix_latitude is None or leg.fix_longitude is None:
        return 0.0
    for previous in reversed(legs[:index]):
        if previous.fix_latitude is not None and previous.fix_longitude is not None:
            if (
                previous.fix_latitude != leg.fix_latitude
                or previous.fix_longitude != leg.fix_longitude
            ):
                return _initial_bearing(
                    previous.fix_latitude,
                    previous.fix_longitude,
                    leg.fix_latitude,
                    leg.fix_longitude,
                )
    for following in legs[index + 1:]:
        if following.fix_latitude is not None and following.fix_longitude is not None:
            if (
                following.fix_latitude != leg.fix_latitude
                or following.fix_longitude != leg.fix_longitude
            ):
                return _initial_bearing(
                    leg.fix_latitude,
                    leg.fix_longitude,
                    following.fix_latitude,
                    following.fix_longitude,
                )
    return 0.0


def _leg_distance(leg) -> float | None:
    if leg.leg_type in {"CD", "CF", "FC", "FD", "PI", "VD"}:
        distance = leg.distance_nm if leg.distance_nm is not None else leg.rho_nm
        if distance is not None:
            return distance
    if leg.leg_type == "RF":
        distance = (
            leg.distance_nm
            if leg.distance_nm is not None
            else leg.arc_radius_nm
        )
        if distance is not None:
            return distance
    if leg.leg_type in _REQUIRED_DISTANCE_LEG_TYPES and leg.distance_nm is None:
        return 0.0
    return leg.distance_nm


def _description_flag(code: str, marker: str) -> str | None:
    return "TRUE" if marker in (code or "").upper() else None


def _terminal_waypoint_key(
    airport: str,
    region: str,
    ident: str,
    latitude: float,
    longitude: float,
) -> tuple[str, str, str, str, str]:
    return (
        airport.upper(),
        (region or airport[:2]).upper()[:2],
        _normalized_waypoint_ident(ident, latitude, longitude),
        f"{float(latitude):.6f}",
        f"{float(longitude):.6f}",
    )


def _terminal_waypoint_identities(points) -> tuple[dict[tuple[str, str, str, str, str], str], dict[tuple[str, str, str, str, str], object]]:
    """Return SDK-safe identities and one deterministic record per coordinate."""
    representatives: dict[tuple[str, str, str, str, str], object] = {}
    for point in sorted(
        points,
        key=lambda item: (
            item.airport,
            item.country or item.airport[:2],
            item.ident,
            float(item.latitude),
            float(item.longitude),
            item.key,
        ),
    ):
        key = _terminal_waypoint_key(
            point.airport,
            point.country,
            point.ident,
            point.latitude,
            point.longitude,
        )
        representatives.setdefault(key, point)

    grouped: dict[tuple[str, str, str], list[tuple[str, str, str, str, str]]] = {}
    reserved: set[tuple[str, str, str]] = set()
    for key in representatives:
        group_key = key[:3]
        grouped.setdefault(group_key, []).append(key)
        reserved.add(group_key)

    identities: dict[tuple[str, str, str, str, str], str] = {}
    for (airport, region, base_ident), keys in sorted(grouped.items()):
        for index, key in enumerate(sorted(keys)):
            if index == 0:
                identities[key] = base_ident
                continue
            suffix = 1
            while True:
                candidate = f"{base_ident[:5]}{suffix:03d}"
                identity = (airport, region, candidate)
                if identity not in reserved:
                    reserved.add(identity)
                    identities[key] = candidate
                    break
                suffix += 1
    return identities, representatives


def _terminal_waypoint_ident(
    identities: dict[tuple[str, str, str, str, str], str],
    airport: str,
    ident: str | None,
    region: str,
    latitude: float | None,
    longitude: float | None,
) -> str | None:
    if not ident:
        return ident
    if latitude is not None and longitude is not None:
        key = _terminal_waypoint_key(airport, region, ident, latitude, longitude)
        mapped = identities.get(key)
        if mapped is not None:
            return mapped
    return ident[:8]


def _leg_fix_ident(
    leg,
    airport: str,
    identities: dict[tuple[str, str, str, str, str], str],
) -> str | None:
    return _terminal_waypoint_ident(
        identities,
        airport,
        leg.fix_ident,
        leg.fix_region,
        leg.fix_latitude,
        leg.fix_longitude,
    )


def _leg_recommended_ident(
    leg,
    airport: str,
    identities: dict[tuple[str, str, str, str, str], str],
) -> str | None:
    return _terminal_waypoint_ident(
        identities,
        airport,
        leg.recommended_ident,
        leg.recommended_region,
        leg.recommended_latitude,
        leg.recommended_longitude,
    )


def _leg_center_ident(
    leg,
    airport: str,
    identities: dict[tuple[str, str, str, str, str], str],
) -> str | None:
    return _terminal_waypoint_ident(
        identities,
        airport,
        leg.center_ident,
        leg.center_region,
        leg.center_latitude,
        leg.center_longitude,
    )


def _leg_attrs(legs, index: int, airport: str, identities) -> dict[str, str]:
    leg = legs[index]
    leg_type = leg.leg_type
    fix_ident = _leg_fix_ident(leg, airport, identities)
    center_ident = _leg_center_ident(leg, airport, identities)
    source_course = leg.course_degrees if leg_type in _COURSE_LEG_TYPES else None
    true_course = (
        _fallback_true_course(legs, index)
        if source_course is None and leg_type in _REQUIRED_COURSE_LEG_TYPES
        else None
    )
    distance = _leg_distance(leg) if leg_type in _DISTANCE_LEG_TYPES else None
    recommended_ident = _leg_recommended_ident(leg, airport, identities)
    recommended_region = leg.recommended_region
    recommended_type = leg.recommended_type
    if not recommended_ident and leg_type in _REQUIRED_RECOMMENDED_LEG_TYPES:
        recommended_ident = center_ident or fix_ident
        recommended_region = leg.center_region or leg.fix_region
        recommended_type = (
            "TERMINAL_WAYPOINT"
            if center_ident
            else leg.fix_type
        )
    theta = leg.theta_degrees
    if theta is None and leg_type in _REQUIRED_THETA_LEG_TYPES:
        theta = leg.course_degrees if leg.course_degrees is not None else 0.0
    rho = leg.rho_nm
    if rho is None and leg_type in _REQUIRED_RHO_LEG_TYPES:
        rho = (
            leg.distance_nm
            if leg.distance_nm is not None
            else leg.arc_radius_nm
        )
        if rho is None:
            rho = 0.0
    turn_direction = leg.turn_direction
    if not turn_direction and leg_type in _REQUIRED_TURN_LEG_TYPES:
        turn_direction = "E"
    attrs = _attrs(
        type=leg_type,
        fixType=(
            leg.fix_type
            if leg_type in _FIX_LEG_TYPES and fix_ident
            else None
        ),
        fixRegion=(
            leg.fix_region[:2]
            if leg_type in _FIX_LEG_TYPES and fix_ident
            else None
        ),
        fixIdent=(
            fix_ident
            if leg_type in _FIX_LEG_TYPES and fix_ident
            else None
        ),
        flyOver=(
            ("TRUE" if leg.fly_over else "FALSE")
            if leg_type in _FLY_OVER_LEG_TYPES
            else None
        ),
        turnDirection=(
            turn_direction
            if leg_type in _TURN_LEG_TYPES
            else None
        ),
        recommendedType=(
            recommended_type
            if leg_type in _RECOMMENDED_LEG_TYPES and recommended_ident
            else None
        ),
        recommendedIdent=(
            recommended_ident[:8]
            if leg_type in _RECOMMENDED_LEG_TYPES and recommended_ident
            else None
        ),
        recommendedRegion=(
            recommended_region[:2]
            if leg_type in _RECOMMENDED_LEG_TYPES and recommended_ident
            else None
        ),
        theta=(
            _float(theta, 3)
            if leg_type in _THETA_LEG_TYPES and theta is not None
            else None
        ),
        rho=(
            _nautical_miles(rho)
            if leg_type in _RHO_LEG_TYPES and rho is not None
            else None
        ),
        magneticCourse=(
            _float(source_course, 3)
            if source_course is not None
            else None
        ),
        trueCourse=(
            _float(true_course, 3)
            if true_course is not None
            else None
        ),
        distance=_nautical_miles(distance) if distance is not None else None,
        altitudeDescriptor=leg.altitude_descriptor,
        altitude1=_feet(leg.altitude1_ft) if leg.altitude1_ft is not None else None,
        altitude2=_feet(leg.altitude2_ft) if leg.altitude2_ft is not None else None,
        speedLimit=leg.speed_limit_knots,
        verticalAngle=_float(leg.vertical_angle, 3) if leg.vertical_angle is not None else None,
        arcCenterFixType=(
            "TERMINAL_WAYPOINT"
            if leg_type == "RF" and center_ident
            else None
        ),
        arcCenterFixIdent=(
            center_ident
            if leg_type == "RF" and center_ident
            else None
        ),
        arcCenterFixRegion=(
            leg.center_region[:2]
            if leg_type == "RF" and center_ident
            else None
        ),
        isIAF=_description_flag(leg.waypoint_description_code, "A"),
        isIF=_description_flag(leg.waypoint_description_code, "I"),
        isFAF=_description_flag(leg.waypoint_description_code, "F"),
        isMAP=_description_flag(leg.waypoint_description_code, "M"),
        arcRadius=(
            _nautical_miles(leg.arc_radius_nm)
            if leg_type == "RF" and leg.arc_radius_nm is not None
            else None
        ),
        speedLimitDescriptor=_speed_descriptor(leg.speed_limit_descriptor),
    )
    return attrs


def _append_legs(parent: ET.Element, legs, airport: str, identities) -> None:
    ordered = sorted(legs, key=lambda item: item.sequence)
    for index, _ in enumerate(ordered):
        ET.SubElement(parent, "Leg", _leg_attrs(ordered, index, airport, identities))


def _append_departures(
    airport_element: ET.Element,
    airport: str,
    segments: list,
    identities,
) -> None:
    labels = sorted({segment.label for segment in segments})
    for label in labels:
        selected = [segment for segment in segments if segment.label == label]
        departure = ET.SubElement(airport_element, "Departure", {"name": label[:6]})
        runway_transitions = ET.SubElement(departure, "RunwayTransitions")
        common = ET.SubElement(departure, "CommonRouteLegs")
        enroute_transitions = ET.SubElement(departure, "EnrouteTransitions")
        for segment in selected:
            transition = segment.transition.upper()
            runway = segment.runway or (transition[2:] if transition.startswith("RW") else "")
            if runway:
                number, designator = _runway_parts(runway)
                target = ET.SubElement(runway_transitions, "RunwayTransitionLegs", {
                    "number": number,
                    "designator": designator,
                })
            elif transition:
                target = ET.SubElement(
                    enroute_transitions,
                    "EnrouteTransitionLegs",
                    _attrs(name=transition[:5]),
                )
            else:
                target = common
            _append_legs(target, segment.legs, airport, identities)


def _append_arrivals(
    airport_element: ET.Element,
    airport: str,
    segments: list,
    identities,
) -> None:
    labels = sorted({segment.label for segment in segments})
    for label in labels:
        selected = [segment for segment in segments if segment.label == label]
        arrival = ET.SubElement(airport_element, "Arrival", {"name": label[:6]})
        enroute_transitions = ET.SubElement(arrival, "EnrouteTransitions")
        common = ET.SubElement(arrival, "CommonRouteLegs")
        runway_transitions = ET.SubElement(arrival, "RunwayTransitions")
        for segment in selected:
            transition = segment.transition.upper()
            runway = segment.runway or (transition[2:] if transition.startswith("RW") else "")
            if runway:
                number, designator = _runway_parts(runway)
                target = ET.SubElement(runway_transitions, "RunwayTransitionLegs", {
                    "number": number,
                    "designator": designator,
                })
            elif transition:
                target = ET.SubElement(
                    enroute_transitions,
                    "EnrouteTransitionLegs",
                    _attrs(name=transition[:5]),
                )
            else:
                target = common
            _append_legs(target, segment.legs, airport, identities)


def _approach_type(label: str) -> str:
    first = (label or "R").upper()[:1]
    return {
        "I": "ILS",
        "L": "LOCALIZER",
        "N": "NDB",
        "Q": "NDBDME",
        "D": "VORDME",
        "V": "VOR",
        "G": "GPS",
        "R": "RNAV",
    }.get(first, "RNAV")


def _append_approaches(
    airport_element: ET.Element,
    airport: str,
    segments: list,
    runways: list,
    identities,
) -> None:
    runway_headings = {runway.ident: runway.true_heading for runway in runways}
    keys = sorted({(segment.label, segment.runway) for segment in segments})
    for label, runway in keys:
        selected = [
            segment for segment in segments
            if segment.label == label and segment.runway == runway
        ]
        all_legs = [leg for segment in selected for leg in segment.legs]
        first_fix = next((leg for leg in all_legs if leg.fix_ident), None)
        first_altitude = next(
            (leg.altitude1_ft for leg in all_legs if leg.altitude1_ft is not None),
            0,
        )
        heading = next(
            (leg.course_degrees for leg in all_legs if leg.course_degrees is not None),
            runway_headings.get(runway, 0),
        )
        missed_altitude = max(
            (leg.altitude1_ft for leg in all_legs if leg.altitude1_ft is not None),
            default=first_altitude,
        )
        number, designator = _runway_parts(runway or "00")
        suffix = label[-1] if label[-1:] in {"X", "Y", "Z"} else None
        approach = ET.SubElement(airport_element, "Approach", _attrs(
            type=_approach_type(label),
            runway=number if runway else None,
            designator=designator if runway else None,
            suffix=suffix,
            gpsOverlay="TRUE" if _approach_type(label) in {"GPS", "RNAV"} else "FALSE",
            fixType=(first_fix.fix_type if first_fix else "AIRPORT"),
            fixRegion=(first_fix.fix_region[:2] if first_fix else airport[:2]),
            fixIdent=(
                _leg_fix_ident(first_fix, airport, identities)
                if first_fix
                else airport[:8]
            ),
            altitude=_feet(first_altitude),
            heading=_float(heading or 0, 3),
            missedAltitude=_feet(missed_altitude),
        ))
        common_legs = [
            leg for segment in selected if not segment.transition for leg in segment.legs
        ]
        if common_legs:
            _append_legs(
                ET.SubElement(approach, "ApproachLegs"),
                common_legs,
                airport,
                identities,
            )
        for segment in selected:
            if not segment.transition:
                continue
            first_transition_fix = next(
                (leg for leg in segment.legs if leg.fix_ident),
                None,
            )
            transition = ET.SubElement(approach, "Transition", _attrs(
                transitionType="FULL",
                fixType=first_transition_fix.fix_type if first_transition_fix else None,
                fixRegion=first_transition_fix.fix_region[:2] if first_transition_fix else None,
                fixIdent=(
                    _leg_fix_ident(first_transition_fix, airport, identities)
                    if first_transition_fix
                    else None
                ),
                altitude=(
                    _feet(first_transition_fix.altitude1_ft)
                    if first_transition_fix and first_transition_fix.altitude1_ft is not None
                    else None
                ),
                name=segment.transition[:5],
            ))
            _append_legs(
                ET.SubElement(transition, "TransitionLegs"),
                segment.legs,
                airport,
                identities,
            )


def _append_airport_procedures(
    airport_element: ET.Element,
    airport: str,
    model: NavModel,
    runways: list,
    identities,
) -> int:
    segments = [
        segment for segment in model.procedure_segments
        if segment.airport == airport
    ]
    _append_departures(
        airport_element,
        airport,
        [segment for segment in segments if segment.kind == "departure"],
        identities,
    )
    _append_arrivals(
        airport_element,
        airport,
        [segment for segment in segments if segment.kind == "arrival"],
        identities,
    )
    _append_approaches(
        airport_element,
        airport,
        [segment for segment in segments if segment.kind == "approach"],
        runways,
        identities,
    )
    return len(segments)


def _normalized_waypoint_ident(
    ident: str,
    latitude: float,
    longitude: float,
) -> str:
    value = str(ident or "").strip().upper()
    if re.fullmatch(r"[A-Z0-9]{1,8}", value):
        return value
    if "/" in value:
        stem = value.split("/", maxsplit=1)[0]
        if re.fullmatch(r"[A-Z0-9]+", stem):
            return stem[:5]
    cleaned = re.sub(r"[^A-Z0-9]", "", value)
    if cleaned:
        return cleaned[:8]
    digest = hashlib.sha1(
        f"{value}|{float(latitude):.6f}|{float(longitude):.6f}".encode("utf-8")
    ).hexdigest().upper()
    return f"P{digest[:7]}"


def _waypoint_identity(
    ident: str,
    country: str,
    latitude: float,
    longitude: float,
) -> tuple[str, str, str]:
    normalized_ident = _normalized_waypoint_ident(ident, latitude, longitude)
    return (
        _waypoint_type(normalized_ident),
        (country or "CN").upper()[:2],
        normalized_ident,
    )


def _append_enroute(
    root: ET.Element,
    model: NavModel,
) -> tuple[int, int, int]:
    points = list(model.waypoints)
    for leg in model.airway_legs:
        if leg.start_latitude is not None and leg.start_longitude is not None:
            points.append(type("_Point", (), {
                "ident": leg.start_ident,
                "country": leg.start_country or "CN",
                "latitude": leg.start_latitude,
                "longitude": leg.start_longitude,
                "name": leg.start_ident,
                "key": f"airway-start:{leg.airway}:{leg.sequence}",
            })())
        if leg.end_latitude is not None and leg.end_longitude is not None:
            points.append(type("_Point", (), {
                "ident": leg.end_ident,
                "country": leg.end_country or "CN",
                "latitude": leg.end_latitude,
                "longitude": leg.end_longitude,
                "name": leg.end_ident,
                "key": f"airway-end:{leg.airway}:{leg.sequence}",
            })())
    deduped: dict[tuple[str, str, str], object] = {}
    for point in sorted(
        points,
        key=lambda item: (
            str(item.ident).upper(),
            str(item.country or "CN").upper(),
            float(item.latitude),
            float(item.longitude),
            str(item.key),
        ),
    ):
        deduped.setdefault(_waypoint_identity(
            str(point.ident),
            str(point.country or "CN"),
            float(point.latitude),
            float(point.longitude),
        ), point)
    route_children: dict[
        tuple[str, str, str],
        list[tuple[str, str, str, dict[str, str]]],
    ] = {}
    for leg in sorted(model.airway_legs, key=lambda item: (item.airway, item.sequence)):
        if None in {
            leg.start_latitude, leg.start_longitude,
            leg.end_latitude, leg.end_longitude,
        }:
            continue
        start_key = _waypoint_identity(
            leg.start_ident,
            leg.start_country,
            leg.start_latitude,
            leg.start_longitude,
        )
        end_key = _waypoint_identity(
            leg.end_ident,
            leg.end_country,
            leg.end_latitude,
            leg.end_longitude,
        )
        route_children.setdefault(start_key, []).append((
            leg.airway,
            _route_type(leg.route_type),
            "Next",
            _attrs(
            waypointRegion=end_key[1],
            waypointIdent=end_key[2],
            waypointType=_route_point_type(leg.end_type),
            altitudeMinimum=_feet(leg.minimum_altitude_ft or 0),
        )))
        route_children.setdefault(end_key, []).append((
            leg.airway,
            _route_type(leg.route_type),
            "Previous",
            _attrs(
            waypointRegion=start_key[1],
            waypointIdent=start_key[2],
            waypointType=_route_point_type(leg.start_type),
            altitudeMinimum=_feet(leg.minimum_altitude_ft or 0),
        )))
    ordered_points = sorted(deduped.values(), key=lambda item: (
        str(item.ident).upper(), float(item.latitude), float(item.longitude), str(item.key),
    ))
    for point in ordered_points:
        identity = _waypoint_identity(
            str(point.ident),
            str(point.country or "CN"),
            float(point.latitude),
            float(point.longitude),
        )
        point_element = ET.SubElement(root, "Waypoint", _attrs(
            lat=_float(point.latitude),
            lon=_float(point.longitude),
            waypointType=identity[0],
            waypointRegion=identity[1],
            waypointIdent=identity[2],
        ))
        grouped_routes: dict[str, tuple[str, list[tuple[str, dict[str, str]]]]] = {}
        for route_name, route_type, direction, attrs in route_children.get(identity, []):
            grouped_routes.setdefault(route_name, (route_type, []))[1].append(
                (direction, attrs)
            )
        for route_name in sorted(grouped_routes):
            route_type, children = grouped_routes[route_name]
            route = ET.SubElement(point_element, "Route", _attrs(
                name=route_name,
                routeType=route_type,
            ))
            for direction, attrs in children:
                ET.SubElement(route, direction, attrs)
    navaids = sorted(model.navaids, key=lambda item: (item.kind, item.ident, item.key))
    for navaid in navaids:
        if navaid.kind == "VOR":
            vor = ET.SubElement(root, "Vor", _attrs(
                lat=_float(navaid.latitude),
                lon=_float(navaid.longitude),
                alt=_feet(navaid.elevation_ft),
                type="HIGH",
                frequency=_float(navaid.frequency, 3),
                magvar=_float(navaid.magnetic_variation, 3),
                range=_nautical_miles(125),
                region=navaid.country[:2],
                ident=navaid.ident[:8],
                name=navaid.name[:48],
                nav="TRUE",
                dme="TRUE",
            ))
            ET.SubElement(vor, "Dme", _attrs(
                lat=_float(navaid.latitude),
                lon=_float(navaid.longitude),
                alt=_feet(navaid.elevation_ft),
                range=_nautical_miles(125),
            ))
        elif navaid.kind == "NDB":
            ET.SubElement(root, "Ndb", _attrs(
                lat=_float(navaid.latitude),
                lon=_float(navaid.longitude),
                alt=_feet(navaid.elevation_ft),
                type="H",
                frequency=_float(navaid.frequency, 1),
                range=_nautical_miles(50),
                magvar=_float(navaid.magnetic_variation, 3),
                region=navaid.country[:2],
                ident=navaid.ident[:8],
                name=navaid.name[:48],
            ))
    return len(ordered_points), len(navaids), len({leg.airway for leg in model.airway_legs})


def write_bglcomp_xml(
    model: NavModel,
    cycle: Cycle,
    output: Path,
    *,
    scope: str = "all",
    airport_prefix: str | None = None,
    duplicate_terminal_waypoints: bool = False,
) -> XmlProjection:
    """把统一中间模型投影为官方 XSD 约束下的 BglComp XML。

    XML 是公开 SDK 的输入格式，不等同于 Navigraph 的最终 BGL；最终字节仍由
    版本匹配的官方设施编译器决定。
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "fenix_to_default_navdata",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": cycle.begin,
        "cycleEnd": cycle.end,
        "cycleNumber": cycle.number[-2:],
    })

    airports = [
        airport for airport in model.airports.values()
        if is_china_icao(airport.icao)
        and (airport_prefix is None or airport.icao.startswith(airport_prefix))
    ]
    airports.sort(key=lambda item: item.icao)
    airport_keys = {airport.key for airport in airports}
    runways = [runway for runway in model.runways if runway.airport_key in airport_keys]
    runways.sort(key=lambda item: (model.airports[item.airport_key].icao, item.ident, item.key))
    if scope not in {"all", "enroute", "airports"}:
        raise ValueError(f"未知 XML 投影范围: {scope}")
    if airport_prefix is not None and airport_prefix not in {
        "ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY",
    }:
        raise ValueError(f"未知机场分区: {airport_prefix}")
    projected_airports = airports if scope in {"all", "airports"} else []
    projected_runways = runways if scope in {"all", "airports"} else []
    terminal_identities, terminal_representatives = _terminal_waypoint_identities(
        model.terminal_waypoints
    )
    projected_procedures = 0
    for airport in projected_airports:
        airport_element = ET.SubElement(root, "Airport", _attrs(
            ident=airport.icao,
            name=airport.name[:48],
            region=airport.icao[:2],
            regionCode=airport.icao[:2],
            lat=_float(airport.latitude),
            lon=_float(airport.longitude),
            alt=_feet(airport.elevation_ft),
            transitionAltitude=_feet(airport.transition_altitude),
            transitionLevel=_feet(airport.transition_level),
        ))
        airport_runway_ends = [
            item for item in projected_runways if item.airport_key == airport.key
        ]
        airport_runways = _physical_runways(airport_runway_ends)
        airport_ilses = [
            ils for ils in model.ilses if ils.airport == airport.icao
        ]
        for runway in airport_runways:
            runway_element = ET.SubElement(airport_element, "Runway", _attrs(
                lat=_float(runway.latitude),
                lon=_float(runway.longitude),
                alt=_feet(runway.elevation_ft),
                surface=_surface(runway.surface),
                heading=_float(runway.true_heading, 3),
                length=_feet(runway.length_ft),
                width=_feet(runway.width_ft),
                number=runway.number,
                primaryDesignator=runway.primary_designator,
                secondaryDesignator=runway.secondary_designator,
                primaryTakeoff="TRUE",
                primaryLanding="TRUE",
                secondaryTakeoff="TRUE",
                secondaryLanding="TRUE",
            ))
            if runway.primary is not None:
                _append_ils(
                    runway_element,
                    runway.primary,
                    _runway_ilses(runway.primary, airport_ilses),
                    end="PRIMARY",
                )
            if runway.secondary is not None:
                _append_ils(
                    runway_element,
                    runway.secondary,
                    _runway_ilses(runway.secondary, airport_ilses),
                    end="SECONDARY",
                )
        terminal_points = sorted(
            (
                (key, point)
                for key, point in terminal_representatives.items()
                if point.airport == airport.icao
            ),
            key=lambda item: (
                terminal_identities[item[0]],
                item[1].latitude,
                item[1].longitude,
                item[1].key,
            ),
        )
        for point_key, point in terminal_points:
            ET.SubElement(airport_element, "Waypoint", _attrs(
                lat=_float(point.latitude),
                lon=_float(point.longitude),
                waypointType="NAMED",
                waypointRegion=(point.country or airport.icao[:2])[:2],
                waypointIdent=terminal_identities[point_key],
            ))
        projected_procedures += _append_airport_procedures(
            airport_element,
            airport.icao,
            model,
            airport_runway_ends,
            terminal_identities,
        )
        airport_holdings = [
            holding for holding in model.holdings
            if holding.fix_region == airport.icao
        ]
        for holding in sorted(airport_holdings, key=lambda item: (item.fix_ident, item.name)):
            ET.SubElement(airport_element, "HoldingPattern", _attrs(
                name=holding.name,
                fixType="TERMINAL_WAYPOINT",
                fixIdent=_terminal_waypoint_ident(
                    terminal_identities,
                    airport.icao,
                    holding.fix_ident,
                    holding.fix_region,
                    holding.latitude,
                    holding.longitude,
                ),
                fixRegion=holding.fix_region[:2],
                inboundHoldingCourse=(
                    _float(holding.inbound_course, 3)
                    if holding.inbound_course is not None
                    else None
                ),
                turnDirection=holding.turn_direction,
                length=(
                    _nautical_miles(holding.length_nm)
                    if holding.length_nm is not None
                    else None
                ),
                time=holding.time_minutes,
                altitudeMinimum=(
                    _feet(holding.minimum_altitude_ft)
                    if holding.minimum_altitude_ft is not None
                    else None
                ),
                altitudeMaximum=(
                    _feet(holding.maximum_altitude_ft)
                    if holding.maximum_altitude_ft is not None
                    else None
                ),
                holdSpeed=holding.speed_limit_knots,
            ))

    selected_terminal_points = [
        (key, point)
        for key, point in terminal_representatives.items()
        if airport_prefix is None or point.airport.startswith(airport_prefix)
    ] if scope in {"all", "airports"} else []
    terminal_waypoint_count = len(selected_terminal_points)
    root_terminal_waypoint_count = 0
    if duplicate_terminal_waypoints and scope in {"all", "airports"}:
        deduped_terminal_points: dict[tuple[str, str], tuple[tuple[str, str, str, str, str], object]] = {}
        for point_key, point in selected_terminal_points:
            key = (
                terminal_identities[point_key],
                (point.country or point.airport[:2]).upper()[:2],
            )
            deduped_terminal_points.setdefault(key, (point_key, point))
        root_terminal_waypoint_count = len(deduped_terminal_points)
        for point_key, point in sorted(
            deduped_terminal_points.values(),
            key=lambda item: (
                terminal_identities[item[0]],
                item[1].latitude,
                item[1].longitude,
                item[1].key,
            ),
        ):
            ET.SubElement(root, "Waypoint", _attrs(
                lat=_float(point.latitude),
                lon=_float(point.longitude),
                waypointType="NAMED",
                waypointRegion=(point.country or point.airport[:2])[:2],
                waypointIdent=terminal_identities[point_key],
            ))

    enroute_waypoints = 0
    enroute_navaids = 0
    airway_routes = 0
    if scope in {"all", "enroute"}:
        enroute_waypoints, enroute_navaids, airway_routes = _append_enroute(root, model)

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return XmlProjection(
        path=output,
        airports=len(projected_airports),
        runways=sum(
            len(_physical_runways([
                runway
                for runway in projected_runways
                if runway.airport_key == airport.key
            ]))
            for airport in projected_airports
        ),
        waypoints=(
            enroute_waypoints
            + terminal_waypoint_count
            + root_terminal_waypoint_count
        ),
        navaids=enroute_navaids,
        airway_routes=airway_routes,
        procedure_segments=projected_procedures,
        rejected_records=len(model.rejected_records),
        rejected_procedures=len(model.rejected_procedures),
    )


def write_package_project(
    project_root: Path,
    *,
    package_name: str,
    title: str,
    output_dir: str,
    source_xmls: tuple[Path, ...],
    package_order_hint: str,
) -> Path:
    """生成可由 MSFS 2024 Package Tool 构建的最小项目。"""
    project_root.mkdir(parents=True, exist_ok=True)
    source_dir = project_root / "PackageSources" / "NavData"
    definition_dir = project_root / "PackageDefinitions"
    source_dir.mkdir(parents=True, exist_ok=True)
    definition_dir.mkdir(parents=True, exist_ok=True)
    for source in source_xmls:
        shutil.copy2(source, source_dir / source.name)

    package = ET.Element("AssetPackage", {"Version": "0.1.0"})
    ET.SubElement(package, "PackageOrderHint").text = package_order_hint
    settings = ET.SubElement(package, "ItemSettings")
    ET.SubElement(settings, "ContentType").text = "SCENERY"
    ET.SubElement(settings, "Title").text = title
    ET.SubElement(settings, "Manufacturer").text = "User NavData"
    ET.SubElement(settings, "Creator").text = "Fenix to Default NavData Converter"
    flags = ET.SubElement(package, "Flags")
    ET.SubElement(flags, "VisibleInStore").text = "false"
    ET.SubElement(flags, "CanBeReferenced").text = "false"
    groups = ET.SubElement(package, "AssetGroups")
    group = ET.SubElement(groups, "AssetGroup", {"Name": "NavData"})
    ET.SubElement(group, "Type").text = "BGL"
    group_flags = ET.SubElement(group, "Flags")
    ET.SubElement(group_flags, "FSXCompatibility").text = "false"
    ET.SubElement(group, "AssetDir").text = r"PackageSources\NavData"
    ET.SubElement(group, "OutputDir").text = output_dir.replace("/", "\\")
    ET.indent(package, space="\t")
    definition_path = definition_dir / f"{package_name}.xml"
    ET.ElementTree(package).write(definition_path, encoding="utf-8", xml_declaration=True)

    project = ET.Element("Project", {
        "Version": "2",
        "Name": package_name,
        "FolderName": "Packages",
        "MetadataFolderName": "PackagesMetadata",
    })
    ET.SubElement(project, "OutputDirectory").text = "."
    ET.SubElement(project, "TemporaryOutputDirectory").text = "_PackageInt"
    packages = ET.SubElement(project, "Packages")
    ET.SubElement(packages, "Package").text = f"PackageDefinitions\\{package_name}.xml"
    ET.SubElement(project, "PublishingGroups")
    ET.indent(project, space="\t")
    project_path = project_root / f"{package_name}.xml"
    ET.ElementTree(project).write(project_path, encoding="utf-8", xml_declaration=True)
    return project_path


def compile_package(
    project_path: Path,
    compiler: CompilerInfo,
    *,
    package_name: str,
    timeout_seconds: int = 3600,
) -> dict[str, object]:
    if compiler.path is None:
        raise CompilerUnavailable(compiler.reason)
    if compiler.kind != "PackageTool":
        raise CompilerUnavailable(f"编译器 {compiler.path} 不是 MSFS Package Tool")
    stage_parent = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "fenix_default_navdata"
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix="sdk-build-", dir=stage_parent))
    try:
        simulator_pids = _simulator_pids()
        if simulator_pids:
            raise RuntimeError(
                "FlightSimulator2024.exe 正在运行；Package Tool 构建前请完全关闭模拟器"
            )
        shutil.copytree(project_path.parent, stage_root, dirs_exist_ok=True)
        staged_project = stage_root / project_path.name
        command = [
            str(compiler.path),
            str(staged_project),
            "-outputtoseparateconsole",
            "-nopause",
            "-rebuild",
            "-forcesteam",
        ]
        result = subprocess.run(
            command,
            cwd=str(stage_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            _wait_for_package_tool_process(
                simulator_pids,
                build_timeout=timeout_seconds,
            )
        staged_package_root = stage_root / "Packages" / package_name
        required = (
            staged_package_root / "manifest.json",
            staged_package_root / "layout.json",
            staged_package_root / "bglIndex.bout",
        )
        missing = [str(path.relative_to(stage_root)) for path in required if not path.is_file()]
        bgls = sorted(staged_package_root.rglob("*.bgl")) if staged_package_root.is_dir() else []
        if missing or not bgls:
            details = "\n".join(filter(None, (result.stdout, result.stderr)))
            builder_log = (
                Path(os.environ.get("APPDATA", ""))
                / "Microsoft Flight Simulator 2024"
                / "BuilderLogError.txt"
            )
            if builder_log.is_file():
                details = f"{details}\n{builder_log.read_text(encoding='utf-8', errors='replace')[-4000:]}"
            raise RuntimeError(
                "Package Tool 未生成完整导航包；"
                f"包装器退出代码={result.returncode}，缺少={missing}，"
                f"BGL={len(bgls)}，输出={details[-4000:]}"
            )
        package_root = project_path.parent / "_compiled" / package_name
        if package_root.exists():
            shutil.rmtree(package_root)
        shutil.copytree(staged_package_root, package_root)
        copied_bgls = sorted(package_root.rglob("*.bgl"))
        return {
            "compiler": str(compiler.path),
            "kind": compiler.kind,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "package_root": str(package_root),
            "bgls": [str(path) for path in copied_bgls],
        }
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


def compile_bgl(xml_path: Path, compiler: CompilerInfo, output_bgl: Path) -> dict[str, object]:
    if compiler.path is None:
        raise CompilerUnavailable(compiler.reason)
    output_bgl.parent.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in xml_path.parent.glob("*.bgl")}
    result = subprocess.run(
        [str(compiler.path), str(xml_path)],
        cwd=str(xml_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    after = [path.resolve() for path in xml_path.parent.glob("*.bgl") if path.resolve() not in before]
    if result.returncode != 0:
        raise RuntimeError(f"BglComp 退出代码 {result.returncode}: {result.stderr or result.stdout}")
    produced = next((path for path in after if path.is_file()), None)
    if produced is None:
        raise RuntimeError("BglComp 未在 XML 目录生成 BGL；请确认编译器版本和调用契约")
    produced.replace(output_bgl)
    return {
        "compiler": str(compiler.path),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output": str(output_bgl),
    }
