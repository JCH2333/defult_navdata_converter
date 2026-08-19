import json
import struct
from xml.etree import ElementTree as ET

import pytest

from scripts.airport_subset_probe import (
    add_airport_procedure_deletion,
    append_airport_children,
    append_root_children,
    describe_file,
    describe_tree,
    drop_root_children,
    drop_runway_children,
    drop_selected_waypoints,
    inspect_bgl_layouts,
    isolate_holding_group,
    normalize_holding_file_groups,
    parse_airport_attributes,
    parse_airport_child_specs,
    parse_airport_waypoint_selectors,
    parse_holding_attributes,
    parse_root_object_specs,
    parse_runway_attributes,
    select_airports,
    select_holding_patterns,
    set_runway_attributes,
    write_probe_report,
)


def _bgl_header() -> bytes:
    return (
        struct.pack(
            "<IIIIII",
            0x19920201,
            0x38,
            0,
            0,
            0x08051803,
            1,
        )
        + struct.pack("<" + "I" * 8, 0x924, 0, 0, 0, 0, 0, 0, 0)
        + struct.pack("<IIIII", 0x03, 1, 4, 0x6C, 0x40)
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


def test_airport_attribute_assignments_are_diagnostic_and_deterministic():
    assert parse_airport_attributes(
        ["country=China", "city=Ali"]
    ) == {
        "country": "China",
        "city": "Ali",
    }

    with pytest.raises(ValueError, match="--set-airport-attribute"):
        parse_airport_attributes(["country=China", "country=China"])


def test_runway_attribute_assignments_only_change_existing_runways():
    airport = ET.fromstring(
        '<Airport ident="ZUAL"><Runway number="15" surface="CONCRETE">'
        '<Ils ident="IKS" /></Runway><Waypoint waypointIdent="AK500" />'
        "</Airport>"
    )

    attributes = parse_runway_attributes(["surface=ASPHALT"])
    set_runway_attributes(airport, attributes)

    runway = airport.find("Runway")
    assert runway is not None
    assert runway.attrib["surface"] == "ASPHALT"
    assert runway.find("Ils").attrib["ident"] == "IKS"
    assert airport.find("Waypoint").attrib["waypointIdent"] == "AK500"
    with pytest.raises(ValueError, match="--set-runway-attribute"):
        parse_runway_attributes(["surface=ASPHALT", "surface=CONCRETE"])


def test_drop_root_children_keeps_selected_airport_and_unrelated_objects():
    root = ET.fromstring(
        "<FSData><AiracCycle cycleNumber=\"08\" />"
        '<Vor ident="ALI" /><Ndb ident="ALS" />'
        '<Airport ident="ZUAL" /><CustomData value="kept" /></FSData>'
    )

    drop_root_children(root, tags={"AiracCycle", "Vor", "Ndb"})

    assert [(child.tag, child.attrib) for child in root] == [
        ("Airport", {"ident": "ZUAL"}),
        ("CustomData", {"value": "kept"}),
    ]


def test_airport_child_specs_are_attribute_only_and_append_in_order():
    children = parse_airport_child_specs([
        "Com;frequency=118.0;type=GROUND;name=Probe",
        "Tower;lat=32.1;lon=80.053056;alt=14022F",
    ])
    airport = ET.fromstring('<Airport ident="ZUAL"><Runway number="15" /></Airport>')

    append_airport_children(airport, children)

    assert [
        (child.tag, child.attrib)
        for child in list(airport)
    ] == [
        ("Runway", {"number": "15"}),
        ("Com", {"frequency": "118.0", "type": "GROUND", "name": "Probe"}),
        ("Tower", {"lat": "32.1", "lon": "80.053056", "alt": "14022F"}),
    ]
    with pytest.raises(ValueError, match="--append-airport-child"):
        parse_airport_child_specs(["Com;frequency=118.0;frequency=121.0"])


def test_root_children_reuse_diagnostic_specs_without_reparenting():
    children = parse_airport_child_specs([
        "Ndb;frequency=385;ident=PRB",
    ])
    root = ET.fromstring("<FSData><Airport ident=\"ZUAL\" /></FSData>")

    append_root_children(root, children)

    assert [
        (child.tag, child.attrib)
        for child in list(root)
    ] == [
        ("Airport", {"ident": "ZUAL"}),
        ("Ndb", {"frequency": "385", "ident": "PRB"}),
    ]
    assert children[0].get("frequency") == "385"


def test_drop_runway_children_keeps_the_runway_and_other_child_objects():
    airport = ET.fromstring(
        '<Airport ident="ZUAL"><Runway number="15"><Ils ident="IKS"/>'
        '<Threshold length="0F"/></Runway></Airport>'
    )

    drop_runway_children(airport, tags={"Ils"})

    runway = airport.find("Runway")
    assert runway is not None
    assert runway.attrib["number"] == "15"
    assert [child.tag for child in runway] == ["Threshold"]


def test_root_object_specs_support_one_level_sdk_children():
    objects = parse_root_object_specs([
        (
            "Vor;lat=32.1;lon=80.053056;alt=14022F;type=HIGH;"
            "frequency=113.0;magvar=0;range=125NM;region=ZU;ident=PRV;"
            "name=Probe;nav=TRUE;dme=TRUE|"
            "Dme;lat=32.1;lon=80.053056;alt=14022F;range=125NM"
        ),
    ])
    root = ET.fromstring("<FSData />")

    append_root_children(root, objects)

    assert root[0].tag == "Vor"
    assert root[0].attrib["ident"] == "PRV"
    assert [(child.tag, child.attrib["range"]) for child in root[0]] == [
        ("Dme", "125NM"),
    ]
    with pytest.raises(ValueError, match="--append-root-object"):
        parse_root_object_specs(["|Dme;lat=32.1"])


def test_airport_procedure_deletion_is_inserted_before_source_children():
    airport = ET.fromstring(
        '<Airport ident="ZUAL"><Runway number="15" /></Airport>'
    )

    add_airport_procedure_deletion(airport)

    deletion = airport.find("DeleteAirport")
    assert deletion is not None
    assert deletion.attrib == {
        "deleteAllApproaches": "TRUE",
        "deleteAllDepartures": "TRUE",
        "deleteAllArrivals": "TRUE",
    }
    assert [child.tag for child in airport] == ["DeleteAirport", "Runway"]


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


def test_probe_layout_summary_reads_only_bgl_headers(tmp_path) -> None:
    package = tmp_path / "package"
    bgl = package / "scenery" / "probe.bgl"
    bgl.parent.mkdir(parents=True)
    bgl.write_bytes(_bgl_header())

    report = inspect_bgl_layouts(package)

    assert report == [{
        "path": "scenery/probe.bgl",
        "size": bgl.stat().st_size,
        "layout": {
            "section_count": 1,
            "section_types": ["0x3"],
            "qmid_tiles": ["0x924", "0x0", "0x0", "0x0", "0x0", "0x0", "0x0", "0x0"],
            "embedded_magvar_size": 0,
            "has_embedded_magvar": False,
            "version": "0x8051803",
            "section_counts": [4],
            "section_sizes": [64],
        },
    }]


def test_probe_report_is_persisted_as_utf8_json(tmp_path) -> None:
    path = tmp_path / "probe-report.json"
    report = {
        "label": "two-tile-empty-airports",
        "airport_idents": ["ZUAL", "ZUUU"],
        "bgl_layouts": [{"path": "scenery/zu_airports.bgl", "size": 565}],
    }

    write_probe_report(path, report)

    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_probe_file_descriptions_use_content_hashes_and_stable_tree_paths(tmp_path) -> None:
    root = tmp_path / "probe"
    nested = root / "nested"
    nested.mkdir(parents=True)
    first = root / "a.txt"
    second = nested / "b.bin"
    first.write_text("airport=ZUAL\n", encoding="utf-8")
    second.write_bytes(b"\x00\x01")

    assert describe_file(first, relative_to=root) == {
        "path": "a.txt",
        "size": 14,
        "sha256": "d086d4fe885e265b62672ac468eb76437cd55a965a7a04e990947c9705947012",
    }
    assert describe_tree(root) == [
        describe_file(first, relative_to=root),
        describe_file(second, relative_to=root),
    ]
