from __future__ import annotations

import json
import csv
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from .model import NavModel


class AirportSourceInventoryError(RuntimeError):
    """机场来源库存输入不满足只读审计要求时抛出。"""


def _csv_rows(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - source.py has the same unsupported-input guard
        raise AirportSourceInventoryError(f"不支持的 CSV 编码: {path}")
    return list(csv.DictReader(text.splitlines()))


def _positive_number(value: str) -> bool:
    try:
        return float((value or "").strip() or "0") > 0
    except ValueError:
        return False


def _runway_offset_threshold_candidates(
    root: Path,
    *,
    airport_key_to_icao: dict[str, str],
) -> dict[str, object]:
    """List only direct 424 displacement rows with one SDK object equivalent."""

    runway_path = root / "RWY.csv"
    direction_path = root / "RWY_DIRECTION.csv"
    if not runway_path.is_file() or not direction_path.is_file():
        return {
            "source_records": 0,
            "source_files": ["RWY.csv", "RWY_DIRECTION.csv"],
            "source_fields": ["RWY_DIRECTION.VAL_THR_DISPLACE"],
            "target_scope": "airport/runway",
            "sdk_elements": ["Runway", "OffsetThreshold"],
            "disposition": "unavailable",
            "reason": "缺少用于跑道端位移审计的当期 424 CSV",
            "examples": [],
        }

    runways = {
        (row.get("RWY_ID") or "").strip(): row
        for row in _csv_rows(runway_path)
        if (row.get("RWY_ID") or "").strip()
    }
    matches: list[dict[str, object]] = []
    airport_counts: Counter[str] = Counter()
    for row_number, row in enumerate(_csv_rows(direction_path), start=2):
        displacement = (row.get("VAL_THR_DISPLACE") or "").strip()
        if not _positive_number(displacement):
            continue
        runway = runways.get((row.get("RWY_ID") or "").strip())
        if runway is None:
            continue
        airport = airport_key_to_icao.get(
            (runway.get("AD_HP_ID") or "").strip().upper(),
            "",
        )
        if not airport:
            continue
        airport_counts[airport] += 1
        matches.append({
            "airport": airport,
            "runway_ident": (row.get("TXT_DESIG") or "").strip().upper(),
            "displacement_meters": displacement,
            "source": {
                "file": "RWY_DIRECTION.csv",
                "row": row_number,
            },
        })

    return {
        "source_records": len(matches),
        "source_files": ["RWY.csv", "RWY_DIRECTION.csv"],
        "source_fields": ["RWY_DIRECTION.VAL_THR_DISPLACE"],
        "airport_counts": dict(sorted(airport_counts.items())),
        "target_scope": "airport/runway",
        "sdk_elements": ["Runway", "OffsetThreshold"],
        "disposition": "eligible_for_sdk_probe",
        "reason": (
            "424 字段和 SDK OffsetThreshold 的位移语义直接对应；"
            "仍须以单跑道探针验证 PRIMARY/SECONDARY 端映射和二进制影响，"
            "不得直接进入正式适配器"
        ),
        "examples": matches[:10],
    }


def _app_sector_radio_candidates(root: Path) -> dict[str, object]:
    """Audit airport-linked approach-sector radios without treating them as airport Com/Tower.

    ``APPSECTOR_RUNWAYDIRECTION`` links an airspace sector to airport runway
    directions, not to an airport radio facility.  A sector radio may repeat
    across several runway directions, so retain this source relationship for
    future adapters while explicitly blocking default-BGL Com/Tower projection.
    """

    source_files = [
        "AD_HP.csv",
        "APPSECTOR_RUNWAYDIRECTION.csv",
        "AIRSPACE_RADIO.csv",
        "CONTROLLED_RADIO.csv",
        "RESTRICTED_RADIO.csv",
        "SPECIAL_AIRSPACE_RADIO.csv",
    ]
    paths = {name: root / name for name in source_files}
    if not all(path.is_file() for path in paths.values()):
        return {
            "source_files": source_files,
            "target_scope": "unmodeled",
            "sdk_elements": ["Com", "Tower"],
            "disposition": "unavailable",
            "reason": "缺少用于进近扇区频率作用域审计的当期 424 CSV",
            "source_records": 0,
            "unique_radio_total": 0,
            "airport_total": 0,
            "examples": [],
        }

    airport_by_id = {
        (row.get("AD_HP_ID") or "").strip(): (row.get("CODE_ID") or "").strip().upper()
        for row in _csv_rows(paths["AD_HP.csv"])
        if (row.get("AD_HP_ID") or "").strip() and (row.get("CODE_ID") or "").strip()
    }
    radios_by_airspace: dict[str, list[dict[str, str]]] = {}
    radio_files = source_files[2:]
    for source_file in radio_files:
        for row in _csv_rows(paths[source_file]):
            airspace_id = (row.get("AIRSPACE_ID") or "").strip()
            if not airspace_id:
                continue
            radios_by_airspace.setdefault(airspace_id, []).append({
                **row,
                "_source_file": source_file,
            })

    linked: list[dict[str, str]] = []
    for link in _csv_rows(paths["APPSECTOR_RUNWAYDIRECTION.csv"]):
        airport = airport_by_id.get((link.get("AD_HP_ID") or "").strip())
        if not airport:
            continue
        runway_direction = (link.get("RWY_DIRECTION_ID") or "").strip()
        for radio in radios_by_airspace.get((link.get("AIRSPACE_ID") or "").strip(), []):
            radio_id = (radio.get("RADIO_ID") or "").strip()
            if not radio_id:
                continue
            linked.append({
                "airport": airport,
                "airspace_id": (link.get("AIRSPACE_ID") or "").strip(),
                "runway_direction_id": runway_direction,
                "source_file": (radio.get("_source_file") or "").strip(),
                "radio_id": radio_id,
                "frequency_type": (radio.get("TXT_FREQ_TYPE") or "").strip(),
                "frequency": (radio.get("VAL_FREQ") or "").strip(),
                "unit": (radio.get("UOM_FREQ") or "").strip(),
                "sector": (radio.get("TXT_SECTOR") or "").strip(),
            })

    radio_links: dict[tuple[str, str], list[dict[str, str]]] = {}
    for item in linked:
        radio_links.setdefault((item["source_file"], item["radio_id"]), []).append(item)
    unique_radios = [
        min(items, key=lambda item: (
            item["airport"],
            item["airspace_id"],
            item["runway_direction_id"],
        ))
        for _, items in sorted(radio_links.items())
    ]
    repeated_by_runway = sum(
        len({item["runway_direction_id"] for item in items}) > 1
        for items in radio_links.values()
    )
    repeated_by_airport = sum(
        len({item["airport"] for item in items}) > 1
        for items in radio_links.values()
    )
    return {
        "source_files": source_files,
        "source_fields": [
            "APPSECTOR_RUNWAYDIRECTION.AIRSPACE_ID",
            "APPSECTOR_RUNWAYDIRECTION.AD_HP_ID",
            "*_RADIO.TXT_FREQ_TYPE",
            "*_RADIO.VAL_FREQ",
        ],
        "target_scope": "airspace/approach_sector",
        "sdk_elements": ["Com", "Tower"],
        "disposition": "rejected_by_scope_and_cardinality",
        "reason": (
            "进近扇区频率只通过空域和跑道方向关联机场；"
            "其类型表示空域扇区而非机场通信设施，且同一记录可关联多个跑道方向，"
            "不能投影为 Com/Tower"
        ),
        "source_records": len(linked),
        "unique_radio_total": len(unique_radios),
        "airport_total": len({item["airport"] for item in linked}),
        "frequency_type_counts": dict(sorted(
            Counter(item["frequency_type"] for item in unique_radios).items(),
        )),
        "radios_with_multiple_runway_links": repeated_by_runway,
        "radios_with_multiple_airport_links": repeated_by_airport,
        "examples": [
            {
                key: item[key]
                for key in (
                    "airport",
                    "airspace_id",
                    "runway_direction_id",
                    "source_file",
                    "frequency_type",
                    "frequency",
                    "unit",
                    "sector",
                    "radio_id",
                )
            }
            for item in unique_radios[:10]
        ],
    }


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
        "diagnostic": "airport-source-inventory-v2",
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
        "sdk_probe_candidates": {
            "runway_offset_thresholds": _runway_offset_threshold_candidates(
                model.root,
                airport_key_to_icao=airport_key_to_icao,
            ),
            "runway_surface": {
                "source_fields": ["RWY.CODE_COMPOSITION"],
                "target_scope": "airport/runway",
                "sdk_elements": ["Runway"],
                "disposition": "rejected_after_r194",
                "reason": (
                    "r194 已证明 surface 仅改变既有 Runway 编码，"
                    "不产生候选缺失的 0x17/0x33 节"
                ),
            },
            "airport_associated_navaids": {
                "source_fields": ["VOR.SERVICED_AIRPORT", "NDB.SERVICED_AIRPORT"],
                "target_scope": "enroute_only",
                "sdk_elements": ["Vor", "Ndb"],
                "disposition": "rejected_by_source_scope",
                "reason": "机场关联字段不能推导为机场子对象投影",
            },
            "airspace_radios": _app_sector_radio_candidates(model.root),
        },
        "source_rejection_reasons": dict(sorted(rejection_reasons.items())),
        "candidate_xml_tag_counts": _xml_tag_counts(candidate_xml),
    }


def write_airport_source_inventory(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
