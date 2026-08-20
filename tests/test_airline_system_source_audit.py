from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.airline_system_source_audit import (
    audit_airline_system_source,
    write_airline_system_source_audit,
)
from fenix_default_navdata.model import NavModel


def test_airline_system_source_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    (raw / "FLIGHT_AIRLINE.csv").write_text(
        "FLIGHT_AIRLINE_ID,name\nline-1,ZBAA-ZSSS\n",
        encoding="utf-8",
    )
    (raw / "FLIGHT_AIRLINE_POINT.csv").write_text(
        "FLIGHT_AIRLINE_POINT_ID,FLIGHT_AIRLINE_ID,Sequnce\npt-1,line-1,1\n",
        encoding="utf-8",
    )
    (raw / "SYSTEMSETTING.csv").write_text(
        "KEYNAME,KEYVALUE\nDataVersion,2026-08.V1\n",
        encoding="utf-8",
    )

    model = NavModel(raw)
    report = audit_airline_system_source(raw, model)

    assert report["diagnostic"] == "airline-system-source-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["total_flight_airlines"] == 1
    assert report["summary"]["total_flight_airline_points"] == 1
    assert report["summary"]["points_matched_parent_airline"] == 1
    assert report["summary"]["all_airline_points_matched"] is True
    assert report["summary"]["system_settings"]["DataVersion"] == "2026-08.V1"
    assert report["summary"]["projection_allowed"] is False
    assert report["summary"]["disposition"] == "source_evidence_only"

    out_file = tmp_path / "out.json"
    write_airline_system_source_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
