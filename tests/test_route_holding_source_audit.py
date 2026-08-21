import json
from pathlib import Path

from fenix_default_navdata.model import Airport, NavModel, SourceRef, Waypoint
from fenix_default_navdata.route_holding_source_audit import (
    audit_route_holding_source,
    write_route_holding_source_audit,
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _model(root: Path, point_id: str) -> NavModel:
    model = NavModel(root)
    model.airports["airport"] = Airport(
        "airport", "ZBAA", "BEIJING", 40.0, 116.0, 100, 9000, 10000, SourceRef("AD_HP.csv", 2),
    )
    model.waypoints.append(
        Waypoint(
            key=point_id,
            ident="FIX1",
            name="FIX1",
            latitude=40.1,
            longitude=116.1,
            country="ZB",
            source=SourceRef("DESIGNATED_POINT.csv", 2),
        )
    )
    return model


def _sources(root: Path, point_id: str) -> None:
    _write(
        root / "ROUTE_HOLDING.csv",
        "ROUTE_HOLDING_ID,POINT_ID,HOLDING_TYPE,GEO_LAT_ACCURACY,"
        "GEO_LONG_ACCURACY,LOCATION_POINT,TXT_AIRWAY_DESC,CODE_DIRECTION\n"
        f"hold-1,{point_id},PVHOLR,N400000,E1160000,reference,FIX1 holding,R\n"
        "hold-2,unresolved,PVHOLL,N410000,E1170000,reference,FIX2 holding,L\n",
    )
    _write(
        root / "DESIGNATED_POINT.csv",
        "SIGNIFICANT_POINT_ID,CODE_ID\n"
        f"{point_id},FIX1\n",
    )
    for filename in ("NDB.csv", "VOR.csv"):
        _write(root / filename, "SIGNIFICANT_POINT_ID,CODE_ID\n")


def test_route_holding_audit_keeps_point_evidence_but_rejects_airport_projection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    point_id = "11111111-1111-1111-1111-111111111111"
    _sources(root, point_id)

    report = audit_route_holding_source(root, _model(root, point_id))

    assert report["diagnostic"] == "route-holding-source-audit-v1"
    assert report["read_only"] is True
    assert report["relationships"]["point_id_source_matches"] == {
        "DESIGNATED_POINT.csv": 1,
    }
    assert report["relationships"]["point_id_unresolved_rows"] == 1
    assert report["relationships"]["model_point_key_match_rows"] == 1
    assert report["relationships"]["rows_with_explicit_airport_field"] == 0
    assert report["relationships"]["rows_with_structured_airway_owner"] == 0
    assert report["relationships"]["designated_point_identity_match_rows"] == 1
    assert report["relationships"]["designated_point_identity_unresolved_rows"] == 1
    assert report["relationships"]["designated_point_rows_with_serviced_airport"] == 0
    assert report["relationships"]["designated_point_rows_with_fir"] == 0
    assert report["relationships"]["designated_point_serviced_airports"] == []
    assert report["target"]["projection_allowed"] is False
    assert report["target"]["disposition"] == "source_evidence_only"


def test_route_holding_audit_output_is_standard_json(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    point_id = "22222222-2222-2222-2222-222222222222"
    _sources(root, point_id)
    report = audit_route_holding_source(root, _model(root, point_id))
    output = tmp_path / "audit.json"
    write_route_holding_source_audit(output, report)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["diagnostic"] == "route-holding-source-audit-v1"
