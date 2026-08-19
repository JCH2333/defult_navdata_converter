from __future__ import annotations

import struct

from fenix_default_navdata.enroute_bgl_cardinality_audit import (
    audit_enroute_bgl_cardinality,
)
from fenix_default_navdata.model import NavModel, Navaid, SourceRef, Waypoint


def _header(sections: tuple[tuple[int, int, int, int, int], ...]) -> bytes:
    data = struct.pack("<IIIIII", 0x19920201, 0x38, 0, 0, 0x08051803, len(sections))
    data += struct.pack("<" + "I" * 8, 0x20, 0x21, 0, 0, 0, 0, 0, 0)
    for section in sections:
        data += struct.pack("<IIIII", *section)
    return data


def test_enroute_bgl_cardinality_audit_reports_only_headers_and_source_counts(tmp_path) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    relative = "pkg/scenery/nav/00_enroute.bgl"
    candidate_path = candidate / relative
    reference_path = reference / relative
    candidate_path.parent.mkdir(parents=True)
    reference_path.parent.mkdir(parents=True)
    candidate_path.write_bytes(_header((
        (0x13, 1, 10, 0x90, 0xA0),
        (0x20, 1, 4, 0x130, 0x60),
        (0x22, 1, 20, 0x190, 0x140),
    )))
    reference_path.write_bytes(_header((
        (0x13, 1, 12, 0x90, 0xC0),
        (0x20, 1, 4, 0x150, 0x60),
        (0x22, 1, 25, 0x1B0, 0x190),
    )))
    model = NavModel(
        root=tmp_path,
        navaids=[
            Navaid(
                key="vor:TEST",
                ident="TEST",
                kind="VOR",
                name="TEST",
                latitude=1.0,
                longitude=2.0,
                frequency=113.0,
                magnetic_variation=0.0,
                elevation_ft=0,
                country="ZB",
                source=SourceRef(file="VOR.csv", row=2),
            ),
        ],
        waypoints=[
            Waypoint(
                key="waypoint:TEST",
                ident="TEST",
                name="TEST",
                latitude=1.0,
                longitude=2.0,
                source=SourceRef(file="DESIGNATED_POINT.csv", row=2),
                country="ZB",
            ),
        ],
    )
    model_path = tmp_path / "model.json.gz"
    model_path.write_bytes(b"model")

    report = audit_enroute_bgl_cardinality(
        model,
        candidate,
        reference,
        model_path=model_path,
    )

    assert report["diagnostic"] == "enroute-bgl-cardinality-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["reference_payload_read"] is False
    assert report["section_type_semantics_inferred"] is False
    assert report["source_counts"] == {
        "navaids_by_kind": {"VOR": 1},
        "global_waypoints": 1,
        "airway_legs": 0,
        "airway_legs_with_resolved_regions": 0,
        "airway_legs_with_missing_region": 0,
        "enroute_navaid_evidence": 0,
        "enroute_airway_minimum_altitude_evidence": 0,
        "rejected_records_by_kind": {},
    }
    assert report["summary"] == {
        "candidate_enroute_bgl_files": 1,
        "reference_enroute_bgl_files": 1,
        "common_enroute_bgl_files": 1,
    }
    assert report["files"][0]["section_deltas"] == [
        {
            "type": "0x13",
            "candidate_count": 10,
            "reference_count": 12,
            "count_delta": -2,
            "candidate_size": 0xA0,
            "reference_size": 0xC0,
            "size_delta": -0x20,
        },
        {
            "type": "0x20",
            "candidate_count": 4,
            "reference_count": 4,
            "count_delta": 0,
            "candidate_size": 0x60,
            "reference_size": 0x60,
            "size_delta": 0,
        },
        {
            "type": "0x22",
            "candidate_count": 20,
            "reference_count": 25,
            "count_delta": -5,
            "candidate_size": 0x140,
            "reference_size": 0x190,
            "size_delta": -0x50,
        },
    ]
