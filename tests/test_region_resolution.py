from pathlib import Path

import pytest

from fenix_default_navdata.baseline import BaselineIndex, BaselineNavaid
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint
from fenix_default_navdata.official_index import OfficialNavaidIndex, OfficialWaypoint
from fenix_default_navdata.region_resolution import (
    RegionResolutionError,
    restore_regions_from_official_index,
)


def _baseline_navaid(
    *,
    kind: str,
    ident: str,
    region: str,
    latitude: float,
    longitude: float,
    row_id: int,
) -> BaselineNavaid:
    return BaselineNavaid(
        kind=kind,
        ident=ident,
        region=region,
        frequency_khz=113000.0,
        latitude=latitude,
        longitude=longitude,
        name=ident,
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=row_id,
    )


def _official_waypoint(
    *,
    ident: str,
    region: str,
    latitude: float,
    longitude: float,
    row_id: int,
) -> OfficialWaypoint:
    return OfficialWaypoint(
        ident=ident,
        region=region,
        latitude=latitude,
        longitude=longitude,
        source="fixture.bgl",
        row_id=row_id,
    )


def _official_index(
    *,
    records: tuple[BaselineNavaid, ...] = (),
    waypoints: tuple[OfficialWaypoint, ...] = (),
    verified: bool = True,
) -> OfficialNavaidIndex:
    return OfficialNavaidIndex(
        database=Path("official.sqlite"),
        metadata_path=Path("official.sqlite.metadata.json"),
        baseline=BaselineIndex(
            records=records,
            sources=("fixture.sqlite",),
            database_counts=(),
            verified=True,
        ),
        waypoints=waypoints,
        metadata={
            "metadata_version": 3 if verified else 0,
            "status": "verified" if verified else "unverified",
        },
        reused=True,
    )


def _leg(
    *,
    start_ident: str,
    end_ident: str,
    start_type: str,
    end_type: str,
    start_latitude: float = 35.0,
    start_longitude: float = 105.0,
    end_latitude: float = 36.0,
    end_longitude: float = 106.0,
    start_country: str = "",
    end_country: str = "",
) -> AirwayLeg:
    return AirwayLeg(
        airway="R1",
        sequence=1,
        start_ident=start_ident,
        end_ident=end_ident,
        source=SourceRef("RTE_SEG.csv", 2),
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        end_latitude=end_latitude,
        end_longitude=end_longitude,
        start_country=start_country,
        end_country=end_country,
        start_type=start_type,
        end_type=end_type,
    )


def test_restores_only_unique_matching_waypoints_and_route_endpoint_types(tmp_path: Path):
    model = NavModel(root=tmp_path)
    model.waypoints.extend((
        Waypoint("dp", "DP01", "", 35.0, 105.0, SourceRef("DESIGNATED_POINT.csv", 2)),
        Waypoint("far", "FAR01", "", 30.0, 100.0, SourceRef("DESIGNATED_POINT.csv", 3)),
    ))
    model.airway_legs.extend((
        _leg(
            start_ident="DP01",
            end_ident="VOR01",
            start_type="DESIGNATED_POINT",
            end_type="VORDME",
            end_latitude=36.0,
            end_longitude=106.0,
        ),
        _leg(
            start_ident="NDB01",
            end_ident="DP02",
            start_type="NDB",
            end_type="DESIGNATED_POINT",
            start_latitude=37.0,
            start_longitude=107.0,
            end_latitude=38.0,
            end_longitude=108.0,
        ),
    ))
    index = _official_index(
        records=(
            _baseline_navaid(
                kind="VOR", ident="VOR01", region="ZG", latitude=36.00005,
                longitude=106.0, row_id=1,
            ),
            _baseline_navaid(
                kind="NDB", ident="NDB01", region="ZU", latitude=37.0,
                longitude=107.0, row_id=2,
            ),
        ),
        waypoints=(
            _official_waypoint(
                ident="DP01", region="ZB", latitude=35.00005,
                longitude=105.0, row_id=3,
            ),
            _official_waypoint(
                ident="DP02", region="ZH", latitude=38.0,
                longitude=108.0, row_id=4,
            ),
            _official_waypoint(
                ident="FAR01", region="ZB", latitude=30.001, longitude=100.0,
                row_id=5,
            ),
        ),
    )

    result = restore_regions_from_official_index(model, index)

    assert [(point.ident, point.country) for point in model.waypoints] == [
        ("DP01", "ZB"),
        ("FAR01", ""),
    ]
    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [("ZB", "ZG"), ("ZU", "ZH")]
    assert result.waypoint_recovered == 1
    assert result.waypoint_unmatched == 1
    assert result.airway_endpoint_recovered == 4
    assert result.airway_legs_resolved_before == 0
    assert result.airway_legs_resolved_after == 2
    assert result.to_report()["airway_legs"] == {
        "total": 2,
        "resolved_before": 0,
        "resolved_after": 2,
        "skipped_before": 2,
        "skipped_after": 0,
    }


def test_ambiguous_waypoint_region_is_not_guessed(tmp_path: Path):
    model = NavModel(root=tmp_path)
    model.waypoints.append(Waypoint(
        "tamot", "TAMOT", "", 22.358333, 113.866667,
        SourceRef("DESIGNATED_POINT.csv", 2),
    ))
    model.airway_legs.append(_leg(
        start_ident="TAMOT",
        end_ident="KNOWN",
        start_type="DESIGNATED_POINT",
        end_type="DESIGNATED_POINT",
        start_latitude=22.358333,
        start_longitude=113.866667,
        end_latitude=23.0,
        end_longitude=114.0,
    ))
    index = _official_index(
        records=(
            _baseline_navaid(
                kind="VOR", ident="SPAREV", region="ZB", latitude=1.0,
                longitude=1.0, row_id=1,
            ),
            _baseline_navaid(
                kind="NDB", ident="SPAREN", region="ZB", latitude=2.0,
                longitude=2.0, row_id=2,
            ),
        ),
        waypoints=(
            _official_waypoint(
                ident="TAMOT", region="VH", latitude=22.35834,
                longitude=113.866667, row_id=3,
            ),
            _official_waypoint(
                ident="TAMOT", region="ZG", latitude=22.35835,
                longitude=113.866667, row_id=4,
            ),
            _official_waypoint(
                ident="KNOWN", region="ZG", latitude=23.0,
                longitude=114.0, row_id=5,
            ),
        ),
    )

    result = restore_regions_from_official_index(model, index)

    assert model.waypoints[0].country == ""
    assert model.airway_legs[0].start_country == ""
    assert model.airway_legs[0].end_country == "ZG"
    assert result.waypoint_ambiguous == 1
    assert result.airway_endpoint_ambiguous == 1
    assert result.airway_legs_resolved_after == 0


def test_endpoint_types_do_not_cross_match_into_wrong_official_table(tmp_path: Path):
    model = NavModel(root=tmp_path)
    model.airway_legs.append(_leg(
        start_ident="CROSS", end_ident="NDB01",
        start_type="VORDME", end_type="NDB",
        start_latitude=35.0, start_longitude=105.0,
        end_latitude=36.0, end_longitude=106.0,
    ))
    index = _official_index(
        records=(
            _baseline_navaid(
                kind="VOR", ident="SPAREV", region="ZB", latitude=1.0,
                longitude=1.0, row_id=1,
            ),
            _baseline_navaid(
                kind="NDB", ident="CROSS", region="ZB", latitude=35.0,
                longitude=105.0, row_id=2,
            ),
            _baseline_navaid(
                kind="NDB", ident="NDB01", region="ZG", latitude=36.0,
                longitude=106.0, row_id=3,
            ),
        ),
        waypoints=(
            _official_waypoint(
                ident="CROSS", region="ZH", latitude=35.0,
                longitude=105.0, row_id=4,
            ),
        ),
    )

    result = restore_regions_from_official_index(model, index)

    assert (model.airway_legs[0].start_country, model.airway_legs[0].end_country) == ("", "ZG")
    assert result.airway_endpoint_unmatched == 1
    assert result.airway_endpoint_recovered == 1


def test_unverified_official_index_is_rejected_before_any_model_change(tmp_path: Path):
    model = NavModel(root=tmp_path)
    point = Waypoint("dp", "DP01", "", 35.0, 105.0, SourceRef("DESIGNATED_POINT.csv", 2))
    model.waypoints.append(point)
    index = _official_index(
        records=(
            _baseline_navaid(
                kind="VOR", ident="SPAREV", region="ZB", latitude=1.0,
                longitude=1.0, row_id=1,
            ),
            _baseline_navaid(
                kind="NDB", ident="SPAREN", region="ZB", latitude=2.0,
                longitude=2.0, row_id=2,
            ),
        ),
        waypoints=(
            _official_waypoint(
                ident="DP01", region="ZB", latitude=35.0,
                longitude=105.0, row_id=3,
            ),
        ),
        verified=False,
    )

    with pytest.raises(RegionResolutionError, match="未通过验证"):
        restore_regions_from_official_index(model, index)

    assert model.waypoints == [point]
