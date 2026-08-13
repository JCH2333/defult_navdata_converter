from pathlib import Path

import pytest

from fenix_default_navdata.source import _surface, load_naip, summarize_airway_source_metadata


def _write_csv(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


def _minimal_naip_root(tmp_path: Path, composition: str, *, include_second_airport: bool = False) -> Path:
    root = tmp_path / "raw"
    root.mkdir()
    airports = [
        "AD_HP_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_ELEV,VAL_TRANSITION_ALT,VAL_TRANSITION_LEVEL",
        "airport,ZBCF,TEST,N350000.00,E1050000.00,100,5486,5486",
    ]
    runways = [
        "RWY_ID,AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION",
        f"runway,airport,3048,45,{composition}",
    ]
    runway_directions = [
        "RWY_DIRECTION_ID,RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV",
        "end03,runway,03,30,100",
        "end21,runway,21,210,100",
    ]
    if include_second_airport:
        airports.append("airport-two,ZGAA,SECOND,N230000.00,E1130000.00,20,5486,5486")
        runways.append(f"runway-two,airport-two,1828.8,30,{composition}")
        runway_directions.append("end09,runway-two,09,90,20")
    _write_csv(root, "AD_HP.csv", "\n".join(airports))
    _write_csv(root, "RWY.csv", "\n".join(runways))
    _write_csv(root, "RWY_DIRECTION.csv", "\n".join(runway_directions))
    for name, header in (
        ("VOR.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR"),
        ("NDB.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR"),
        ("DESIGNATED_POINT.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR"),
        ("RTE_SEG.csv", "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END"),
    ):
        _write_csv(root, name, header)
    return root


@pytest.mark.parametrize(("composition", "expected"), (
    ("\u6c34\u6ce5\u6df7\u51dd\u571f", "CON"),
    ("\u6ca5\u9752", "ASP"),
    ("\u6c34\u6ce5\u6df7\u51dd\u571f/\u6ca5\u9752", "CON"),
    ("\u6ca5\u9752/\u6c34\u6ce5\u6df7\u51dd\u571f", "ASP"),
    ("GRASS", "GRE"),
    ("WATER", "WAT"),
))
def test_surface_retains_first_expressible_source_component(composition: str, expected: str) -> None:
    assert _surface(composition) == expected


def test_load_naip_derives_runway_end_coordinates_from_airport_reference(tmp_path: Path) -> None:
    model = load_naip(
        _minimal_naip_root(tmp_path, "\u6c34\u6ce5\u6df7\u51dd\u571f"),
        include_terminal_documents=False,
    )

    runway_03, runway_21 = model.runways
    assert runway_03.surface == "CON"
    assert runway_21.surface == "CON"
    assert runway_03.latitude is not None and runway_03.longitude is not None
    assert runway_21.latitude is not None and runway_21.longitude is not None
    assert runway_03.latitude < 35.0 < runway_21.latitude
    assert runway_03.longitude < 105.0 < runway_21.longitude
    assert (runway_03.latitude + runway_21.latitude) / 2 == pytest.approx(35.0, abs=0.00001)
    assert (runway_03.longitude + runway_21.longitude) / 2 == pytest.approx(105.0, abs=0.00001)


def test_load_naip_retains_each_runways_own_airport_key(tmp_path: Path) -> None:
    model = load_naip(
        _minimal_naip_root(tmp_path, "\u6ca5\u9752", include_second_airport=True),
        include_terminal_documents=False,
    )

    assert [(runway.ident, runway.airport_key) for runway in model.runways] == [
        ("03", "airport"),
        ("21", "airport"),
        ("09", "airport-two"),
    ]


def test_load_naip_converts_vor_elevation_meters_and_keeps_raw_navaid_name(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "kns,KNS,喀纳斯,N481315,E0870030,111.2,-5.2,1200,M,ZWKN,乌鲁木齐情报区",
        "cka,CKA,茶卡,N364653,E0990656,115.9,-7.0,3146,,,兰州情报区",
    )))
    _write_csv(root, "NDB.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "dm,DM,泽当,N291522,E0914551,435,-0.5,,,,昆明情报区",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert [(item.kind, item.ident, item.name, item.elevation_ft) for item in model.navaids] == [
        ("VOR", "KNS", "喀纳斯", 3937),
        ("VOR", "CKA", "茶卡", 10322),
        ("NDB", "DM", "泽当", 0),
    ]


def test_load_naip_retains_raw_navaid_selection_attributes(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,CODE_IN_AIRWAY,PURPOSE,IS_REP_ATC,ROUTE_RESTRICT,IS_TRANS_POINT,IS_BORDER_POINT,SERVICED_AIRPORT,CODE_FIR",
        "vor,VOR1,VOR,N230000,E1130000,113.1,-2,0,Y,AE,Y,Y,N,Y,ZGAA,广州情报区",
    )))

    model = load_naip(root, include_terminal_documents=False)

    navaid = next(item for item in model.navaids if item.ident == "VOR1")
    assert (
        navaid.code_in_airway,
        navaid.purpose,
        navaid.is_rep_atc,
        navaid.route_restrict,
        navaid.is_trans_point,
        navaid.is_border_point,
        navaid.serviced_airport,
        navaid.code_fir,
    ) == ("Y", "AE", "Y", "Y", "N", "Y", "ZGAA", "广州情报区")


def test_load_naip_recovers_blank_route_endpoint_firs_from_matching_424_records(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "point,DP01,DESIGNATED,N350000,E1050000,北京情报区",
        "nofir,NOFIR,UNRESOLVED,N360000,E1060000,",
    )))
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "vor,VOR1,VOR,N230000,E1130000,113.1,0,0,ZGAA,广州情报区",
    )))
    _write_csv(root, "NDB.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "ndb,NDB1,NDB,N290000,E0910000,350,0,0,ZULS,昆明情报区",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END",
        "R1,1,DP01,VOR1,N350000,E1050000,N230000,E1130000,,,B,L,DESIGNATED_POINT,VORDME",
        "R2,2,NDB1,DP01,N290000,E0910000,N350000,E1050000,,,B,L,NDB,地名点",
        "R3,3,DP01,NOFIR,N350000,E1050000,N360000,E1060000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [
        ("ZB", "ZG"),
        ("ZU", "ZB"),
        ("ZB", ""),
    ]
    assert next(point.country for point in model.waypoints if point.ident == "NOFIR") == ""


def test_load_naip_uses_strict_serviced_airport_prefix_for_blank_waypoint_fir(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "娌ラ潚")
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT,CODE_FIR",
        "valid,P216,VALID,N350000,E1050000,ZUHY,",
        "short,SHORT,SHORT,N360000,E1060000,ZU,",
        "foreign,FOREIGN,FOREIGN,N370000,E1070000,EDDF,",
        "explicit,EXPLICIT,EXPLICIT,N380000,E1080000,ZGAA,\u5317\u4eac\u60c5\u62a5\u533a",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "P216": "ZU",
        "SHORT": "",
        "FOREIGN": "",
        "EXPLICIT": "ZB",
    }


def test_load_naip_separates_source_pbn_from_target_route_type_and_links_airway_tables(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "RTE_SEG_ID,EN_ROUTE_RTE_ID,SEGMENT_ID,TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END",
        "rte-seg-1,route-1,segment-1,R1,1,DP01,DP02,N350000,E1050000,N360000,E1060000,,,B,RNAV2,DESIGNATED_POINT,DESIGNATED_POINT",
        "rte-seg-2,route-1,missing-segment,R1,2,DP02,DP03,N360000,E1060000,N370000,E1070000,,,B,RNP4,DESIGNATED_POINT,DESIGNATED_POINT",
    )))
    _write_csv(root, "SEGMENT.csv", "\n".join((
        "SEGMENT_ID,TXT_DESIG_RNP,VAL_MTCA",
        "segment-1,P4,2300",
    )))
    _write_csv(root, "EN_ROUTE_RTE.csv", "\n".join((
        "EN_ROUTE_RTE_ID,TXT_LOC_TYPE,VAL_MTCA",
        "route-1,国际区域导航航路,2600",
    )))

    model = load_naip(root, include_terminal_documents=False)

    first, second = model.airway_legs
    assert first.route_type == ""
    assert first.source_code_type == "RNAV2"
    assert first.source_segment_rnp_designator == "P4"
    assert first.source_enroute_location_type == "国际区域导航航路"
    assert first.source_segment_minimum_crossing_altitude == "2300"
    assert first.source_route_minimum_crossing_altitude == "2600"
    assert first.source_rte_seg_id == "rte-seg-1"
    assert first.source_segment_id == "segment-1"
    assert first.source_en_route_rte_id == "route-1"
    assert first.source_segment_found is True
    assert first.source_en_route_rte_found is True
    assert second.source_segment_found is False
    assert second.source_en_route_rte_found is True

    summary = summarize_airway_source_metadata(model)
    assert summary["source_code_type"] == {"RNAV2": 1, "RNP4": 1}
    assert summary["target_route_type_hint"] == {"<unresolved>": 2}
    assert summary["links"] == {
        "segment_found": 1,
        "segment_missing": 1,
        "en_route_rte_found": 2,
        "en_route_rte_missing": 0,
    }
