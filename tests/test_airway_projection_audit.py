from fenix_default_navdata.airway_projection_audit import audit_airway_xml_projection
from fenix_default_navdata.bgl import write_bglcomp_xml
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef
from fenix_default_navdata.profile import Cycle


def test_xml_projection_audit_keeps_yhd_dwz_edge(tmp_path):
    model = NavModel(root=tmp_path)
    model.airway_legs.append(
        AirwayLeg(
            "W215",
            1,
            "YHD",
            "DWZ",
            SourceRef("RTE_SEG.csv", 1),
            start_latitude=38.3,
            start_longitude=106.4,
            end_latitude=37.9,
            end_longitude=106.3,
            start_country="ZL",
            end_country="ZL",
            start_type="VORDME",
            end_type="VORDME",
        )
    )
    output = tmp_path / "00_enroute.xml"
    write_bglcomp_xml(
        model,
        Cycle("2608", 1, "20260806", "20260903"),
        output,
        scope="enroute",
    )
    report = audit_airway_xml_projection(model, output)
    assert report["verified"] is True
    assert report["critical_missing_edges"] == []
