from pathlib import Path

from fenix_default_navdata.airport_source_inventory import (
    build_airport_source_inventory,
)
from fenix_default_navdata.model import (
    Airport,
    Holding,
    Ils,
    Navaid,
    NavModel,
    ProcedureSegment,
    Runway,
    SourceRef,
    TerminalWaypoint,
)


def _model(root: Path) -> NavModel:
    source = SourceRef("AD_HP.csv", row=2)
    pdf_source = SourceRef("Terminal/ZBAA/ZBAA-9A.pdf", page=1)
    model = NavModel(root)
    model.airports["A1"] = Airport(
        "A1", "ZBAA", "BEIJING", 40.0, 116.0, 100, 9000, 10000, source,
    )
    model.runways.append(
        Runway("R1", "A1", "36L", 360.0, 12000, 200, "ASPHALT", 100, source)
    )
    model.terminal_waypoints.append(
        TerminalWaypoint("T1", "ZBAA", "FIX1", 40.1, 116.1, pdf_source)
    )
    model.ilses.append(
        Ils(
            "ZBAA", "36L", "IBAA", 110.3, None, 40.0, 116.0, 360.0, None,
            None, None, None, None, None, None, pdf_source,
        )
    )
    for kind in ("离场", "进场", "进近过渡", "进近", "复飞"):
        model.procedure_segments.append(
            ProcedureSegment("ZBAA", f"{kind}1", kind, "36L", "", (), pdf_source)
        )
    model.holdings.append(
        Holding(
            "H1", "FIX1", "ZB", 40.1, 116.1, None, "R", None, None, None,
            None, None, source,
        )
    )
    model.navaids.extend((
        Navaid(
            "V1", "VOR1", "VOR", "VOR ONE", 40.0, 116.0, 113.0, 0.0, 100,
            "CN", source, serviced_airport="ZBAA",
        ),
        Navaid(
            "N1", "NDB1", "NDB", "NDB ONE", 40.2, 116.2, 385.0, 0.0, 100,
            "CN", source, serviced_airport="ZZZZ",
        ),
    ))
    return model


def test_inventory_keeps_source_scope_and_rejection_boundaries(tmp_path: Path) -> None:
    xml = tmp_path / "candidate.xml"
    xml.write_text("<FSData><Airport/><Waypoint/></FSData>", encoding="utf-8")

    report = build_airport_source_inventory(_model(tmp_path / "raw"), candidate_xml=xml)

    assert report["diagnostic"] == "airport-source-inventory-v2"
    assert report["read_only"] is True
    assert report["reference_records_read"] is False
    assert report["summary"]["airport_total"] == 1
    assert report["categories"]["runways"]["sdk_elements"] == ["Runway", "Ils"]
    assert report["categories"]["runways"]["airport_counts"] == {"ZBAA": 1}
    assert report["categories"]["terminal_waypoints"]["source_file_groups"] == {
        "Terminal": 1,
    }
    assert report["categories"]["holdings"]["disposition"] == (
        "projected_after_terminal_identity_resolution"
    )
    assert report["categories"]["departure_segments"]["source_records"] == 1
    assert report["categories"]["approach_segments"]["source_records"] == 1
    assert report["categories"]["missed_approach_segments"]["source_records"] == 1
    assert report["categories"]["airport_associated_navaids"]["disposition"] == (
        "not_projected_as_airport_children"
    )
    assert report["summary"]["navaids_with_unknown_serviced_airport_total"] == 1
    assert report["candidate_xml_tag_counts"] == {
        "Airport": 1,
        "FSData": 1,
        "Waypoint": 1,
    }
    assert report["sdk_probe_candidates"]["runway_offset_thresholds"][
        "disposition"
    ] == "unavailable"


def test_inventory_lists_direct_runway_offset_threshold_probe_candidates(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    (root / "RWY.csv").write_text(
        "RWY_ID,AD_HP_ID\nR1,A1\n",
        encoding="utf-8",
    )
    (root / "RWY_DIRECTION.csv").write_text(
        "RWY_DIRECTION_ID,RWY_ID,TXT_DESIG,VAL_THR_DISPLACE\n"
        "D1,R1,04R,300\n"
        "D2,R1,22L,0\n",
        encoding="utf-8",
    )

    report = build_airport_source_inventory(_model(root))
    candidate = report["sdk_probe_candidates"]["runway_offset_thresholds"]

    assert candidate["disposition"] == "eligible_for_sdk_probe"
    assert candidate["source_records"] == 1
    assert candidate["airport_counts"] == {"ZBAA": 1}
    assert candidate["examples"] == [{
        "airport": "ZBAA",
        "runway_ident": "04R",
        "displacement_meters": "300",
        "source": {"file": "RWY_DIRECTION.csv", "row": 2},
    }]


def test_inventory_rejects_airport_linked_approach_sector_radios(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    (root / "AD_HP.csv").write_text(
        "AD_HP_ID,CODE_ID\nA1,ZBAA\n",
        encoding="utf-8",
    )
    (root / "APPSECTOR_RUNWAYDIRECTION.csv").write_text(
        "AIRSPACE_ID,AD_HP_ID,RWY_DIRECTION_ID\n"
        "S1,A1,D1\n"
        "S1,A1,D2\n",
        encoding="utf-8",
    )
    (root / "AIRSPACE_RADIO.csv").write_text(
        "RADIO_ID,AIRSPACE_ID,TXT_SECTOR,TXT_FREQ_TYPE,VAL_FREQ,UOM_FREQ\n"
        "R1,S1,APP01,APP,120.0,MHz\n",
        encoding="utf-8",
    )
    (root / "CONTROLLED_RADIO.csv").write_text(
        "RADIO_ID,AIRSPACE_ID,TXT_SECTOR,TXT_FREQ_TYPE,VAL_FREQ,UOM_FREQ\n"
        "R1,S1,APP02,APP,121.0,MHz\n",
        encoding="utf-8",
    )
    for name in ("RESTRICTED_RADIO.csv", "SPECIAL_AIRSPACE_RADIO.csv"):
        (root / name).write_text(
            "RADIO_ID,AIRSPACE_ID,TXT_SECTOR,TXT_FREQ_TYPE,VAL_FREQ,UOM_FREQ\n",
            encoding="utf-8",
        )

    report = build_airport_source_inventory(_model(root))
    candidate = report["sdk_probe_candidates"]["airspace_radios"]

    assert candidate["disposition"] == "rejected_by_scope_and_cardinality"
    assert candidate["target_scope"] == "airspace/approach_sector"
    assert candidate["source_records"] == 4
    assert candidate["unique_radio_total"] == 2
    assert candidate["airport_total"] == 1
    assert candidate["frequency_type_counts"] == {"APP": 2}
    assert candidate["radios_with_multiple_runway_links"] == 2
    assert candidate["radios_with_multiple_airport_links"] == 0
    assert candidate["examples"] == [
        {
            "airport": "ZBAA",
            "airspace_id": "S1",
            "runway_direction_id": "D1",
            "source_file": "AIRSPACE_RADIO.csv",
            "frequency_type": "APP",
            "frequency": "120.0",
            "unit": "MHz",
            "sector": "APP01",
            "radio_id": "R1",
        },
        {
            "airport": "ZBAA",
            "airspace_id": "S1",
            "runway_direction_id": "D1",
            "source_file": "CONTROLLED_RADIO.csv",
            "frequency_type": "APP",
            "frequency": "121.0",
            "unit": "MHz",
            "sector": "APP02",
            "radio_id": "R1",
        },
    ]
