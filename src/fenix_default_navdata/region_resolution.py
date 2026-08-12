from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .baseline import BaselineNavaid
from .model import AirwayLeg, NavModel, Waypoint
from .official_index import OfficialNavaidIndex, OfficialWaypoint


_EARTH_RADIUS_NM = 3440.065
OFFICIAL_REGION_TOLERANCE_NM = 0.01
_ENDPOINT_KINDS = {
    "DESIGNATED_POINT": "WAYPOINT",
    "地名点": "WAYPOINT",
    "VORDME": "VOR",
    "NDB": "NDB",
}


class RegionResolutionError(RuntimeError):
    """官方索引不能安全用于恢复 424 航路区域码时抛出的错误。"""


@dataclass(frozen=True)
class _RegionMatch:
    status: str
    region: str = ""
    candidate_regions: tuple[str, ...] = ()


@dataclass(frozen=True)
class OfficialRegionResolution:
    """只用可信官方索引恢复空白 424 区域码的可审计统计。"""

    coordinate_tolerance_nm: float
    waypoint_blank_before: int
    waypoint_recovered: int
    waypoint_ambiguous: int
    waypoint_unmatched: int
    airway_endpoint_blank_before: int
    airway_endpoint_recovered: int
    airway_endpoint_ambiguous: int
    airway_endpoint_unmatched: int
    airway_endpoint_unsupported_type: int
    airway_endpoint_missing_coordinate: int
    airway_endpoint_blank_after: int
    airway_leg_count: int
    airway_legs_resolved_before: int
    airway_legs_resolved_after: int

    @property
    def verified(self) -> bool:
        return True

    def to_report(self) -> dict[str, object]:
        return {
            "verified": self.verified,
            "coordinate_tolerance_nm": self.coordinate_tolerance_nm,
            "waypoints": {
                "blank_before": self.waypoint_blank_before,
                "recovered": self.waypoint_recovered,
                "ambiguous": self.waypoint_ambiguous,
                "unmatched": self.waypoint_unmatched,
                "blank_after": self.waypoint_blank_before - self.waypoint_recovered,
            },
            "airway_endpoints": {
                "blank_before": self.airway_endpoint_blank_before,
                "recovered": self.airway_endpoint_recovered,
                "ambiguous": self.airway_endpoint_ambiguous,
                "unmatched": self.airway_endpoint_unmatched,
                "unsupported_type": self.airway_endpoint_unsupported_type,
                "missing_coordinate": self.airway_endpoint_missing_coordinate,
                "blank_after": self.airway_endpoint_blank_after,
            },
            "airway_legs": {
                "total": self.airway_leg_count,
                "resolved_before": self.airway_legs_resolved_before,
                "resolved_after": self.airway_legs_resolved_after,
                "skipped_before": (
                    self.airway_leg_count - self.airway_legs_resolved_before
                ),
                "skipped_after": (
                    self.airway_leg_count - self.airway_legs_resolved_after
                ),
            },
        }


def _distance_nm(
    latitude: float,
    longitude: float,
    candidate_latitude: float,
    candidate_longitude: float,
) -> float:
    first_latitude = math.radians(latitude)
    second_latitude = math.radians(candidate_latitude)
    delta_latitude = second_latitude - first_latitude
    delta_longitude = math.radians(candidate_longitude - longitude)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first_latitude)
        * math.cos(second_latitude)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_NM * math.asin(math.sqrt(min(1.0, value)))


def _records_by_ident(
    records: tuple[BaselineNavaid, ...] | tuple[OfficialWaypoint, ...],
) -> dict[str, tuple[BaselineNavaid | OfficialWaypoint, ...]]:
    grouped: dict[str, list[BaselineNavaid | OfficialWaypoint]] = {}
    for item in records:
        grouped.setdefault(item.ident.upper(), []).append(item)
    return {
        ident: tuple(items)
        for ident, items in grouped.items()
    }


def _match_region(
    records: dict[str, tuple[BaselineNavaid | OfficialWaypoint, ...]],
    ident: str,
    latitude: float,
    longitude: float,
    coordinate_tolerance_nm: float,
) -> _RegionMatch:
    candidates = records.get((ident or "").strip().upper(), ())
    regions = {
        item.region.upper()[:2]
        for item in candidates
        if _distance_nm(latitude, longitude, item.latitude, item.longitude)
        <= coordinate_tolerance_nm
    }
    if len(regions) == 1:
        return _RegionMatch("recovered", next(iter(regions)))
    if len(regions) > 1:
        return _RegionMatch("ambiguous", candidate_regions=tuple(sorted(regions)))
    return _RegionMatch("unmatched")


def _fully_resolved(leg: AirwayLeg) -> bool:
    return bool(
        leg.start_country
        and leg.end_country
        and leg.start_latitude is not None
        and leg.start_longitude is not None
        and leg.end_latitude is not None
        and leg.end_longitude is not None
    )


def _resolve_endpoint(
    *,
    endpoint_type: str,
    ident: str,
    latitude: float | None,
    longitude: float | None,
    indexes: dict[str, dict[str, tuple[BaselineNavaid | OfficialWaypoint, ...]]],
    coordinate_tolerance_nm: float,
) -> _RegionMatch:
    kind = _ENDPOINT_KINDS.get((endpoint_type or "").strip().upper())
    if kind is None:
        return _RegionMatch("unsupported_type")
    if latitude is None or longitude is None:
        return _RegionMatch("missing_coordinate")
    return _match_region(
        indexes[kind],
        ident,
        latitude,
        longitude,
        coordinate_tolerance_nm,
    )


def restore_regions_from_official_index(
    model: NavModel,
    official_index: OfficialNavaidIndex,
    *,
    coordinate_tolerance_nm: float = OFFICIAL_REGION_TOLERANCE_NM,
) -> OfficialRegionResolution:
    """Restore only uniquely proven blank 424 regions in the default adapter.

    The raw loader deliberately remains unaware of Community data.  This
    adapter-level pass queries a trusted, provenance-checked official index
    only for a region key.  It never copies official waypoints, navaids, or
    routes into the source model.
    """
    if not official_index.verified:
        raise RegionResolutionError("官方索引未通过验证，不能恢复航路端点区域")
    if (
        coordinate_tolerance_nm <= 0
        or not math.isfinite(coordinate_tolerance_nm)
    ):
        raise ValueError("官方区域匹配坐标阈值必须为正数")
    indexes = {
        "VOR": _records_by_ident(tuple(
            item for item in official_index.baseline.records if item.kind == "VOR"
        )),
        "NDB": _records_by_ident(tuple(
            item for item in official_index.baseline.records if item.kind == "NDB"
        )),
        "WAYPOINT": _records_by_ident(official_index.waypoints),
    }
    if not indexes["VOR"] or not indexes["NDB"] or not indexes["WAYPOINT"]:
        raise RegionResolutionError("官方索引缺少 VOR、NDB 或航点记录，不能恢复区域")

    waypoint_blank_before = sum(1 for point in model.waypoints if not point.country)
    waypoint_recovered = 0
    waypoint_ambiguous = 0
    waypoint_unmatched = 0
    updated_waypoints: list[Waypoint] = []
    for point in model.waypoints:
        if point.country:
            updated_waypoints.append(point)
            continue
        result = _match_region(
            indexes["WAYPOINT"],
            point.ident,
            point.latitude,
            point.longitude,
            coordinate_tolerance_nm,
        )
        if result.status == "recovered":
            waypoint_recovered += 1
            updated_waypoints.append(replace(point, country=result.region))
        else:
            if result.status == "ambiguous":
                waypoint_ambiguous += 1
            else:
                waypoint_unmatched += 1
            updated_waypoints.append(point)

    airway_legs_resolved_before = sum(
        1 for leg in model.airway_legs if _fully_resolved(leg)
    )
    airway_endpoint_blank_before = 0
    airway_endpoint_recovered = 0
    airway_endpoint_ambiguous = 0
    airway_endpoint_unmatched = 0
    airway_endpoint_unsupported_type = 0
    airway_endpoint_missing_coordinate = 0
    updated_legs: list[AirwayLeg] = []
    for leg in model.airway_legs:
        start_country = leg.start_country
        end_country = leg.end_country
        for side in ("start", "end"):
            country = start_country if side == "start" else end_country
            if country:
                continue
            airway_endpoint_blank_before += 1
            result = _resolve_endpoint(
                endpoint_type=getattr(leg, f"{side}_type"),
                ident=getattr(leg, f"{side}_ident"),
                latitude=getattr(leg, f"{side}_latitude"),
                longitude=getattr(leg, f"{side}_longitude"),
                indexes=indexes,
                coordinate_tolerance_nm=coordinate_tolerance_nm,
            )
            if result.status == "recovered":
                airway_endpoint_recovered += 1
                if side == "start":
                    start_country = result.region
                else:
                    end_country = result.region
            elif result.status == "ambiguous":
                airway_endpoint_ambiguous += 1
            elif result.status == "unsupported_type":
                airway_endpoint_unsupported_type += 1
            elif result.status == "missing_coordinate":
                airway_endpoint_missing_coordinate += 1
            else:
                airway_endpoint_unmatched += 1
        updated_legs.append(replace(
            leg,
            start_country=start_country,
            end_country=end_country,
        ))

    model.waypoints = updated_waypoints
    model.airway_legs = updated_legs
    airway_endpoint_blank_after = sum(
        int(not leg.start_country) + int(not leg.end_country)
        for leg in model.airway_legs
    )
    airway_legs_resolved_after = sum(
        1 for leg in model.airway_legs if _fully_resolved(leg)
    )
    return OfficialRegionResolution(
        coordinate_tolerance_nm=coordinate_tolerance_nm,
        waypoint_blank_before=waypoint_blank_before,
        waypoint_recovered=waypoint_recovered,
        waypoint_ambiguous=waypoint_ambiguous,
        waypoint_unmatched=waypoint_unmatched,
        airway_endpoint_blank_before=airway_endpoint_blank_before,
        airway_endpoint_recovered=airway_endpoint_recovered,
        airway_endpoint_ambiguous=airway_endpoint_ambiguous,
        airway_endpoint_unmatched=airway_endpoint_unmatched,
        airway_endpoint_unsupported_type=airway_endpoint_unsupported_type,
        airway_endpoint_missing_coordinate=airway_endpoint_missing_coordinate,
        airway_endpoint_blank_after=airway_endpoint_blank_after,
        airway_leg_count=len(model.airway_legs),
        airway_legs_resolved_before=airway_legs_resolved_before,
        airway_legs_resolved_after=airway_legs_resolved_after,
    )
