from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.airspace_source_audit import (
    audit_airspace_source,
    write_airspace_source_audit,
)
from fenix_default_navdata.model import NavModel


def test_airspace_source_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    for name in [
        "AIRSPACE.csv", "AIRSPACE_BORDER_VERTEX.csv", "AIRSPACE_CLASS.csv",
        "CONTROLLED.csv", "CONTROLLED_BORDER_VERTEX.csv", "CONTROLLED_CLASS.csv",
        "RESTRICTED.csv", "RESTRICTED_BORDER_VERTEX.csv", "RESTRICTED_CLASS.csv",
        "SPECIAL_AIRSPACE.csv", "SPECIAL_AIRSPACE_BORDER_VERTEX.csv", "SPECIAL_AIRSPACE_CLASS.csv",
    ]:
        (raw / name).write_text("AIRSPACE_ID\n1\n", encoding="utf-8")

    model = NavModel(raw)
    report = audit_airspace_source(raw, model)

    assert report["diagnostic"] == "airspace-source-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["total_airspace_main_records"] == 4
    assert report["summary"]["total_vertex_records"] == 4
    assert report["summary"]["total_class_records"] == 4
    assert report["summary"]["projection_allowed"] is False
    assert report["summary"]["disposition"] == "source_evidence_only"
    for group in report["summary"]["groups"].values():
        assert group["all_children_matched"] is True

    out_file = tmp_path / "out.json"
    write_airspace_source_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
