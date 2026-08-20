from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint
from fenix_default_navdata.route_restrict_source_audit import (
    audit_route_restrict_source,
    write_route_restrict_source_audit,
)


def test_route_restrict_source_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    (raw / "ROUTE_RESTRICT.csv").write_text(
        "ROUTE_RESTRICT_ID,REMARK_CHAR,SPECIAL_REMARK,IS_MODIFIED\n"
        "res-1,1,W69 restriction,N\n",
        encoding="utf-8",
    )
    (raw / "ROUTE_RESTRICT_RTE.csv").write_text(
        "ROUTE_RESTRICT_RTE_ID,ROUTE_RESTRICT_ID,ROUTE_SEGMENT_UUID,AIRWAY_POINT_UUID\n"
        "rte-res-1,res-1,seg-1,\n"
        "rte-res-2,res-1,,pt-1\n",
        encoding="utf-8",
    )

    model = NavModel(raw)
    model.airway_legs.append(
        AirwayLeg(
            "W69",
            1,
            "FIX1",
            "FIX2",
            SourceRef("RTE_SEG.csv", 2),
            "F",
            30.0,
            110.0,
            31.0,
            111.0,
            "ZB",
            "ZB",
            source_rte_seg_id="seg-1",
        )
    )
    model.waypoints.append(
        Waypoint(
            "pt-1",
            "FIX1",
            "FIX1",
            30.0,
            110.0,
            SourceRef("DESIGNATED_POINT.csv", 2),
            "ZB",
        )
    )

    report = audit_route_restrict_source(raw, model)

    assert report["diagnostic"] == "route-restrict-source-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["route_restrict_total"] == 1
    assert report["summary"]["route_restrict_rte_total"] == 2
    assert report["summary"]["parent_restrict_match_total"] == 2
    assert report["summary"]["rte_seg_match_total"] == 1
    assert report["summary"]["point_match_total"] == 1
    assert report["summary"]["projection_allowed"] is False
    assert report["summary"]["disposition"] == "source_evidence_only"

    out_file = tmp_path / "out.json"
    write_route_restrict_source_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
