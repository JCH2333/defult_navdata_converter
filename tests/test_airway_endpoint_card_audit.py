from pathlib import Path

from fenix_default_navdata.airway_endpoint_card_audit import (
    audit_airway_endpoint_card,
)
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint


def _write_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_card_audit_rejects_blank_direct_region_at_multiple_region_boundary(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "DESIGNATED_POINT.csv",
        "\n".join((
            "SIGNIFICANT_POINT_ID,CODE_FIR,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT",
            "point-p225,,P225,N340124,E1103130,",
        )),
    )
    _write_csv(
        raw / "RTE_SEG.csv",
        "\n".join((
            "RTE_SEG_ID,VAL_SORT,CODE_POINT_START,CODE_TYPE_START,CODE_FIR_START,POINT_START_ID,CODE_POINT_END,CODE_TYPE_END,CODE_FIR_END,POINT_END_ID,TXT_DESIG,Airspace_Remark",
            "first,3,P612,DESIGNATED_POINT,,other-zh,P225,DESIGNATED_POINT,,point-p225,H34,西安ACC",
            "second,4,P225,DESIGNATED_POINT,,point-p225,SHX,VORDME,,other-zl,H34,西安ACC",
        )),
    )
    _write_csv(
        raw / "AIRSPACE.csv",
        "\n".join((
            "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
            "fir-zl,FIR,ZLHW,兰州飞行情报区",
        )),
    )
    source = SourceRef("RTE_SEG.csv", 3)
    model = NavModel(
        raw,
        waypoints=[Waypoint(
            "p225", "P225", "", 34.023333, 110.525, SourceRef(
                "DESIGNATED_POINT.csv", 2
            ), "",
        )],
        airway_legs=[
            AirwayLeg(
                "H34", 3, "P612", "P225", source,
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=34.2, start_longitude=110.8, start_country="ZH",
                end_latitude=34.023333, end_longitude=110.525,
                source_airspace_remark="西安ACC",
            ),
            AirwayLeg(
                "H34", 4, "P225", "SHX", SourceRef("RTE_SEG.csv", 4),
                start_type="DESIGNATED_POINT", end_type="VORDME",
                start_latitude=34.023333, start_longitude=110.525,
                end_latitude=33.9, end_longitude=109.9, end_country="ZL",
                source_airspace_remark="西安ACC",
            ),
        ],
    )

    report = audit_airway_endpoint_card(raw, model, ident="P225")

    assert report["read_only"] is True
    assert report["model_changed"] is False
    assert report["projection_changed"] is False
    assert report["endpoint"]["significant_point_id"] == "point-p225"
    assert report["endpoint"]["code_fir"] == ""
    assert report["endpoint"]["serviced_airport"] == ""
    assert report["direct_evidence"] == {
        "endpoint_firs": [],
        "acc_names": ["西安"],
        "fir_acc_region_mappings": {},
    }
    assert report["model_source_evidence"]["neighbor_regions"] == ["ZH", "ZL"]
    assert report["disposition"] == (
        "rejected_multiple_neighbor_regions_with_blank_direct_region"
    )
    assert report["projection_allowed"] is False


def test_card_audit_requires_exactly_one_designated_point_identity(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "DESIGNATED_POINT.csv",
        "\n".join((
            "SIGNIFICANT_POINT_ID,CODE_ID",
            "first,P225",
            "second,P225",
        )),
    )
    _write_csv(raw / "RTE_SEG.csv", "POINT_START_ID,POINT_END_ID\n")
    _write_csv(raw / "AIRSPACE.csv", "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME\n")

    model = NavModel(raw)

    try:
        audit_airway_endpoint_card(raw, model, ident="P225")
    except ValueError as error:
        assert "唯一身份数为 2" in str(error)
    else:  # pragma: no cover - assertion keeps the failure message direct
        raise AssertionError("重复指定点身份必须拒绝")
