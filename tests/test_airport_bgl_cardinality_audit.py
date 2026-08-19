from __future__ import annotations

import struct
from pathlib import Path

from fenix_default_navdata.airport_bgl_cardinality_audit import (
    audit_airport_bgl_cardinality,
)
from fenix_default_navdata.model import (
    Airport,
    Holding,
    Ils,
    NavModel,
    ProcedureSegment,
    Runway,
    SourceRef,
    TerminalWaypoint,
)


def _header(
    *,
    qmid: tuple[int, ...],
    sections: tuple[tuple[int, int, int, int, int], ...],
) -> bytes:
    payload = struct.pack(
        "<IIIIII",
        0x19920201,
        0x38,
        0,
        0,
        0x08051803,
        len(sections),
    )
    payload += struct.pack("<" + "I" * 8, *(qmid + (0,) * (8 - len(qmid)))[:8])
    for section in sections:
        payload += struct.pack("<IIIII", *section)
    return payload


def _model(root: Path) -> NavModel:
    source = SourceRef(file="AD_HP.csv", row=1)
    airport = Airport(
        key="airport:ZBAA",
        icao="ZBAA",
        name="Test",
        latitude=40.0,
        longitude=116.0,
        elevation_ft=100,
        transition_altitude=3000,
        transition_level=3600,
        source=source,
    )
    return NavModel(
        root=root,
        airports={airport.key: airport},
        runways=[
            Runway(
                key="runway:ZBAA:01",
                airport_key=airport.key,
                ident="01",
                true_heading=10.0,
                length_ft=10000,
                width_ft=150,
                surface="CONCRETE",
                elevation_ft=100,
                source=source,
            ),
        ],
        terminal_waypoints=[
            TerminalWaypoint(
                key="terminal:ZBAA:TEST",
                airport="ZBAA",
                ident="TEST",
                latitude=40.1,
                longitude=116.1,
                source=SourceRef(file="Terminal/ZBAA/ZBAA-4A.pdf", page=1),
            ),
        ],
        ilses=[
            Ils(
                airport="ZBAA",
                runway="01",
                ident="IAA",
                frequency_mhz=110.3,
                category="I",
                localizer_latitude=40.0,
                localizer_longitude=116.0,
                localizer_course_magnetic=10.0,
                glide_slope_degrees=3.0,
                crossing_height_meters=15.0,
                glide_slope_latitude=40.0,
                glide_slope_longitude=116.0,
                dme_latitude=40.0,
                dme_longitude=116.0,
                dme_elevation_meters=30.0,
                source=SourceRef(file="Terminal/ZBAA/ZBAA-2A.pdf", page=1),
            ),
        ],
        procedure_segments=[
            ProcedureSegment(
                airport="ZBAA",
                label="I01",
                kind="approach",
                runway="01",
                transition="",
                legs=(),
                source=SourceRef(file="Terminal/ZBAA/ZBAA-4A.pdf", page=1),
            ),
        ],
        holdings=[
            Holding(
                name="HOLD",
                fix_ident="TEST",
                fix_region="ZB",
                latitude=40.1,
                longitude=116.1,
                inbound_course=10.0,
                turn_direction="R",
                length_nm=5.0,
                time_minutes=None,
                minimum_altitude_ft=None,
                maximum_altitude_ft=None,
                speed_limit_knots=None,
                source=source,
            ),
        ],
    )


def test_airport_bgl_cardinality_audit_reports_headers_and_source_counts(tmp_path) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    relative = "airport-patch/scenery/airport/ZB_airports.bgl"
    candidate_path = candidate / relative
    reference_path = reference / relative
    candidate_path.parent.mkdir(parents=True)
    reference_path.parent.mkdir(parents=True)
    candidate_path.write_bytes(_header(
        qmid=(0x20,),
        sections=(
            (0x03, 1, 1, 0x90, 0x10),
            (0x22, 1, 2, 0xA0, 0x20),
        ),
    ))
    reference_path.write_bytes(_header(
        qmid=(0x20,),
        sections=(
            (0x03, 1, 1, 0xB8, 0x10),
            (0x17, 1, 100, 0xC8, 0x100),
            (0x22, 1, 2, 0x1C8, 0x20),
            (0x33, 1, 101, 0x1E8, 0x200),
        ),
    ))
    support = candidate / "support" / "scenery" / "airport" / "ZG_airports.bgl"
    support.parent.mkdir(parents=True)
    support.write_bytes(_header(
        qmid=(0x20,),
        sections=((0x03, 1, 1, 0x6C, 0x10),),
    ))
    model_path = tmp_path / "model.json.gz"
    model_path.write_bytes(b"frozen-model")

    report = audit_airport_bgl_cardinality(
        _model(tmp_path),
        candidate,
        reference,
        model_path=model_path,
    )

    assert report["diagnostic"] == "airport-bgl-cardinality-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["reference_payload_read"] is False
    assert report["section_type_semantics_inferred"] is False
    assert report["scope"] == {
        "reference_package_roots": ["airport-patch"],
        "candidate_excluded_sdk_work_bgl_files": 0,
        "candidate_excluded_support_package_bgl_files": 1,
        "reference_excluded_sdk_work_bgl_files": 0,
    }
    assert report["summary"] == {
        "candidate_airport_bgl_files": 1,
        "reference_airport_bgl_files": 1,
        "common_airport_bgl_files": 1,
        "all_reference_has_0x17": True,
        "all_candidate_lacks_0x17": True,
        "all_reference_has_0x33": True,
        "all_candidate_lacks_0x33": True,
    }
    assert report["model_sha256"]
    row = report["files"][0]
    assert row["region"] == "ZB"
    assert row["source_counts"] == {
        "airports": 1,
        "runway_directions": 1,
        "terminal_waypoints": 1,
        "ilses": 1,
        "procedure_segments": 1,
        "holdings": 1,
        "procedure_segments_approach": 1,
    }
    assert row["candidate_only_section_types"] == []
    assert row["reference_only_section_types"] == ["0x17", "0x33"]
    assert row["candidate"]["sections"] == [
        {"type": "0x3", "count": 1, "size": 0x10},
        {"type": "0x22", "count": 2, "size": 0x20},
    ]
    presence = {row["type"]: row for row in report["section_presence"]}
    assert presence["0x17"]["reference_only_file_total"] == 1
    assert presence["0x33"]["candidate_file_total"] == 0
