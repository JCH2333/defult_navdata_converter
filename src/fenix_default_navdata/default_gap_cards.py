from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .airway_endpoint_audit import audit_unresolved_airway_endpoints
from .model import NavModel, SourceRef
from .unclassified_procedure_audit import audit_unclassified_procedures


class DefaultGapCardAuditError(RuntimeError):
    """默认通用数据候选的来源缺口卡无法安全建立时抛出。"""


def _source_payload(source: SourceRef) -> dict[str, object]:
    return {
        "file": source.file,
        "row": source.row,
        "page": source.page,
        "sha256": source.sha256,
    }


def _load_candidate_report(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DefaultGapCardAuditError(f"无法读取候选报告: {path}") from error
    if not isinstance(payload, dict):
        raise DefaultGapCardAuditError("候选报告根节点必须是对象")
    if payload.get("status") != "candidate":
        raise DefaultGapCardAuditError("来源缺口卡只接受 candidate 候选报告")
    projection = payload.get("projection")
    if not isinstance(projection, Mapping):
        raise DefaultGapCardAuditError("候选报告缺少 projection")
    return payload


def _projection_airway_cards(
    model: NavModel,
    projection: Mapping[str, object],
) -> tuple[list[dict[str, object]], set[str]]:
    details = projection.get("skipped_airway_leg_details")
    expected = projection.get("skipped_airway_legs")
    if not isinstance(details, list) or not isinstance(expected, int):
        raise DefaultGapCardAuditError("候选报告缺少跳过航路段明细")
    if len(details) != expected:
        raise DefaultGapCardAuditError("跳过航路段明细数量与计数不一致")

    source_legs = {
        (leg.airway, leg.sequence, leg.start_ident, leg.end_ident): leg
        for leg in model.airway_legs
    }
    endpoint_audit = audit_unresolved_airway_endpoints(model)
    endpoint_items = endpoint_audit.get("items")
    if not isinstance(endpoint_items, list):
        raise DefaultGapCardAuditError("航路端点来源审计缺少明细")
    endpoint_evidence: dict[
        tuple[str, str, float | None, float | None],
        Mapping[str, object],
    ] = {}
    for item in endpoint_items:
        if not isinstance(item, Mapping) or not isinstance(item.get("endpoint"), Mapping):
            raise DefaultGapCardAuditError("航路端点来源审计明细格式无效")
        endpoint = item["endpoint"]
        endpoint_type = endpoint.get("type")
        ident = endpoint.get("ident")
        latitude = endpoint.get("latitude")
        longitude = endpoint.get("longitude")
        if not isinstance(endpoint_type, str) or not isinstance(ident, str):
            raise DefaultGapCardAuditError("航路端点来源审计缺少端点身份")
        endpoint_evidence[(
            endpoint_type,
            ident,
            round(float(latitude), 6) if latitude is not None else None,
            round(float(longitude), 6) if longitude is not None else None,
        )] = item
    cards: list[dict[str, object]] = []
    unresolved_idents: set[str] = set()
    for detail in details:
        if not isinstance(detail, Mapping):
            raise DefaultGapCardAuditError("跳过航路段明细格式无效")
        airway = detail.get("airway")
        sequence = detail.get("sequence")
        start = detail.get("start")
        end = detail.get("end")
        reasons = detail.get("reasons")
        if (
            not isinstance(airway, str)
            or not isinstance(sequence, int)
            or not isinstance(start, Mapping)
            or not isinstance(end, Mapping)
            or not isinstance(reasons, list)
        ):
            raise DefaultGapCardAuditError("跳过航路段明细缺少身份或拒绝原因")
        start_ident = start.get("ident")
        end_ident = end.get("ident")
        if not isinstance(start_ident, str) or not isinstance(end_ident, str):
            raise DefaultGapCardAuditError("跳过航路段端点标识无效")
        leg = source_legs.get((airway, sequence, start_ident, end_ident))
        if leg is None:
            raise DefaultGapCardAuditError("候选跳过航路段无法回链冻结 NavModel")
        start_region = str(start.get("region") or "")
        end_region = str(end.get("region") or "")
        unresolved_endpoints: list[dict[str, object]] = []
        for side, endpoint, region, latitude, longitude in (
            ("start", start, start_region, leg.start_latitude, leg.start_longitude),
            ("end", end, end_region, leg.end_latitude, leg.end_longitude),
        ):
            if region:
                continue
            endpoint_type = str(endpoint.get("type") or "")
            endpoint_ident = str(endpoint.get("ident") or "")
            evidence = endpoint_evidence.get((
                endpoint_type,
                endpoint_ident,
                round(latitude, 6) if latitude is not None else None,
                round(longitude, 6) if longitude is not None else None,
            ))
            if evidence is None:
                raise DefaultGapCardAuditError(
                    "候选空区域端点无法回链航路端点来源审计"
                )
            unresolved_endpoints.append({
                "side": side,
                "category": evidence.get("category"),
                "reason": evidence.get("reason"),
                "neighbor_regions": evidence.get("neighbor_regions"),
                "acc_names": evidence.get("acc_names"),
            })
        if not start_region:
            unresolved_idents.add(start_ident)
        if not end_region:
            unresolved_idents.add(end_ident)
        cards.append({
            "kind": "airway_endpoint_region",
            "key": f"{airway}:{sequence}",
            "disposition": "blocked_missing_endpoint_region",
            "source": _source_payload(leg.source),
            "airway": airway,
            "sequence": sequence,
            "start": {
                "ident": start_ident,
                "type": str(start.get("type") or ""),
                "region": start_region,
            },
            "end": {
                "ident": end_ident,
                "type": str(end.get("type") or ""),
                "region": end_region,
            },
            "reasons": sorted(str(reason) for reason in reasons),
            "unresolved_endpoint_evidence": unresolved_endpoints,
            "allowed_next_evidence": [
                "同周期 DESIGNATED_POINT.csv 的唯一身份与 FIR",
                "AIRSPACE.csv 与 AIRSPACE_BORDER_VERTEX.csv 的非边界 FIR 归属",
                "RTE_SEG.csv 的显式端点 ACC/FIR 证据",
                "与以上证据一致的受控邻接恢复",
            ],
        })
    return sorted(cards, key=lambda card: (card["airway"], card["sequence"])), unresolved_idents


def _projection_waypoint_cards(
    model: NavModel,
    projection: Mapping[str, object],
    unresolved_idents: set[str],
) -> list[dict[str, object]]:
    expected = projection.get("skipped_enroute_waypoints")
    if not isinstance(expected, int):
        raise DefaultGapCardAuditError("候选报告缺少跳过航路点计数")
    points = sorted(
        (
            point
            for point in model.waypoints
            if not point.country and point.ident in unresolved_idents
        ),
        key=lambda point: (point.ident, point.source.file, point.source.row or 0),
    )
    if len(points) != expected:
        raise DefaultGapCardAuditError(
            "候选跳过航路点与冻结 NavModel 的空区域端点数量不一致"
        )
    return [
        {
            "kind": "enroute_waypoint_region",
            "key": point.ident,
            "disposition": "blocked_missing_region",
            "source": _source_payload(point.source),
            "ident": point.ident,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "allowed_next_evidence": [
                "同周期 DESIGNATED_POINT.csv 的唯一 FIR/服务机场",
                "AIRSPACE FIR 多边形中的非边界唯一归属",
                "RTE_SEG.csv 端点的显式 ACC/FIR 证据",
                "全部相邻已恢复地区一致且 ACC 不冲突的邻接恢复",
            ],
        }
        for point in points
    ]


def _iap_cards(model: NavModel) -> list[dict[str, object]]:
    unresolved = model.iap_coverage.get("unresolved_groups")
    if not isinstance(unresolved, list):
        raise DefaultGapCardAuditError("NavModel 缺少 IAP 未决分组审计")
    rejected = {
        (item.airport, item.chart): item
        for item in model.rejected_procedures
    }
    cards: list[dict[str, object]] = []
    for item in unresolved:
        if not isinstance(item, Mapping):
            raise DefaultGapCardAuditError("IAP 未决分组格式无效")
        airport = item.get("airport")
        label = item.get("label")
        runway = item.get("runway")
        source = item.get("source")
        if (
            not isinstance(airport, str)
            or not isinstance(label, str)
            or not isinstance(runway, str)
            or not isinstance(source, Mapping)
        ):
            raise DefaultGapCardAuditError("IAP 未决分组缺少来源身份")
        rejected_item = rejected.get((airport, label))
        if rejected_item is None:
            raise DefaultGapCardAuditError("IAP 未决分组未同步到 RejectedProcedure")
        cards.append({
            "kind": "iap_primary_selection",
            "key": f"{airport}:{label}",
            "disposition": "rejected_no_unique_primary",
            "source": _source_payload(rejected_item.source),
            "airport": airport,
            "label": label,
            "runway": runway,
            "allowed_next_evidence": [
                "已有数据库主段与同周期 PDF 的直接标题/角色证据",
                "可重放且多次一致的 OCR 直接标题或角色证据",
                "唯一、保守的同页主段归属规则及正反例",
            ],
        })
    if len(cards) != len(model.rejected_procedures):
        raise DefaultGapCardAuditError("IAP 未决分组与拒绝程序数量不一致")
    return sorted(cards, key=lambda card: card["key"])


def _unclassified_cards(model: NavModel) -> list[dict[str, object]]:
    audit = audit_unclassified_procedures(model)
    items = audit.get("items")
    if not isinstance(items, list):
        raise DefaultGapCardAuditError("未分类程序审计缺少明细")
    cards: list[dict[str, object]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping) or not isinstance(item.get("source"), Mapping):
            raise DefaultGapCardAuditError("未分类程序审计明细格式无效")
        airport = item.get("airport")
        label = item.get("label")
        runway = item.get("runway")
        family = item.get("label_family")
        if not all(isinstance(value, str) for value in (airport, label, runway, family)):
            raise DefaultGapCardAuditError("未分类程序审计缺少身份字段")
        cards.append({
            "kind": "unclassified_procedure",
            "key": f"{airport}:{label}:{runway}:{index}",
            "disposition": "rejected_for_target_mapping",
            "source": dict(item["source"]),
            "airport": airport,
            "label": label,
            "runway": runway,
            "label_family": family,
            "source_chart_status": item.get("source_chart_status"),
            "allowed_next_evidence": [
                "同周期 424 直接字段明确给出的程序类别",
                "同一来源 PDF 的可重放直接标题证据",
            ],
        })
    return cards


def audit_default_gap_cards(
    model: NavModel,
    candidate_report_path: Path,
) -> dict[str, object]:
    """Create source-linked, target-safe cards for the remaining default gaps.

    The candidate report is generated by this converter and is used only for
    the converter's own skipped-projection identities. Reference BGL/SQLite
    records and Fenix data are never read or emitted.
    """

    report = _load_candidate_report(candidate_report_path)
    projection = report["projection"]
    assert isinstance(projection, Mapping)
    airway_cards, unresolved_idents = _projection_airway_cards(model, projection)
    waypoint_cards = _projection_waypoint_cards(
        model,
        projection,
        unresolved_idents,
    )
    iap_cards = _iap_cards(model)
    procedure_cards = _unclassified_cards(model)
    categories = {
        "airway_endpoint_region": airway_cards,
        "enroute_waypoint_region": waypoint_cards,
        "iap_primary_selection": iap_cards,
        "unclassified_procedure": procedure_cards,
    }
    totals = {name: len(items) for name, items in categories.items()}
    return {
        "diagnostic": "default-source-gap-cards-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "source": {
            "model_root": str(model.root),
            "candidate_report": str(candidate_report_path.expanduser().resolve()),
            "candidate_status": report["status"],
        },
        "summary": {
            "total": sum(totals.values()),
            "by_kind": totals,
            "all_cards_rejected_or_blocked": True,
        },
        "cards": categories,
    }


def write_default_gap_cards(path: Path, report: Mapping[str, object]) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
