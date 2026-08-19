from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.sdk_bgl_expression_matrix import audit_sdk_bgl_expression_matrix


def _write(path: Path, diagnostic: str, **values: object) -> Path:
    path.write_text(json.dumps({"diagnostic": diagnostic, **values}), encoding="utf-8")
    return path


def test_sdk_matrix_reports_no_new_machine_readable_variable(tmp_path: Path) -> None:
    report = audit_sdk_bgl_expression_matrix(
        _write(tmp_path / "inventory.json", "airport-source-inventory-v2", sdk_probe_candidates={"threshold": {"disposition": "eligible_for_sdk_probe"}}),
        _write(tmp_path / "projection.json", "airway-projection-matrix-audit-v1", classification_counts={"projected": 1}, candidate_connections_without_source_owner=0),
        _write(tmp_path / "cardinality.json", "enroute-bgl-cardinality-audit-v1", files=[{"section_deltas": [{"type": "0x22", "count_delta": -1}]}]),
        _write(tmp_path / "connection.json", "sdk_airway_connection_shape", airway_rows=[{}]),
        _write(tmp_path / "order.json", "sdk_airway_route_child_order", airway_rows=[{}]),
    )
    assert report["read_only"] is True
    assert report["matrix"]["enroute_route_serialization"]["source_xml_complete"] is True
    assert report["matrix"]["next_action"]["status"] == "blocked_on_machine_readable_target_evidence"
