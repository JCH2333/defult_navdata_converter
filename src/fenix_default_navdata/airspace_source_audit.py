from __future__ import annotations

import csv
import json
from pathlib import Path

from .model import NavModel


class AirspaceSourceAuditError(RuntimeError):
    """当空域与管制区类关系审计无法在只读边界内完成时抛出。"""


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AirspaceSourceAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return list(csv.DictReader(_csv_text(path).splitlines()))


def audit_airspace_source(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise AirspaceSourceAuditError(f"424 原始目录不存在: {root}")

    groups = {
        "fir": {
            "main": "AIRSPACE.csv",
            "vertex": "AIRSPACE_BORDER_VERTEX.csv",
            "class": "AIRSPACE_CLASS.csv",
        },
        "controlled": {
            "main": "CONTROLLED.csv",
            "vertex": "CONTROLLED_BORDER_VERTEX.csv",
            "class": "CONTROLLED_CLASS.csv",
        },
        "restricted": {
            "main": "RESTRICTED.csv",
            "vertex": "RESTRICTED_BORDER_VERTEX.csv",
            "class": "RESTRICTED_CLASS.csv",
        },
        "special_airspace": {
            "main": "SPECIAL_AIRSPACE.csv",
            "vertex": "SPECIAL_AIRSPACE_BORDER_VERTEX.csv",
            "class": "SPECIAL_AIRSPACE_CLASS.csv",
        },
    }

    group_reports = {}
    total_main_records = 0
    total_vertex_records = 0
    total_class_records = 0

    for group_key, file_map in groups.items():
        main_rows = _rows(root / file_map["main"])
        vertex_rows = _rows(root / file_map["vertex"])
        class_rows = _rows(root / file_map["class"])

        main_ids = {
            (r.get("AIRSPACE_ID") or "").strip()
            for r in main_rows
            if (r.get("AIRSPACE_ID") or "").strip()
        }
        vertex_matched = sum(
            1 for r in vertex_rows
            if (r.get("AIRSPACE_ID") or "").strip() in main_ids
        )
        class_matched = sum(
            1 for r in class_rows
            if (r.get("AIRSPACE_ID") or "").strip() in main_ids
        )

        total_main_records += len(main_rows)
        total_vertex_records += len(vertex_rows)
        total_class_records += len(class_rows)

        group_reports[group_key] = {
            "main_file": file_map["main"],
            "main_row_count": len(main_rows),
            "unique_airspace_id_count": len(main_ids),
            "vertex_file": file_map["vertex"],
            "vertex_row_count": len(vertex_rows),
            "vertex_matched_parent_count": vertex_matched,
            "class_file": file_map["class"],
            "class_row_count": len(class_rows),
            "class_matched_parent_count": class_matched,
            "all_children_matched": (
                vertex_matched == len(vertex_rows) and class_matched == len(class_rows)
            ),
        }

    return {
        "diagnostic": "airspace-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "airspace_file_groups": groups,
        },
        "summary": {
            "total_airspace_main_records": total_main_records,
            "total_vertex_records": total_vertex_records,
            "total_class_records": total_class_records,
            "groups": group_reports,
            "disposition": "source_evidence_only",
            "projection_allowed": False,
            "reason": (
                "424 空域类表（管制区、限制区、特别空域及其多边形顶点与垂直高度级别）"
                "与主表 AIRSPACE_ID 100% 完整关联；"
                "除 FIR 多边形用于航路点区域消歧外，MSFS 默认 BGL 目前无对应独立结构化空域对象，"
                "仅作为来源证据保留，不授权直接投影。"
            ),
        },
    }


def write_airspace_source_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
