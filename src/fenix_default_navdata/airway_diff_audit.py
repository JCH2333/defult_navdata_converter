from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

from .model import NavModel


class AirwayDiffAuditError(RuntimeError):
    """航路差异输入不满足只读、完整、脱敏契约时抛出。"""


_AIRWAY_LOGICAL_FIELDS = (
    "airway_name",
    "airway_type",
    "route_type",
    "airway_fragment_no",
    "sequence_no",
)
_AIRWAY_SEMANTIC_FIELDS = {
    *_AIRWAY_LOGICAL_FIELDS,
    "direction",
    "minimum_altitude",
    "maximum_altitude",
    "left_lonx",
    "top_laty",
    "right_lonx",
    "bottom_laty",
    "from_lonx",
    "from_laty",
    "to_lonx",
    "to_laty",
}
_FIELD_GROUPS = {
    "geometry": frozenset({
        "left_lonx",
        "top_laty",
        "right_lonx",
        "bottom_laty",
        "from_lonx",
        "from_laty",
        "to_lonx",
        "to_laty",
    }),
    "topology": frozenset({"airway_fragment_no", "sequence_no"}),
    "altitude": frozenset({"minimum_altitude", "maximum_altitude"}),
    "route_metadata": frozenset({"airway_type", "route_type", "direction"}),
}
_GROUP_PRIORITY = ("topology", "geometry", "altitude", "route_metadata", "other")


def _normalized(value: object) -> str:
    return str(value or "").strip().upper()


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_redacted_semantic_report(
    report: Mapping[str, object],
) -> Mapping[str, object]:
    if report.get("diagnostic") != "navdatareader-semantic-diff-v1":
        raise AirwayDiffAuditError("只接受 navdatareader-semantic-diff-v1 报告")
    if report.get("read_only") is not True:
        raise AirwayDiffAuditError("语义差分必须声明 read_only=true")
    if report.get("reference_values_redacted") is not True:
        raise AirwayDiffAuditError(
            "语义差分必须声明 reference_values_redacted=true"
        )
    tables = report.get("tables")
    if not isinstance(tables, Mapping):
        raise AirwayDiffAuditError("语义差分缺少 tables")
    table = tables.get("airway")
    if not isinstance(table, Mapping):
        raise AirwayDiffAuditError("语义差分缺少 airway 表")
    deltas = table.get("field_delta_samples")
    if not isinstance(deltas, list):
        raise AirwayDiffAuditError("airway 表缺少字段差异样本")
    omitted = int(table.get("field_delta_samples_omitted") or 0)
    expected = int(table.get("field_delta_rows") or 0)
    if omitted != 0 or len(deltas) != expected:
        raise AirwayDiffAuditError(
            "airway 字段差异样本不完整，拒绝生成关联审计"
        )
    reader_output = report.get("reader_output")
    if not isinstance(reader_output, Mapping):
        raise AirwayDiffAuditError("语义差分缺少读取器完整性证明")
    for label in ("candidate", "reference"):
        item = reader_output.get(label)
        if not isinstance(item, Mapping) or item.get("bgl_file_rows") != item.get(
            "expected_bgl_count"
        ):
            raise AirwayDiffAuditError(
                f"{label} 读取器 BGL 登记不完整，拒绝生成关联审计"
            )
    return table


def _load_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AirwayDiffAuditError(f"无法读取{label}: {path}") from error
    if not isinstance(value, dict):
        raise AirwayDiffAuditError(f"{label} 根对象必须是 JSON 对象")
    return value


def load_airway_diff_report(path: Path) -> dict[str, object]:
    """读取并校验只读脱敏 semantic diff。"""
    report = _load_json(path, "semantic diff")
    _require_redacted_semantic_report(report)
    return report


def load_source_audit(path: Path) -> dict[str, object]:
    """读取已有来源审计，只保留其脱敏聚合结果作为旁证。"""
    report = _load_json(path, "source audit")
    if report.get("read_only") is not True or report.get(
        "reference_values_redacted"
    ) is not True:
        raise AirwayDiffAuditError(
            "来源审计必须声明 read_only=true 和 reference_values_redacted=true"
        )
    if not str(report.get("diagnostic", "")).startswith("source-gap-audit-"):
        raise AirwayDiffAuditError("不支持的来源审计版本")
    return report


def _source_index(model: NavModel) -> dict[tuple[str, int], list[object]]:
    index: dict[tuple[str, int], list[object]] = defaultdict(list)
    for leg in model.airway_legs:
        index[(_normalized(leg.airway), int(leg.sequence))].append(leg)
    return index


def _source_category(
    airway: str,
    sequence: int,
    source_index: Mapping[tuple[str, int], list[object]],
    source_airways: set[str],
) -> tuple[str, int]:
    matches = source_index.get((airway, sequence), ())
    if not matches:
        category = (
            "source_airway_name_with_different_sequence"
            if airway in source_airways
            else "absent_from_rte_seg"
        )
    elif len(matches) != 1:
        category = "same_source_airway_and_sequence_ambiguous"
    else:
        category = "same_source_airway_and_sequence"
    return category, len(matches)


def _groups_for_fields(fields: tuple[str, ...]) -> tuple[str, ...]:
    groups = [
        name
        for name, known_fields in _FIELD_GROUPS.items()
        if any(field in known_fields for field in fields)
    ]
    return tuple(groups) if groups else ("other",)


def _exclusive_group(groups: tuple[str, ...]) -> str:
    if len(groups) > 1:
        return "mixed"
    return next(group for group in _GROUP_PRIORITY if group in groups)


def audit_airway_differences(
    model: NavModel,
    semantic_report: Mapping[str, object],
    *,
    source_audit: Mapping[str, object] | None = None,
    association_sample_limit: int = 100,
) -> dict[str, object]:
    """分类航路字段差异，并输出哈希化的候选到来源关联。

    该审计只使用候选侧逻辑身份和 424 `NavModel` 的 `(airway, sequence)`。
    输出不包含航路名、航点、坐标、高度、参考字段值或参考独有身份。
    """
    if association_sample_limit <= 0:
        raise ValueError("association_sample_limit 必须为正整数")
    table = _require_redacted_semantic_report(semantic_report)
    if source_audit is not None:
        if source_audit.get("read_only") is not True or source_audit.get(
            "reference_values_redacted"
        ) is not True:
            raise AirwayDiffAuditError("source audit 未通过脱敏契约")

    source_index = _source_index(model)
    source_airways = {key[0] for key in source_index}
    changed_fields: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    exclusive_counts: Counter[str] = Counter()
    source_categories: Counter[str] = Counter()
    match_counts: Counter[str] = Counter()
    association_counts: Counter[tuple[str, str, str]] = Counter()
    association_samples: list[dict[str, object]] = []

    deltas = table["field_delta_samples"]
    assert isinstance(deltas, list)
    for sample in deltas:
        if not isinstance(sample, Mapping):
            raise AirwayDiffAuditError("airway 字段差异样本不是对象")
        key = sample.get("logical_key")
        fields = sample.get("fields")
        if not isinstance(key, Mapping) or not isinstance(fields, list):
            raise AirwayDiffAuditError("airway 字段差异样本缺少 logical_key/fields")
        if any(field not in key for field in _AIRWAY_LOGICAL_FIELDS):
            raise AirwayDiffAuditError("airway 逻辑身份字段不完整")
        if not fields or any(
            not isinstance(field, str) or field not in _AIRWAY_SEMANTIC_FIELDS
            for field in fields
        ):
            raise AirwayDiffAuditError("airway 字段差异包含未知字段")

        normalized_fields = tuple(sorted(set(fields)))
        groups = _groups_for_fields(normalized_fields)
        exclusive = _exclusive_group(groups)
        changed_fields.update(normalized_fields)
        group_counts.update(groups)
        exclusive_counts[exclusive] += 1

        airway = _normalized(key["airway_name"])
        try:
            sequence = int(key["sequence_no"])
        except (TypeError, ValueError) as error:
            raise AirwayDiffAuditError("airway sequence_no 必须是整数") from error
        source_category, source_match_count = _source_category(
            airway, sequence, source_index, source_airways
        )
        source_categories[source_category] += 1
        match_counts[str(source_match_count)] += 1

        candidate_digest = _digest({
            field: key[field] for field in _AIRWAY_LOGICAL_FIELDS
        })
        source_digest = _digest({"airway": airway, "sequence": sequence})
        association_counts[(source_category, exclusive, source_digest)] += 1
        if len(association_samples) < association_sample_limit:
            association_samples.append({
                "candidate_key_digest": candidate_digest,
                "source_airway_sequence_digest": source_digest,
                "source_category": source_category,
                "source_match_count": source_match_count,
                "changed_field_groups": list(groups),
                "changed_fields": list(normalized_fields),
            })

    result: dict[str, object] = {
        "diagnostic": "airway-diff-audit-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "model_airway_legs": len(model.airway_legs),
            "source_airway_names": len(source_airways),
        },
        "airway_field_delta_total": len(deltas),
        "changed_fields": dict(sorted(changed_fields.items())),
        "field_group_row_counts": dict(sorted(group_counts.items())),
        "exclusive_classification_counts": dict(sorted(exclusive_counts.items())),
        "source_category_counts": dict(sorted(source_categories.items())),
        "source_match_count_distribution": dict(sorted(match_counts.items())),
        "association_summary": {
            "unique_source_airway_sequence_digests": len(
                {item[2] for item in association_counts}
            ),
            "unique_category_group_pairs": len({
                (item[0], item[1]) for item in association_counts
            }),
            "rows_by_category_group": {
                f"{category}:{group}": sum(
                    count
                    for (item_category, item_group, _), count in association_counts.items()
                    if item_category == category and item_group == group
                )
                for category, group in sorted({
                    (item[0], item[1]) for item in association_counts
                })
            },
            "sample_limit": association_sample_limit,
            "samples": association_samples,
            "samples_omitted": max(0, len(deltas) - len(association_samples)),
        },
    }
    if source_audit is not None:
        coverage = source_audit.get("airway_field_delta_coverage")
        if isinstance(coverage, Mapping):
            result["source_audit_aggregate"] = {
                "diagnostic": source_audit.get("diagnostic"),
                "airway_field_delta_total": coverage.get("total"),
                "source_categories": coverage.get("source_categories"),
                "source_metadata": coverage.get("source_metadata"),
            }
    return result


def write_airway_diff_audit(path: Path, report: Mapping[str, object]) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
