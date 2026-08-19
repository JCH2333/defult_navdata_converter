from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .airway_endpoint_audit import audit_unresolved_airway_endpoints
from .model import NavModel
from .source import _airway_acc_names, _load_fir_acc_countries, _rows


class AirwayEndpointCardAuditError(ValueError):
    """单张航路端点来源卡不能由当前 424 输入唯一定位。"""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_designated_point(
    raw_root: Path,
    ident: str,
) -> tuple[int, dict[str, str]]:
    matches = [
        (row_number, row)
        for row_number, row in enumerate(
            _rows(raw_root / "DESIGNATED_POINT.csv"),
            start=2,
        )
        if (row.get("CODE_ID") or "").strip().upper() == ident
    ]
    if len(matches) != 1:
        raise AirwayEndpointCardAuditError(
            f"DESIGNATED_POINT.csv 中 {ident} 的唯一身份数为 {len(matches)}"
        )
    return matches[0]


def _raw_related_segments(
    raw_root: Path,
    point_id: str,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for row_number, row in enumerate(_rows(raw_root / "RTE_SEG.csv"), start=2):
        start_id = (row.get("POINT_START_ID") or "").strip()
        end_id = (row.get("POINT_END_ID") or "").strip()
        if point_id not in {start_id, end_id}:
            continue
        side = "start" if point_id == start_id else "end"
        items.append({
            "source_row": row_number,
            "airway": (row.get("TXT_DESIG") or "").strip().upper(),
            "sequence": int(float(row.get("VAL_SORT") or 0)),
            "side": side,
            "endpoint_fir": (
                row.get("CODE_FIR_START")
                if side == "start"
                else row.get("CODE_FIR_END")
            ) or "",
            "other_endpoint": {
                "ident": (
                    row.get("CODE_POINT_END")
                    if side == "start"
                    else row.get("CODE_POINT_START")
                ) or "",
                "type": (
                    row.get("CODE_TYPE_END")
                    if side == "start"
                    else row.get("CODE_TYPE_START")
                ) or "",
                "fir": (
                    row.get("CODE_FIR_END")
                    if side == "start"
                    else row.get("CODE_FIR_START")
                ) or "",
            },
            "acc_names": sorted(
                _airway_acc_names(row.get("Airspace_Remark") or "")
            ),
        })
    return sorted(
        items,
        key=lambda item: (
            str(item["airway"]),
            int(item["sequence"]),
            str(item["side"]),
        ),
    )


def audit_airway_endpoint_card(
    raw_root: Path,
    model: NavModel,
    *,
    ident: str,
) -> dict[str, object]:
    """Audit one designated route endpoint without modifying the NavModel.

    The review joins the exact designated-point identity to raw RTE_SEG rows
    using UUIDs, then compares direct FIR/serviced-airport facts with the
    model's already source-derived neighboring regions.  It never reads target
    packages, reference records, or Fenix data and never changes projection.
    """

    normalized_ident = ident.strip().upper()
    if not normalized_ident:
        raise AirwayEndpointCardAuditError("端点标识不能为空")
    raw_root = raw_root.expanduser().resolve()
    point_row, point = _find_designated_point(raw_root, normalized_ident)
    point_id = (point.get("SIGNIFICANT_POINT_ID") or "").strip()
    if not point_id:
        raise AirwayEndpointCardAuditError(
            f"DESIGNATED_POINT.csv 第 {point_row} 行缺少 SIGNIFICANT_POINT_ID"
        )
    endpoint_audit = audit_unresolved_airway_endpoints(model)
    matches = [
        item
        for item in endpoint_audit["items"]
        if item["endpoint"]["type"] == "DESIGNATED_POINT"
        and item["endpoint"]["ident"] == normalized_ident
    ]
    if len(matches) != 1:
        raise AirwayEndpointCardAuditError(
            f"NavModel 中 {normalized_ident} 的未决指定点身份数为 {len(matches)}"
        )
    model_item = matches[0]
    raw_segments = _raw_related_segments(raw_root, point_id)
    if not raw_segments:
        raise AirwayEndpointCardAuditError(
            f"RTE_SEG.csv 中没有引用 {normalized_ident} 的精确指定点 UUID"
        )
    acc_names = sorted({
        name
        for segment in raw_segments
        for name in segment["acc_names"]
    })
    fir_acc_countries = _load_fir_acc_countries(raw_root)
    mapped_acc = {
        name: fir_acc_countries[name]
        for name in acc_names
        if name in fir_acc_countries
    }
    unmapped_acc = sorted(set(acc_names) - mapped_acc.keys())
    direct_firs = sorted({
        str(segment["endpoint_fir"]).strip()
        for segment in raw_segments
        if str(segment["endpoint_fir"]).strip()
    })
    direct_region_blank = not (
        (point.get("CODE_FIR") or "").strip()
        or (point.get("SERVICED_AIRPORT") or "").strip()
        or direct_firs
    )
    model_category = str(model_item["category"])
    if (
        model_category == "multiple_neighbor_regions"
        and unmapped_acc
    ):
        disposition = (
            "rejected_multiple_neighbor_regions_with_incomplete_acc_evidence"
        )
        projection_allowed = False
        reason = (
            "相邻已解析地区不唯一，且至少一个航段 ACC 名称不能由 "
            "AIRSPACE.csv 的 FIR 标题唯一映射；不能以部分 ACC 映射或任一相邻地区"
            "发明区域键"
        )
    elif (
        direct_region_blank
        and model_category == "multiple_neighbor_regions"
    ):
        disposition = "rejected_multiple_neighbor_regions_with_blank_direct_region"
        projection_allowed = False
        reason = (
            "指定点自身 FIR/服务机场为空，关联航段端点 FIR 为空，"
            "且相邻已解析地区不唯一；不能从任一相邻地区发明区域键"
        )
    else:
        disposition = "unresolved_requires_new_direct_evidence"
        projection_allowed = False
        reason = "当前直接来源不足以唯一恢复端点区域"
    designated_path = raw_root / "DESIGNATED_POINT.csv"
    segment_path = raw_root / "RTE_SEG.csv"
    return {
        "diagnostic": "airway-endpoint-card-source-audit-v1",
        "read_only": True,
        "model_changed": False,
        "projection_changed": False,
        "reference_records_read": False,
        "fenix_records_read": False,
        "endpoint": {
            "ident": normalized_ident,
            "significant_point_id": point_id,
            "designated_point_source_row": point_row,
            "latitude": point.get("GEO_LAT_ACCURACY") or "",
            "longitude": point.get("GEO_LONG_ACCURACY") or "",
            "code_fir": point.get("CODE_FIR") or "",
            "serviced_airport": point.get("SERVICED_AIRPORT") or "",
        },
        "source_files": {
            "DESIGNATED_POINT.csv": _file_sha256(designated_path),
            "RTE_SEG.csv": _file_sha256(segment_path),
            "AIRSPACE.csv": _file_sha256(raw_root / "AIRSPACE.csv"),
        },
        "raw_related_segments": raw_segments,
        "direct_evidence": {
            "endpoint_firs": direct_firs,
            "acc_names": acc_names,
            "fir_acc_region_mappings": mapped_acc,
            "unmapped_acc_names": unmapped_acc,
        },
        "model_source_evidence": {
            "category": model_category,
            "neighbor_regions": model_item["neighbor_regions"],
            "related_legs": model_item["related_legs"],
        },
        "disposition": disposition,
        "projection_allowed": projection_allowed,
        "reason": reason,
    }


def write_airway_endpoint_card_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
