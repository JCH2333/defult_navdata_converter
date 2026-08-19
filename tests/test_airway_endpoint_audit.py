from pathlib import Path

from fenix_default_navdata.airway_endpoint_audit import (
    audit_unresolved_airway_endpoints,
)
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint


def test_audit_unresolved_airway_endpoints_classifies_boundaries_and_unknowns(
    tmp_path: Path,
) -> None:
    source = SourceRef("RTE_SEG.csv", 2)
    model = NavModel(
        tmp_path,
        waypoints=[
            Waypoint("boundary", "BOUNDARY", "", 35.0, 105.0, source, ""),
            Waypoint("lonely", "LONELY", "", 36.0, 106.0, source, ""),
        ],
        airway_legs=[
            AirwayLeg(
                "A1", 1, "ZBPT", "BOUNDARY", source,
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=35.1, start_longitude=105.1, start_country="ZB",
                end_latitude=35.0, end_longitude=105.0,
            ),
            AirwayLeg(
                "A2", 1, "ZGPT", "BOUNDARY", source,
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=35.2, start_longitude=105.2, start_country="ZG",
                end_latitude=35.0, end_longitude=105.0,
            ),
            AirwayLeg(
                "A3", 1, "ZUPT", "****", source,
                start_type="DESIGNATED_POINT", end_type="地名点",
                start_latitude=36.1, start_longitude=106.1, start_country="ZU",
                end_latitude=14.0, end_longitude=111.0,
            ),
            AirwayLeg(
                "A4", 1, "ZSPT", "LONELY", source,
                start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
                start_latitude=36.2, start_longitude=106.2, start_country="ZS",
                end_latitude=36.0, end_longitude=106.0,
                source_airspace_remark="上海ACC",
            ),
        ],
    )

    report = audit_unresolved_airway_endpoints(model)

    assert report["unresolved_endpoint_total"] == 3
    assert report["related_unprojected_leg_total"] == 4
    assert report["categories"] == {
        "multiple_neighbor_regions": 1,
        "non_designated_endpoint_identity_unavailable": 1,
        "single_neighbor_region_with_acc_evidence": 1,
    }
    items = {item["endpoint"]["ident"]: item for item in report["items"]}
    assert items["BOUNDARY"]["neighbor_regions"] == ["ZB", "ZG"]
    assert items["****"]["category"] == "non_designated_endpoint_identity_unavailable"
