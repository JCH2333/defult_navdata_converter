from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .model import NavModel


class RouteRestrictSourceAuditError(RuntimeError):
    """当航路限制关系审计无法在只读边界内完成时抛出。"""


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RouteRestrictSourceAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return list(csv.DictReader(_csv_text(path).splitlines()))


def audit_route_restrict_source(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise RouteRestrictSourceAuditError(f"424 原始目录不存在: {root}")

    restrict_path = root / "ROUTE_RESTRICT.csv"
    restrict_rte_path = root / "ROUTE_RESTRICT_RTE.csv"

    restrict_rows = _rows(restrict_path)
    restrict_rte_rows = _rows(restrict_rte_path)

    restrict_ids = {
        (row.get("ROUTE_RESTRICT_ID") or "").strip()
        for row in restrict_rows
        if (row.get("ROUTE_RESTRICT_ID") or "").strip()
    }

    model_rte_seg_ids = {
        leg.source_rte_seg_id
        for leg in model.airway_legs
        if getattr(leg, "source_rte_seg_id", "")
    }
    model_point_keys = {point.key for point in model.waypoints}
    model_point_keys.update(navaid.key for navaid in model.navaids)

    rte_seg_matches = 0
    point_matches = 0
    parent_restrict_matches = 0

    for row in restrict_rte_rows:
        parent_id = (row.get("ROUTE_RESTRICT_ID") or "").strip()
        if parent_id in restrict_ids:
            parent_restrict_matches += 1

        seg_uuid = (row.get("ROUTE_SEGMENT_UUID") or "").strip()
        if seg_uuid and seg_uuid in model_rte_seg_ids:
            rte_seg_matches += 1

        pt_uuid = (row.get("AIRWAY_POINT_UUID") or "").strip()
        if pt_uuid and pt_uuid in model_point_keys:
            point_matches += 1

    return {
        "diagnostic": "route-restrict-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "files": {
                "ROUTE_RESTRICT.csv": len(restrict_rows),
                "ROUTE_RESTRICT_RTE.csv": len(restrict_rte_rows),
            },
        },
        "summary": {
            "route_restrict_total": len(restrict_rows),
            "route_restrict_rte_total": len(restrict_rte_rows),
            "parent_restrict_match_total": parent_restrict_matches,
            "rte_seg_match_total": rte_seg_matches,
            "point_match_total": point_matches,
            "disposition": "source_evidence_only",
            "projection_allowed": False,
            "reason": (
                "ROUTE_RESTRICT 及其关联表包含航路/航段文本说明与限制条件，"
                "MSFS 默认 BGL 目前无对应独立结构化空域或航路限制模型对象，仅作来源证据保留。"
            ),
        },
    }


def write_route_restrict_source_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
