from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from .general_docs import load_enroute_key_point_evidence
from .model import NavModel
from .source import (
    _EARTH_RADIUS_NM,
    _angular_distance,
    _load_fir_polygons,
    _match_source_fir_region,
    _rows,
)


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


def _require_complete_reader_output(report: Mapping[str, object]) -> None:
    reader_output = report.get("reader_output")
    if not isinstance(reader_output, Mapping):
        raise SourceGapAuditError("语义差分缺少读取器完整性证明")
    for label in ("candidate", "reference"):
        output = reader_output.get(label)
        if not isinstance(output, Mapping):
            raise SourceGapAuditError(f"语义差分缺少 {label} 读取器完整性证明")
        expected = output.get("expected_bgl_count")
        actual = output.get("bgl_file_rows")
        if not isinstance(expected, int) or expected <= 0:
            raise SourceGapAuditError(f"{label} 读取器缺少有效的预期 BGL 数")
        if actual != expected:
            raise SourceGapAuditError(
                f"{label} 读取器仅登记 {actual}/{expected} 个请求的 BGL，拒绝不完整扫描"
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


def _field_delta_keys(
    report: Mapping[str, object],
    table: str,
    fields: tuple[str, ...],
) -> tuple[tuple[dict[str, object], tuple[str, ...]], ...]:
    """Return complete, redacted field-delta identities without reference values."""
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
    samples = table_report.get("field_delta_samples")
    if not isinstance(samples, list):
        raise SourceGapAuditError(f"{table} 表缺少字段差异样本")
    if int(table_report.get("field_delta_samples_omitted") or 0) != 0:
        raise SourceGapAuditError(
            f"{table} 表字段差异样本被截断，不能用于完整来源审计"
        )
    expected = int(table_report.get("field_delta_rows") or 0)
    if len(samples) != expected:
        raise SourceGapAuditError(
            f"{table} 表字段差异样本数量与逻辑身份总数不一致"
        )
    result: list[tuple[dict[str, object], tuple[str, ...]]] = []
    seen: set[tuple[object, ...]] = set()
    for sample in samples:
        if not isinstance(sample, Mapping) or not isinstance(sample.get("logical_key"), Mapping):
            raise SourceGapAuditError(f"{table} 表存在无效字段差异样本")
        key = sample["logical_key"]
        if any(field not in key for field in fields):
            raise SourceGapAuditError(f"{table} 表字段差异样本缺少逻辑身份字段")
        identity = tuple(key[field] for field in fields)
        if identity in seen:
            raise SourceGapAuditError(f"{table} 表字段差异样本存在重复逻辑身份")
        changed_fields = sample.get("fields")
        if (
            not isinstance(changed_fields, list)
            or not changed_fields
            or any(not isinstance(value, str) or not value for value in changed_fields)
        ):
            raise SourceGapAuditError(f"{table} 表存在无效字段差异字段列表")
        seen.add(identity)
        result.append((
            {field: key[field] for field in fields},
            tuple(changed_fields),
        ))
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


def audit_terminal_coordinate_reference_coverage(
    model: NavModel,
    semantic_report: Mapping[str, object],
    *,
    retained_terminal_waypoints: Iterable[object] | None = None,
) -> dict[str, object]:
    """Classify redacted missing waypoint identities against source PDF coordinates.

    The caller must populate ``model.terminal_waypoints`` from source coordinate
    pages before calling this function. The report contains category totals
    only, so reference identities never become conversion inputs.
    """
    _require_complete_reader_output(semantic_report)
    keys = _reference_only_keys(
        semantic_report,
        "waypoint",
        _WAYPOINT_FIELDS,
    )
    grouped: dict[tuple[str, str], list[object]] = defaultdict(list)
    airport_grouped: dict[tuple[str, str, str], list[object]] = defaultdict(list)
    for point in model.terminal_waypoints:
        region = _normalized(point.country or point.airport[:2])[:2]
        ident = _normalized(point.ident)
        grouped[(region, ident)].append(point)
        airport_grouped[(_normalized(point.airport), region, ident)].append(point)
    retained_airport_identities = (
        {
            (
                _normalized(point.airport),
                _normalized(point.country or point.airport[:2])[:2],
                _normalized(point.ident),
            )
            for point in retained_terminal_waypoints
        }
        if retained_terminal_waypoints is not None
        else None
    )
    existing_identities = {
        (_normalized(point.country)[:2], _normalized(point.ident))
        for point in model.waypoints
    }
    existing_identities.update(
        (_normalized(navaid.country)[:2], _normalized(navaid.ident))
        for navaid in model.navaids
    )
    categories: Counter[str] = Counter()
    for key in keys:
        region = _normalized(key["region"])[:2]
        ident = _normalized(key["ident"])
        airport = _normalized(key["airport_ident"])
        if airport:
            airport_identity = (airport, region, ident)
            candidates = airport_grouped.get(airport_identity, [])
            if candidates:
                if retained_airport_identities is None:
                    categories["airport_terminal_coordinate_source_present"] += 1
                elif airport_identity in retained_airport_identities:
                    categories["airport_terminal_coordinate_retained"] += 1
                else:
                    categories["airport_terminal_coordinate_not_retained"] += 1
            else:
                categories["airport_terminal_not_present_in_coordinate_pages"] += 1
            continue
        identity = (region, ident)
        candidates = grouped.get(identity, [])
        if not candidates:
            categories["not_present_in_terminal_coordinate_pages"] += 1
            continue
        raw_idents = {point.ident.strip() for point in candidates}
        coordinates = {
            (round(point.latitude, 6), round(point.longitude, 6))
            for point in candidates
        }
        airports = {point.airport.upper() for point in candidates}
        if not identity[1]:
            categories["terminal_empty_identifier"] += 1
        elif len(raw_idents) != 1:
            categories["terminal_identifier_variants"] += 1
        elif len(next(iter(raw_idents))) > 8:
            categories["terminal_identifier_too_long"] += 1
        elif len(coordinates) != 1:
            categories["terminal_multiple_coordinates"] += 1
        elif len(airports) < 2:
            categories["terminal_single_airport"] += 1
        elif identity in existing_identities:
            categories["terminal_existing_global_identity"] += 1
        else:
            categories["terminal_source_promotable"] += 1
    if sum(categories.values()) != len(keys):
        raise SourceGapAuditError("终端坐标页来源分类未覆盖全部参考缺失航点身份")
    return {
        "diagnostic": "terminal-coordinate-reference-coverage-v2",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "global_waypoints": len(model.waypoints),
            "navaids": len(model.navaids),
            "terminal_coordinate_points": len(model.terminal_waypoints),
            "terminal_coordinate_identity_groups": len(grouped),
            "terminal_coordinate_airport_identity_groups": len(airport_grouped),
            "retention_checked": retained_airport_identities is not None,
            "retained_terminal_coordinate_airport_identity_groups": (
                len(retained_airport_identities)
                if retained_airport_identities is not None
                else None
            ),
        },
        "reference_only_waypoint_identities": len(keys),
        "categories": dict(sorted(categories.items())),
    }


def audit_terminal_coordinate_field_delta_coverage(
    model: NavModel,
    semantic_report: Mapping[str, object],
    *,
    retained_terminal_waypoints: Iterable[object] | None = None,
) -> dict[str, object]:
    """Classify waypoint field deltas against 424 terminal-coordinate evidence.

    The semantic report supplies only logical identities and changed field
    names.  It never exposes reference values, so this diagnostic cannot be
    repurposed as a reverse-input channel for coordinates or magnetic
    variation.
    """
    _require_complete_reader_output(semantic_report)
    deltas = _field_delta_keys(
        semantic_report,
        "waypoint",
        _WAYPOINT_FIELDS,
    )
    airport_grouped: dict[tuple[str, str, str], list[object]] = defaultdict(list)
    root_grouped: dict[tuple[str, str], list[object]] = defaultdict(list)
    for point in model.terminal_waypoints:
        airport = _normalized(point.airport)
        region = _normalized(point.country or point.airport[:2])[:2]
        ident = _normalized(point.ident)
        airport_grouped[(airport, region, ident)].append(point)
        root_grouped[(region, ident)].append(point)
    retained_airport_identities = (
        {
            (
                _normalized(point.airport),
                _normalized(point.country or point.airport[:2])[:2],
                _normalized(point.ident),
            )
            for point in retained_terminal_waypoints
        }
        if retained_terminal_waypoints is not None
        else None
    )
    categories: Counter[str] = Counter()
    scope_counts: Counter[str] = Counter()
    field_counts: Counter[str] = Counter()
    for key, changed_fields in deltas:
        airport = _normalized(key["airport_ident"])
        region = _normalized(key["region"])[:2]
        ident = _normalized(key["ident"])
        field_counts.update(changed_fields)
        if airport:
            scope_counts["airport_scoped"] += 1
            candidates = airport_grouped.get((airport, region, ident), [])
            coordinates = {
                (round(point.latitude, 6), round(point.longitude, 6))
                for point in candidates
            }
            if not candidates:
                categories["airport_terminal_not_present_in_coordinate_pages"] += 1
            elif len(coordinates) != 1:
                categories["airport_terminal_multiple_source_coordinates"] += 1
            elif (
                retained_airport_identities is not None
                and (airport, region, ident) not in retained_airport_identities
            ):
                categories["airport_terminal_coordinate_not_retained"] += 1
            else:
                categories["airport_terminal_coordinate_source_backed"] += 1
            continue
        scope_counts["root_scoped"] += 1
        candidates = root_grouped.get((region, ident), [])
        coordinates = {
            (round(point.latitude, 6), round(point.longitude, 6))
            for point in candidates
        }
        if not candidates:
            categories["root_terminal_not_present_in_coordinate_pages"] += 1
        elif len(coordinates) != 1:
            categories["root_terminal_multiple_source_coordinates"] += 1
        elif (
            retained_airport_identities is not None
            and not any(
                (
                    _normalized(point.airport),
                    _normalized(point.country or point.airport[:2])[:2],
                    _normalized(point.ident),
                ) in retained_airport_identities
                for point in candidates
            )
        ):
            categories["root_terminal_coordinate_not_retained"] += 1
        else:
            categories["root_terminal_coordinate_source_backed"] += 1
    if sum(categories.values()) != len(deltas):
        raise SourceGapAuditError("终端坐标页字段差异分类未覆盖全部候选航点身份")
    return {
        "diagnostic": "terminal-coordinate-field-delta-coverage-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "terminal_coordinate_points": len(model.terminal_waypoints),
            "terminal_coordinate_airport_identity_groups": len(airport_grouped),
            "terminal_coordinate_root_identity_groups": len(root_grouped),
            "retention_checked": retained_airport_identities is not None,
            "retained_terminal_coordinate_airport_identity_groups": (
                len(retained_airport_identities)
                if retained_airport_identities is not None
                else None
            ),
        },
        "field_delta_waypoint_identities": len(deltas),
        "scope": dict(sorted(scope_counts.items())),
        "changed_fields": dict(sorted(field_counts.items())),
        "categories": dict(sorted(categories.items())),
    }


def audit_general_document_key_point_reference_coverage(
    model: NavModel,
    semantic_report: Mapping[str, object],
    *,
    source_root: Path,
    cache_root: Path,
    cache_directory: str = "enr-4.4",
) -> dict[str, object]:
    """Classify redacted global waypoint gaps against ENR 4.4 source evidence.

    ``model`` must contain only direct structured-source waypoints, before
    ENR 4.4 OCR points are accepted. The report contains counts only and never
    serializes reference logical identities or source evidence records.
    """
    _require_complete_reader_output(semantic_report)
    keys = _reference_only_keys(
        semantic_report,
        "waypoint",
        _WAYPOINT_FIELDS,
    )
    polygons, vertices_loaded = _load_fir_polygons(source_root)
    evidence, evidence_report = load_enroute_key_point_evidence(
        source_root,
        cache_root,
        cache_directory=cache_directory,
    )
    by_ident: dict[str, list[tuple[object, object]]] = defaultdict(list)
    for item in evidence:
        by_ident[_normalized(item.ident)].append((
            item,
            _match_source_fir_region(polygons, item.latitude, item.longitude),
        ))
    existing: dict[tuple[str, str], list[object]] = defaultdict(list)
    for point in model.waypoints:
        if point.country:
            existing[(_normalized(point.country)[:2], _normalized(point.ident))].append(
                point
            )

    categories: Counter[str] = Counter()
    for key in keys:
        if key["airport_ident"] not in (None, ""):
            categories["airport_scoped_reference_only"] += 1
            continue
        identity = (
            _normalized(key["region"])[:2],
            _normalized(key["ident"]),
        )
        candidates = by_ident.get(identity[1], [])
        if not candidates:
            categories["general_doc_ident_absent"] += 1
            continue
        recovered = [
            (item, result)
            for item, result in candidates
            if result.status == "recovered"
        ]
        regional = [
            (item, result)
            for item, result in recovered
            if result.country == identity[0]
        ]
        if not regional:
            if recovered:
                categories["general_doc_region_mismatch"] += 1
            else:
                statuses = {result.status for _, result in candidates}
                suffix = "mixed" if len(statuses) > 1 else next(iter(statuses))
                categories[f"general_doc_region_{suffix}"] += 1
            continue
        coordinates = {
            (round(item.latitude, 6), round(item.longitude, 6))
            for item, _ in regional
        }
        if len(coordinates) != 1:
            categories["general_doc_multiple_coordinates"] += 1
            continue
        source_point = regional[0][0]
        matches = existing.get(identity, [])
        if matches:
            if any(
                _angular_distance(
                    point.latitude,
                    point.longitude,
                    source_point.latitude,
                    source_point.longitude,
                ) * _EARTH_RADIUS_NM <= 0.01
                for point in matches
            ):
                categories["general_doc_already_present"] += 1
            else:
                categories["general_doc_identity_conflict"] += 1
            continue
        categories["general_doc_source_promotable"] += 1

    if sum(categories.values()) != len(keys):
        raise SourceGapAuditError("GeneralDoc 关键点来源分类未覆盖全部参考缺失航点身份")
    return {
        "diagnostic": "general-document-keypoint-reference-coverage-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "source": {
            "global_waypoints": len(model.waypoints),
            "fir_polygons": len(polygons),
            "fir_vertices": vertices_loaded,
            "document": evidence_report["document"],
            "source_sha256": evidence_report["source_sha256"],
            "pages": evidence_report["pages"],
            "parsed_records": len(evidence),
        },
        "reference_only_waypoint_identities": len(keys),
        "categories": dict(sorted(categories.items())),
    }


def _airway_categories(
    model: NavModel,
    keys: tuple[dict[str, object], ...],
    candidate_pairs: set[tuple[str, str, str, str, str]] | None = None,
) -> dict[str, int]:
    source_sequences: dict[
        tuple[str, int],
        set[tuple[str, str, str, str, str]],
    ] = defaultdict(set)
    for leg in model.airway_legs:
        source_sequences[(_normalized(leg.airway), int(leg.sequence))].add((
            _normalized(leg.airway),
            _normalized(leg.start_country),
            _normalized(leg.start_ident),
            _normalized(leg.end_country),
            _normalized(leg.end_ident),
        ))
    source_airways = {_normalized(leg.airway) for leg in model.airway_legs}
    categories: Counter[str] = Counter()
    for key in keys:
        airway = _normalized(key["airway_name"])
        sequence = int(key["sequence_no"])
        source_pairs = source_sequences.get((airway, sequence))
        if source_pairs:
            if candidate_pairs is None:
                categories["same_source_airway_and_sequence"] += 1
            elif source_pairs & candidate_pairs:
                categories[
                    "same_source_airway_and_sequence_candidate_pair_projected"
                ] += 1
            elif any(not pair[1] or not pair[3] for pair in source_pairs):
                categories[
                    "same_source_airway_and_sequence_unprojected_missing_endpoint_region"
                ] += 1
            else:
                categories[
                    "same_source_airway_and_sequence_unprojected_from_candidate_xml"
                ] += 1
        elif airway in source_airways:
            categories["source_airway_name_with_different_sequence"] += 1
        else:
            categories["absent_from_rte_seg"] += 1
    return dict(sorted(categories.items()))


def _airway_field_delta_coverage(
    model: NavModel,
    semantic_report: Mapping[str, object],
    candidate_pairs: set[tuple[str, str, str, str, str]] | None = None,
) -> dict[str, object]:
    """Summarize 424 evidence behind redacted airway field deltas.

    This intentionally reports only aggregate source availability and source
    metadata presence. Reference values, logical identities, and raw source
    values remain out of the output, so the audit cannot become a backfill
    channel for target coordinates or altitude values.
    """
    deltas = _field_delta_keys(semantic_report, "airway", _AIRWAY_FIELDS)
    source_sequences: dict[tuple[str, int], list[object]] = defaultdict(list)
    for leg in model.airway_legs:
        source_sequences[(_normalized(leg.airway), int(leg.sequence))].append(leg)
    source_airways = {_normalized(leg.airway) for leg in model.airway_legs}

    categories: Counter[str] = Counter()
    changed_fields: Counter[str] = Counter()
    metadata: Counter[str] = Counter()
    for key, fields in deltas:
        changed_fields.update(fields)
        airway = _normalized(key["airway_name"])
        sequence = int(key["sequence_no"])
        matches = source_sequences.get((airway, sequence), [])
        if not matches:
            categories[
                "source_airway_name_with_different_sequence"
                if airway in source_airways
                else "absent_from_rte_seg"
            ] += 1
            continue
        if len(matches) != 1:
            categories["same_source_airway_and_sequence_ambiguous"] += 1
            continue

        leg = matches[0]
        pair = (
            _normalized(leg.airway),
            _normalized(leg.start_country),
            _normalized(leg.start_ident),
            _normalized(leg.end_country),
            _normalized(leg.end_ident),
        )
        if candidate_pairs is None:
            categories["same_source_airway_and_sequence"] += 1
        elif pair in candidate_pairs:
            categories["same_source_airway_and_sequence_candidate_pair_projected"] += 1
        elif not pair[1] or not pair[3]:
            categories[
                "same_source_airway_and_sequence_unprojected_missing_endpoint_region"
            ] += 1
        else:
            categories[
                "same_source_airway_and_sequence_unprojected_from_candidate_xml"
            ] += 1

        metadata["same_source_rows"] += 1
        if leg.source_segment_found:
            metadata["segment_linked"] += 1
        if leg.source_en_route_rte_found:
            metadata["route_linked"] += 1
        if leg.source_segment_minimum_crossing_altitude.strip():
            metadata["segment_mtca_populated"] += 1
        if leg.source_route_minimum_crossing_altitude.strip():
            metadata["route_mtca_populated"] += 1
        if leg.source_code_type.strip():
            metadata["pbn_code_populated"] += 1
        if leg.source_segment_rnp_designator.strip():
            metadata["segment_rnp_designator_populated"] += 1
        if leg.source_enroute_location_type.strip():
            metadata["route_location_type_populated"] += 1
        if leg.source_airspace_remark.strip():
            metadata["airspace_remark_populated"] += 1
        if leg.direction.strip():
            metadata["direction_populated"] += 1
        if (
            leg.start_latitude is not None
            and leg.start_longitude is not None
            and leg.end_latitude is not None
            and leg.end_longitude is not None
        ):
            metadata["endpoint_coordinates_complete"] += 1
        if leg.start_country and leg.end_country:
            metadata["endpoint_regions_complete"] += 1

    if sum(categories.values()) != len(deltas):
        raise SourceGapAuditError("航路字段差异来源分类未覆盖全部参考逻辑身份")
    return {
        "total": len(deltas),
        "changed_fields": dict(sorted(changed_fields.items())),
        "source_categories": dict(sorted(categories.items())),
        "source_metadata": dict(sorted(metadata.items())),
    }


def _xml_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _candidate_airway_pairs(
    candidate_xml: Path,
) -> tuple[set[tuple[str, str, str, str, str]], dict[str, object]]:
    """Read only candidate Route edges and keep no reference-side identities."""
    candidate_xml = candidate_xml.expanduser().resolve()
    if not candidate_xml.is_file():
        raise SourceGapAuditError(f"candidate XML does not exist: {candidate_xml}")
    try:
        root = ET.parse(candidate_xml).getroot()
    except ET.ParseError as error:
        raise SourceGapAuditError(
            f"candidate XML is not well formed: {candidate_xml}"
        ) from error

    pairs: set[tuple[str, str, str, str, str]] = set()
    skipped: Counter[str] = Counter()
    route_links = 0
    for facility in root.iter():
        parent_ident = _normalized(facility.get("waypointIdent"))
        parent_region = _normalized(facility.get("waypointRegion"))
        if not parent_ident or not parent_region:
            continue
        for route in facility:
            if _xml_tag(route) != "Route":
                continue
            airway = _normalized(route.get("name"))
            if not airway:
                skipped["route_without_name"] += 1
                continue
            for link in route:
                link_tag = _xml_tag(link)
                if link_tag not in {"Next", "Previous"}:
                    continue
                adjacent_ident = _normalized(link.get("waypointIdent"))
                adjacent_region = _normalized(link.get("waypointRegion"))
                if not adjacent_ident or not adjacent_region:
                    skipped["link_without_complete_identity"] += 1
                    continue
                route_links += 1
                if link_tag == "Next":
                    pairs.add((
                        airway,
                        parent_region,
                        parent_ident,
                        adjacent_region,
                        adjacent_ident,
                    ))
                else:
                    pairs.add((
                        airway,
                        adjacent_region,
                        adjacent_ident,
                        parent_region,
                        parent_ident,
                    ))
    return pairs, {
        "candidate_xml": str(candidate_xml),
        "route_links": route_links,
        "unique_route_pairs": len(pairs),
        "skipped": dict(sorted(skipped.items())),
    }


def _flight_airline_point_evidence(
    model: NavModel,
    keys: tuple[dict[str, object], ...],
) -> dict[str, object]:
    """Show whether airline-route references add source legs beyond RTE_SEG."""
    rte_path = model.root / "RTE_SEG.csv"
    airline_point_path = model.root / "FLIGHT_AIRLINE_POINT.csv"
    if not rte_path.is_file() or not airline_point_path.is_file():
        return {"available": False}
    rte_rows = tuple(_rows(rte_path))
    rte_signatures = {
        (
            _normalized(row.get("TXT_DESIG")),
            str(row.get("POINT_START_ID") or "").strip(),
            str(row.get("POINT_END_ID") or "").strip(),
        )
        for row in rte_rows
    }
    source_airways = {
        _normalized(row.get("TXT_DESIG"))
        for row in rte_rows
    }
    absent_reference_airways = {
        _normalized(key["airway_name"])
        for key in keys
        if _normalized(key["airway_name"]) not in source_airways
    }
    direct_point_ids = {point.key for point in model.waypoints}
    direct_point_ids.update(navaid.key for navaid in model.navaids)
    counts: Counter[str] = Counter()
    for row in _rows(airline_point_path):
        counts["rows"] += 1
        airway = _normalized(row.get("AirwayName"))
        start_id = str(row.get("StartPointID") or "").strip()
        end_id = str(row.get("EndPointID") or "").strip()
        if start_id in direct_point_ids and end_id in direct_point_ids:
            counts["endpoint_pairs_resolved_to_direct_424_points"] += 1
        signature = (airway, start_id, end_id)
        if signature in rte_signatures:
            counts["forward_rte_seg_matches"] += 1
        elif (airway, end_id, start_id) in rte_signatures:
            counts["reverse_rte_seg_matches"] += 1
        else:
            counts["unmatched_rte_seg_references"] += 1
        if airway in absent_reference_airways:
            counts["rows_for_rte_absent_reference_airways"] += 1
    return {
        "available": True,
        "rows": counts["rows"],
        "endpoint_pairs_resolved_to_direct_424_points": (
            counts["endpoint_pairs_resolved_to_direct_424_points"]
        ),
        "forward_rte_seg_matches": counts["forward_rte_seg_matches"],
        "reverse_rte_seg_matches": counts["reverse_rte_seg_matches"],
        "unmatched_rte_seg_references": counts["unmatched_rte_seg_references"],
        "rte_absent_reference_airway_names": len(absent_reference_airways),
        "rows_for_rte_absent_reference_airways": (
            counts["rows_for_rte_absent_reference_airways"]
        ),
    }


def _route_holding_evidence(model: NavModel) -> dict[str, object]:
    """Show whether raw holding rows can prove independent enroute waypoints."""
    holding_path = model.root / "ROUTE_HOLDING.csv"
    if not holding_path.is_file():
        return {"available": False}
    direct_point_ids = {point.key for point in model.waypoints}
    direct_point_ids.update(navaid.key for navaid in model.navaids)
    unresolved_locations: Counter[str] = Counter()
    unresolved_coordinates: set[tuple[str, str, str]] = set()
    counts: Counter[str] = Counter()
    for row in _rows(holding_path):
        counts["rows"] += 1
        point_id = str(row.get("POINT_ID") or "").strip()
        if point_id in direct_point_ids:
            counts["direct_point_id_resolved"] += 1
            continue
        counts["point_id_unresolved"] += 1
        location = _normalized(row.get("LOCATION_POINT"))
        latitude = str(row.get("GEO_LAT_ACCURACY") or "").strip()
        longitude = str(row.get("GEO_LONG_ACCURACY") or "").strip()
        if latitude and longitude:
            counts["unresolved_rows_with_coordinate"] += 1
            unresolved_coordinates.add((location, latitude, longitude))
        if location:
            unresolved_locations[location] += 1
    return {
        "available": True,
        "rows": counts["rows"],
        "direct_point_id_resolved": counts["direct_point_id_resolved"],
        "point_id_unresolved": counts["point_id_unresolved"],
        "unresolved_rows_with_coordinate": counts["unresolved_rows_with_coordinate"],
        "unresolved_location_point_values": len(unresolved_locations),
        "unresolved_location_point_reused": sum(
            count > 1 for count in unresolved_locations.values()
        ),
        "unresolved_unique_location_coordinate_pairs": len(unresolved_coordinates),
        # The source table has no region key. A repeated LOCATION_POINT must
        # never become several MSFS named waypoints with the same identity.
        "can_add_independent_enroute_waypoints": False,
    }


def audit_source_gaps(
    model: NavModel,
    semantic_report: Mapping[str, object],
    candidate_xml: Path | None = None,
    *,
    tables: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Classify redacted reference gaps using only normalized 424 records.

    The report intentionally keeps reference logical identities in memory only.
    It returns source-category totals, so it can guide new source research
    without becoming a reference-field backfill channel.
    """
    _require_complete_reader_output(semantic_report)
    selected_tables = tuple(tables or ("waypoint", "airway"))
    allowed_tables = {"waypoint", "airway"}
    if (
        not selected_tables
        or any(table not in allowed_tables for table in selected_tables)
        or len(set(selected_tables)) != len(selected_tables)
    ):
        raise SourceGapAuditError("source-gap-audit 只支持不重复的 waypoint 和 airway 表")
    waypoint_keys: tuple[dict[str, object], ...] = ()
    airway_keys: tuple[dict[str, object], ...] = ()
    waypoint_categories: dict[str, int] = {}
    if "waypoint" in selected_tables:
        waypoint_keys = _reference_only_keys(
            semantic_report, "waypoint", _WAYPOINT_FIELDS
        )
        waypoint_categories = _waypoint_categories(model, waypoint_keys)
    candidate_pairs: set[tuple[str, str, str, str, str]] | None = None
    candidate_projection: dict[str, object] = {"available": False}
    if "airway" in selected_tables and candidate_xml is not None:
        candidate_pairs, projection_report = _candidate_airway_pairs(candidate_xml)
        candidate_projection = {"available": True, **projection_report}
    airway_categories: dict[str, int] = {}
    airway_field_delta_coverage: dict[str, object] = {}
    if "airway" in selected_tables:
        airway_keys = _reference_only_keys(
            semantic_report, "airway", _AIRWAY_FIELDS
        )
        airway_categories = _airway_categories(
            model,
            airway_keys,
            candidate_pairs=candidate_pairs,
        )
        airway_field_delta_coverage = _airway_field_delta_coverage(
            model,
            semantic_report,
            candidate_pairs=candidate_pairs,
        )
    if "waypoint" in selected_tables and sum(waypoint_categories.values()) != len(waypoint_keys):
        raise SourceGapAuditError("航点来源分类未覆盖全部参考缺失逻辑身份")
    if "airway" in selected_tables and sum(airway_categories.values()) != len(airway_keys):
        raise SourceGapAuditError("航路来源分类未覆盖全部参考缺失逻辑身份")
    report: dict[str, object] = {
        "diagnostic": "source-gap-audit-v5",
        "read_only": True,
        "reference_values_redacted": True,
        "selected_tables": list(selected_tables),
        "source": {
            "designated_points": len(model.waypoints),
            "airway_legs": len(model.airway_legs),
        },
        "candidate_airway_projection": candidate_projection,
    }
    if "waypoint" in selected_tables:
        report.update(
            {
                "waypoint_reference_only_total": len(waypoint_keys),
                "waypoint_source_categories": waypoint_categories,
            }
        )
    if "airway" in selected_tables:
        report.update(
            {
                "airway_reference_only_total": len(airway_keys),
                "airway_source_categories": airway_categories,
                "airway_field_delta_coverage": airway_field_delta_coverage,
                "flight_airline_point_evidence": _flight_airline_point_evidence(
                    model, airway_keys
                ),
                "route_holding_evidence": _route_holding_evidence(model),
            }
        )
    return report


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
