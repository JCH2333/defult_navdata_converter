from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .model import NavModel


class SourceModelCompletenessAuditError(RuntimeError):
    """原始 424 字段库存无法在只读边界内完成时抛出。"""


@dataclass(frozen=True)
class _SourceGroup:
    key: str
    source_files: tuple[str, ...]
    source_fields: tuple[str, ...]
    model_collections: tuple[str, ...]
    disposition: str
    target_scope: str
    reason: str


_RETAINED_GROUPS = (
    _SourceGroup(
        "airports",
        ("AD_HP.csv",),
        (
            "AD_HP.CODE_ID",
            "AD_HP.TXT_NAME",
            "AD_HP.GEO_LAT_ACCURACY",
            "AD_HP.GEO_LONG_ACCURACY",
            "AD_HP.VAL_ELEV",
            "AD_HP.VAL_TRANSITION_ALT",
            "AD_HP.VAL_TRANSITION_LEVEL",
            "AD_HP.VAL_MAG_VAR",
        ),
        ("airports",),
        "retained_and_projected",
        "airport",
        "字段已规范化到 Airport，默认 BGL 适配器消费该对象。",
    ),
    _SourceGroup(
        "runways",
        ("RWY.csv", "RWY_DIRECTION.csv"),
        (
            "RWY.AD_HP_ID",
            "RWY.VAL_LEN",
            "RWY.VAL_WID",
            "RWY.CODE_COMPOSITION",
            "RWY_DIRECTION.RWY_ID",
            "RWY_DIRECTION.TXT_DESIG",
            "RWY_DIRECTION.VAL_TRUE_BRG",
            "RWY_DIRECTION.VAL_ELEV",
        ),
        ("runways",),
        "retained_and_projected",
        "airport/runway",
        "字段已规范化到 Runway；跑道端坐标由来源机场、真方位和长度确定性计算。",
    ),
    _SourceGroup(
        "navaids",
        ("VOR.csv", "NDB.csv"),
        (
            "VOR.CODE_ID",
            "VOR.GEO_LAT_ACCURACY",
            "VOR.GEO_LONG_ACCURACY",
            "VOR.VAL_FREQ",
            "VOR.VAL_MAG_VAR",
            "VOR.VAL_ELEV",
            "VOR.SERVICED_AIRPORT",
            "VOR.CODE_FIR",
            "NDB.CODE_ID",
            "NDB.GEO_LAT_ACCURACY",
            "NDB.GEO_LONG_ACCURACY",
            "NDB.VAL_FREQ",
            "NDB.VAL_MAG_VAR",
            "NDB.VAL_ELEV",
            "NDB.SERVICED_AIRPORT",
            "NDB.CODE_FIR",
        ),
        ("navaids",),
        "retained_and_projected",
        "enroute",
        "字段已规范化到 Navaid；官方索引只决定同一物理身份的替换选择，不提供内容。",
    ),
    _SourceGroup(
        "designated_points",
        ("DESIGNATED_POINT.csv",),
        (
            "DESIGNATED_POINT.CODE_ID",
            "DESIGNATED_POINT.TXT_NAME",
            "DESIGNATED_POINT.GEO_LAT_ACCURACY",
            "DESIGNATED_POINT.GEO_LONG_ACCURACY",
            "DESIGNATED_POINT.SERVICED_AIRPORT",
            "DESIGNATED_POINT.CODE_FIR",
        ),
        ("waypoints",),
        "retained_and_projected",
        "enroute",
        "字段已规范化到 Waypoint；区域恢复只使用同周期 424 FIR/航路证据。",
    ),
    _SourceGroup(
        "airways",
        ("RTE_SEG.csv", "SEGMENT.csv", "EN_ROUTE_RTE.csv"),
        (
            "RTE_SEG.TXT_DESIG",
            "RTE_SEG.VAL_SORT",
            "RTE_SEG.CODE_POINT_START",
            "RTE_SEG.CODE_POINT_END",
            "RTE_SEG.GEO_LAT_START_ACCURACY",
            "RTE_SEG.GEO_LONG_START_ACCURACY",
            "RTE_SEG.GEO_LAT_END_ACCURACY",
            "RTE_SEG.GEO_LONG_END_ACCURACY",
            "RTE_SEG.CODE_TYPE",
            "RTE_SEG.SEGMENT_ID",
            "RTE_SEG.EN_ROUTE_RTE_ID",
            "SEGMENT.TXT_DESIG_RNP",
            "SEGMENT.VAL_MTCA",
            "EN_ROUTE_RTE.TXT_LOC_TYPE",
            "EN_ROUTE_RTE.VAL_MTCA",
        ),
        ("airway_legs",),
        "retained_and_projected",
        "enroute",
        "字段已规范化到 AirwayLeg；不能由 PBN CODE_TYPE 猜测目标航路类别。",
    ),
)

_AUDIT_ONLY_GROUPS = (
    _SourceGroup(
        "fir_geometry",
        ("AIRSPACE.csv", "AIRSPACE_BORDER_VERTEX.csv"),
        (
            "AIRSPACE.CODE_TYPE",
            "AIRSPACE.CODE_ID",
            "AIRSPACE.AIRSPACE_ID",
            "AIRSPACE_BORDER_VERTEX.AIRSPACE_ID",
            "AIRSPACE_BORDER_VERTEX.NO_SEQ",
            "AIRSPACE_BORDER_VERTEX.GEO_LAT",
            "AIRSPACE_BORDER_VERTEX.GEO_LONG",
        ),
        ("source_fir_region_resolution",),
        "source_evidence_only",
        "region-resolution",
        "FIR 多边形只证明空白指定点的区域，当前不形成独立默认 BGL 空域对象。",
    ),
    _SourceGroup(
        "route_holdings",
        ("ROUTE_HOLDING.csv",),
        (
            "ROUTE_HOLDING.ROUTE_HOLDING_ID",
            "ROUTE_HOLDING.POINT_ID",
            "ROUTE_HOLDING.HOLDING_TYPE",
            "ROUTE_HOLDING.GEO_LAT_ACCURACY",
            "ROUTE_HOLDING.GEO_LONG_ACCURACY",
            "ROUTE_HOLDING.CODE_DIRECTION",
            "ROUTE_HOLDING.VAL_DISTANCE",
            "ROUTE_HOLDING.VAL_ANGLE",
            "ROUTE_HOLDING.VAL_MIN_HEIGHT",
            "ROUTE_HOLDING.VAL_MAX_HEIGHT",
            "ROUTE_HOLDING.VAL_SPEED_LIMIT",
            "ROUTE_HOLDING.VAL_RADIUS",
        ),
        (),
        "source_evidence_only",
        "airport/holding-or-enroute",
        (
            "ROUTE_HOLDING 通过 POINT_ID 提供保持参数和部分固定点身份，但不携带机场、"
            "终端程序、跑道或结构化航路归属；独立关系审计未授权默认 BGL 投影。"
        ),
    ),
    _SourceGroup(
        "route_restrictions",
        ("ROUTE_RESTRICT.csv", "ROUTE_RESTRICT_RTE.csv"),
        (
            "ROUTE_RESTRICT.ROUTE_RESTRICT_ID",
            "ROUTE_RESTRICT.REMARK_CHAR",
            "ROUTE_RESTRICT.SPECIAL_REMARK",
            "ROUTE_RESTRICT_RTE.ROUTE_RESTRICT_RTE_ID",
            "ROUTE_RESTRICT_RTE.ROUTE_RESTRICT_ID",
            "ROUTE_RESTRICT_RTE.ROUTE_SEGMENT_UUID",
        ),
        (),
        "source_evidence_only",
        "enroute/airway-restriction",
        (
            "ROUTE_RESTRICT ?????????/????????????"
            "MSFS ?? BGL ????????????????????????"
        ),
    ),
)

_UNMODELED_GROUPS = (
    _SourceGroup(
        "runway_threshold_displacement",
        ("RWY.csv", "RWY_DIRECTION.csv"),
        ("RWY.AD_HP_ID", "RWY_DIRECTION.RWY_ID", "RWY_DIRECTION.VAL_THR_DISPLACE"),
        (),
        "source_complete_current_target_rejected",
        "airport/runway",
        (
            "字段可合法编码为 SDK OffsetThreshold，但 r195/r246 已在当前默认 BGL "
            "profile 验证其不改变节类型或节计数，且未提高参考一致文件数。"
        ),
    ),
    _SourceGroup(
        "approach_sector_radios",
        (
            "AD_HP.csv",
            "APPSECTOR_RUNWAYDIRECTION.csv",
            "AIRSPACE_RADIO.csv",
            "CONTROLLED_RADIO.csv",
            "RESTRICTED_RADIO.csv",
            "SPECIAL_AIRSPACE_RADIO.csv",
        ),
        (
            "APPSECTOR_RUNWAYDIRECTION.AIRSPACE_ID",
            "APPSECTOR_RUNWAYDIRECTION.AD_HP_ID",
            "*_RADIO.TXT_FREQ_TYPE",
            "*_RADIO.VAL_FREQ",
        ),
        (),
        "rejected_by_source_scope_and_cardinality",
        "airspace/approach_sector",
        "扇区频率经空域和跑道方向关联机场，不是机场 Com/Tower；同一记录可服务多个跑道方向。",
    ),
)


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - matches the source loader boundary
        raise SourceModelCompletenessAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    text = _csv_text(path)
    return list(csv.DictReader(text.splitlines()))


def _headers(path: Path) -> set[str]:
    reader = csv.reader(_csv_text(path).splitlines())
    return set(next(reader, []))


def _split_source_field(field: str) -> tuple[str, str]:
    if "." not in field:
        raise SourceModelCompletenessAuditError(f"无效来源字段声明: {field}")
    filename, column = field.split(".", maxsplit=1)
    return f"{filename}.csv", column


def _field_present(headers: dict[str, set[str]], filename: str, column: str) -> bool:
    return column in headers.get(filename, set())


def _positive_displacement_rows(
    source_rows: dict[str, list[dict[str, str]]],
) -> int:
    return sum(
        _positive_number(row.get("VAL_THR_DISPLACE") or "")
        for row in source_rows.get("RWY_DIRECTION.csv", [])
    )


def _positive_number(value: str) -> bool:
    try:
        return float(value.strip() or "0") > 0
    except ValueError:
        return False


def _source_group_report(
    group: _SourceGroup,
    *,
    source_rows: dict[str, list[dict[str, str]]],
    source_headers: dict[str, set[str]],
    model: NavModel,
) -> dict[str, object]:
    missing_files = [
        filename for filename in group.source_files if filename not in source_rows
    ]
    missing_fields = []
    for field in group.source_fields:
        if field.startswith("*_RADIO."):
            column = field.split(".", maxsplit=1)[1]
            radio_files = [
                filename for filename in group.source_files if filename.endswith("_RADIO.csv")
            ]
            if not all(
                _field_present(source_headers, filename, column)
                for filename in radio_files
            ):
                missing_fields.append(field)
            continue
        filename, column = _split_source_field(field)
        if not _field_present(source_headers, filename, column):
            missing_fields.append(field)

    result: dict[str, object] = {
        "source_files": list(group.source_files),
        "source_fields": list(group.source_fields),
        "source_row_counts": {
            filename: len(source_rows.get(filename, []))
            for filename in group.source_files
        },
        "model_collections": list(group.model_collections),
        "model_record_counts": {
            name: len(getattr(model, name))
            if isinstance(getattr(model, name), (list, dict))
            else int(bool(getattr(model, name)))
            for name in group.model_collections
        },
        "target_scope": group.target_scope,
        "disposition": group.disposition,
        "reason": group.reason,
        "source_complete": not missing_files and not missing_fields,
    }
    if missing_files:
        result["missing_source_files"] = missing_files
    if missing_fields:
        result["missing_source_fields"] = missing_fields
    if group.key == "runway_threshold_displacement":
        result["positive_displacement_record_total"] = _positive_displacement_rows(
            source_rows,
        )
        result["target_profile"] = "default-bgl-msfs2024-sdk-1.6.9"
        result["historical_probe_evidence"] = {
            "probe": "r195-offset-threshold",
            "consolidated_audit": "r246-historical-sdk-probe-evidence-v1",
            "result": "no_section_cardinality_effect",
        }
        result["reconsideration_gate"] = (
            "仅当目标格式、可哈希 SDK 或真实加载契约发生可复核变化时，才可建立新的隔离探针。"
        )
    if group.key == "approach_sector_radios":
        result["radio_file_row_total"] = sum(
            len(source_rows.get(filename, []))
            for filename in group.source_files
            if filename.endswith("_RADIO.csv")
        )
    return result


def audit_source_model_completeness(
    raw_root: Path,
    model: NavModel,
) -> dict[str, object]:
    """Inventory declared 424 source groups against current NavModel consumption.

    The audit deliberately does not inspect reference navigation payloads,
    Fenix data, OCR caches, candidates, or SDK output.  Its result can only
    identify a source-complete group for a later isolated contract probe; it
    never authorizes a model or adapter change by itself. Root CSV files that
    are not assigned to a declared group are reported explicitly rather than
    being silently treated as absent content.
    """

    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise SourceModelCompletenessAuditError(f"424 原始目录不存在: {root}")
    groups = _RETAINED_GROUPS + _AUDIT_ONLY_GROUPS + _UNMODELED_GROUPS
    filenames = sorted({filename for group in groups for filename in group.source_files})
    root_csv_files = sorted(path.name for path in root.glob("*.csv"))
    unclassified_csv_files = sorted(set(root_csv_files) - set(filenames))
    source_rows = {
        filename: _rows(root / filename)
        for filename in filenames
        if (root / filename).is_file()
    }
    source_headers = {
        filename: _headers(root / filename)
        for filename in source_rows
    }
    reports = {
        group.key: _source_group_report(
            group,
            source_rows=source_rows,
            source_headers=source_headers,
            model=model,
        )
        for group in groups
    }
    disposition_counts = Counter(
        str(item["disposition"]) for item in reports.values()
    )
    source_complete_candidates = [
        key
        for key, item in reports.items()
        if item["disposition"] == "source_complete_target_contract_unverified"
        and item["source_complete"]
        and int(item.get("positive_displacement_record_total", 0)) > 0
    ]
    source_complete_rejections = [
        key
        for key, item in reports.items()
        if item["disposition"] == "source_complete_current_target_rejected"
        and item["source_complete"]
    ]
    return {
        "diagnostic": "source-model-completeness-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "model_root": str(model.root),
            "csv_files_checked": filenames,
            "root_csv_files": root_csv_files,
        },
        "summary": {
            "declared_source_group_total": len(groups),
            "source_complete_group_total": sum(
                bool(item["source_complete"]) for item in reports.values()
            ),
            "root_csv_file_total": len(root_csv_files),
            "unclassified_csv_files": unclassified_csv_files,
            "unclassified_csv_file_total": len(unclassified_csv_files),
            "dispositions": dict(sorted(disposition_counts.items())),
            "source_complete_sdk_probe_candidates": source_complete_candidates,
            "source_complete_current_target_rejections": source_complete_rejections,
            "model_or_adapter_change_authorized": False,
        },
        "groups": reports,
    }


def write_source_model_completeness_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
