from __future__ import annotations

import json
import struct
from pathlib import Path

from fenix_default_navdata.model import (
    Airport,
    NavModel,
    Runway,
    SourceRef,
    Waypoint,
)
from fenix_default_navdata.projection_contribution_audit import (
    audit_projection_contributions,
    write_projection_contribution_audit,
)


def _bgl(section_type: int) -> bytes:
    body = bytes([section_type]) * 16
    return (
        struct.pack("<IIIIII", 0x19920201, 0x38, 0, 0, 0x08051803, 1)
        + struct.pack("<IIIIIIII", 0x20, 0, 0, 0, 0, 0, 0, 0)
        + struct.pack("<IIIII", section_type, 1, 1, 0x4C, 16)
        + body
    )


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("AIRPORT.csv", 2)
    airport = Airport(
        key="zbaa",
        icao="ZBAA",
        name="BEIJING CAPITAL",
        latitude=40.08,
        longitude=116.59,
        elevation_ft=116,
        transition_altitude=9800,
        transition_level=11800,
        source=source,
    )
    runway = Runway(
        key="zbaa-01",
        airport_key="zbaa",
        ident="01",
        true_heading=10.0,
        length_ft=12000,
        width_ft=150,
        surface="CON",
        elevation_ft=116,
        latitude=40.08,
        longitude=116.59,
        source=SourceRef("RWY_DIRECTION.csv", 2),
    )
    return NavModel(
        tmp_path,
        airports={"zbaa": airport},
        runways=[runway],
        waypoints=[
            Waypoint(
                key="point",
                ident="POINT",
                name="POINT",
                latitude=40.0,
                longitude=116.0,
                country="ZB",
                source=SourceRef("DESIGNATED_POINT.csv", 2),
            )
        ],
    )


def test_projection_contribution_audit_writes_xml_and_reads_candidate_headers(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    bgl_dir = candidate / "main" / "scenery"
    bgl_dir.mkdir(parents=True)
    (bgl_dir / "ZB_airports.bgl").write_bytes(_bgl(0x03))
    (bgl_dir / "00_enroute.bgl").write_bytes(_bgl(0x22))

    report = audit_projection_contributions(
        _model(tmp_path),
        candidate,
        tmp_path / "projection-xml",
    )

    assert report["diagnostic"] == "projection-contribution-audit-v1"
    assert report["candidate_modified"] is False
    assert report["reference_payload_read"] is False
    assert report["source_model"]["entity_counts"]["airports"] == 1
    assert report["source_model"]["source_references"]["airports"][
        "referenced_source_record_count"
    ] == 1
    rows = {row["path"]: row for row in report["generated_projection_xml"]}
    assert rows["ZB_airports.xml"]["xml_tag_counts"]["Airport"] == 1
    assert rows["00_enroute.xml"]["xml_tag_counts"]["Waypoint"] == 1
    assert {row["path"] for row in report["candidate_bgl_headers"]} == {
        "main/scenery/00_enroute.bgl",
        "main/scenery/zb_airports.bgl",
    }
    output = write_projection_contribution_audit(
        tmp_path / "projection-contribution-audit.json",
        report,
    )
    reread = json.loads(output.read_text(encoding="utf-8"))
    assert reread["generated_projection_xml"][0]["projection"]["path"].endswith(
        "00_enroute.xml"
    )
