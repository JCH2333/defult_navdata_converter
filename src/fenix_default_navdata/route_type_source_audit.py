from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

from .model import NavModel
from .source_gap import (
    _field_delta_keys,
    _reference_only_keys,
    _require_complete_reader_output,
)


class RouteTypeSourceAuditError(RuntimeError):
    """航路类型来源审计输入不满足只读、完整、脱敏契约时抛出。"""


_AIRWAY_FIELDS = (
    "airway_name",
    "airway_type",
    "route_type",
    "airway_fragment_no",
    "sequence_no",
)
_TARGET_TYPES = frozenset({"J", "V"})


def _metadata_key(leg: object) -> str:
    values = (
        str(getattr(leg, "source_enroute_location_type", "") or "").strip(),
        str(getattr(leg, "source_code_type", "") or "").strip(),
        str(getattr(leg, "direction", "") or "").strip(),
    )
    return "|".join(value or "<empty>" for value in values)


def _validate_report(report: Mapping[str, object]) -> None:
    if report.get("diagnostic") != "navdatareader-semantic-diff-v1":
        raise RouteTypeSourceAuditError(
            "只接受 navdatareader-semantic-diff-v1 报告"
        )
    if report.get("read_only") is not True:
        raise RouteTypeSourceAuditError("语义差分必须声明 read_only=true")
    if report.get("reference_values_redacted") is not True:
        raise RouteTypeSourceAuditError(
            "语义差分必须声明 reference_values_redacted=true"
        )
    try:
        _require_complete_reader_output(report)
        _reference_only_keys(report, "airway", _AIRWAY_FIELDS)
        _field_delta_keys(report, "airway", _AIRWAY_FIELDS)
    except Exception as error:
        raise RouteTypeSourceAuditError(str(error)) from error


def audit_route_type_source(
    model: NavModel,
    semantic_report: Mapping[str, object],
) -> dict[str, object]:
    """Audit whether observed target J/V rows have a unique source mapping.

    The semantic report contains only logical identities and changed-field names;
    no reference coordinates, payloads, or target field values are consumed.
    This audit is evidence-only and never changes ``NavModel``.
    """
    _validate_report(semantic_report)
    reference_only = _reference_only_keys(
        semantic_report, "airway", _AIRWAY_FIELDS
    )
    field_deltas = _field_delta_keys(
        semantic_report, "airway", _AIRWAY_FIELDS
    )
    source_by_sequence: dict[tuple[str, int], list[object]] = defaultdict(list)
    for leg in model.airway_legs:
        source_by_sequence[(
            str(leg.airway or "").strip().upper(),
            int(leg.sequence),
        )].append(leg)

    target_type_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    match_counts: Counter[str] = Counter()
    metadata_target_types: dict[str, set[str]] = defaultdict(set)
    for bucket, keys in (
        ("reference_only", reference_only),
        ("field_delta", tuple(key for key, _ in field_deltas)),
    ):
        for key in keys:
            target_type = str(key["airway_type"] or "").strip().upper()
            if target_type not in _TARGET_TYPES:
                continue
            target_type_counts[target_type] += 1
            bucket_counts[bucket] += 1
            source = source_by_sequence.get((
                str(key["airway_name"] or "").strip().upper(),
                int(key["sequence_no"]),
            ), [])
            if not source:
                match_counts["unmatched"] += 1
                continue
            if len(source) != 1:
                match_counts["ambiguous"] += 1
                continue
            match_counts["unique"] += 1
            metadata_target_types[_metadata_key(source[0])].add(target_type)

    conflict_count = sum(
        len(target_types) > 1
        for target_types in metadata_target_types.values()
    )
    unique_metadata_count = len(metadata_target_types)
    evidence_status = (
        "insufficient_for_adapter_rule"
        if (
            match_counts["unmatched"]
            or match_counts["ambiguous"]
            or conflict_count
            or not unique_metadata_count
        )
        else "candidate_mapping_requires_independent_contract"
    )
    return {
        "diagnostic": "route-type-source-audit-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "target_type_counts": dict(sorted(target_type_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "source_match_counts": dict(sorted(match_counts.items())),
        "unique_source_metadata_combinations": unique_metadata_count,
        "conflicting_source_metadata_combinations": conflict_count,
        "evidence_status": evidence_status,
    }


def write_route_type_source_audit(
    path: Path,
    report: Mapping[str, object],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
