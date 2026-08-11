from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fenix_default_navdata.fenix_source import (
    FenixSourceError,
    decode_fenix_frequency,
    load_fenix_model,
)
from fenix_default_navdata.model import NavModel
from fenix_default_navdata.profile import DEFAULT_CYCLE


def _database(path: Path, cycle_name: str = "2608n1") -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE config (key TEXT PRIMARY KEY, val TEXT);
        CREATE TABLE Airports (
            ID INTEGER PRIMARY KEY, Name TEXT, ICAO TEXT, PrimaryID INTEGER,
            Latitude DOUBLE, Longtitude DOUBLE, Elevation INTEGER,
            TransitionAltitude INTEGER, TransitionLevel INTEGER,
            SpeedLimit INTEGER, SpeedLimitAltitude INTEGER
        );
        CREATE TABLE Runways (
            ID INTEGER PRIMARY KEY, AirportID INTEGER, Ident TEXT,
            TrueHeading DOUBLE, Length INTEGER, Width INTEGER, Surface TEXT,
            Latitude DOUBLE, Longtitude DOUBLE, Elevation INTEGER
        );
        CREATE TABLE ILSes (
            ID INTEGER PRIMARY KEY, RunwayID INTEGER, Freq INTEGER,
            GsAngle DOUBLE, Latitude DOUBLE, Longtitude DOUBLE, Category TEXT,
            Ident TEXT, LocCourse DOUBLE, CrossingHeight TEXT,
            HasDme INTEGER NOT NULL, Elevation INTEGER
        );
        CREATE TABLE Navaids (
            ID INTEGER PRIMARY KEY, Ident TEXT, Type TEXT, Name TEXT,
            Freq INTEGER, Channel TEXT, Usage TEXT, Latitude DOUBLE,
            Longtitude DOUBLE, Elevation INTEGER, SlavedVar DOUBLE,
            MagneticVariation DOUBLE, Range INTEGER
        );
        CREATE TABLE NavaidLookup (
            Ident TEXT, Type TEXT, Country TEXT, NavKeyCode TEXT, ID INTEGER
        );
        CREATE TABLE Waypoints (
            ID INTEGER PRIMARY KEY, Ident TEXT NOT NULL, Collocated INTEGER,
            Name TEXT, Latitude DOUBLE, Longtitude DOUBLE, NavaidID INTEGER
        );
        CREATE TABLE WaypointLookup (Ident TEXT, Country TEXT, ID INTEGER);
        CREATE TABLE Terminals (
            ID INTEGER PRIMARY KEY, AirportID INTEGER, Proc TEXT, ICAO TEXT,
            FullName TEXT, Name TEXT, Rwy TEXT, RwyID INTEGER, IlsID INTEGER
        );
        CREATE TABLE TerminalLegs (
            ID INTEGER PRIMARY KEY, TerminalID INTEGER, Type TEXT,
            Transition TEXT, TrackCode TEXT, WptID INTEGER, WptLat DOUBLE,
            WptLon DOUBLE, TurnDir TEXT, NavID INTEGER, NavLat DOUBLE,
            NavLon DOUBLE, NavBear DOUBLE, NavDist DOUBLE, Course DOUBLE,
            Distance DOUBLE, Alt TEXT, Vnav DOUBLE, CenterID INTEGER,
            CenterLat DOUBLE, CenterLon DOUBLE, WptDescCode TEXT
        );
        CREATE TABLE TerminalLegsEx (
            ID INTEGER PRIMARY KEY, IsFlyOver INTEGER, SpeedLimit DOUBLE,
            SpeedLimitDescription TEXT
        );
        CREATE TABLE Holdings (
            area_code TEXT, region_code TEXT, icao_code TEXT,
            waypoint_identifier TEXT, holding_name TEXT,
            waypoint_latitude DOUBLE, waypoint_longitude DOUBLE,
            duplicate_identifier INTEGER, inbound_holding_course DOUBLE,
            turn_direction TEXT, leg_length DOUBLE, leg_time DOUBLE,
            minimum_altitude INTEGER, maximum_altitude INTEGER,
            holding_speed INTEGER
        );
    """)
    connection.executemany(
        "INSERT INTO config VALUES (?, ?)",
        [
            ("CycleName", cycle_name),
            ("CycleStartDate", "06AUG26"),
            ("CycleEndDate", "02SEP26"),
        ],
    )
    connection.execute(
        "INSERT INTO Airports VALUES (1,'TEST AIRPORT','ZBCF',NULL,35,105,1000,18000,180,250,10000)"
    )
    connection.execute(
        "INSERT INTO Airports VALUES (2,'FOREIGN','KSEA',NULL,47,-122,400,18000,180,250,10000)"
    )
    connection.execute(
        "INSERT INTO Runways VALUES (10,1,'03',30,10000,150,'ASP',35.01,105.02,1000)"
    )
    connection.execute(
        "INSERT INTO ILSes VALUES (20,10,17321984,3,35.02,105.03,'1','ICF',30,50,1,1000)"
    )
    connection.execute(
        "INSERT INTO Navaids VALUES (11396,'CFV','4','CF VOR',18055168,'','H',35.1,105.1,1100,0,2,125)"
    )
    connection.execute(
        "INSERT INTO Navaids VALUES (11395,'OLD','4','OLD VOR',18055168,'','H',35.2,105.2,1100,0,2,125)"
    )
    connection.execute(
        "INSERT INTO Navaids VALUES (11000,'CF','5','CF NDB',22609920,'','H',35.3,105.3,900,0,2,50)"
    )
    connection.executemany(
        "INSERT INTO NavaidLookup VALUES (?,?,?,?,?)",
        [
            ("CFV", "4", "ZB", "1", 11396),
            ("OLD", "4", "ZB", "1", 11395),
            ("CF", "5", "ZB", "1", 11000),
        ],
    )
    connection.executemany(
        "INSERT INTO Waypoints VALUES (?,?,?,?,?,?,?)",
        [
            (329291, "CF001", 0, "CF001", 35.4, 105.4, None),
            (329292, "ARC01", 0, "ARC01", 35.5, 105.5, None),
        ],
    )
    connection.executemany(
        "INSERT INTO WaypointLookup VALUES (?,?,?)",
        [
            ("CF001", "ZB", 329291),
            ("CF001", "ZZ", 329291),
            ("ARC01", "ZB", 329292),
        ],
    )
    connection.execute(
        "INSERT INTO Terminals VALUES (30,1,'2','ZBCF','CF0011','CF0011','03',10,NULL)"
    )
    connection.executemany(
        "INSERT INTO TerminalLegs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                40, 30, "4", "RW03", "IF", 329291, 35.4, 105.4, None,
                None, None, None, None, None, None, None, "6000A", None,
                None, None, None, "E",
            ),
            (
                41, 30, "5", "ALL", "RF", 329291, 35.4, 105.4, "R",
                None, None, None, None, None, None, 8.0, "7000B6000A", -3.0,
                329292, 35.5, 105.5, "EE",
            ),
        ],
    )
    connection.executemany(
        "INSERT INTO TerminalLegsEx VALUES (?,?,?,?)",
        [(40, 0, None, None), (41, 1, 220, "-")],
    )
    connection.execute(
        "INSERT INTO Holdings VALUES ('CHN','ENRT','ZB','CF001','CF HOLD',35.4,105.4,0,180,'R',NULL,1,6000,12000,220)"
    )
    connection.commit()
    connection.close()


def test_frequency_decoding() -> None:
    assert decode_fenix_frequency(0x1085000, kind="ils") == 108.5
    assert decode_fenix_frequency(0x3450000, kind="ndb") == 345.0


def test_fenix_loader_uses_fenix_content_and_raw_route_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "nd.db3"
    _database(database)
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.fenix_source.load_naip",
        lambda root, include_terminal_documents=False: NavModel(root),
    )

    model = load_fenix_model(database, raw, DEFAULT_CYCLE)

    assert [airport.icao for airport in model.airports.values()] == ["ZBCF"]
    assert len(model.runways) == 1
    assert (model.runways[0].latitude, model.runways[0].longitude) == (35.01, 105.02)
    assert len(model.ilses) == 1
    assert model.ilses[0].frequency_mhz == 108.5
    assert {point.ident for point in model.waypoints} == {"CF001", "ARC01"}
    assert {(navaid.kind, navaid.ident) for navaid in model.navaids} == {
        ("VOR", "CFV"),
        ("NDB", "CF"),
    }
    assert len(model.procedure_segments) == 2
    assert sum(len(segment.legs) for segment in model.procedure_segments) == 2
    rf_leg = model.procedure_segments[1].legs[0]
    assert rf_leg.leg_type == "RF"
    assert rf_leg.arc_radius_nm is not None and rf_leg.arc_radius_nm > 0
    assert (rf_leg.altitude_descriptor, rf_leg.altitude1_ft, rf_leg.altitude2_ft) == (
        "-",
        7000,
        6000,
    )
    assert len(model.terminal_waypoints) == 2
    assert len(model.holdings) == 1


def test_fenix_loader_rejects_wrong_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "nd.db3"
    _database(database, "2607n1")
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.fenix_source.load_naip",
        lambda root, include_terminal_documents=False: NavModel(root),
    )

    with pytest.raises(FenixSourceError, match="周期不匹配"):
        load_fenix_model(database, raw, DEFAULT_CYCLE)


def test_fenix_loader_repairs_known_zlzy_arrival_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "nd.db3"
    _database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE Airports SET ICAO='ZLZY' WHERE ID=1")
        connection.execute(
            "UPDATE Terminals SET Proc='1', Name=?, FullName=?, Rwy='29R' WHERE ID=30",
            ("P91A\u95c1?", "P91A\u95c1?"),
        )
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.fenix_source.load_naip",
        lambda root, include_terminal_documents=False: NavModel(root),
    )

    model = load_fenix_model(database, raw, DEFAULT_CYCLE)

    assert {segment.label for segment in model.procedure_segments} == {"P9119A"}
    assert {
        leg.procedure_label
        for segment in model.procedure_segments
        for leg in segment.legs
    } == {"P9119A"}
