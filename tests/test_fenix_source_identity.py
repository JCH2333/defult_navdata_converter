from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fenix_default_navdata.fenix_source import load_fenix_model
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint
from fenix_default_navdata.profile import DEFAULT_CYCLE
from test_fenix_source import _database


def test_fenix_point_identity_overrides_matching_raw_route_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "nd.db3"
    _database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO Waypoints VALUES (329293, '72PCA', 0, '72PCA', 14.56666667, 111.925, NULL)"
        )
        connection.execute(
            "INSERT INTO WaypointLookup VALUES ('72PCA', 'ZJ', 329293)"
        )
        connection.commit()
    raw = tmp_path / "raw"
    raw.mkdir()
    raw_model = NavModel(raw)
    source = SourceRef("RTE_SEG.csv", 2)
    raw_model.waypoints.append(Waypoint(
        "raw-placeholder", "****", "****", 14.566667, 111.925, source, "CN",
    ))
    raw_model.airway_legs.append(AirwayLeg(
        "A1", 1, "****", "****", source,
        start_latitude=14.566667, start_longitude=111.925,
        end_latitude=14.566667, end_longitude=111.925,
        start_country="CN", end_country="CN",
    ))
    monkeypatch.setattr(
        "fenix_default_navdata.fenix_source.load_naip",
        lambda root, include_terminal_documents=False: raw_model,
    )

    model = load_fenix_model(database, raw, DEFAULT_CYCLE)

    point = next(point for point in model.waypoints if point.key == "raw-placeholder")
    assert (point.ident, point.country) == ("72PCA", "ZJ")
    assert {
        (leg.start_ident, leg.start_country, leg.end_ident, leg.end_country)
        for leg in model.airway_legs
    } == {("72PCA", "ZJ", "72PCA", "ZJ")}
