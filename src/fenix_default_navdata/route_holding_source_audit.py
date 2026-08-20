from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .model import NavModel


class RouteHoldingSourceAuditError(RuntimeError):
    """424 ROUTE_HOLDING 来源关系无法在只读边界内审计。"""


_POINT_SOURCE_FILES = (
    "DESIGNATED_POINT.csv",
    "NDB.csv",
    "VOR.csv",
)


def _decode_csv(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise RouteHoldingSourceAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> tuple[list[dict[str, str]], str]:
    text, encoding = _decode_csv(path)
    return list(csv.DictReader(text.splitlines())), encoding


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _source_point_ids(root: Path) -> tuple[dict[str, set[str]], dict[str, int], dict[str, str]]:
    ids: dict[str, set[str]] = {}
    counts: dict[str, int] = {}
    encodings: dict[str, str] = {}
    for filename in _POINT_SOURCE_FILES:
        path = root / filename
        if not path.is_file():
            ids[filename] = set()
            counts[filename] = 0
            continue
        rows, encoding = _rows(path)
        encodings[filename] = encoding
        ids[filename] = {
            _clean(row.get("SIGNIFICANT_POINT_ID"))
            for row in rows
            if _clean(row.get("SIGNIFICANT_POINT_ID"))
        }
        counts[filename] = len(rows)
    return ids, counts, encodings


def audit_route_holding_source(
    raw_root: Path,
    model: NavModel,
) -> dict[str, object]:
    """Audit ROUTE_HOLDING relationships without authorizing projection.

    ROUTE_HOLDING carries a point UUID and descriptive holding fields, but no
    airport, terminal procedure, runway, or structured airway owner.  Direct
    point-ID matches are useful source evidence; they do not establish the
    airport scope required by the default BGL HoldingPattern element.
    """

    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise RouteHoldingSourceAuditError(f"424 原始目录不存在: {root}")
    holding_path = root / "ROUTE_HOLDING.csv"
    if not holding_path.is_file():
        raise RouteHoldingSourceAuditError(f"缺少 ROUTE_HOLDING.csv: {holding_path}")

    rows, holding_encoding = _rows(holding_path)
    point_ids, point_row_counts, point_encodings = _source_point_ids(root)
    model_point_keys = {
        *(point.key for point in model.waypoints),
        *(point.key for point in model.navaids),
    }
    source_point_owner: dict[str, str] = {}
    for filename, ids in point_ids.items():
        for point_id in ids:
            source_point_owner.setdefault(point_id, filename)

    route_ids = [_clean(row.get("ROUTE_HOLDING_ID")) for row in rows]
    holding_point_ids = [_clean(row.get("POINT_ID")) for row in rows]
    matched_source_files: Counter[str] = Counter()
    matched_model_keys = 0
    rows_with_coordinates = 0
    rows_with_airport_field = 0
    rows_with_structured_airway_owner = 0
    unresolved_point_ids: list[str] = []
    for row, point_id in zip(rows, holding_point_ids):
        owner = source_point_owner.get(point_id)
        if owner:
            matched_source_files[owner] += 1
        else:
            unresolved_point_ids.append(point_id)
        if point_id in model_point_keys:
            matched_model_keys += 1
        if _clean(row.get("GEO_LAT_ACCURACY")) and _clean(
            row.get("GEO_LONG_ACCURACY")
        ):
            rows_with_coordinates += 1
        if any(_clean(row.get(field)) for field in ("AD_HP_ID", "AIRPORT_ID", "ICAO")):
            rows_with_airport_field += 1
        if any(
            _clean(row.get(field))
            for field in ("EN_ROUTE_RTE_ID", "RTE_SEG_ID", "SEGMENT_ID")
        ):
            rows_with_structured_airway_owner += 1

    duplicate_route_ids = {
        value: count
        for value, count in Counter(route_ids).items()
        if value and count > 1
    }
    duplicate_point_ids = {
        value: count
        for value, count in Counter(holding_point_ids).items()
        if value and count > 1
    }
    location_values = sorted(
        {_clean(row.get("LOCATION_POINT")) for row in rows if _clean(row.get("LOCATION_POINT"))}
    )
    desc_values = sorted(
        {_clean(row.get("TXT_AIRWAY_DESC")) for row in rows if _clean(row.get("TXT_AIRWAY_DESC"))}
    )
    report: dict[str, object] = {
        "diagnostic": "route-holding-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "files": {
                "ROUTE_HOLDING.csv": {
                    "rows": len(rows),
                    "encoding": holding_encoding,
                    "sha256": _file_sha256(holding_path),
                },
                **{
                    filename: {
                        "rows": point_row_counts[filename],
                        "encoding": point_encodings.get(filename),
                        "sha256": _file_sha256(root / filename)
                        if (root / filename).is_file()
                        else None,
                    }
                    for filename in _POINT_SOURCE_FILES
                },
            },
        },
        "table": {
            "row_count": len(rows),
            "unique_route_holding_id_count": len({value for value in route_ids if value}),
            "unique_point_id_count": len({value for value in holding_point_ids if value}),
            "duplicate_route_holding_ids": duplicate_route_ids,
            "duplicate_point_ids": duplicate_point_ids,
            "rows_with_coordinates": rows_with_coordinates,
            "location_point_values": location_values,
            "location_point_value_count": len(location_values),
            "unique_holding_description_count": len(desc_values),
        },
        "relationships": {
            "point_id_source_matches": dict(sorted(matched_source_files.items())),
            "point_id_source_match_rows": sum(matched_source_files.values()),
            "point_id_unresolved_rows": len(unresolved_point_ids),
            "unresolved_point_id_count": len(set(unresolved_point_ids)),
            "unresolved_point_ids": sorted(set(unresolved_point_ids)),
            "model_point_key_match_rows": matched_model_keys,
            "rows_with_explicit_airport_field": rows_with_airport_field,
            "rows_with_structured_airway_owner": rows_with_structured_airway_owner,
            "source_point_identity_is_uuid": all(
                len(value.split("-")) == 5 for value in holding_point_ids if value
            ),
        },
        "target": {
            "existing_model_holding_count": len(model.holdings),
            "holding_target_scope": "airport",
            "sdk_element": "HoldingPattern",
            "projection_allowed": False,
            "disposition": "source_evidence_only",
            "reason": (
                "ROUTE_HOLDING 可通过 POINT_ID 提供部分 424 固定点身份和保持参数，"
                "但没有机场、终端程序、跑道或结构化航路归属；坐标和描述不能替代机场作用域。"
            ),
            "reconsideration_gate": (
                "只有同周期 424 中出现可重放的机场/终端程序关系，或目标真实加载契约证明"
                "独立航路保持对象可表达，才可建立最小正反 fixture 并重新评估。"
            ),
        },
    }
    return report


def write_route_holding_source_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
