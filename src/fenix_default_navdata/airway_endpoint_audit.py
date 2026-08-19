from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .model import AirwayLeg, NavModel
from .source import _airway_acc_names


def _endpoint_key(
    endpoint_type: str,
    ident: str,
    latitude: float | None,
    longitude: float | None,
) -> tuple[str, str, float | None, float | None]:
    return (
        (endpoint_type or "").strip().upper(),
        (ident or "").strip().upper(),
        round(latitude, 6) if latitude is not None else None,
        round(longitude, 6) if longitude is not None else None,
    )


def _leg_source(leg: AirwayLeg) -> dict[str, object]:
    return {
        "airway": leg.airway,
        "sequence": leg.sequence,
        "file": leg.source.file,
        "row": leg.source.row,
    }


def audit_unresolved_airway_endpoints(model: NavModel) -> dict[str, object]:
    """Explain source-only reasons that prevent enroute endpoint projection."""

    neighbors: dict[
        tuple[str, str, float | None, float | None],
        set[str],
    ] = defaultdict(set)
    acc_names: dict[
        tuple[str, str, float | None, float | None],
        set[str],
    ] = defaultdict(set)
    related_legs: dict[
        tuple[str, str, float | None, float | None],
        list[dict[str, object]],
    ] = defaultdict(list)
    blank_keys: set[tuple[str, str, float | None, float | None]] = set()

    for leg in model.airway_legs:
        endpoints = (
            (
                "start",
                leg.start_type,
                leg.start_ident,
                leg.start_latitude,
                leg.start_longitude,
                leg.start_country,
            ),
            (
                "end",
                leg.end_type,
                leg.end_ident,
                leg.end_latitude,
                leg.end_longitude,
                leg.end_country,
            ),
        )
        for index, (
            side,
            endpoint_type,
            ident,
            latitude,
            longitude,
            country,
        ) in enumerate(endpoints):
            if country:
                continue
            key = _endpoint_key(endpoint_type, ident, latitude, longitude)
            blank_keys.add(key)
            other = endpoints[1 - index]
            other_country = str(other[5] or "").strip().upper()
            if other_country:
                neighbors[key].add(other_country)
            acc_names[key].update(_airway_acc_names(leg.source_airspace_remark))
            related_legs[key].append({
                "side": side,
                "other_endpoint_type": str(other[1] or "").strip().upper(),
                "other_endpoint_ident": str(other[2] or "").strip().upper(),
                "other_endpoint_region": other_country,
                **_leg_source(leg),
            })

    waypoints = {
        _endpoint_key("DESIGNATED_POINT", point.ident, point.latitude, point.longitude):
        point
        for point in model.waypoints
    }
    items: list[dict[str, object]] = []
    categories: dict[str, int] = defaultdict(int)
    skipped_legs = 0
    for key in sorted(blank_keys):
        endpoint_type, ident, latitude, longitude = key
        endpoint_legs = sorted(
            related_legs[key],
            key=lambda item: (
                str(item["airway"]),
                int(item["sequence"]),
                str(item["side"]),
            ),
        )
        skipped_legs += len(endpoint_legs)
        point = waypoints.get(key)
        regions = sorted(neighbors[key])
        endpoint_acc_names = sorted(acc_names[key])
        if endpoint_type != "DESIGNATED_POINT":
            category = "non_designated_endpoint_identity_unavailable"
            reason = (
                "端点不在 DESIGNATED_POINT.csv 的可唯一身份集合中，"
                "不能仅凭相邻航段发明区域键"
            )
        elif point is None:
            category = "designated_point_identity_not_found"
            reason = "RTE_SEG 端点不能唯一回链到 DESIGNATED_POINT.csv"
        elif len(regions) > 1:
            category = "multiple_neighbor_regions"
            reason = "所有已解析相邻端点并非同一地区，保持跨 FIR 边界点未决"
        elif len(regions) == 1 and endpoint_acc_names:
            category = "single_neighbor_region_with_acc_evidence"
            reason = (
                "虽然存在单一相邻地区，但航段 ACC 证据必须先与该地区一致，"
                "不能绕过来源 ACC 门禁自动恢复"
            )
        elif len(regions) == 1:
            category = "single_neighbor_region_not_recovered"
            reason = "存在单一相邻地区但当前来源恢复未写入；需要检查直接来源证据"
        else:
            category = "no_resolved_neighbor_region"
            reason = "没有可用于来源恢复的已解析相邻地区"
        categories[category] += 1
        items.append({
            "endpoint": {
                "type": endpoint_type,
                "ident": ident,
                "latitude": latitude,
                "longitude": longitude,
                "designated_point_source": (
                    {
                        "file": point.source.file,
                        "row": point.source.row,
                    }
                    if point is not None
                    else None
                ),
            },
            "category": category,
            "reason": reason,
            "neighbor_regions": regions,
            "acc_names": endpoint_acc_names,
            "related_legs": endpoint_legs,
        })
    return {
        "diagnostic": "airway-endpoint-source-audit-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "waypoints": "DESIGNATED_POINT.csv",
            "airway_legs": "RTE_SEG.csv",
        },
        "unresolved_endpoint_total": len(items),
        "related_unprojected_leg_total": skipped_legs,
        "categories": dict(sorted(categories.items())),
        "items": items,
    }


def write_unresolved_airway_endpoint_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
