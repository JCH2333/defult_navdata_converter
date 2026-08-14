from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

from .model import NavModel


class SourceGapAuditError(RuntimeError):
    """语义差分不具备安全、完整的来源审计条件时抛出。"""


_WAYPOINT_FIELDS = ("ident", "region", "airport_ident")
_AIRWAY_FIELDS = (
    "airway_name",
    "airway_type",
    "route_type",
    "airway_fragment_no",
    "sequence_no",
)


def _normalized(value: object) -> str:
    return str(value or "").strip().upper()


def _reference_only_keys(
    report: Mapping[str, object],
    table: str,
    fields: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    if report.get("diagnostic") != "navdatareader-semantic-diff-v1":
        raise SourceGapAuditError("来源审计只接受 navdatareader-semantic-diff-v1 报告")
    if report.get("read_only") is not True or report.get("reference_values_redacted") is not True:
        raise SourceGapAuditError("来源审计只接受只读且已脱敏的语义差分报告")
    tables = report.get("tables")
    if not isinstance(tables, Mapping):
        raise SourceGapAuditError("语义差分缺少 tables")
    table_report = tables.get(table)
    if not isinstance(table_report, Mapping):
        raise SourceGapAuditError(f"语义差分缺少 {table} 表")
    samples = table_report.get("reference_only_samples")
    if not isinstance(samples, list):
        raise SourceGapAuditError(f"{table} 表缺少参考缺失样本")
    if int(table_report.get("reference_only_samples_omitted") or 0) != 0:
        raise SourceGapAuditError(
            f"{table} 表参考缺失样本被截断，不能用于完整来源审计"
        )
    expected = int(table_report.get("reference_only_logical_keys") or 0)
    if len(samples) != expected:
        raise SourceGapAuditError(
            f"{table} 表参考缺失样本数量与逻辑身份总数不一致"
        )
    result: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for sample in samples:
        if not isinstance(sample, Mapping) or not isinstance(sample.get("logical_key"), Mapping):
            raise SourceGapAuditError(f"{table} 表存在无效参考缺失样本")
        key = sample["logical_key"]
        if any(field not in key for field in fields):
            raise SourceGapAuditError(f"{table} 表参考缺失样本缺少逻辑身份字段")
        identity = tuple(key[field] for field in fields)
        if identity in seen:
            raise SourceGapAuditError(f"{table} 表参考缺失样本存在重复逻辑身份")
        seen.add(identity)
        result.append({field: key[field] for field in fields})
    return tuple(result)


def _waypoint_categories(
    model: NavModel,
    keys: tuple[dict[str, object], ...],
) -> dict[str, int]:
    designated_regions: dict[str, set[str]] = defaultdict(set)
    endpoint_regions: dict[str, set[str]] = defaultdict(set)
    for point in model.waypoints:
        designated_regions[_normalized(point.ident)].add(_normalized(point.country))
    for leg in model.airway_legs:
        endpoint_regions[_normalized(leg.start_ident)].add(_normalized(leg.start_country))
        endpoint_regions[_normalized(leg.end_ident)].add(_normalized(leg.end_country))

    categories: Counter[str] = Counter()
    for key in keys:
        if key["airport_ident"] not in (None, ""):
            categories["airport_scoped_reference_only"] += 1
            continue
        ident = _normalized(key["ident"])
        region = _normalized(key["region"])
        direct = designated_regions.get(ident, set())
        if direct:
            if region in direct:
                categories["direct_designated_same_region_unprojected"] += 1
            elif "" in direct:
                categories["direct_designated_region_unresolved"] += 1
            else:
                categories["direct_designated_different_region"] += 1
            continue
        endpoints = endpoint_regions.get(ident, set())
        if endpoints:
            if region in endpoints:
                categories["route_endpoint_same_region_unprojected"] += 1
            elif "" in endpoints:
                categories["route_endpoint_region_unresolved"] += 1
            else:
                categories["route_endpoint_different_region"] += 1
            continue
        categories["absent_from_structured_designated_and_route_endpoints"] += 1
    return dict(sorted(categories.items()))


def _airway_categories(
    model: NavModel,
    keys: tuple[dict[str, object], ...],
) -> dict[str, int]:
    source_sequences = {
        (_normalized(leg.airway), int(leg.sequence))
        for leg in model.airway_legs
    }
    source_airways = {_normalized(leg.airway) for leg in model.airway_legs}
    categories: Counter[str] = Counter()
    for key in keys:
        airway = _normalized(key["airway_name"])
        sequence = int(key["sequence_no"])
        if (airway, sequence) in source_sequences:
            categories["same_source_airway_and_sequence"] += 1
        elif airway in source_airways:
            categories["source_airway_name_with_different_sequence"] += 1
        else:
            categories["absent_from_rte_seg"] += 1
    return dict(sorted(categories.items()))


def audit_source_gaps(
    model: NavModel,
    semantic_report: Mapping[str, object],
) -> dict[str, object]:
    """Classify redacted reference gaps using only normalized 424 records.

    The report intentionally keeps reference logical identities in memory only.
    It returns source-category totals, so it can guide new source research
    without becoming a reference-field backfill channel.
    """
    waypoint_keys = _reference_only_keys(
        semantic_report, "waypoint", _WAYPOINT_FIELDS
    )
    airway_keys = _reference_only_keys(semantic_report, "airway", _AIRWAY_FIELDS)
    waypoint_categories = _waypoint_categories(model, waypoint_keys)
    airway_categories = _airway_categories(model, airway_keys)
    if sum(waypoint_categories.values()) != len(waypoint_keys):
        raise SourceGapAuditError("航点来源分类未覆盖全部参考缺失逻辑身份")
    if sum(airway_categories.values()) != len(airway_keys):
        raise SourceGapAuditError("航路来源分类未覆盖全部参考缺失逻辑身份")
    return {
        "diagnostic": "source-gap-audit-v2",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "designated_points": len(model.waypoints),
            "airway_legs": len(model.airway_legs),
        },
        "waypoint_reference_only_total": len(waypoint_keys),
        "waypoint_source_categories": waypoint_categories,
        "airway_reference_only_total": len(airway_keys),
        "airway_source_categories": airway_categories,
    }


def load_semantic_diff(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGapAuditError(f"无法读取语义差分报告: {path}") from error
    if not isinstance(payload, dict):
        raise SourceGapAuditError("语义差分报告根节点必须是对象")
    return payload


def write_source_gap_audit(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
