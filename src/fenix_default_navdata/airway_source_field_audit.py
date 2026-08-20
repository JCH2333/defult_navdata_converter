from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

from .model import NavModel
from .source_gap import (
    _field_delta_keys,
    _require_complete_reader_output,
)


class AirwaySourceFieldAuditError(RuntimeError):
    """航路来源字段审计输入不满足只读契约时抛出。"""


_KEY_FIELDS = (
    "airway_name",
    "airway_type",
    "route_type",
    "airway_fragment_no",
    "sequence_no",
)
_REQUIRED_COLUMNS = (*_KEY_FIELDS, "minimum_altitude")
_METERS_TO_FEET = 3.280839895013123


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validate_semantic_report(report: Mapping[str, object]) -> None:
    if report.get("diagnostic") != "navdatareader-semantic-diff-v1":
        raise AirwaySourceFieldAuditError(
            "只接受 navdatareader-semantic-diff-v1 报告"
        )
    if report.get("read_only") is not True:
        raise AirwaySourceFieldAuditError("语义差分必须声明 read_only=true")
    if report.get("reference_values_redacted") is not True:
        raise AirwaySourceFieldAuditError(
            "语义差分必须声明 reference_values_redacted=true"
        )
    try:
        _require_complete_reader_output(report)
        _field_delta_keys(report, "airway", _KEY_FIELDS)
    except Exception as error:
        raise AirwaySourceFieldAuditError(str(error)) from error


def _text(value: object) -> str:
    return str(value or "").strip()


def _key(row: Mapping[str, object]) -> tuple[str, str, str, int, int]:
    try:
        return (
            _text(row["airway_name"]).upper(),
            _text(row["airway_type"]).upper(),
            _text(row["route_type"]).upper(),
            int(row["airway_fragment_no"]),
            int(row["sequence_no"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AirwaySourceFieldAuditError("读取器 airway 逻辑键无效") from error


def _read_airway_rows(path: Path) -> list[dict[str, object]]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise AirwaySourceFieldAuditError(f"读取器数据库不存在: {path}")
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise AirwaySourceFieldAuditError(f"无法只读打开读取器数据库: {path}") from error
    try:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(airway)")
        }
        missing = sorted(set(_REQUIRED_COLUMNS) - columns)
        if missing:
            raise AirwaySourceFieldAuditError(
                f"读取器 airway 缺少字段: {','.join(missing)}"
            )
        rows = connection.execute(
            """
            SELECT airway_name, airway_type, route_type,
                   airway_fragment_no, sequence_no, minimum_altitude
            FROM airway
            ORDER BY airway_name, airway_type, route_type,
                     airway_fragment_no, sequence_no
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise AirwaySourceFieldAuditError(
            f"读取器 airway 查询失败: {path}"
        ) from error
    finally:
        connection.close()
    result: list[dict[str, object]] = []
    for row in rows:
        values = dict(zip(_REQUIRED_COLUMNS, row, strict=True))
        values["key"] = _key(values)
        try:
            values["minimum_altitude"] = int(values["minimum_altitude"] or 0)
        except (TypeError, ValueError) as error:
            raise AirwaySourceFieldAuditError(
                "读取器 minimum_altitude 不是整数"
            ) from error
        result.append(values)
    return result


def _parse_source_value(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not math.isfinite(parsed) or parsed < 0 or not parsed.is_integer():
        return None
    return int(parsed)


def _source_index(model: NavModel) -> dict[tuple[str, int], list[object]]:
    index: dict[tuple[str, int], list[object]] = defaultdict(list)
    for leg in model.airway_legs:
        index[(_text(leg.airway).upper(), int(leg.sequence))].append(leg)
    return index


def _source_evidence(leg: object) -> tuple[str, tuple[int, ...], bool]:
    route = _parse_source_value(
        getattr(leg, "source_route_minimum_crossing_altitude", "")
    )
    segment = _parse_source_value(
        getattr(leg, "source_segment_minimum_crossing_altitude", "")
    )
    values = tuple(value for value in (route, segment) if value is not None)
    if route is None and segment is None:
        category = "both_empty"
    elif route is None:
        category = "segment_only"
    elif segment is None:
        category = "route_only"
    elif route == segment:
        category = "both_same"
    else:
        category = "both_different"
    invalid = bool(
        _text(getattr(leg, "source_route_minimum_crossing_altitude", ""))
        and route is None
    ) or bool(
        _text(getattr(leg, "source_segment_minimum_crossing_altitude", ""))
        and segment is None
    )
    return category, values, invalid


def _transform_matches(values: tuple[int, ...], target: int) -> str | None:
    transforms = {
        "identity": lambda value: value,
        "meters_to_feet_floor": lambda value: math.floor(
            value * _METERS_TO_FEET
        ),
        "meters_to_feet_round": lambda value: round(
            value * _METERS_TO_FEET
        ),
        "meters_to_feet_ceil": lambda value: math.ceil(
            value * _METERS_TO_FEET
        ),
    }
    for name, transform in transforms.items():
        if any(transform(value) == target for value in values):
            return name
    return None


def audit_airway_source_fields(
    model: NavModel,
    semantic_report: Mapping[str, object],
    candidate_database: Path,
    reference_database: Path,
) -> dict[str, object]:
    """Compare 424 ``VAL_MTCA`` evidence with reader altitude semantics.

    The function is read-only.  It consumes reference values only to count
    transform matches; no reference value, key, or payload is written to the
    report.
    """
    _validate_semantic_report(semantic_report)
    candidate_rows = _read_airway_rows(candidate_database)
    reference_rows = _read_airway_rows(reference_database)
    source_index = _source_index(model)

    source_categories: Counter[str] = Counter()
    source_invalid = 0
    source_match_counts: Counter[str] = Counter()
    transform_matches: Counter[str] = Counter()
    reference_nonzero = 0
    reference_nonzero_with_source = 0
    reference_nonzero_source_matches = 0
    candidate_reference_altitude_deltas = 0
    matched_reference_rows = 0
    unmatched_reference_rows = 0

    for row in reference_rows:
        airway, _, _, _, sequence = row["key"]
        source_rows = source_index.get((airway, sequence), [])
        source_match_counts[str(len(source_rows))] += 1
        if len(source_rows) != 1:
            unmatched_reference_rows += 1
            continue
        matched_reference_rows += 1
        category, values, invalid = _source_evidence(source_rows[0])
        source_categories[category] += 1
        source_invalid += int(invalid)
        target = int(row["minimum_altitude"])
        if target == 0:
            continue
        reference_nonzero += 1
        if not values:
            continue
        reference_nonzero_with_source += 1
        transform = _transform_matches(values, target)
        if transform is not None:
            transform_matches[transform] += 1
            reference_nonzero_source_matches += 1

    candidate_by_key = {row["key"]: row for row in candidate_rows}
    reference_by_key = {row["key"]: row for row in reference_rows}
    delta_keys = {
        _key(key)
        for key, fields in _field_delta_keys(
            semantic_report,
            "airway",
            _KEY_FIELDS,
        )
        if "minimum_altitude" in fields
    }
    for key in delta_keys:
        candidate = candidate_by_key.get(key)
        reference = reference_by_key.get(key)
        if (
            candidate is not None
            and reference is not None
            and int(candidate["minimum_altitude"]) != int(
                reference["minimum_altitude"]
            )
        ):
            candidate_reference_altitude_deltas += 1

    if (
        reference_nonzero
        and reference_nonzero_source_matches == reference_nonzero
        and source_invalid == 0
    ):
        evidence_status = "source_transform_covers_all_reference_nonzero_rows"
    elif reference_nonzero_source_matches:
        evidence_status = "source_transform_partially_covers_reference_nonzero_rows"
    else:
        evidence_status = "no_source_transform_match"

    return {
        "diagnostic": "airway-source-field-audit-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "model_airway_legs": len(model.airway_legs),
            "unique_airway_sequence_keys": len(source_index),
        },
        "reader": {
            "candidate_airway_rows": len(candidate_rows),
            "reference_airway_rows": len(reference_rows),
            "matched_reference_rows": matched_reference_rows,
            "unmatched_or_ambiguous_reference_rows": unmatched_reference_rows,
            "source_match_count_distribution": dict(
                sorted(source_match_counts.items())
            ),
        },
        "source_val_mtca": {
            "evidence_categories": dict(sorted(source_categories.items())),
            "invalid_value_rows": source_invalid,
            "transform_match_counts": dict(sorted(transform_matches.items())),
            "raw_value_digest": _digest([
                (
                    getattr(leg, "source_route_minimum_crossing_altitude", ""),
                    getattr(leg, "source_segment_minimum_crossing_altitude", ""),
                )
                for leg in model.airway_legs
            ]),
        },
        "reference_altitude": {
            "nonzero_rows": reference_nonzero,
            "nonzero_rows_with_source_value": reference_nonzero_with_source,
            "nonzero_rows_with_source_transform_match": (
                reference_nonzero_source_matches
            ),
            "candidate_reference_altitude_delta_rows": (
                candidate_reference_altitude_deltas
            ),
        },
        "semantic_altitude_delta_rows": len(delta_keys),
        "evidence_status": evidence_status,
        "adapter_change_authorized": False,
    }


def write_airway_source_field_audit(
    path: Path,
    report: Mapping[str, object],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
