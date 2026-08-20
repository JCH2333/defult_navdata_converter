from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.bgl_projection_master_audit import (
    audit_bgl_projection_master,
    write_bgl_projection_master_audit,
)
from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    ChartTerminalLeg,
    Ils,
    Navaid,
    NavModel,
    ProcedureSegment,
    Runway,
    SourceRef,
    Waypoint,
)


def test_bgl_projection_master_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

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
    ils = Ils(
        airport="ZBAA",
        runway="01",
        ident="IPE",
        frequency_mhz=110.1,
        category="II",
        localizer_latitude=40.09,
        localizer_longitude=116.61,
        localizer_course_magnetic=None,
        glide_slope_degrees=3.0,
        crossing_height_meters=15.0,
        glide_slope_latitude=40.06,
        glide_slope_longitude=116.61,
        dme_latitude=40.06,
        dme_longitude=116.61,
        dme_elevation_meters=31.0,
        source=SourceRef("Terminal/ZBAA/ils.pdf", 1),
    )
    leg = ChartTerminalLeg(
        procedure_label="TEST-1",
        runway="01",
        leg_type="TF",
        fix_ident="FIX1",
        raw="TF FIX1",
    )
    seg = ProcedureSegment(
        airport="ZBAA",
        label="TEST-1",
        kind="进场",
        runway="01",
        transition="",
        legs=(leg,),
        source=SourceRef("Terminal/ZBAA/test.pdf", 1),
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
    airway_leg = AirwayLeg(
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
    model.ilses = [ils]
    model.procedure_segments = [seg]
    model.waypoints = [wp]
    model.navaids = []
    model.airway_legs = [airway_leg]

    report = audit_bgl_projection_master(model)

    assert report["diagnostic"] == "bgl-projection-master-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["total_airport_regions"] == 1
    assert report["summary"]["total_airports"] == 1
    assert "ZB" in report["summary"]["regions"]
    assert report["summary"]["regions"]["ZB"]["airport_bgl_target"] == "ZB_airports.bgl"

    out_file = tmp_path / "out.json"
    write_bgl_projection_master_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
