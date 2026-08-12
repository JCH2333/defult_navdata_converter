from pathlib import Path

import pytest

from fenix_default_navdata.source import _surface, load_naip


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
