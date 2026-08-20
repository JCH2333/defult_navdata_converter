from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.core_model_mapping_audit import (
    audit_core_model_mapping,
    write_core_model_mapping_audit,
)
from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    Navaid,
    NavModel,
    Runway,
    SourceRef,
    Waypoint,
)


def test_core_model_mapping_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    (raw / "AD_HP.csv").write_text(
        "CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_ELEV\n"
        "ZBAA,BEIJING CAPITAL,N400448,E1163553,116\n",
        encoding="utf-8",
    )
    (raw / "RWY.csv").write_text(
        "AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION\n"
        "apt-1,3800,60,CON\n",
        encoding="utf-8",
    )
    (raw / "RWY_DIRECTION.csv").write_text(
        "RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV\n"
        "rwy-1,01,10.0,116\n",
        encoding="utf-8",
    )
    (raw / "VOR.csv").write_text(
        "SIGNIFICANT_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ\n"
        "vor-1,PEK,N400258,E1164402,114.7\n",
        encoding="utf-8",
    )
    (raw / "NDB.csv").write_text(
        "SIGNIFICANT_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ\n"
        "ndb-1,PK,N400200,E1164400,300\n",
        encoding="utf-8",
    )
    (raw / "DESIGNATED_POINT.csv").write_text(
        "DESIGNATED_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY\n"
        "pt-1,TIKME,N303224,E1125337\n",
        encoding="utf-8",
    )
    (raw / "RTE_SEG.csv").write_text(
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END\n"
        "W47,1,TIKME,PEK\n",
        encoding="utf-8",
    )

    model = NavModel(raw)
    apt = Airport(
        key="apt-1",
        icao="ZBAA",
        name="BEIJING CAPITAL",
        latitude=40.08,
        longitude=116.59,
        elevation_ft=116,
        transition_altitude=9800,
        transition_level=11800,
        source=SourceRef("AD_HP.csv", 2),
    )
    rwy = Runway(
        key="rwy-1",
        airport_key="apt-1",
        ident="01",
        true_heading=10.0,
        length_ft=12467,
        width_ft=197,
        surface="CON",
        elevation_ft=116,
        latitude=40.08,
        longitude=116.59,
        source=SourceRef("RWY_DIRECTION.csv", 2),
    )
    vor_navaid = Navaid(
        key="vor-1",
        ident="PEK",
        kind="VOR",
        name="PEK",
        latitude=40.04,
        longitude=116.73,
        frequency=114.7,
        magnetic_variation=-7.0,
        elevation_ft=100,
        country="ZB",
        source=SourceRef("VOR.csv", 2),
    )
    ndb_navaid = Navaid(
        key="ndb-1",
        ident="PK",
        kind="NDB",
        name="PK",
        latitude=40.03,
        longitude=116.73,
        frequency=300.0,
        magnetic_variation=-7.0,
        elevation_ft=100,
        country="ZB",
        source=SourceRef("NDB.csv", 2),
    )
    wp = Waypoint(
        key="pt-1",
        ident="TIKME",
        name="TIKME",
        latitude=30.54,
        longitude=112.89,
        source=SourceRef("DESIGNATED_POINT.csv", 2),
        country="ZH",
    )
    leg = AirwayLeg(
        airway="W47",
        sequence=1,
        start_ident="TIKME",
        end_ident="PEK",
        source=SourceRef("RTE_SEG.csv", 2),
        direction="X",
        start_latitude=30.54,
        start_longitude=112.89,
        end_latitude=40.04,
        end_longitude=116.73,
        start_country="ZH",
        end_country="ZB",
    )

    model.airports = {"apt-1": apt}
    model.runways = {"rwy-1": rwy}
    model.navaids = [vor_navaid, ndb_navaid]
    model.waypoints = [wp]
    model.airway_legs = [leg]

    report = audit_core_model_mapping(raw, model)

    assert report["diagnostic"] == "core-model-mapping-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["airports"]["model_airports_total"] == 1
    assert report["summary"]["runways"]["model_runways_total"] == 1
    assert report["summary"]["navaids"]["model_navaids_total"] == 2
    assert report["summary"]["waypoints"]["model_waypoints_total"] == 1
    assert report["summary"]["airways"]["model_airway_legs_total"] == 1
    assert report["summary"]["all_core_groups_verified"] is True

    out_file = tmp_path / "out.json"
    write_core_model_mapping_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
