from __future__ import annotations

import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from .model import (
    Airport,
    ChartTerminalLeg,
    Holding,
    Ils,
    Navaid,
    NavModel,
    ProcedureSegment,
    RejectedRecord,
    Runway,
    SourceRef,
    TerminalWaypoint,
    Waypoint,
    is_china_icao,
)
from .profile import Cycle
from .source import load_naip


FENIX_ENROUTE_WAYPOINT_START = 329291
FENIX_ENROUTE_VOR_START = 11396
FENIX_VOR_TYPES = {"1", "2", "3", "4", "9"}
FENIX_NDB_TYPES = {"5", "7"}
PROCEDURE_KINDS = {"1": "arrival", "2": "departure", "3": "approach"}
SDK_LEG_TYPES = {
    "AF", "CA", "CD", "CF", "CI", "CR", "DF", "FA", "FC", "FD", "FM",
    "HA", "HF", "HM", "IF", "PI", "RF", "TF", "VA", "VD", "VI", "VM", "VR",
}
SDK_FIX_REQUIRED_LEG_TYPES = {
    "AF", "CF", "DF", "FA", "FC", "FD", "FM", "HA", "HF", "HM", "IF", "PI",
    "RF", "TF",
}


class FenixSourceError(RuntimeError):
    """Raised when the Fenix database cannot satisfy the source contract."""


def decode_fenix_frequency(value: int | None, *, kind: str) -> float | None:
    """Decode Fenix's BCD-packed VHF/ILS and NDB frequencies."""
    if not value:
        return None
    shift = 12 if kind in {"vor", "ils"} else 16
    digits = f"{int(value) >> shift:X}"
    if not digits or any(character not in "0123456789" for character in digits):
        raise FenixSourceError(f"无法解码 Fenix {kind} 频率: {value}")
    return int(digits) / 10.0 if kind in {"vor", "ils"} else float(int(digits))


def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _validate_cycle(connection: sqlite3.Connection, cycle: Cycle) -> None:
    config = dict(connection.execute("SELECT key, val FROM config"))
    expected = f"{cycle.number}n{cycle.revision}"
    actual = str(config.get("CycleName") or "").strip().lower()
    if actual != expected.lower():
        raise FenixSourceError(f"Fenix 周期不匹配: 需要 {expected}，实际 {actual or '空'}")


def _altitudes(value: str | None) -> tuple[str | None, int | None, int | None]:
    raw = (value or "").strip().upper()
    match = re.fullmatch(r"(FL)?(\d+)([AB+\-])?(?:(FL)?(\d+)([AB+\-])?)?", raw)
    if not match:
        return None, None, None
    first = int(match.group(2)) * (100 if match.group(1) else 1)
    second = int(match.group(5)) * (100 if match.group(4) else 1) if match.group(5) else None
    descriptor = {"A": "+", "+": "+", "B": "-", "-": "-"}.get(match.group(3))
    return descriptor, first, second


def _great_circle_nm(
    latitude1: float | None,
    longitude1: float | None,
    latitude2: float | None,
    longitude2: float | None,
) -> float | None:
    if None in {latitude1, longitude1, latitude2, longitude2}:
        return None
    lat1, lon1 = math.radians(float(latitude1)), math.radians(float(longitude1))
    lat2, lon2 = math.radians(float(latitude2)), math.radians(float(longitude2))
    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_longitude / 2) ** 2
    )
    return round(3440.065 * 2 * math.asin(min(1.0, math.sqrt(value))), 3)


def _fix_type(navaid_type: str | None, *, terminal: bool) -> str:
    if navaid_type in FENIX_VOR_TYPES:
        return "VOR"
    if navaid_type in FENIX_NDB_TYPES:
        return "TERMINAL_NDB" if terminal else "NDB"
    return "TERMINAL_WAYPOINT" if terminal else "WAYPOINT"


def _leg_type(track_code: str | None) -> str | None:
    value = str(track_code or "IF").strip().upper()
    if value.startswith("RWY"):
        value = value.removeprefix("RWY")
    return value if value in SDK_LEG_TYPES else None


def _load_airports(connection: sqlite3.Connection, model: NavModel) -> dict[int, str]:
    model.airports.clear()
    result: dict[int, str] = {}
    for row in connection.execute("SELECT * FROM Airports WHERE ICAO IS NOT NULL ORDER BY ID"):
        icao = str(row["ICAO"]).strip().upper()
        if not is_china_icao(icao):
            continue
        key = f"fenix-airport:{row['ID']}"
        result[int(row["ID"])] = key
        model.airports[key] = Airport(
            key=key,
            icao=icao,
            name=str(row["Name"] or icao),
            latitude=float(row["Latitude"] or 0),
            longitude=float(row["Longtitude"] or 0),
            elevation_ft=int(row["Elevation"] or 0),
            transition_altitude=int(row["TransitionAltitude"] or 0),
            transition_level=int(row["TransitionLevel"] or 0),
            source=SourceRef("Fenix:Airports", int(row["ID"])),
        )
    return result


def _load_runways(
    connection: sqlite3.Connection,
    model: NavModel,
    airport_keys: dict[int, str],
) -> dict[int, Runway]:
    model.runways.clear()
    result: dict[int, Runway] = {}
    for row in connection.execute("SELECT * FROM Runways WHERE AirportID IS NOT NULL ORDER BY ID"):
        airport_key = airport_keys.get(int(row["AirportID"]))
        if airport_key is None:
            continue
        runway = Runway(
            key=f"fenix-runway:{row['ID']}",
            airport_key=airport_key,
            ident=str(row["Ident"] or "").strip().upper(),
            true_heading=float(row["TrueHeading"] or 0),
            length_ft=int(row["Length"] or 0),
            width_ft=int(row["Width"] or 0),
            surface=str(row["Surface"] or "U"),
            elevation_ft=int(row["Elevation"] or 0),
            source=SourceRef("Fenix:Runways", int(row["ID"])),
            latitude=float(row["Latitude"] or 0),
            longitude=float(row["Longtitude"] or 0),
        )
        model.runways.append(runway)
        result[int(row["ID"])] = runway
    return result


def _load_ilses(
    connection: sqlite3.Connection,
    model: NavModel,
    runways: dict[int, Runway],
) -> None:
    model.ilses.clear()
    for row in connection.execute("SELECT * FROM ILSes WHERE RunwayID IS NOT NULL ORDER BY ID"):
        runway = runways.get(int(row["RunwayID"]))
        if runway is None:
            continue
        airport = model.airports[runway.airport_key]
        frequency = decode_fenix_frequency(row["Freq"], kind="ils")
        if frequency is None:
            continue
        latitude = float(row["Latitude"] or 0)
        longitude = float(row["Longtitude"] or 0)
        elevation_meters = float(row["Elevation"] or 0) * 0.3048
        model.ilses.append(Ils(
            airport=airport.icao,
            runway=runway.ident,
            ident=str(row["Ident"] or "").strip().upper(),
            frequency_mhz=frequency,
            category=str(row["Category"] or "") or None,
            localizer_latitude=latitude,
            localizer_longitude=longitude,
            localizer_course_magnetic=(
                float(row["LocCourse"]) if row["LocCourse"] is not None else None
            ),
            glide_slope_degrees=(
                float(row["GsAngle"]) if row["GsAngle"] is not None else None
            ),
            crossing_height_meters=(
                float(row["CrossingHeight"]) * 0.3048
                if row["CrossingHeight"] not in {None, ""}
                else None
            ),
            glide_slope_latitude=latitude,
            glide_slope_longitude=longitude,
            dme_latitude=latitude if row["HasDme"] else None,
            dme_longitude=longitude if row["HasDme"] else None,
            dme_elevation_meters=elevation_meters if row["HasDme"] else None,
            source=SourceRef("Fenix:ILSes", int(row["ID"])),
        ))


def _load_enroute_points(connection: sqlite3.Connection, model: NavModel) -> None:
    countries = {
        int(row["ID"]): str(row["Country"] or "")
        for row in connection.execute("SELECT ID, Country FROM WaypointLookup")
    }
    existing = {
        (point.ident.upper(), round(point.latitude, 6), round(point.longitude, 6))
        for point in model.waypoints
    }
    for row in connection.execute(
        "SELECT * FROM Waypoints WHERE ID>=? AND NavaidID IS NULL ORDER BY ID",
        (FENIX_ENROUTE_WAYPOINT_START,),
    ):
        ident = str(row["Ident"] or "").strip().upper()
        if not ident:
            continue
        key = (ident, round(float(row["Latitude"]), 6), round(float(row["Longtitude"]), 6))
        if key in existing:
            continue
        existing.add(key)
        model.waypoints.append(Waypoint(
            key=f"fenix-waypoint:{row['ID']}",
            ident=ident,
            name=str(row["Name"] or ident),
            latitude=float(row["Latitude"]),
            longitude=float(row["Longtitude"]),
            source=SourceRef("Fenix:Waypoints", int(row["ID"])),
            country=countries.get(int(row["ID"]), ""),
        ))


def _load_navaids(connection: sqlite3.Connection, model: NavModel) -> None:
    countries = {
        int(row["ID"]): str(row["Country"] or "")
        for row in connection.execute("SELECT ID, Country FROM NavaidLookup")
    }
    model.navaids.clear()
    for row in connection.execute("SELECT * FROM Navaids ORDER BY ID"):
        identifier = int(row["ID"])
        navaid_type = str(row["Type"] or "")
        country = countries.get(identifier, "")
        if navaid_type in FENIX_VOR_TYPES:
            if identifier < FENIX_ENROUTE_VOR_START:
                continue
            kind = "VOR"
            frequency = decode_fenix_frequency(row["Freq"], kind="vor")
        elif navaid_type in FENIX_NDB_TYPES:
            if not is_china_icao(country):
                continue
            kind = "NDB"
            frequency = decode_fenix_frequency(row["Freq"], kind="ndb")
        else:
            continue
        if frequency is None:
            continue
        model.navaids.append(Navaid(
            key=f"fenix-navaid:{identifier}",
            ident=str(row["Ident"] or "").strip().upper(),
            kind=kind,
            name=str(row["Name"] or row["Ident"] or ""),
            latitude=float(row["Latitude"] or 0),
            longitude=float(row["Longtitude"] or 0),
            frequency=frequency,
            magnetic_variation=float(row["MagneticVariation"] or 0),
            elevation_ft=int(row["Elevation"] or 0),
            country=country,
            source=SourceRef("Fenix:Navaids", identifier),
            terminal=navaid_type == "7",
        ))


def _load_procedures(
    connection: sqlite3.Connection,
    model: NavModel,
    airport_keys: dict[int, str],
) -> None:
    model.procedure_segments.clear()
    model.terminal_waypoints.clear()
    terminal_points: dict[tuple[str, str, str, float, float], TerminalWaypoint] = {}
    query = """
        WITH waypoint_country AS (
            SELECT ID, MIN(Country) AS Country
            FROM WaypointLookup
            GROUP BY ID
        ),
        navaid_country AS (
            SELECT ID, MIN(Country) AS Country
            FROM NavaidLookup
            GROUP BY ID
        )
        SELECT
            t.ID AS terminal_id, t.AirportID AS airport_id, t.Proc AS proc,
            t.FullName AS full_name, t.Name AS procedure_name, t.Rwy AS runway,
            l.*, x.IsFlyOver, x.SpeedLimit, x.SpeedLimitDescription,
            w.Ident AS fix_ident, w.Latitude AS fix_latitude, w.Longtitude AS fix_longitude,
            wn.Type AS fix_navaid_type, wl.Country AS fix_country,
            n.Ident AS recommended_ident, n.Type AS recommended_navaid_type,
            nl.Country AS recommended_country,
            c.Ident AS center_ident, c.Latitude AS center_latitude,
            c.Longtitude AS center_longitude, cn.Type AS center_navaid_type,
            cl.Country AS center_country
        FROM TerminalLegs l
        JOIN Terminals t ON t.ID=l.TerminalID
        LEFT JOIN TerminalLegsEx x ON x.ID=l.ID
        LEFT JOIN Waypoints w ON w.ID=l.WptID
        LEFT JOIN Navaids wn ON wn.ID=w.NavaidID
        LEFT JOIN waypoint_country wl ON wl.ID=w.ID
        LEFT JOIN Navaids n ON n.ID=l.NavID
        LEFT JOIN navaid_country nl ON nl.ID=n.ID
        LEFT JOIN Waypoints c ON c.ID=l.CenterID
        LEFT JOIN Navaids cn ON cn.ID=c.NavaidID
        LEFT JOIN waypoint_country cl ON cl.ID=c.ID
        WHERE t.AirportID IS NOT NULL
        ORDER BY t.ID, l.ID
    """
    active_key: tuple[int, str, str] | None = None
    active_header: sqlite3.Row | None = None
    active_legs: list[ChartTerminalLeg] = []

    def flush() -> None:
        if active_key is None or active_header is None or not active_legs:
            return
        airport_key = airport_keys.get(int(active_header["airport_id"]))
        kind = PROCEDURE_KINDS.get(str(active_header["proc"] or ""))
        if airport_key is None or kind is None:
            return
        airport = model.airports[airport_key]
        transition = active_key[2]
        model.procedure_segments.append(ProcedureSegment(
            airport=airport.icao,
            label=str(active_header["procedure_name"] or active_header["full_name"] or "")[:6],
            kind=kind,
            runway=str(active_header["runway"] or "").strip().upper(),
            transition="" if transition == "ALL" else transition,
            legs=tuple(active_legs),
            source=SourceRef("Fenix:Terminals", int(active_header["terminal_id"])),
            fenix_name=str(active_header["full_name"] or active_header["procedure_name"] or ""),
        ))

    for row in connection.execute(query):
        airport_key = airport_keys.get(int(row["airport_id"]))
        if airport_key is None:
            continue
        key = (
            int(row["terminal_id"]),
            str(row["Type"] or ""),
            str(row["Transition"] or "").strip().upper(),
        )
        if active_key is not None and key != active_key:
            flush()
            active_legs = []
        active_key = key
        active_header = row
        airport = model.airports[airport_key]
        fix_ident = str(row["fix_ident"] or "").strip().upper() or None
        fix_country = str(row["fix_country"] or airport.icao[:2])
        center_ident = str(row["center_ident"] or "").strip().upper() or None
        center_country = str(row["center_country"] or airport.icao[:2])
        altitude_descriptor, altitude1, altitude2 = _altitudes(row["Alt"])
        arc_radius = (
            _great_circle_nm(
                row["center_latitude"],
                row["center_longitude"],
                row["fix_latitude"],
                row["fix_longitude"],
            )
            if str(row["TrackCode"] or "").strip().upper() == "RF"
            else None
        )
        leg_type = _leg_type(row["TrackCode"])
        if leg_type is None:
            model.rejected_records.append(RejectedRecord(
                kind="terminal-leg",
                key=str(row["ID"]),
                reason=f"unsupported Fenix TrackCode: {row['TrackCode']!r}",
                source=SourceRef("Fenix:TerminalLegs", int(row["ID"])),
            ))
            continue
        if leg_type in SDK_FIX_REQUIRED_LEG_TYPES and fix_ident is None:
            model.rejected_records.append(RejectedRecord(
                kind="terminal-leg",
                key=str(row["ID"]),
                reason=f"{leg_type} leg is missing its required fix",
                source=SourceRef("Fenix:TerminalLegs", int(row["ID"])),
            ))
            continue
        active_legs.append(ChartTerminalLeg(
            procedure_label=str(row["procedure_name"] or "")[:6],
            runway=str(row["runway"] or "").strip().upper(),
            leg_type=leg_type,
            fix_ident=fix_ident,
            raw=f"Fenix TerminalLegs.ID={row['ID']}",
            procedure_kind=PROCEDURE_KINDS.get(str(row["proc"] or ""), ""),
            course_degrees=float(row["Course"]) if row["Course"] is not None else None,
            turn_direction=str(row["TurnDir"] or "") or None,
            speed_limit_knots=(
                int(row["SpeedLimit"]) if row["SpeedLimit"] is not None else None
            ),
            transition="" if key[2] == "ALL" else key[2],
            center_ident=center_ident,
            sequence=int(row["ID"]),
            fix_region=fix_country,
            fix_type=(
                "RUNWAY"
                if str(row["TrackCode"] or "").strip().upper().startswith("RWY")
                else _fix_type(row["fix_navaid_type"], terminal=True)
            ),
            fix_latitude=(
                float(row["fix_latitude"])
                if row["fix_latitude"] is not None
                else row["WptLat"]
            ),
            fix_longitude=(
                float(row["fix_longitude"])
                if row["fix_longitude"] is not None
                else row["WptLon"]
            ),
            fly_over=bool(row["IsFlyOver"]),
            recommended_ident=str(row["recommended_ident"] or "") or None,
            recommended_region=str(row["recommended_country"] or ""),
            recommended_type=_fix_type(row["recommended_navaid_type"], terminal=False),
            recommended_latitude=(
                float(row["NavLat"]) if row["NavLat"] is not None else None
            ),
            recommended_longitude=(
                float(row["NavLon"]) if row["NavLon"] is not None else None
            ),
            theta_degrees=(
                float(row["NavBear"]) if row["NavBear"] is not None else None
            ),
            rho_nm=float(row["NavDist"]) if row["NavDist"] is not None else None,
            distance_nm=float(row["Distance"]) if row["Distance"] is not None else None,
            altitude_descriptor=altitude_descriptor,
            altitude1_ft=altitude1,
            altitude2_ft=altitude2,
            vertical_angle=float(row["Vnav"]) if row["Vnav"] is not None else None,
            center_region=center_country,
            center_latitude=(
                float(row["center_latitude"])
                if row["center_latitude"] is not None
                else row["CenterLat"]
            ),
            center_longitude=(
                float(row["center_longitude"])
                if row["center_longitude"] is not None
                else row["CenterLon"]
            ),
            arc_radius_nm=arc_radius,
            waypoint_description_code=str(row["WptDescCode"] or ""),
            speed_limit_descriptor=str(row["SpeedLimitDescription"] or "") or None,
        ))
        for ident, country, latitude, longitude, point_id in (
            (fix_ident, fix_country, row["fix_latitude"], row["fix_longitude"], row["WptID"]),
            (
                center_ident,
                center_country,
                row["center_latitude"],
                row["center_longitude"],
                row["CenterID"],
            ),
        ):
            if not ident or latitude is None or longitude is None or point_id is None:
                continue
            point_key = (airport.icao, country, ident, float(latitude), float(longitude))
            terminal_points.setdefault(point_key, TerminalWaypoint(
                key=f"fenix-terminal-waypoint:{point_id}",
                airport=airport.icao,
                ident=ident,
                latitude=float(latitude),
                longitude=float(longitude),
                source=SourceRef("Fenix:Waypoints", int(point_id)),
                country=country,
            ))
    flush()
    model.terminal_waypoints.extend(terminal_points.values())


def _load_holdings(connection: sqlite3.Connection, model: NavModel) -> None:
    model.holdings.clear()
    for row_number, row in enumerate(connection.execute("SELECT * FROM Holdings"), start=1):
        region = str(row["icao_code"] or "")
        if not is_china_icao(region):
            continue
        model.holdings.append(Holding(
            name=str(row["holding_name"] or row["waypoint_identifier"] or ""),
            fix_ident=str(row["waypoint_identifier"] or "").strip().upper(),
            fix_region=region,
            latitude=float(row["waypoint_latitude"] or 0),
            longitude=float(row["waypoint_longitude"] or 0),
            inbound_course=(
                float(row["inbound_holding_course"])
                if row["inbound_holding_course"] is not None
                else None
            ),
            turn_direction=str(row["turn_direction"] or "R"),
            length_nm=float(row["leg_length"]) if row["leg_length"] is not None else None,
            time_minutes=float(row["leg_time"]) if row["leg_time"] is not None else None,
            minimum_altitude_ft=(
                int(row["minimum_altitude"]) if row["minimum_altitude"] is not None else None
            ),
            maximum_altitude_ft=(
                int(row["maximum_altitude"]) if row["maximum_altitude"] is not None else None
            ),
            speed_limit_knots=(
                int(row["holding_speed"]) if row["holding_speed"] is not None else None
            ),
            source=SourceRef("Fenix:Holdings", row_number),
        ))


def load_fenix_model(fenix_db: Path, raw_root: Path, cycle: Cycle) -> NavModel:
    """Build the normalized 2608 model from Fenix plus structured 424 routes."""
    model = load_naip(raw_root, include_terminal_documents=False)
    with closing(_open_readonly(fenix_db)) as connection:
        _validate_cycle(connection, cycle)
        airport_keys = _load_airports(connection, model)
        runways = _load_runways(connection, model, airport_keys)
        _load_ilses(connection, model, runways)
        _load_enroute_points(connection, model)
        _load_navaids(connection, model)
        _load_procedures(connection, model, airport_keys)
        _load_holdings(connection, model)
    return model
