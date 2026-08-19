from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

from .bgl import _airway_waypoint_identity, _feet, _route_type
from .model import AirwayLeg, NavModel


class AirwayProjectionMatrixAuditError(RuntimeError):
    """Raised when the read-only model-to-XML projection matrix is invalid."""


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(value: object) -> str:
    return str(value or "").strip().upper()


def _source_sort_key(leg: AirwayLeg) -> tuple[object, ...]:
    return (
        _text(leg.airway),
        int(leg.sequence),
        _text(leg.start_country),
        _text(leg.start_ident),
        _text(leg.end_country),
        _text(leg.end_ident),
        leg.source.file,
        int(leg.source.row or 0),
    )


def _source_rejection_reasons(leg: AirwayLeg) -> tuple[str, ...]:
    fields = (
        ("missing_airway_name", leg.airway),
        ("missing_start_ident", leg.start_ident),
        ("missing_end_ident", leg.end_ident),
        ("missing_start_region", leg.start_country),
        ("missing_end_region", leg.end_country),
    )
    reasons = [name for name, value in fields if not _text(value)]
    if leg.start_latitude is None or leg.start_longitude is None:
        reasons.append("missing_start_coordinate")
    if leg.end_latitude is None or leg.end_longitude is None:
        reasons.append("missing_end_coordinate")
    return tuple(reasons)


def _connection(
    *,
    route_name: str,
    route_type: str,
    waypoint_region: str,
    waypoint_ident: str,
    direction: str,
    adjacent_region: str,
    adjacent_ident: str,
    altitude_minimum: str,
) -> dict[str, str]:
    return {
        "route_name": route_name,
        "route_type": route_type,
        "waypoint_region": waypoint_region,
        "waypoint_ident": waypoint_ident,
        "direction": direction,
        "adjacent_region": adjacent_region,
        "adjacent_ident": adjacent_ident,
        "altitude_minimum": altitude_minimum,
    }


def _base_key(connection: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(connection[field] for field in (
        "route_name",
        "route_type",
        "waypoint_region",
        "waypoint_ident",
        "direction",
        "adjacent_region",
        "adjacent_ident",
    ))


def _exact_key(connection: Mapping[str, str]) -> tuple[str, ...]:
    return (*_base_key(connection), connection["altitude_minimum"])


def _region_wildcard_key(connection: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(connection[field] for field in (
        "route_name",
        "route_type",
        "waypoint_ident",
        "direction",
        "adjacent_ident",
        "altitude_minimum",
    ))


def _expected_connections(leg: AirwayLeg) -> tuple[dict[str, str], ...]:
    assert leg.start_latitude is not None
    assert leg.start_longitude is not None
    assert leg.end_latitude is not None
    assert leg.end_longitude is not None
    start = _airway_waypoint_identity(
        leg.start_ident, leg.start_country, leg.start_latitude, leg.start_longitude,
    )
    end = _airway_waypoint_identity(
        leg.end_ident, leg.end_country, leg.end_latitude, leg.end_longitude,
    )
    route_name = _text(leg.airway)
    route_type = _route_type(leg.route_type)
    altitude = _feet(leg.minimum_altitude_ft or 0)
    return (
        _connection(
            route_name=route_name,
            route_type=route_type,
            waypoint_region=start[1],
            waypoint_ident=start[2],
            direction="NEXT",
            adjacent_region=end[1],
            adjacent_ident=end[2],
            altitude_minimum=altitude,
        ),
        _connection(
            route_name=route_name,
            route_type=route_type,
            waypoint_region=end[1],
            waypoint_ident=end[2],
            direction="PREVIOUS",
            adjacent_region=start[1],
            adjacent_ident=start[2],
            altitude_minimum=altitude,
        ),
    )


def _expected_connections_without_regions(leg: AirwayLeg) -> tuple[dict[str, str], ...]:
    assert leg.start_latitude is not None
    assert leg.start_longitude is not None
    assert leg.end_latitude is not None
    assert leg.end_longitude is not None
    start = _airway_waypoint_identity(
        leg.start_ident, "", leg.start_latitude, leg.start_longitude,
    )
    end = _airway_waypoint_identity(
        leg.end_ident, "", leg.end_latitude, leg.end_longitude,
    )
    route_name = _text(leg.airway)
    route_type = _route_type(leg.route_type)
    altitude = _feet(leg.minimum_altitude_ft or 0)
    return (
        _connection(
            route_name=route_name,
            route_type=route_type,
            waypoint_region="",
            waypoint_ident=start[2],
            direction="NEXT",
            adjacent_region="",
            adjacent_ident=end[2],
            altitude_minimum=altitude,
        ),
        _connection(
            route_name=route_name,
            route_type=route_type,
            waypoint_region="",
            waypoint_ident=end[2],
            direction="PREVIOUS",
            adjacent_region="",
            adjacent_ident=start[2],
            altitude_minimum=altitude,
        ),
    )


def _read_candidate_connections(
    candidate_xml: Path,
) -> tuple[
    dict[tuple[str, ...], list[dict[str, int]]],
    dict[tuple[str, ...], list[dict[str, object]]],
    dict[tuple[str, ...], list[dict[str, object]]],
    dict[str, int],
]:
    source = candidate_xml.expanduser().resolve()
    if not source.is_file():
        raise AirwayProjectionMatrixAuditError(f"candidate XML does not exist: {source}")
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as error:
        raise AirwayProjectionMatrixAuditError(
            f"candidate XML is not well formed: {source}"
        ) from error

    exact: dict[tuple[str, ...], list[dict[str, int]]] = defaultdict(list)
    base: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    wildcard: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    waypoint_index = 0
    for waypoint in root:
        if _tag(waypoint) != "Waypoint":
            continue
        waypoint_index += 1
        waypoint_region = _text(waypoint.get("waypointRegion"))
        waypoint_ident = _text(waypoint.get("waypointIdent"))
        if not waypoint_region or not waypoint_ident:
            counts["waypoints_without_complete_identity"] += 1
            continue
        route_index = 0
        for route in waypoint:
            if _tag(route) != "Route":
                continue
            route_index += 1
            route_name = _text(route.get("name"))
            route_type = _text(route.get("routeType"))
            if not route_name or not route_type:
                counts["routes_without_complete_identity"] += 1
                continue
            child_index = 0
            for child in route:
                direction = _tag(child).upper()
                if direction not in {"NEXT", "PREVIOUS"}:
                    continue
                child_index += 1
                connection = _connection(
                    route_name=route_name,
                    route_type=route_type,
                    waypoint_region=waypoint_region,
                    waypoint_ident=waypoint_ident,
                    direction=direction,
                    adjacent_region=_text(child.get("waypointRegion")),
                    adjacent_ident=_text(child.get("waypointIdent")),
                    altitude_minimum=_text(child.get("altitudeMinimum")),
                )
                if not all(connection.values()):
                    counts["connections_without_complete_identity"] += 1
                    continue
                location = {
                    "waypoint_index": waypoint_index,
                    "route_index": route_index,
                    "child_index": child_index,
                }
                exact[_exact_key(connection)].append(location)
                base[_base_key(connection)].append({
                    **location,
                    "altitude_minimum": connection["altitude_minimum"],
                })
                wildcard[_region_wildcard_key(connection)].append({
                    **location,
                    "waypoint_region": connection["waypoint_region"],
                    "adjacent_region": connection["adjacent_region"],
                })
                counts["connections"] += 1
    return exact, base, wildcard, dict(sorted(counts.items()))


def audit_airway_projection_matrix(
    model: NavModel,
    candidate_xml: Path,
) -> dict[str, object]:
    """Associate every source airway leg with candidate Route XML only."""

    candidate = candidate_xml.expanduser().resolve()
    exact, base, wildcard, candidate_counts = _read_candidate_connections(candidate)
    classifications: Counter[str] = Counter()
    entries: list[dict[str, object]] = []
    owned_candidate_edges: set[tuple[str, ...]] = set()
    for leg in sorted(model.airway_legs, key=_source_sort_key):
        entry: dict[str, object] = {
            "source": {
                "airway": _text(leg.airway),
                "sequence": int(leg.sequence),
                "file": leg.source.file,
                "row": int(leg.source.row or 0),
            },
        }
        reasons = _source_rejection_reasons(leg)
        non_region_reasons = tuple(
            reason
            for reason in reasons
            if reason not in {"missing_start_region", "missing_end_region"}
        )
        if non_region_reasons:
            entry["classification"] = "rejected_by_source"
            entry["reasons"] = list(reasons)
            classifications["rejected_by_source"] += 1
            entries.append(entry)
            continue
        if reasons:
            connection_rows: list[dict[str, object]] = []
            promoted = True
            for connection in _expected_connections_without_regions(leg):
                locations = wildcard.get(_region_wildcard_key(connection), [])
                row: dict[str, object] = {
                    **connection,
                    "region_resolution_required": True,
                    "wildcard_xml_match_count": len(locations),
                    "xml_locations": locations,
                }
                if len(locations) == 1:
                    row["status"] = "unique_target_identity_resolution"
                    location = locations[0]
                    actual = _connection(
                        route_name=connection["route_name"],
                        route_type=connection["route_type"],
                        waypoint_region=str(location["waypoint_region"]),
                        waypoint_ident=connection["waypoint_ident"],
                        direction=connection["direction"],
                        adjacent_region=str(location["adjacent_region"]),
                        adjacent_ident=connection["adjacent_ident"],
                        altitude_minimum=connection["altitude_minimum"],
                    )
                    owned_candidate_edges.add(_exact_key(actual))
                else:
                    row["status"] = "unresolved_target_identity_resolution"
                    promoted = False
                connection_rows.append(row)
            entry["connections"] = connection_rows
            entry["reasons"] = list(reasons)
            if promoted:
                entry["classification"] = "projected_after_target_identity_resolution"
                classifications["projected_after_target_identity_resolution"] += 1
            else:
                entry["classification"] = "rejected_by_source"
                classifications["rejected_by_source"] += 1
            entries.append(entry)
            continue

        connection_rows: list[dict[str, object]] = []
        classification = "projected"
        for connection in _expected_connections(leg):
            exact_locations = exact.get(_exact_key(connection), [])
            base_locations = base.get(_base_key(connection), [])
            row: dict[str, object] = {
                **connection,
                "exact_xml_match_count": len(exact_locations),
                "base_xml_match_count": len(base_locations),
                "xml_locations": exact_locations,
            }
            if len(exact_locations) == 1:
                row["status"] = "exact"
                owned_candidate_edges.add(_exact_key(connection))
            elif not base_locations:
                row["status"] = "missing_from_xml"
                classification = "missing_from_xml"
            else:
                row["status"] = "ambiguous_output_match"
                row["base_xml_locations"] = base_locations
                if classification != "missing_from_xml":
                    classification = "ambiguous_output_match"
            connection_rows.append(row)
        entry["classification"] = classification
        entry["connections"] = connection_rows
        classifications[classification] += 1
        entries.append(entry)

    if sum(classifications.values()) != len(model.airway_legs):
        raise AirwayProjectionMatrixAuditError(
            "airway projection classifications do not cover every source leg"
        )
    return {
        "diagnostic": "airway-projection-matrix-audit-v1",
        "read_only": True,
        "reference_payload_read": False,
        "source": {
            "model_airway_legs": len(model.airway_legs),
            "candidate_xml": str(candidate),
        },
        "candidate_xml": candidate_counts,
        "classification_counts": dict(sorted(classifications.items())),
        "candidate_connections_without_source_owner": sum(
            len(locations)
            for key, locations in exact.items()
            if key not in owned_candidate_edges
        ),
        "entries": entries,
    }


def write_airway_projection_matrix_audit(
    path: Path,
    report: Mapping[str, object],
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
