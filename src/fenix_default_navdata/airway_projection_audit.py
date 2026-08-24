from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def _point_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized in {"NAMED", "WAYPOINT", "WN", "WPT"}:
        return "NAMED"
    if normalized.startswith("V"):
        return "VOR"
    if normalized.startswith("N"):
        return "NDB"
    return "NAMED"


def _identity(point_type: str, region: str, ident: str) -> tuple[str, str, str]:
    return (
        _point_type(point_type),
        (region or "").strip().upper()[:2],
        (ident or "").strip().upper(),
    )


def audit_airway_xml_projection(model, xml_path: Path) -> dict[str, object]:
    """Compare source airway edges with the generated XML route graph."""
    root = ET.parse(xml_path).getroot()
    actual: set[tuple[str, tuple[str, str, str], tuple[str, str, str]]] = set()
    for waypoint in root.findall("Waypoint"):
        current = _identity(
            waypoint.get("waypointType", ""),
            waypoint.get("waypointRegion", ""),
            waypoint.get("waypointIdent", ""),
        )
        for route in waypoint.findall("Route"):
            name = (route.get("name") or "").strip().upper()
            for child in list(route):
                target = _identity(
                    child.get("waypointType", ""),
                    child.get("waypointRegion", ""),
                    child.get("waypointIdent", ""),
                )
                if child.tag == "Next":
                    actual.add((name, current, target))
                elif child.tag == "Previous":
                    actual.add((name, target, current))

    expected: set[tuple[str, tuple[str, str, str], tuple[str, str, str]]] = set()
    for leg in model.airway_legs:
        if not leg.start_country or not leg.end_country:
            continue
        if None in {
            leg.start_latitude,
            leg.start_longitude,
            leg.end_latitude,
            leg.end_longitude,
        }:
            continue
        expected.add((
            leg.airway.strip().upper(),
            _identity(leg.start_type, leg.start_country, leg.start_ident),
            _identity(leg.end_type, leg.end_country, leg.end_ident),
        ))

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    focus = [
        item for item in missing
        if item[0] in {"W215", "H14", "B213", "W214"}
        and (
            item[1][2] in {"YHD", "DWZ", "HO", "P396", "OLPOV", "WHA"}
            or item[2][2] in {"YHD", "DWZ", "HO", "P396", "OLPOV", "WHA"}
        )
    ]
    return {
        "verified": not missing,
        "expected_edges": len(expected),
        "actual_edges": len(actual),
        "missing_edges": [
            {"airway": name, "from": list(start), "to": list(end)}
            for name, start, end in missing[:200]
        ],
        "extra_edges": [
            {"airway": name, "from": list(start), "to": list(end)}
            for name, start, end in extra[:200]
        ],
        "critical_missing_edges": [
            {"airway": name, "from": list(start), "to": list(end)}
            for name, start, end in focus
        ],
    }
