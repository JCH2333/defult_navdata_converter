from pathlib import Path

from fenix_default_navdata.bgl import write_bglcomp_xml
from fenix_default_navdata.model import AirwayLeg, Navaid, NavModel, SourceRef
from fenix_default_navdata.official_overlay import (
    OfficialOverlayIndex,
    OfficialOverlayNavaid,
)
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_overlay_canonicalizes_facilities_and_retains_custom_airway_edges(
    tmp_path: Path,
) -> None:
    source = SourceRef("RTE_SEG.csv", 1)
    model = NavModel(tmp_path / "source")
    model.navaids.extend([
        Navaid(
            "ho",
            "HO",
            "NDB",
            "HO",
            35.2111129,
            107.7705688,
            375.0,
            4.16,
            40,
            "ZL",
            source,
        ),
        Navaid(
            "wha",
            "WHA",
            "VOR",
            "WHA",
            30.7816696,
            114.2033386,
            112.2,
            -4.9561,
            141,
            "ZH",
            source,
        ),
    ])
    model.airway_legs.extend([
        AirwayLeg(
            "H14",
            1,
            "HO",
            "P396",
            source,
            start_latitude=35.2100029,
            start_longitude=107.7683105,
            end_latitude=34.5972252,
            end_longitude=108.5258484,
            start_country="ZL",
            end_country="ZL",
            start_type="NDB",
            end_type="DESIGNATED_POINT",
        ),
        AirwayLeg(
            "B213",
            31,
            "OBDON",
            "WHA",
            source,
            start_latitude=30.7738914,
            start_longitude=114.0141602,
            end_latitude=30.7816696,
            end_longitude=114.2033386,
            start_country="ZH",
            end_country="ZH",
            start_type="DESIGNATED_POINT",
            end_type="VORDME",
        ),
    ])
    overlay = OfficialOverlayIndex(
        database=tmp_path / "official.sqlite",
        navaids=(
            OfficialOverlayNavaid(
                "NDB",
                "HO",
                "ZL",
                37500.0,
                35.2100029,
                107.7683105,
                -3.8528,
                40,
            ),
            OfficialOverlayNavaid(
                "VOR",
                "WHA",
                "ZH",
                112200.0,
                30.7816696,
                114.2033386,
                -4.9561,
                141,
            ),
        ),
        waypoint_identities=frozenset({
            ("NDB", "ZL", "HO"),
            ("VOR", "ZH", "WHA"),
        }),
        airway_edges=(
            (
                "B213",
                ("NAMED", "ZH", "OBDON"),
                30.7738914,
                114.0141602,
                ("VOR", "ZH", "WHA"),
                30.7816696,
                114.2033386,
            ),
        ),
    )

    output = tmp_path / "enroute.xml"
    projection = write_bglcomp_xml(
        model,
        DEFAULT_CYCLE,
        output,
        scope="enroute",
        selected_navaids=tuple(model.navaids),
        official_overlay=overlay,
    )

    text = output.read_text(encoding="utf-8")
    assert 'name="H14"' in text
    assert 'waypointIdent="P396"' in text
    assert 'name="B213"' in text
    assert 'lat="35.210003"' in text
    assert 'lon="107.76831"' in text
    assert '<Ndb ' in text
    assert '<Vor ' in text
    assert projection.official_canonicalized_navaids == 1
    assert projection.official_overlapping_airway_legs_retained == 1
