from pathlib import Path

from fenix_default_navdata.airway_endpoint_card_audit import (
    audit_airway_endpoint_card,
    audit_non_designated_airway_endpoint_card,
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
        "unmapped_acc_names": ["西安"],
        "mapped_acc_regions": [],
    }
    assert report["model_source_evidence"]["neighbor_regions"] == ["ZH", "ZL"]
    assert report["disposition"] == (
        "rejected_multiple_neighbor_regions_with_incomplete_acc_evidence"
    )
    assert report["projection_allowed"] is False


def test_card_audit_rejects_partially_mapped_acc_at_multi_region_boundary(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "DESIGNATED_POINT.csv",
        "\n".join((
            "SIGNIFICANT_POINT_ID,CODE_FIR,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT",
            "point-p127,,P127,N291830,E1092342,",
        )),
    )
    _write_csv(
        raw / "RTE_SEG.csv",
        "\n".join((
            "RTE_SEG_ID,VAL_SORT,CODE_POINT_START,CODE_TYPE_START,CODE_FIR_START,POINT_START_ID,CODE_POINT_END,CODE_TYPE_END,CODE_FIR_END,POINT_END_ID,TXT_DESIG,Airspace_Remark",
            "first,2,P448,DESIGNATED_POINT,,other-zg,P127,DESIGNATED_POINT,,point-p127,H35,广州ACC长沙ACC",
            "second,3,P127,DESIGNATED_POINT,,point-p127,P613,DESIGNATED_POINT,,other-zp,H35,广州ACC长沙ACC",
        )),
    )
    _write_csv(
        raw / "AIRSPACE.csv",
        "\n".join((
            "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
            "fir-zg,FIR,ZGZU,广州飞行情报区",
        )),
    )
    model = NavModel(
        raw,
        waypoints=[Waypoint(
            "p127", "P127", "", 29.308333, 109.395, SourceRef(
                "DESIGNATED_POINT.csv", 2
            ), "",
        )],
        airway_legs=[
            AirwayLeg(
                "H35", 2, "P448", "P127", SourceRef("RTE_SEG.csv", 3),
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=29.2, start_longitude=109.2, start_country="ZG",
                end_latitude=29.308333, end_longitude=109.395,
                source_airspace_remark="广州ACC长沙ACC",
            ),
            AirwayLeg(
                "H35", 3, "P127", "P613", SourceRef("RTE_SEG.csv", 4),
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=29.308333, start_longitude=109.395,
                end_latitude=29.4, end_longitude=109.5, end_country="ZP",
                source_airspace_remark="广州ACC长沙ACC",
            ),
        ],
    )

    report = audit_airway_endpoint_card(raw, model, ident="P127")

    assert report["direct_evidence"]["fir_acc_region_mappings"] == {"广州": "ZG"}
    assert report["direct_evidence"]["unmapped_acc_names"] == ["长沙"]
    assert report["disposition"] == (
        "rejected_multiple_neighbor_regions_with_incomplete_acc_evidence"
    )
    assert report["projection_allowed"] is False


def test_card_audit_rejects_conflicting_mapped_acc_regions_at_boundary(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "DESIGNATED_POINT.csv",
        "\n".join((
            "SIGNIFICANT_POINT_ID,CODE_FIR,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT",
            "point-p239,,P239,N302146,E1092628,",
        )),
    )
    _write_csv(
        raw / "RTE_SEG.csv",
        "\n".join((
            "RTE_SEG_ID,VAL_SORT,CODE_POINT_START,CODE_TYPE_START,CODE_FIR_START,POINT_START_ID,CODE_POINT_END,CODE_TYPE_END,CODE_FIR_END,POINT_END_ID,TXT_DESIG,Airspace_Remark",
            "first,2,P616,DESIGNATED_POINT,,other-zp,P239,DESIGNATED_POINT,,point-p239,H38,广州ACC武汉ACC",
            "second,3,P239,DESIGNATED_POINT,,point-p239,IGITA,DESIGNATED_POINT,,other-zh,H38,广州ACC武汉ACC",
        )),
    )
    _write_csv(
        raw / "AIRSPACE.csv",
        "\n".join((
            "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
            "fir-zg,FIR,ZGZU,广州飞行情报区",
            "fir-zh,FIR,ZHWH,武汉飞行情报区",
        )),
    )
    model = NavModel(
        raw,
        waypoints=[Waypoint(
            "p239", "P239", "", 30.362778, 109.441111, SourceRef(
                "DESIGNATED_POINT.csv", 2
            ), "",
        )],
        airway_legs=[
            AirwayLeg(
                "H38", 2, "P616", "P239", SourceRef("RTE_SEG.csv", 3),
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=30.2, start_longitude=109.2, start_country="ZP",
                end_latitude=30.362778, end_longitude=109.441111,
                source_airspace_remark="广州ACC武汉ACC",
            ),
            AirwayLeg(
                "H38", 3, "P239", "IGITA", SourceRef("RTE_SEG.csv", 4),
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=30.362778, start_longitude=109.441111,
                end_latitude=30.4, end_longitude=109.5, end_country="ZH",
                source_airspace_remark="广州ACC武汉ACC",
            ),
        ],
    )

    report = audit_airway_endpoint_card(raw, model, ident="P239")

    assert report["direct_evidence"]["mapped_acc_regions"] == ["ZG", "ZH"]
    assert report["direct_evidence"]["unmapped_acc_names"] == []
    assert report["disposition"] == (
        "rejected_multiple_neighbor_regions_with_conflicting_acc_regions"
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


def test_non_designated_card_rejects_internal_uuid_without_named_identity(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "RTE_SEG.csv",
        "\n".join((
            "RTE_SEG_ID,VAL_SORT,CODE_POINT_START,CODE_TYPE_START,CODE_FIR_START,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,POINT_START_ID,CODE_POINT_END,CODE_TYPE_END,CODE_FIR_END,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,POINT_END_ID,TXT_DESIG,Airspace_Remark",
            "m771,1,****,地名点,,N143400,E1115530,internal-id,DONDA,DESIGNATED_POINT,,N144212,E1120118,donda-id,M771,三亚ACC",
        )),
    )
    _write_csv(
        raw / "DESIGNATED_POINT.csv",
        "SIGNIFICANT_POINT_ID,CODE_ID\n"
        "donda-id,DONDA\n",
    )
    _write_csv(raw / "VOR.csv", "VOR_ID,CODE_ID\n")
    _write_csv(raw / "NDB.csv", "NDB_ID,CODE_ID\n")
    source = SourceRef("RTE_SEG.csv", 2)
    model = NavModel(
        raw,
        airway_legs=[AirwayLeg(
            "M771", 1, "****", "DONDA", source,
            start_type="地名点", end_type="DESIGNATED_POINT",
            start_latitude=14.566667, start_longitude=111.925,
            end_latitude=14.703333, end_longitude=112.021667,
            end_country="ZJ", source_airspace_remark="三亚ACC",
        )],
    )

    report = audit_non_designated_airway_endpoint_card(
        raw,
        model,
        ident="****",
        endpoint_type="地名点",
    )

    assert report["endpoint"]["internal_point_id"] == "internal-id"
    assert report["identity_catalog_uuid_occurrences"] == {
        "DESIGNATED_POINT.csv": 0,
        "VOR.csv": 0,
        "NDB.csv": 0,
    }
    assert report["model_source_evidence"]["neighbor_regions"] == ["ZJ"]
    assert report["disposition"] == (
        "rejected_non_designated_endpoint_identity_unavailable"
    )
    assert report["projection_allowed"] is False
