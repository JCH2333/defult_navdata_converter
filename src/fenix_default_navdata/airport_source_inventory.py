from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from .model import NavModel


class AirportSourceInventoryError(RuntimeError):
    """机场来源库存输入不满足只读审计要求时抛出。"""


def _source_file_summary(records: list[object]) -> dict[str, object]:
    files = sorted({
        str(getattr(getattr(record, "source", None), "file", "") or "")
        for record in records
    } - {""})
    groups = Counter(
        Path(name).parts[0] if len(Path(name).parts) > 1 else name
        for name in files
    )
    return {
        "source_file_total": len(files),
        "source_file_groups": dict(sorted(groups.items())),
        "source_file_examples": files[:10],
    }


def _airport_counts(
    records: list[object],
    *,
    attribute: str = "airport",
) -> dict[str, int]:
    counts = Counter(
        str(getattr(record, attribute, "") or "").strip().upper()
        for record in records
    )
    return {airport: count for airport, count in sorted(counts.items()) if airport}


def _xml_tag_counts(path: Path | None) -> dict[str, int] | None:
    if path is None:
        return None
    source = path.expanduser().resolve()
    if not source.is_file():
        raise AirportSourceInventoryError(f"候选 XML 不存在: {source}")
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as error:
        raise AirportSourceInventoryError(f"候选 XML 无法解析: {source}") from error
    return dict(sorted(Counter(element.tag for element in root.iter()).items()))


def _row(
    *,
    records: list[object],
    target_scope: str,
    sdk_elements: tuple[str, ...],
    disposition: str,
    airport_attribute: str = "airport",
    airport_key_map: dict[str, str] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    airport_counts = _airport_counts(records, attribute=airport_attribute)
    if airport_key_map is not None:
        airport_counts = dict(sorted(Counter({
            airport_key_map.get(key, key): count
            for key, count in airport_counts.items()
        }).items()))
    result: dict[str, object] = {
        "source_records": len(records),
        **_source_file_summary(records),
        "airport_counts": airport_counts,
        "target_scope": target_scope,
        "sdk_elements": list(sdk_elements),
        "disposition": disposition,
    }
    if reason:
        result["reason"] = reason
    return result


def build_airport_source_inventory(
    model: NavModel,
    *,
    candidate_xml: Path | None = None,
) -> dict[str, object]:
    """Describe source-backed airport objects without reading reference records.

    This is a reusable source/evidence boundary for target adapters and SDK
    probes. It never asks the reference package what objects should exist.
    """

    airports = list(model.airports.values())
    known_airport_keys = {airport.key.upper() for airport in airports}
    known_icaos = {airport.icao.upper() for airport in airports}
    airport_key_to_icao = {
        airport.key.upper(): airport.icao.upper() for airport in airports
    }
    runways = list(model.runways)
    terminal_waypoints = list(model.terminal_waypoints)
    ilses = list(model.ilses)
    procedures = list(model.procedure_segments)
    holdings = list(model.holdings)
    navaids = list(model.navaids)
    procedure_by_kind = {
        kind: [record for record in procedures if record.kind == kind]
        for kind in ("离场", "进场", "进近过渡", "进近", "复飞")
    }
    unclassified_procedures = [
        record for record in procedures if record.kind not in procedure_by_kind
    ]
    vor = [record for record in navaids if record.kind.upper() == "VOR"]
    ndb = [record for record in navaids if record.kind.upper() == "NDB"]
    associated_navaids = [
        record
        for record in navaids
        if str(record.serviced_airport or "").strip().upper() in known_icaos
    ]
    unknown_associated_navaids = [
        record
        for record in navaids
        if record.serviced_airport
        and str(record.serviced_airport).strip().upper() not in known_icaos
    ]
    unmatched_runways = [
        record for record in runways if record.airport_key.upper() not in known_airport_keys
    ]
    unmatched_ilses = [
        record for record in ilses if record.airport.upper() not in known_icaos
    ]
    rejection_reasons = Counter(
        f"{record.kind}:{record.reason}" for record in model.rejected_records
    )
    rejection_reasons.update(
        f"procedure:{record.reason}" for record in model.rejected_procedures
    )

    categories = {
        "airports": _row(
            records=airports,
            target_scope="airport",
            sdk_elements=("Airport", "DeleteAirport"),
            disposition="projected",
            airport_attribute="icao",
        ),
        "runways": _row(
            records=runways,
            target_scope="airport",
            sdk_elements=("Runway", "Ils"),
            disposition="projected" if not unmatched_runways else "partially_rejected",
            airport_attribute="airport_key",
            airport_key_map=airport_key_to_icao,
            reason=(
                "跑道必须通过来源机场键关联；无法关联的记录不能静默投影"
                if unmatched_runways
                else None
            ),
        ),
        "terminal_waypoints": _row(
            records=terminal_waypoints,
            target_scope="airport",
            sdk_elements=("Waypoint",),
            disposition="projected",
        ),
        "ils": _row(
            records=ilses,
            target_scope="airport/runway",
            sdk_elements=("Runway", "Ils"),
            disposition="projected" if not unmatched_ilses else "partially_rejected",
            reason=(
                "无法关联来源机场的 ILS 不能静默投影"
                if unmatched_ilses
                else None
            ),
        ),
        "departure_segments": _row(
            records=procedure_by_kind["离场"],
            target_scope="airport",
            sdk_elements=("Departure",),
            disposition="projected",
        ),
        "arrival_segments": _row(
            records=procedure_by_kind["进场"],
            target_scope="airport",
            sdk_elements=("Arrival",),
            disposition="projected",
        ),
        "approach_transition_segments": _row(
            records=procedure_by_kind["进近过渡"],
            target_scope="airport",
            sdk_elements=("Approach", "Transition", "TransitionLegs"),
            disposition="projected_with_rejections",
            reason=(
                "无唯一主进近证据的分组保留在 rejected_procedures，"
                "不得按参考包补写"
            ),
        ),
        "approach_segments": _row(
            records=procedure_by_kind["进近"],
            target_scope="airport",
            sdk_elements=("Approach", "ApproachLegs"),
            disposition="projected_with_rejections",
            reason=(
                "无唯一主进近证据的分组保留在 rejected_procedures，"
                "不得按参考包补写"
            ),
        ),
        "missed_approach_segments": _row(
            records=procedure_by_kind["复飞"],
            target_scope="airport",
            sdk_elements=("Approach", "MissedApproachLegs"),
            disposition="projected_with_rejections",
            reason=(
                "复飞只能与经来源证据确认的同一进近组一起投影，"
                "不得单独推断主进近"
            ),
        ),
        "unclassified_procedure_segments": _row(
            records=unclassified_procedures,
            target_scope="airport",
            sdk_elements=(),
            disposition="rejected_for_target_mapping",
            reason="程序段 kind 为空或不在已验证枚举中，必须先建立来源映射规则",
        ),
        "holdings": _row(
            records=holdings,
            target_scope="airport",
            sdk_elements=("HoldingPattern",),
            disposition="projected_after_terminal_identity_resolution",
            reason=(
                "Holding 源记录不直接携带机场字段，必须通过来源终端航点身份解析；"
                "不能按同名固定点猜测机场归属"
            ),
        ),
        "airport_associated_navaids": _row(
            records=associated_navaids,
            target_scope="enroute_only",
            sdk_elements=("Vor", "Ndb"),
            disposition="not_projected_as_airport_children",
            airport_attribute="serviced_airport",
            reason=(
                "机场关联字段本身不构成机场子对象投影规则；当前适配器只在根 "
                "enroute 作用域投影来源完整的导航台"
            ),
        ),
        "vor": _row(
            records=vor,
            target_scope="enroute",
            sdk_elements=("Vor", "Dme"),
            disposition="selected_by_official_identity_contract",
            reason="物理身份冲突只由官方基线索引判定，内容字段仍只来自 424",
        ),
        "ndb": _row(
            records=ndb,
            target_scope="enroute",
            sdk_elements=("Ndb",),
            disposition="selected_by_official_identity_contract",
            reason="不得把 NDB 诊断性节表效果直接变成机场适配器规则",
        ),
        "communications": {
            "source_records": 0,
            "source_file_total": 0,
            "source_file_groups": {},
            "source_file_examples": [],
            "airport_counts": {},
            "target_scope": "unmodeled",
            "sdk_elements": ["Com", "Tower"],
            "disposition": "not_ingested",
            "reason": "当前 NavModel 没有通信记录；须先建立 424 来源加载、字段契约和 fixture",
        },
        "ad219_vor_evidence": _row(
            records=list(model.ad219_vors),
            target_scope="evidence_only",
            sdk_elements=(),
            disposition="rejected_for_default_bgl",
            reason="AD 2.19 VOR/DME 表未提供默认 BGL 所需的完整磁差和高度契约",
        ),
    }

    return {
        "diagnostic": "airport-source-inventory-v1",
        "read_only": True,
        "reference_records_read": False,
        "source": {
            "model_root": str(model.root),
            "candidate_xml_read": str(candidate_xml.expanduser().resolve())
            if candidate_xml is not None
            else None,
        },
        "summary": {
            "airport_total": len(airports),
            "unmatched_runway_total": len(unmatched_runways),
            "ils_without_known_airport_total": len(unmatched_ilses),
            "navaids_with_unknown_serviced_airport_total": len(
                unknown_associated_navaids
            ),
            "rejected_record_total": len(model.rejected_records),
            "rejected_procedure_total": len(model.rejected_procedures),
            "unclassified_procedure_segment_total": len(unclassified_procedures),
        },
        "categories": categories,
        "source_rejection_reasons": dict(sorted(rejection_reasons.items())),
        "candidate_xml_tag_counts": _xml_tag_counts(candidate_xml),
    }


def write_airport_source_inventory(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
