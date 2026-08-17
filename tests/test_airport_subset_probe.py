from xml.etree import ElementTree as ET

import pytest

from scripts.airport_subset_probe import (
    drop_selected_waypoints,
    isolate_holding_group,
    normalize_holding_file_groups,
    parse_airport_waypoint_selectors,
    parse_holding_attributes,
    select_airports,
    select_holding_patterns,
)


def _airport() -> ET.Element:
    return ET.fromstring(
        """<Airport ident="ZYJM">
        <HoldingPattern fixIdent="JM405"/>
        <HoldingPattern fixIdent="JM505"/>
        <HoldingPattern fixIdent="JM506"/>
        <HoldingPattern fixIdent="JM603"/>
        </Airport>"""
    )


def test_airport_ident_selection_preserves_source_order():
    airports = [
        ET.fromstring('<Airport ident="ZYAS"/>'),
        ET.fromstring('<Airport ident="ZYBA"/>'),
        ET.fromstring('<Airport ident="ZYJD"/>'),
    ]

    selected = select_airports(
        airports,
        start=None,
        end=None,
        airport_idents=("ZYJD", "ZYAS"),
    )

    assert [airport.attrib["ident"] for airport in selected] == ["ZYAS", "ZYJD"]


def test_airport_selection_requires_exactly_one_mode():
    airports = [ET.fromstring('<Airport ident="ZYAS"/>')]

    with pytest.raises(ValueError, match="不能与"):
        select_airports(
            airports,
            start=0,
            end=1,
            airport_idents=("ZYAS",),
        )

    with pytest.raises(ValueError, match="必须二选一"):
        select_airports(
            airports,
            start=None,
            end=None,
            airport_idents=(),
        )


def test_holding_ident_selection_supports_non_contiguous_subsets_in_source_order():
    airport = _airport()

    result = select_holding_patterns(
        airport,
        holding_idents=("JM405", "JM506", "JM603"),
        start=None,
        end=None,
    )

    assert result == ("JM405", "JM506", "JM603")
    assert [
        holding.attrib["fixIdent"]
        for holding in airport.findall("HoldingPattern")
    ] == ["JM405", "JM506", "JM603"]


def test_holding_ident_selection_rejects_ambiguous_selection_modes():
    with pytest.raises(ValueError, match="不能与"):
        select_holding_patterns(
            _airport(),
            holding_idents=("JM405",),
            start=0,
            end=1,
        )


def test_holding_file_groups_require_an_exact_non_overlapping_partition():
    groups = normalize_holding_file_groups(
        [["JM405", "JM505"], ["JM506", "JM603"]],
        selected_holding_idents=("JM405", "JM505", "JM506", "JM603"),
    )

    assert groups == (("JM405", "JM505"), ("JM506", "JM603"))

    with pytest.raises(ValueError, match="重复"):
        normalize_holding_file_groups(
            [["JM405", "JM505"], ["JM505", "JM506", "JM603"]],
            selected_holding_idents=("JM405", "JM505", "JM506", "JM603"),
        )


def test_holding_attribute_assignments_require_unique_name_value_pairs():
    assert parse_holding_attributes(
        ["requiredNavigationPerformance=1", "arcRadius=3.5NM"]
    ) == {
        "requiredNavigationPerformance": "1",
        "arcRadius": "3.5NM",
    }

    with pytest.raises(ValueError, match="重复"):
        parse_holding_attributes(["holdSpeed=210", "holdSpeed=250"])


def test_isolated_holding_group_keeps_only_its_waypoint_and_holding_pattern():
    airport = ET.fromstring(
        """<Airport ident="ZYJM">
        <Runway number="06"/>
        <Waypoint waypointIdent="JM405"/>
        <Waypoint waypointIdent="JM505"/>
        <HoldingPattern fixIdent="JM405"/>
        <HoldingPattern fixIdent="JM505"/>
        <Approach type="RNP"/>
        </Airport>"""
    )

    isolate_holding_group(airport, holding_idents=("JM405",))

    assert [child.tag for child in airport] == ["Waypoint", "HoldingPattern"]
    assert airport.find("Waypoint").attrib["waypointIdent"] == "JM405"
    assert airport.find("HoldingPattern").attrib["fixIdent"] == "JM405"

    without_waypoint = _airport()
    isolate_holding_group(
        without_waypoint,
        holding_idents=("JM405",),
        include_waypoints=False,
    )
    assert [child.tag for child in without_waypoint] == ["HoldingPattern"]


def test_parse_airport_waypoint_selectors_normalizes_and_rejects_duplicates() -> None:
    assert parse_airport_waypoint_selectors([
        "zggg:gg101",
        "ZGUH:UH402",
    ]) == {("ZGGG", "GG101"), ("ZGUH", "UH402")}

    with pytest.raises(ValueError, match="重复"):
        parse_airport_waypoint_selectors(["ZGGG:GG101", "zggg:gg101"])


def test_drop_selected_waypoints_keeps_unselected_scopes() -> None:
    root = ET.fromstring(
        "<FSData>"
        '<Waypoint waypointIdent="ROOT01" />'
        '<Waypoint waypointIdent="ROOT02" />'
        '<Airport ident="ZGGG"><Waypoint waypointIdent="GG101" />'
        '<Waypoint waypointIdent="KEEP" /></Airport>'
        '<Airport ident="ZGUH"><Waypoint waypointIdent="UH401" /></Airport>'
        "</FSData>"
    )

    drop_selected_waypoints(
        root,
        airport_selectors={("ZGGG", "GG101")},
        root_idents={"ROOT01"},
    )

    assert [point.get("waypointIdent") for point in root.findall("Waypoint")] == [
        "ROOT02",
    ]
    assert [
        point.get("waypointIdent")
        for point in root.find("Airport[@ident='ZGGG']").findall("Waypoint")
    ] == ["KEEP"]
    assert [
        point.get("waypointIdent")
        for point in root.find("Airport[@ident='ZGUH']").findall("Waypoint")
    ] == ["UH401"]
