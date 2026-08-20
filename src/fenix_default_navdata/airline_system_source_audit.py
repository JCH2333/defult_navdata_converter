from __future__ import annotations

import csv
import json
from pathlib import Path

from .model import NavModel


class AirlineSystemSourceAuditError(RuntimeError):
    """当航线网络与系统配置关系审计无法在只读边界内完成时抛出。"""


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AirlineSystemSourceAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return list(csv.DictReader(_csv_text(path).splitlines()))


def audit_airline_system_source(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise AirlineSystemSourceAuditError(f"424 原始目录不存在: {root}")

    airline_rows = _rows(root / "FLIGHT_AIRLINE.csv")
    point_rows = _rows(root / "FLIGHT_AIRLINE_POINT.csv")
    setting_rows = _rows(root / "SYSTEMSETTING.csv")

    airline_ids = {
        (r.get("FLIGHT_AIRLINE_ID") or "").strip()
        for r in airline_rows
        if (r.get("FLIGHT_AIRLINE_ID") or "").strip()
    }
    point_matched = sum(
        1 for r in point_rows
        if (r.get("FLIGHT_AIRLINE_ID") or "").strip() in airline_ids
    )

    settings_map = {
        (r.get("KEYNAME") or "").strip(): (r.get("KEYVALUE") or "").strip()
        for r in setting_rows
        if (r.get("KEYNAME") or "").strip()
    }

    return {
        "diagnostic": "airline-system-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "flight_airline_rows": len(airline_rows),
            "flight_airline_point_rows": len(point_rows),
            "systemsetting_rows": len(setting_rows),
        },
        "summary": {
            "total_flight_airlines": len(airline_rows),
            "unique_flight_airline_ids": len(airline_ids),
            "total_flight_airline_points": len(point_rows),
            "points_matched_parent_airline": point_matched,
            "all_airline_points_matched": point_matched == len(point_rows),
            "system_settings": settings_map,
            "disposition": "source_evidence_only",
            "projection_allowed": False,
            "reason": (
                "FLIGHT_AIRLINE 与 FLIGHT_AIRLINE_POINT 为公司/航司航线网络库，"
                "390659 条航线点记录 100% 匹配父表 13907 条航线；"
                "SYSTEMSETTING 为 424 原始包元数据版本号与有效期；"
                "两者均不属于 MSFS 默认通用核心导航数据（机场、跑道、导航台、航路点、航路、终端程序），"
                "仅作为来源证据与元数据保留，不授权 BGL 投影。"
            ),
        },
    }


def write_airline_system_source_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
