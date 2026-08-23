from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

from .official_index import OfficialNavaidIndex


LogicalIdentity = tuple[str, str, str]


def logical_waypoint_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized.startswith("V"):
        return "VOR"
    if normalized.startswith("N"):
        return "NDB"
    return "NAMED"


def _distance_nm(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    earth_radius_nm = 3440.065
    first_lat = math.radians(first_latitude)
    second_lat = math.radians(second_latitude)
    delta_lat = second_lat - first_lat
    delta_lon = math.radians(second_longitude - first_longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat)
        * math.cos(second_lat)
        * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_nm * math.asin(math.sqrt(min(1.0, value)))


@dataclass(frozen=True)
class OfficialOverlayNavaid:
    kind: str
    ident: str
    region: str
    frequency_khz: float
    latitude: float
    longitude: float
    magnetic_variation: float | None
    elevation_ft: int | None


@dataclass(frozen=True)
class OfficialOverlayIndex:
    """Verified official identities used to prevent duplicate overlay records."""

    database: Path
    navaids: tuple[OfficialOverlayNavaid, ...]
    waypoint_identities: frozenset[LogicalIdentity]
    airway_edges: tuple[
        tuple[str, LogicalIdentity, float, float, LogicalIdentity, float, float],
        ...,
    ]

    def canonicalize_navaid(self, navaid):
        """Keep the custom endpoint record, but use official facility fields."""
        kind = (navaid.kind or "").strip().upper()
        ident = (navaid.ident or "").strip().upper()
        region = (navaid.country or "").strip().upper()[:2]
        for item in self.navaids:
            if (item.kind, item.ident, item.region) != (kind, ident, region):
                continue
            if _distance_nm(
                float(navaid.latitude),
                float(navaid.longitude),
                item.latitude,
                item.longitude,
            ) > 0.25:
                continue
            frequency = (
                item.frequency_khz / 1000
                if kind == "VOR"
                else item.frequency_khz / 100
            )
            return replace(
                navaid,
                latitude=item.latitude,
                longitude=item.longitude,
                frequency=frequency,
                magnetic_variation=(
                    item.magnetic_variation
                    if item.magnetic_variation is not None
                    else navaid.magnetic_variation
                ),
                elevation_ft=(
                    item.elevation_ft
                    if item.elevation_ft is not None
                    else navaid.elevation_ft
                ),
            )
        return navaid

    def has_official_navaid(self, navaid) -> bool:
        """Return true when the official package already owns this facility.

        The overlay must not replace an official facility with a same-identity
        source correction: MSFS merges both packages by identity and can then
        attach airway links to the wrong physical record.
        """
        kind = (navaid.kind or "").strip().upper()
        ident = (navaid.ident or "").strip().upper()
        region = (navaid.country or "").strip().upper()[:2]
        for item in self.navaids:
            if (item.kind, item.ident, item.region) != (kind, ident, region):
                continue
            if _distance_nm(
                float(navaid.latitude),
                float(navaid.longitude),
                item.latitude,
                item.longitude,
            ) <= 0.25:
                return True
        return False

    def has_official_airway_edge(self, airway: str, leg) -> bool:
        name = (airway or "").strip().upper()
        start = (
            logical_waypoint_type(leg.start_type),
            (leg.start_country or "").strip().upper()[:2],
            (leg.start_ident or "").strip().upper(),
        )
        end = (
            logical_waypoint_type(leg.end_type),
            (leg.end_country or "").strip().upper()[:2],
            (leg.end_ident or "").strip().upper(),
        )
        for (
            official_name,
            official_start,
            official_start_latitude,
            official_start_longitude,
            official_end,
            official_end_latitude,
            official_end_longitude,
        ) in self.airway_edges:
            if official_name != name:
                continue
            same_direction = start == official_start and end == official_end
            reverse_direction = start == official_end and end == official_start
            if not (same_direction or reverse_direction):
                continue
            if same_direction:
                first = (
                    leg.start_latitude,
                    leg.start_longitude,
                    official_start_latitude,
                    official_start_longitude,
                )
                second = (
                    leg.end_latitude,
                    leg.end_longitude,
                    official_end_latitude,
                    official_end_longitude,
                )
            else:
                first = (
                    leg.start_latitude,
                    leg.start_longitude,
                    official_end_latitude,
                    official_end_longitude,
                )
                second = (
                    leg.end_latitude,
                    leg.end_longitude,
                    official_start_latitude,
                    official_start_longitude,
                )
            if None in first or None in second:
                continue
            if (
                _distance_nm(*map(float, first)) <= 0.01
                and _distance_nm(*map(float, second)) <= 0.01
            ):
                return True
        return False

    def to_report(self) -> dict[str, object]:
        return {
            "verified": True,
            "database": str(self.database),
            "official_navaids": len(self.navaids),
            "official_waypoint_identities": len(self.waypoint_identities),
            "official_airway_edges": len(self.airway_edges),
        }


def load_official_overlay(index: OfficialNavaidIndex) -> OfficialOverlayIndex:
    """Load only identity/connection facts from an already verified index."""

    database = index.database.expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0]).lower()
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"waypoint", "airway"}
        missing = sorted(required - tables)
        if missing:
            raise ValueError(
                "官方设施索引缺少覆盖冲突表: " + ", ".join(missing)
            )
        waypoint_columns = {
            str(row[1]).lower()
            for row in connection.execute('PRAGMA table_info("waypoint")')
        }
        airway_columns = {
            str(row[1]).lower()
            for row in connection.execute('PRAGMA table_info("airway")')
        }
        required_waypoint = {"ident", "region", "type", "laty", "lonx"}
        required_airway = {
            "airway_name",
            "from_waypoint_id",
            "to_waypoint_id",
        }
        if missing := sorted(required_waypoint - waypoint_columns):
            raise ValueError(
                "官方 waypoint 表缺少覆盖字段: " + ", ".join(missing)
            )
        if missing := sorted(required_airway - airway_columns):
            raise ValueError(
                "官方 airway 表缺少覆盖字段: " + ", ".join(missing)
            )
        waypoint_rows = connection.execute(
            """
            SELECT waypoint_id, ident, region, type, laty, lonx
            FROM waypoint
            ORDER BY waypoint_id
            """
        ).fetchall()
        waypoint_by_id: dict[int, tuple[LogicalIdentity, float, float]] = {}
        waypoint_identities: set[LogicalIdentity] = set()
        for row in waypoint_rows:
            identity = (
                logical_waypoint_type(str(row["type"] or "")),
                str(row["region"] or "").strip().upper()[:2],
                str(row["ident"] or "").strip().upper(),
            )
            if not identity[1] or not identity[2]:
                continue
            latitude = float(row["laty"])
            longitude = float(row["lonx"])
            waypoint_by_id[int(row["waypoint_id"])] = (
                identity,
                latitude,
                longitude,
            )
            waypoint_identities.add(identity)
        airway_rows = connection.execute(
            """
            SELECT airway_name, from_waypoint_id, to_waypoint_id
            FROM airway
            ORDER BY airway_name, airway_fragment_no, sequence_no
            """
        ).fetchall()
        airway_edges = []
        for row in airway_rows:
            start = waypoint_by_id.get(int(row["from_waypoint_id"]))
            end = waypoint_by_id.get(int(row["to_waypoint_id"]))
            if start is None or end is None:
                continue
            airway_edges.append((
                str(row["airway_name"] or "").strip().upper(),
                start[0],
                start[1],
                start[2],
                end[0],
                end[1],
                end[2],
            ))
    finally:
        connection.close()

    navaids = tuple(
        OfficialOverlayNavaid(
            kind=item.kind,
            ident=item.ident,
            region=item.region,
            frequency_khz=item.frequency_khz,
            latitude=item.latitude,
            longitude=item.longitude,
            magnetic_variation=item.magnetic_variation,
            elevation_ft=item.elevation_ft,
        )
        for item in index.baseline.records
    )
    return OfficialOverlayIndex(
        database=database,
        navaids=navaids,
        waypoint_identities=frozenset(waypoint_identities),
        airway_edges=tuple(airway_edges),
    )
