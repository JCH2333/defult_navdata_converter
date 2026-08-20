from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.pipeline_master_audit import (
    audit_pipeline_master,
    write_pipeline_master_audit,
)
from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    ChartTerminalLeg,
    Navaid,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    RejectedProcedure,
    Runway,
    SourceRef,
    Waypoint,
)


def test_pipeline_master_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    # Create all required CSV files for source_model_completeness_audit
    all_csvs = [
        ("AD_HP.csv", "CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_ELEV,VAL_TRANSITION_ALT,VAL_TRANSITION_LEVEL,VAL_MAG_VAR\nZBAA,BEIJING,N400448,E1163553,116,9800,11800,-7.0\n"),
        ("RWY.csv", "AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION\napt-1,3800,60,CON\n"),
        ("RWY_DIRECTION.csv", "RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV,VAL_THR_DISPLACE\nrwy-1,01,10.0,116,0\n"),
        ("VOR.csv", "SIGNIFICANT_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR\nvor-1,PEK,N400258,E1164402,114.7,-7.0,100,ZBAA,FIR\n"),
        ("NDB.csv", "SIGNIFICANT_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR\nndb-1,PK,N400200,E1164400,300,-7.0,100,ZBAA,FIR\n"),
        ("DESIGNATED_POINT.csv", "SIGNIFICANT_POINT_ID,DESIGNATED_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT,CODE_FIR\npt-1,pt-1,TIKME,TIKME,N303224,E1125337,ZBAA,FIR\n"),
        ("RTE_SEG.csv", "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_TYPE,SEGMENT_ID,EN_ROUTE_RTE_ID\nW47,1,TIKME,PEK,N303224,E1125337,N400258,E1164402,RNAV2,seg-1,rte-1\n"),
        ("SEGMENT.csv", "TXT_DESIG_RNP,VAL_MTCA\n2,2000\n"),
        ("EN_ROUTE_RTE.csv", "TXT_LOC_TYPE,VAL_MTCA\nLOC,2000\n"),
        ("AIRSPACE.csv", "AIRSPACE_ID,CODE_TYPE,CODE_ID\nair-1,FIR,ZBPE\n"),
        ("AIRSPACE_BORDER_VERTEX.csv", "AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG\nair-1,1,N40,E116\n"),
        ("AIRSPACE_CLASS.csv", "AIRSPACE_ID\nair-1\n"),
        ("AIRSPACE_RADIO.csv", "AIRSPACE_ID,TXT_FREQ_TYPE,VAL_FREQ\n"),
        ("APPSECTOR_RUNWAYDIRECTION.csv", "AIRSPACE_ID,AD_HP_ID\n"),
        ("CONTROLLED.csv", "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME\n"),
        ("CONTROLLED_BORDER_VERTEX.csv", "AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG\n"),
        ("CONTROLLED_CLASS.csv", "AIRSPACE_ID\n"),
        ("CONTROLLED_RADIO.csv", "AIRSPACE_ID,TXT_FREQ_TYPE,VAL_FREQ\n"),
        ("RESTRICTED.csv", "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME\n"),
        ("RESTRICTED_BORDER_VERTEX.csv", "AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG\n"),
        ("RESTRICTED_CLASS.csv", "AIRSPACE_ID\n"),
        ("RESTRICTED_RADIO.csv", "AIRSPACE_ID,TXT_FREQ_TYPE,VAL_FREQ\n"),
        ("SPECIAL_AIRSPACE.csv", "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME\n"),
        ("SPECIAL_AIRSPACE_BORDER_VERTEX.csv", "AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG\n"),
        ("SPECIAL_AIRSPACE_CLASS.csv", "AIRSPACE_ID\n"),
        ("SPECIAL_AIRSPACE_RADIO.csv", "AIRSPACE_ID,TXT_FREQ_TYPE,VAL_FREQ\n"),
        ("ROUTE_HOLDING.csv", "ROUTE_HOLDING_ID,POINT_ID,HOLDING_TYPE,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_DIRECTION,VAL_DISTANCE,VAL_ANGLE,VAL_MIN_HEIGHT,VAL_MAX_HEIGHT,VAL_SPEED_LIMIT,VAL_RADIUS\n"),
        ("ROUTE_RESTRICT.csv", "ROUTE_RESTRICT_ID,REMARK_CHAR,SPECIAL_REMARK\n"),
        ("ROUTE_RESTRICT_RTE.csv", "ROUTE_RESTRICT_RTE_ID,ROUTE_RESTRICT_ID,ROUTE_SEGMENT_UUID\n"),
        ("GENERAL_DOC.csv", "ID,ParentId,Title,PdfName\n"),
        ("FLIGHT_AIRLINE.csv", "FLIGHT_AIRLINE_ID,name,LineType,StartAirportID,EndAirportID\n"),
        ("FLIGHT_AIRLINE_POINT.csv", "FLIGHT_AIRLINE_POINT_ID,FLIGHT_AIRLINE_ID,Sequnce,AirwayName,StartPointID,EndPointID\n"),
        ("SYSTEMSETTING.csv", "KEYNAME,KEYVALUE\n"),
    ]

    for filename, content in all_csvs:
        (raw / filename).write_text(content, encoding="utf-8")

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
    chart_leg = ChartTerminalLeg(
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
        legs=(chart_leg,),
        source=SourceRef("Terminal/ZBAA/test.pdf", 1),
    )
    chart = ProcedureChart(
        airport="ZBAA",
        filename="test.pdf",
        page=1,
        chart_type="standard-terminal-procedure",
        chart_name="TEST",
        text_sha256="abc123",
        procedure_labels=("TEST-1",),
        runways=("01",),
        waypoints=("FIX1",),
        terminal_legs=(chart_leg,),
        fix_coordinates=(),
        source=SourceRef("Terminal/ZBAA/test.pdf", 1),
    )

    model.airports = {"apt-1": apt}
    model.runways = {"rwy-1": rwy}
    model.navaids = [vor_navaid, ndb_navaid]
    model.waypoints = [wp]
    model.airway_legs = [leg]
    model.procedure_segments = [seg]
    model.procedure_charts = [chart]
    model.rejected_procedures = [
        RejectedProcedure(f"rej-{i}", "chart", "reason", SourceRef("file", 1))
        for i in range(10)
    ]
    model.ilses = []
    model.holdings = []

    report = audit_pipeline_master(raw, model)

    assert report["diagnostic"] == "pipeline-master-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["pipeline_master_verified"] is True
    assert report["summary"]["disposition"] == "pipeline_master_verified"
    assert report["pipeline"]["source_model_verified"] is True
    assert report["pipeline"]["bgl_projection_verified"] is True
    assert "ZB" in report["sub_audits"]["bgl_projection_master"]["summary"]["regions"]

    out_file = tmp_path / "out.json"
    write_pipeline_master_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
