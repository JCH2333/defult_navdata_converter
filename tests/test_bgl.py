import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from fenix_default_navdata.bgl import (
    CompilerInfo,
    PackageToolProcessTrace,
    _iap_chart_roles,
    compile_package,
    find_compiler,
    write_bglcomp_xml,
    write_package_project,
)
from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    ChartRouteFix,
    ChartTerminalLeg,
    Holding,
    IapOcrRoleEvidence,
    Ils,
    NavModel,
    Navaid,
    ProcedureChart,
    ProcedureSegment,
    Runway,
    SourceRef,
    TerminalWaypoint,
    Waypoint,
)
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_bgl_xml_is_deterministic(tmp_path: Path):
    model = NavModel(Path("source"))
    model.airports["a"] = Airport("a", "ZBCF", "TEST", 35.0, 105.0, 1000, 18000, 180, SourceRef("AD_HP.csv", 2))
    model.runways.append(Runway("r", "a", "03L", 30.0, 10000, 150, "ASP", 1000, SourceRef("RWY_DIRECTION.csv", 2)))
    model.waypoints.extend([
        Waypoint("w1", "START", "START", 35.0, 105.0, SourceRef("points", 1), "ZB"),
        Waypoint("w2", "END", "END", 36.0, 106.0, SourceRef("points", 2), "ZB"),
    ])
    model.airway_legs.append(AirwayLeg(
        "W1", 1, "START", "END", SourceRef("RTE_SEG.csv", 2),
        start_latitude=35.0, start_longitude=105.0,
        end_latitude=36.0, end_longitude=106.0,
        start_country="ZB", end_country="ZB",
    ))
    first = tmp_path / "one.xml"
    second = tmp_path / "two.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, first)
    write_bglcomp_xml(model, DEFAULT_CYCLE, second)
    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    assert root.tag == "FSData"
    assert root.find("AiracCycle").attrib["cycleNumber"] == "08"
    assert root.find("Airport/Runway").attrib["number"] == "03"
    route = root.find("./Waypoint[@waypointIdent='START']/Route")
    assert route is not None
    assert route.attrib == {"name": "W1", "routeType": "BOTH"}
    assert route.find("Next").attrib == {
        "waypointRegion": "ZB",
        "waypointIdent": "END",
        "waypointType": "NAMED",
        "altitudeMinimum": "0F",
    }


def test_enroute_projection_does_not_reduce_links_from_raw_424_code_dir(
    tmp_path: Path,
):
    """CODE_DIR remains source provenance until an SDK direction contract exists."""
    model = NavModel(Path("source"))
    source = SourceRef("RTE_SEG.csv", 2)
    legs = (
        AirwayLeg(
            "F1", 1, "FSTART", "FEND", source, direction="F",
            start_latitude=35.0, start_longitude=105.0,
            end_latitude=35.1, end_longitude=105.1,
            start_country="ZB", end_country="ZB",
        ),
        AirwayLeg(
            "B1", 1, "BSTART", "BEND", source, direction="B",
            start_latitude=36.0, start_longitude=106.0,
            end_latitude=36.1, end_longitude=106.1,
            start_country="ZB", end_country="ZB",
        ),
        AirwayLeg(
            "X1", 1, "XSTART", "XEND", source, direction="X",
            start_latitude=37.0, start_longitude=107.0,
            end_latitude=37.1, end_longitude=107.1,
            start_country="ZB", end_country="ZB",
        ),
    )
    model.airway_legs.extend(legs)

    output = tmp_path / "raw-code-dir.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    for leg in legs:
        start_route = root.find(
            f"./Waypoint[@waypointIdent='{leg.start_ident}']/Route[@name='{leg.airway}']"
        )
        end_route = root.find(
            f"./Waypoint[@waypointIdent='{leg.end_ident}']/Route[@name='{leg.airway}']"
        )
        assert start_route is not None
        assert end_route is not None
        assert [child.tag for child in start_route] == ["Next"]
        assert [child.tag for child in end_route] == ["Previous"]


def test_enroute_projection_romanizes_chinese_navaid_names(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("VOR.csv", 2)
    model.navaids.extend((
        Navaid("vor", "KNS", "VOR", "喀纳斯", 48.220000, 87.008333, 111.2, -5.2, 3937, "ZW", source),
        Navaid("ndb", "DM", "NDB", "泽当", 29.256111, 91.764167, 435.0, -0.5, 0, "ZU", source),
    ))

    output = tmp_path / "navaids.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    assert root.find("Vor").attrib["name"] == "KANASI"
    assert root.find("Vor").attrib["alt"] == "3937F"
    assert root.find("Ndb").attrib["name"] == "ZEDANG"


def test_enroute_projection_can_emit_only_verified_selected_navaids(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("VOR.csv", 2)
    kept = Navaid(
        "kept", "KEEP", "VOR", "保留", 35.0, 105.0, 111.2, 0.0, 100, "ZB", source,
    )
    suppressed = Navaid(
        "suppressed", "DROP", "NDB", "抑制", 36.0, 106.0, 445.0, 0.0, 0, "ZB", source,
    )
    model.navaids.extend((kept, suppressed))

    output = tmp_path / "selected-navaids.xml"
    projection = write_bglcomp_xml(
        model,
        DEFAULT_CYCLE,
        output,
        scope="enroute",
        selected_navaids=(kept,),
    )

    root = ET.parse(output).getroot()
    assert [item.attrib["ident"] for item in root.findall("Vor")] == ["KEEP"]
    assert root.findall("Ndb") == []
    assert projection.navaids == 1


def test_enroute_projection_uses_verified_default_navaid_name_exceptions(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("VOR.csv", 2)
    model.navaids.extend((
        Navaid("dgl", "DGL", "VOR", "霍林郭勒", 45.469444, 119.503333, 112.4, -9.8, 3116, "ZB", source),
        Navaid("kel", "KEL", "VOR", "库尔勒", 41.700000, 86.133333, 115.9, -2.0, 3035, "ZW", source),
        Navaid("lua", "LUA", "VOR", "阿拉尔", 40.506667, 81.227500, 117.4, -2.0, 3369, "ZW", source),
        Navaid("klm", "KLM", "VOR", "克拉玛依", 45.000000, 84.000000, 113.3, -4.0, 938, "ZW", source),
        Navaid("ptg", "PTG", "VOR", "吐鲁番", 42.950000, 89.000000, 116.0, -3.0, 899, "ZW", source),
        Navaid("ho", "HO", "NDB", "长武", 35.000000, 107.000000, 300.0, 0.0, 0, "ZL", source),
        Navaid("sq", "SQ", "NDB", "长治", 36.000000, 113.000000, 300.0, 0.0, 0, "ZH", source),
        Navaid("rg", "RG", "NDB", "昌都", 31.000000, 97.000000, 300.0, 0.0, 0, "ZP", source),
    ))

    output = tmp_path / "navaid-name-exceptions.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    names = {
        item.attrib["ident"]: item.attrib["name"]
        for item in (*root.findall("Vor"), *root.findall("Ndb"))
    }
    assert names == {
        "DGL": "HUOLINGUOLE",
        "KEL": "KUERLE",
        "LUA": "ALAE",
        "KLM": "KALAMAYI",
        "PTG": "TURPAN",
        "HO": "CHANGWU",
        "SQ": "CHANGZHI",
        "RG": "CHANGDU",
    }


def test_enroute_projection_skips_records_without_source_proven_regions(tmp_path: Path):
    model = NavModel(Path("source"))
    model.waypoints.append(Waypoint(
        "unresolved-point", "UNRES", "UNRES", 36.0, 106.0,
        SourceRef("DESIGNATED_POINT.csv", 2), "",
    ))
    model.airway_legs.append(AirwayLeg(
        "R1", 1, "KNOWN", "UNRES", SourceRef("RTE_SEG.csv", 2),
        start_latitude=35.0, start_longitude=105.0,
        end_latitude=36.0, end_longitude=106.0,
        start_country="ZB", end_country="",
        start_type="DESIGNATED_POINT", end_type="DESIGNATED_POINT",
    ))

    output = tmp_path / "unresolved-enroute.xml"
    projection = write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    assert root.findall("Waypoint") == []
    assert projection.skipped_enroute_waypoints == 1
    assert projection.skipped_airway_legs == 1
    assert projection.skipped_airway_leg_details == (
        {
            "airway": "R1",
            "sequence": 1,
            "source": {"file": "RTE_SEG.csv", "row": 2},
            "reasons": ["missing_end_region"],
            "start": {
                "ident": "KNOWN",
                "type": "DESIGNATED_POINT",
                "region": "ZB",
            },
            "end": {
                "ident": "UNRES",
                "type": "DESIGNATED_POINT",
                "region": "",
            },
        },
    )


def test_enroute_projection_adds_only_shared_terminal_waypoints(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("Terminal/ZBAA/coordinate-page.pdf", page=1)
    model.waypoints.append(Waypoint(
        "existing", "EXISTING", "EXISTING", 35.0, 105.0, source, "ZB",
    ))
    model.terminal_waypoints.extend((
        TerminalWaypoint("shared-one", "ZBAA", "SHARED", 35.1, 105.1, source, "ZB"),
        TerminalWaypoint("shared-two", "ZBAD", "SHARED", 35.1, 105.1, source, "ZB"),
        TerminalWaypoint("local", "ZBAA", "LOCAL", 35.2, 105.2, source, "ZB"),
        TerminalWaypoint("ambiguous-one", "ZBAA", "AMBIG", 35.3, 105.3, source, "ZB"),
        TerminalWaypoint("ambiguous-two", "ZBAD", "AMBIG", 35.3, 105.3, source, "ZB"),
        TerminalWaypoint("ambiguous-three", "ZBCF", "AMBIG", 35.4, 105.4, source, "ZB"),
        TerminalWaypoint("ambiguous-four", "ZBSJ", "AMBIG", 35.4, 105.4, source, "ZB"),
        TerminalWaypoint("existing-one", "ZBAA", "EXISTING", 35.5, 105.5, source, "ZB"),
        TerminalWaypoint("existing-two", "ZBAD", "EXISTING", 35.5, 105.5, source, "ZB"),
    ))

    output = tmp_path / "shared-terminal-enroute.xml"
    projection = write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    points = {
        point.attrib["waypointIdent"]: point
        for point in root.findall("Waypoint")
    }
    assert set(points) == {"EXISTING", "SHARED"}
    assert points["EXISTING"].attrib["lat"] == "35"
    assert projection.waypoints == 2
    assert projection.shared_terminal_enroute_waypoints == 1


def test_airport_projection_emits_source_backed_holding_pattern(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("ZBAA-0C-15.pdf", page=1)
    model.airports["a"] = Airport(
        "a", "ZBAA", "ZBAA", 40.0, 116.0, 100, 18000, 180, source,
    )
    model.terminal_waypoints.append(TerminalWaypoint(
        "holding-fix", "ZBAA", "IGMOR", 40.1, 116.1, source, "ZB",
    ))
    model.holdings.append(Holding(
        "IGMOR", "IGMOR", "ZBAA", 40.1, 116.1, 109, "L", None, 1.5,
        19685, None, None, source,
    ))

    output = tmp_path / "holdings.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    holding = ET.parse(output).getroot().find("Airport/HoldingPattern")
    assert holding is not None
    assert holding.attrib == {
        "name": "IGMOR",
        "fixType": "TERMINAL_WAYPOINT",
        "fixIdent": "IGMOR",
        "fixRegion": "ZB",
        "inboundHoldingCourse": "109",
        "turnDirection": "L",
        "time": "1.5",
        "altitudeMinimum": "19685F",
    }


def test_airport_projection_keeps_source_holdings_in_main_bgl(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("ZYJM-4Z03.pdf", page=1)
    model.airports["zyjm"] = Airport(
        "zyjm", "ZYJM", "ZYJM", 46.8, 130.4, 100, 18000, 180, source,
    )
    holdings = (
        ("JM405", 46.908333, 130.373889, 59, "L"),
        ("JM505", 46.716389, 130.455556, 239, "L"),
        ("JM506", 46.635278, 130.129167, 59, "R"),
        ("JM603", 47.04, 130.786389, 239, "R"),
    )
    for ident, latitude, longitude, course, turn in holdings:
        model.terminal_waypoints.append(TerminalWaypoint(
            f"holding:{ident}", "ZYJM", ident, latitude, longitude, source, "ZY",
        ))
        model.holdings.append(Holding(
            ident, ident, "ZYJM", latitude, longitude, course, turn, None, 1.0,
            4199, None, 210, source,
        ))

    output = tmp_path / "ZY_airports.xml"
    write_bglcomp_xml(
        model,
        DEFAULT_CYCLE,
        output,
        scope="airports",
        airport_prefix="ZY",
    )
    airport = ET.parse(output).getroot().find("Airport")
    assert airport is not None
    assert [
        holding.attrib["fixIdent"]
        for holding in airport.findall("HoldingPattern")
    ] == ["JM405", "JM505", "JM506", "JM603"]


def test_airport_projection_filters_prefix_and_emits_ils_and_procedure(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["zb"] = Airport("zb", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source)
    model.airports["zg"] = Airport("zg", "ZGAA", "ZGAA", 23.0, 113.0, 40, 18000, 180, source)
    model.runways.append(Runway(
        "r", "zb", "03L", 30.0, 10000, 150, "ASP", 1000, source, 35.1, 105.1,
    ))
    model.ilses.append(Ils(
        "ZBCF", "03L", "ICF", 109.5, "1", 35.11, 105.11, 27.0, 3.0, None,
        35.11, 105.11, 35.11, 105.11, 304.8, source,
    ))
    model.terminal_waypoints.append(TerminalWaypoint(
        "t", "ZBCF", "FIX01", 35.3, 105.3, source, "ZB",
    ))
    leg = ChartTerminalLeg(
        "SID01", "03L", "TF", "FIX01", "fixture",
        procedure_kind="departure", sequence=1, fix_region="ZB",
        fix_type="TERMINAL_WAYPOINT", fix_latitude=35.3, fix_longitude=105.3,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF", "SID01", "departure", "03L", "", (leg,), source,
    ))
    output = tmp_path / "ZB_airports.xml"
    projection = write_bglcomp_xml(
        model,
        DEFAULT_CYCLE,
        output,
        scope="airports",
        airport_prefix="ZB",
        duplicate_terminal_waypoints=True,
    )
    root = ET.parse(output).getroot()
    assert [airport.attrib["ident"] for airport in root.findall("Airport")] == ["ZBCF"]
    assert root.find("Airport/Runway/Ils/GlideSlope") is not None
    assert root.find("Airport/Runway/Ils/Dme") is not None
    leg_attributes = root.find(
        "Airport/Departure/RunwayTransitions/RunwayTransitionLegs/Leg"
    ).attrib
    assert leg_attributes["fixIdent"] == "FIX01"
    assert leg_attributes["trueCourse"] == "0"
    assert leg_attributes["flyOver"] == "FALSE"
    assert leg_attributes["turnDirection"] == "E"
    assert len(root.findall("Waypoint")) == 1
    assert projection.waypoints == 2


def test_airport_projection_maps_raw_chinese_procedure_kinds_and_iap_sections(
    tmp_path: Path,
):
    model = NavModel(Path("source"))
    source = SourceRef("approach.pdf", 1, 1, "hash")
    primary_source = SourceRef("approach-continuation.pdf", 1, 1, "hash")
    missed_source = SourceRef("approach-missed.pdf", 1, 1, "hash")
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "03", 30.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.extend([
        TerminalWaypoint(f"point-{ident}", "ZBCF", ident, 35.0 + index / 100, 105.0, source, "ZB")
        for index, ident in enumerate(("DEP01", "ARR01", "TRANS", "IAF", "RW03", "MAHF", "MISSED"))
    ])
    model.procedure_segments.extend([
        ProcedureSegment(
            "ZBCF", "SID01", "离场", "03", "", (
                ChartTerminalLeg(
                    "SID01", "03", "TF", "DEP01", "fixture",
                    sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.01, fix_longitude=105.0,
                ),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "STAR01", "进场", "", "ARRTR", (
                ChartTerminalLeg(
                    "STAR01", "", "TF", "ARR01", "fixture",
                    sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.02, fix_longitude=105.0,
                ),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "R03", "进近过渡", "03", "TRANS", (
                ChartTerminalLeg(
                    "R03", "03", "IF", "TRANS", "fixture",
                    sequence=1, transition="TRANS", fix_region="ZB",
                    fix_type="TERMINAL_WAYPOINT", fix_latitude=35.03, fix_longitude=105.0,
                ),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "R03-Z", "进近", "03", "", (
                ChartTerminalLeg(
                    "R03-Z", "03", "IF", "IAF", "fixture",
                    sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.04, fix_longitude=105.0,
                ),
                ChartTerminalLeg(
                    "R03-Z", "03", "TF", "RW03", "fixture",
                    sequence=2, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.05, fix_longitude=105.0,
                ),
                ChartTerminalLeg(
                    "R03-Z", "03", "DF", "MISSED", "fixture",
                    sequence=3, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.06, fix_longitude=105.0,
                ),
            ), primary_source,
        ),
        ProcedureSegment(
            "ZBCF", "R03", "复飞", "03", "", (
                ChartTerminalLeg(
                    "R03", "03", "DF", "MAHF", "fixture",
                    sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                    fix_latitude=35.06, fix_longitude=105.0,
                ),
            ), missed_source,
        ),
    ])
    model.procedure_charts.append(ProcedureChart(
        "ZBCF", "ZBCF-5Z03.pdf", 1, "instrument-approach-index",
        "RNP Z RWY03", "text", (), ("03",), (), (), (), source,
        has_missed_approach=True,
    ))

    output = tmp_path / "raw-kinds.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    airport = ET.parse(output).getroot().find("Airport")
    assert airport is not None
    assert airport.find("Departure[@name='SID01']") is not None
    assert airport.find("Arrival[@name='STAR01']") is not None
    approach = airport.find("Approach[@suffix='Z']")
    assert approach is not None
    assert approach.find("ApproachLegs/Leg[@fixIdent='IAF']") is not None
    assert approach.find("Transition[@name='TRANS']") is not None
    missed = approach.find("MissedApproachLegs")
    assert missed is not None
    assert [leg.attrib["fixIdent"] for leg in missed.findall("Leg")] == ["MISSED", "MAHF"]


def test_iap_chart_roles_select_unique_map_chart_and_project_role_flags(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "03", 30.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.extend([
        TerminalWaypoint("iaf", "ZBCF", "IAF01", 35.10, 105.0, source, "ZB"),
        TerminalWaypoint("faf", "ZBCF", "FAF01", 35.05, 105.0, source, "ZB"),
        TerminalWaypoint("map", "ZBCF", "RW03", 35.01, 105.0, source, "ZB"),
    ])
    primary = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg(
                "R03", "03", "IF", "IAF01", "fixture", sequence=1,
                fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.10, fix_longitude=105.0,
            ),
            ChartTerminalLeg(
                "R03", "03", "TF", "FAF01", "fixture", sequence=2,
                fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.05, fix_longitude=105.0,
            ),
            ChartTerminalLeg(
                "R03", "03", "TF", "RW03", "fixture", sequence=3,
                fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.01, fix_longitude=105.0,
            ),
        ), source,
    )
    model.procedure_segments.append(primary)
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ZBCF-rnp-a.pdf", 1, "instrument-approach-index",
            "RNP RWY03", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("OTHER", "MAPT"),),
        ),
        ProcedureChart(
            "ZBCF", "ZBCF-rnp-b.pdf", 1, "instrument-approach-index",
            "RNP RWY03", "text", (), ("03",), (), (), (), source,
            route_fixes=(
                ChartRouteFix("IAF01", "IAF"),
                ChartRouteFix("IAF01", "IF"),
                ChartRouteFix("FAF01", "FAF"),
                ChartRouteFix("RW03", "MAPT"),
            ),
        ),
    ])

    assert _iap_chart_roles(model, primary) == {
        "IAF01": {"IAF", "IF"},
        "FAF01": {"FAF"},
        "RW03": {"MAPT"},
    }

    output = tmp_path / "iap-role-flags.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    legs = ET.parse(output).getroot().findall("Airport/Approach/ApproachLegs/Leg")
    assert [leg.attrib["fixIdent"] for leg in legs] == ["IAF01", "FAF01", "RW03"]
    assert legs[0].attrib["isIAF"] == "TRUE"
    assert legs[0].attrib["isIF"] == "TRUE"
    assert legs[1].attrib["isFAF"] == "TRUE"
    assert legs[2].attrib["isMAP"] == "TRUE"


def test_bgl_iap_chart_roles_reuse_rnp_ar_title_qualifier_selection(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("Terminal/ZUNZ/ZUNZ-4G05.pdf", 1, 1, "database-hash")
    model.airports["a"] = Airport(
        "a", "ZUNZ", "ZUNZ", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "05", 50.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.extend([
        TerminalWaypoint("first", "ZUNZ", "LZ250", 35.10, 105.0, source, "ZU"),
        TerminalWaypoint("qualifier", "ZUNZ", "LZ302", 35.05, 105.0, source, "ZU"),
    ])
    primary = ProcedureSegment(
        "ZUNZ", "R05", "approach", "05", "", (
            ChartTerminalLeg(
                "R05", "05", "TF", "LZ250", "fixture", sequence=1,
                fix_region="ZU", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.10, fix_longitude=105.0,
            ),
            ChartTerminalLeg(
                "R05", "05", "TF", "LZ302", "fixture", sequence=2,
                fix_region="ZU", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.05, fix_longitude=105.0,
            ),
        ), source,
    )
    model.procedure_segments.append(primary)
    model.procedure_charts.extend([
        ProcedureChart(
            "ZUNZ", "ZUNZ-9A.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(DUMIX)", "text", (), ("05",), (), (), (), source,
        ),
        ProcedureChart(
            "ZUNZ", "ZUNZ-9C.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(LZ302)", "text", (), ("05",), (), (), (), source,
            route_fixes=(ChartRouteFix("LZ302", "IAF"),),
        ),
    ])

    assert _iap_chart_roles(model, primary) == {"LZ302": {"IAF"}}

    output = tmp_path / "iap-title-qualifier.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    leg = ET.parse(output).getroot().find("Airport/Approach/ApproachLegs/Leg[@fixIdent='LZ302']")
    assert leg is not None
    assert leg.attrib["isIAF"] == "TRUE"


def test_bgl_iap_chart_roles_reuse_unqualified_rnp_ar_direct_role_selection(
    tmp_path: Path,
):
    model = NavModel(Path("source"))
    source = SourceRef("Terminal/ZUNP/ZUNP-4Z03.pdf", 1, 1, "database-hash")
    model.airports["a"] = Airport(
        "a", "ZUNP", "ZUNP", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "06", 50.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.extend([
        TerminalWaypoint("first", "ZUNP", "NP508", 35.10, 105.0, source, "ZU"),
        TerminalWaypoint("last", "ZUNP", "LIP", 35.05, 105.0, source, "ZU"),
    ])
    primary = ProcedureSegment(
        "ZUNP", "R06", "approach", "06", "", (
            ChartTerminalLeg(
                "R06", "06", "TF", "NP508", "fixture", sequence=1,
                fix_region="ZU", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.10, fix_longitude=105.0,
            ),
            ChartTerminalLeg(
                "R06", "06", "TF", "LIP", "fixture", sequence=2,
                fix_region="ZU", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.05, fix_longitude=105.0,
            ),
        ), source,
    )
    model.procedure_segments.append(primary)
    model.procedure_charts.extend([
        ProcedureChart(
            "ZUNP", "ZUNP-9A.pdf", 1, "instrument-approach-index",
            "RNP RWY06(AR)", "text", (), ("06",), (), (), (), source,
            route_fixes=(ChartRouteFix("NP800", "IAF"),),
        ),
        ProcedureChart(
            "ZUNP", "ZUNP-9B.pdf", 1, "instrument-approach-index",
            "RNP RWY06(AR)", "text", (), ("06",), (), (), (), source,
            route_fixes=(ChartRouteFix("LIP", "IAF"),),
        ),
    ])

    assert _iap_chart_roles(model, primary) == {"LIP": {"IAF"}}

    output = tmp_path / "iap-unqualified-rnp-ar-direct-role.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    leg = ET.parse(output).getroot().find("Airport/Approach/ApproachLegs/Leg[@fixIdent='LIP']")
    assert leg is not None
    assert leg.attrib["isIAF"] == "TRUE"


def test_bgl_projects_same_runway_rnp_and_rnp_ar_from_direct_primary_identity(
    tmp_path: Path,
):
    model = NavModel(Path("source"))
    source = SourceRef("database.pdf", 1, 1, "database-hash")
    normal_source = SourceRef("Terminal/ZBCF/ZBCF-4H.pdf", 1, 1, "normal-db")
    ar_source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "ar-db")
    normal_missed_source = SourceRef("Terminal/ZBCF/ZBCF-4J.pdf", 1, 1, "normal-missed")
    model.airports["airport"] = Airport(
        "airport", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "runway", "airport", "03", 30.0, 10000, 150, "ASP", 1000, source,
    ))
    model.procedure_segments.extend([
        ProcedureSegment(
            "ZBCF", "R03", "approach_transition", "03", "VIA", (
                ChartTerminalLeg("R03", "03", "IF", "NORMAL1", "fixture", sequence=1),
            ), normal_source, approach_family="RNP",
        ),
        ProcedureSegment(
            "ZBCF", "R03", "approach", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "NORMAL1", "fixture", sequence=1),
                ChartTerminalLeg("R03", "03", "TF", "NORMAL2", "fixture", sequence=2),
            ), normal_source, approach_family="RNP",
        ),
        ProcedureSegment(
            "ZBCF", "R03", "approach", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "ARFIX1", "fixture", sequence=1),
                ChartTerminalLeg("R03", "03", "TF", "ARFIX2", "fixture", sequence=2),
            ), ar_source, approach_family="RNP_AR",
        ),
        ProcedureSegment(
            "ZBCF", "R03", "missed", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "ARMAHF", "fixture", sequence=1),
            ), ar_source, approach_family="RNP_AR",
        ),
        ProcedureSegment(
            "ZBCF", "R03", "missed", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "NMHF1", "fixture", sequence=1),
                ChartTerminalLeg("R03", "03", "TF", "NML1", "fixture", sequence=2),
            ), normal_missed_source,
        ),
    ])
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ZBCF-9A.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("NORMAL1", "NORMAL2", "NMHF1", "NML1"), (), (),
            SourceRef("Terminal/ZBCF/ZBCF-9A.pdf", 1, 1, "normal-chart"),
        ),
        ProcedureChart(
            "ZBCF", "ZBCF-9C.pdf", 1, "instrument-approach-index", "RNP RWY03(AR)",
            "text", (), ("03",), ("ARFIX1", "ARFIX2"), (), (),
            SourceRef("Terminal/ZBCF/ZBCF-9C.pdf", 1, 1, "ar-chart"),
            has_missed_approach=True,
        ),
    ])

    output = tmp_path / "rnp-ar-primary-identity.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    approaches = ET.parse(output).getroot().findall("Airport/Approach")
    assert len(approaches) == 2
    normal, ar = approaches
    assert normal.attrib.get("rnpAr") is None
    assert normal.find("Transition[@name='VIA']") is not None
    assert normal.find("MissedApproachLegs/Leg[@fixIdent='NMHF1']") is not None
    assert ar.attrib["rnpAr"] == "TRUE"
    assert ar.attrib["rnpArMissed"] == "TRUE"
    assert ar.find("Transition") is None
    assert ar.find("MissedApproachLegs/Leg[@fixIdent='ARMAHF']") is not None


def test_iap_chart_roles_leave_ambiguous_plates_unmarked(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "03", 30.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.append(
        TerminalWaypoint("final", "ZBCF", "FINAL", 35.05, 105.0, source, "ZB"),
    )
    primary = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg(
                "R03", "03", "TF", "FINAL", "fixture", sequence=1,
                fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.05, fix_longitude=105.0,
            ),
        ), source,
    )
    model.procedure_segments.append(primary)
    for filename in ("first.pdf", "second.pdf"):
        model.procedure_charts.append(ProcedureChart(
            "ZBCF", filename, 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("FINAL", "MAPT"),),
        ))

    assert _iap_chart_roles(model, primary) == {}

    output = tmp_path / "iap-ambiguous.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    leg = ET.parse(output).getroot().find("Airport/Approach/ApproachLegs/Leg")
    assert leg is not None
    assert "isMAP" not in leg.attrib


def test_bgl_iap_chart_roles_reuses_consensus_ocr_selection():
    model = NavModel(Path("source"))
    primary_source = SourceRef("database.pdf", 1, 1, "database-sha256")
    selected_source = SourceRef(
        "Terminal/ZBCF/selected.pdf", 1, 1, "selected-sha256",
    )
    other_source = SourceRef(
        "Terminal/ZBCF/other.pdf", 1, 1, "other-sha256",
    )
    primary = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FINAL", "fixture", sequence=1),
        ), primary_source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), selected_source,
        ),
        ProcedureChart(
            "ZBCF", "other.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), other_source,
        ),
    ])
    model.iap_ocr_role_evidence = IapOcrRoleEvidence(
        candidate_roles={
            (
                "ZBCF",
                "R03",
                "03",
                "Terminal/ZBCF/selected.pdf",
                "selected-sha256",
            ): frozenset({("FINAL", "MAPT")}),
        },
        report={"accepted": True},
    )

    assert _iap_chart_roles(model, primary) == {"FINAL": {"MAPT"}}


def test_terminal_coordinate_evidence_fills_missing_leg_identity(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "03", 30.0, 10000, 150, "ASP", 1000, source,
    ))
    model.terminal_waypoints.append(
        TerminalWaypoint("point", "ZBCF", "IAF01", 35.1, 105.1, source, "ZB"),
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF", "R03", "进近", "03", "", (
            ChartTerminalLeg("R03", "03", "IF", "IAF01", "fixture"),
        ), source,
    ))

    output = tmp_path / "resolved-leg.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    leg = ET.parse(output).getroot().find("Airport/Approach/ApproachLegs/Leg")
    assert leg is not None
    assert leg.attrib["fixType"] == "TERMINAL_WAYPOINT"
    assert leg.attrib["fixRegion"] == "ZB"
    assert leg.attrib["fixIdent"] == "IAF01"


def test_global_designated_waypoint_fills_cross_airport_procedure_leg(
    tmp_path: Path,
):
    model = NavModel(Path("source"))
    source = SourceRef("DESIGNATED_POINT.csv", 2)
    model.airports["a"] = Airport(
        "a", "ZYBA", "ZYBA", 45.0, 123.0, 500, 18000, 180, source,
    )
    model.runways.append(Runway(
        "r", "a", "07", 60.0, 10000, 150, "ASP", 500, source,
    ))
    model.waypoints.append(
        Waypoint("global", "P105", "P105", 44.81, 123.075, source, "ZY"),
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZYBA", "P105-08A", "进场", "07", "", (
            ChartTerminalLeg("P105-08A", "07", "IF", "P105", "fixture"),
        ), source,
    ))

    output = tmp_path / "global-leg.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    leg = ET.parse(output).getroot().find(
        "Airport/Arrival/RunwayTransitions/RunwayTransitionLegs/Leg",
    )
    assert leg is not None
    assert leg.attrib["fixType"] == "WAYPOINT"
    assert leg.attrib["fixRegion"] == "ZY"
    assert leg.attrib["fixIdent"] == "P105"


def test_reciprocal_runway_ends_become_one_physical_runway(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.extend([
        Runway(
            "primary", "a", "03L", 30.0, 10000, 150, "ASP", 1000,
            source, 35.0, 105.0,
        ),
        Runway(
            "secondary", "a", "21R", 210.0, 10000, 150, "ASP", 1020,
            source, 35.02, 105.02,
        ),
    ])
    model.ilses.extend([
        Ils(
            "ZBCF", "03L", "IPRI", 109.5, "1", 35.0, 105.0, 30.0,
            None, None, None, None, None, None, None, source,
        ),
        Ils(
            "ZBCF", "21R", "ISEC", 110.3, "1", 35.02, 105.02, 210.0,
            None, None, None, None, None, None, None, source,
        ),
        Ils(
            "ZBCF", "03L", "WRONG", 111.1, "1", 45.0, 115.0, 30.0,
            None, None, None, None, None, None, None, source,
        ),
    ])

    output = tmp_path / "runways.xml"
    projection = write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    root = ET.parse(output).getroot()
    runways = root.findall("Airport/Runway")
    assert len(runways) == 1
    assert projection.runways == 1
    assert runways[0].attrib["number"] == "03"
    assert runways[0].attrib["primaryDesignator"] == "L"
    assert runways[0].attrib["secondaryDesignator"] == "R"
    assert "designator" not in runways[0].attrib
    assert 35.0 < float(runways[0].attrib["lat"]) < 35.02
    assert 105.0 < float(runways[0].attrib["lon"]) < 105.02
    assert runways[0].attrib["alt"] == "1010F"
    assert [
        (ils.attrib["ident"], ils.attrib["end"])
        for ils in runways[0].findall("Ils")
    ] == [("IPRI", "PRIMARY"), ("ISEC", "SECONDARY")]


def test_root_terminal_waypoints_are_deduplicated_across_airports(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["one"] = Airport(
        "one", "ZBAA", "ZBAA", 40.0, 116.0, 100, 18000, 180, source,
    )
    model.airports["two"] = Airport(
        "two", "ZBAD", "ZBAD", 39.5, 116.4, 100, 18000, 180, source,
    )
    model.terminal_waypoints.extend([
        TerminalWaypoint("one:fix", "ZBAA", "FIX01", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("two:fix", "ZBAD", "FIX01", 40.2, 116.2, source, "ZB"),
    ])

    output = tmp_path / "ZB_airports.xml"
    projection = write_bglcomp_xml(
        model,
        DEFAULT_CYCLE,
        output,
        scope="airports",
        airport_prefix="ZB",
        duplicate_terminal_waypoints=True,
    )

    root = ET.parse(output).getroot()
    assert len(root.findall("Waypoint")) == 1
    assert len(root.findall("Airport/Waypoint")) == 2
    assert projection.waypoints == 3


def test_airport_terminal_waypoint_collisions_are_renamed_with_all_references(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.terminal_waypoints.extend([
        TerminalWaypoint("first", "ZBCF", "DUP", 35.1, 105.1, source, "ZB"),
        TerminalWaypoint("second", "ZBCF", "DUP", 35.2, 105.2, source, "ZB"),
        TerminalWaypoint("same-second", "ZBCF", "DUP", 35.2, 105.2, source, "ZB"),
    ])
    mapped_leg = ChartTerminalLeg(
        "SID01", "", "CF", "DUP", "fixture",
        sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
        fix_latitude=35.2, fix_longitude=105.2,
        recommended_ident="DUP", recommended_region="ZB",
        recommended_type="WAYPOINT", recommended_latitude=35.2,
        recommended_longitude=105.2, course_degrees=90, distance_nm=1,
    )
    arc_leg = ChartTerminalLeg(
        "SID01", "", "RF", "DUP", "fixture",
        sequence=2, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
        fix_latitude=35.2, fix_longitude=105.2, center_ident="DUP",
        center_region="ZB", center_latitude=35.2, center_longitude=105.2,
        arc_radius_nm=1, course_degrees=90,
    )
    model.procedure_segments.extend([
        ProcedureSegment("ZBCF", "SID01", "departure", "", "", (mapped_leg, arc_leg), source),
        ProcedureSegment("ZBCF", "R03", "approach", "03", "", (mapped_leg,), source),
        ProcedureSegment("ZBCF", "R03", "approach", "03", "TRANS", (mapped_leg,), source),
    ])

    output = tmp_path / "terminal-collisions.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    root = ET.parse(output).getroot()
    point_idents = [
        point.attrib["waypointIdent"] for point in root.findall("Airport/Waypoint")
    ]
    assert point_idents == ["DUP", "DUP001"]
    departure_legs = root.findall("Airport/Departure/CommonRouteLegs/Leg")
    assert departure_legs[0].attrib["fixIdent"] == "DUP001"
    assert departure_legs[0].attrib["recommendedIdent"] == "DUP001"
    assert departure_legs[1].attrib["arcCenterFixIdent"] == "DUP001"
    approach = root.find("Airport/Approach")
    assert approach is not None
    assert approach.attrib["fixIdent"] == "DUP001"
    assert approach.find("Transition").attrib["fixIdent"] == "DUP001"


def test_enroute_projection_normalizes_sdk_identity_and_route_requirements(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.waypoints.extend([
        Waypoint("invalid", "AIWD50/CH", "invalid", 21.521667, 113.533333, source, "ZG"),
        Waypoint("duplicate-one", "DUP", "duplicate", 30.0, 110.0, source, "ZB"),
        Waypoint("duplicate-two", "DUP", "duplicate", 31.0, 111.0, source, "ZB"),
        Waypoint("unicode", "香港", "unicode", 22.31, 113.911667, source, "CN"),
    ])
    model.airway_legs.append(AirwayLeg(
        "A1", 1, "AIWD50/CH", "DUP", source,
        start_latitude=21.521667, start_longitude=113.533333,
        end_latitude=30.0, end_longitude=110.0,
        start_country="ZG", end_country="ZB",
    ))

    output = tmp_path / "enroute.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    waypoints = root.findall("Waypoint")
    assert len([point for point in waypoints if point.attrib["waypointIdent"] == "DUP"]) == 1
    assert root.find("Waypoint[@waypointIdent='AIWD5']") is not None
    unicode_point = next(
        point for point in waypoints if point.attrib["waypointRegion"] == "CN"
    )
    assert unicode_point.attrib["waypointIdent"].startswith("P")
    assert len(unicode_point.attrib["waypointIdent"]) == 8
    next_leg = root.find("Waypoint[@waypointIdent='AIWD5']/Route/Next")
    assert next_leg is not None
    assert next_leg.attrib == {
        "waypointRegion": "ZB",
        "waypointIdent": "DUP",
        "waypointType": "NAMED",
        "altitudeMinimum": "0F",
    }


def test_enroute_projection_uses_named_route_shadows_and_preserves_facilities(
    tmp_path: Path,
):
    model = NavModel(Path("source"))
    source = SourceRef("RTE_SEG.csv", 2)
    model.navaids.extend((
        Navaid(
            "vor", "VOR01", "VOR", "VOR one", 30.0, 110.0,
            113.0, 0.0, 0, "ZH", SourceRef("VOR.csv", 3),
        ),
        Navaid(
            "ndb", "NDB01", "NDB", "NDB one", 31.0, 111.0,
            350.0, 0.0, 0, "ZH", SourceRef("NDB.csv", 4),
        ),
    ))
    model.airway_legs.append(AirwayLeg(
        "A1", 1, "VOR01", "NDB01", source,
        start_latitude=30.0, start_longitude=110.0,
        end_latitude=31.0, end_longitude=111.0,
        start_country="ZH", end_country="ZH",
        start_type="VORDME", end_type="NDB",
    ))

    output = tmp_path / "enroute-types.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="enroute")

    root = ET.parse(output).getroot()
    start = root.find("Waypoint[@waypointIdent='VOR01']")
    end = root.find("Waypoint[@waypointIdent='NDB01']")
    assert start is not None
    assert end is not None
    assert start.attrib["waypointType"] == "NAMED"
    assert end.attrib["waypointType"] == "NAMED"
    assert start.find("Route/Next").attrib["waypointType"] == "NAMED"
    assert end.find("Route/Previous").attrib["waypointType"] == "NAMED"
    assert root.find("Vor[@ident='VOR01']") is not None
    assert root.find("Ndb[@ident='NDB01']") is not None


def test_leg_projection_uses_type_specific_semantic_fields(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF",
        "SID01",
        "departure",
        "",
        "",
        (
            ChartTerminalLeg(
                "SID01", "", "CF", "FIX01", "fixture",
                sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.1, fix_longitude=105.1,
                recommended_ident="VOR01", recommended_region="ZB",
                recommended_type="VOR", theta_degrees=123.4, rho_nm=12.5,
                course_degrees=90, distance_nm=8, center_ident="IGNORED",
                fly_over=False,
            ),
        ),
        source,
    ))

    output = tmp_path / "procedures.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    attributes = ET.parse(output).getroot().find(
        "Airport/Departure/CommonRouteLegs/Leg"
    ).attrib
    assert attributes["theta"] == "123.4"
    assert attributes["rho"] == "12.5N"
    assert attributes["magneticCourse"] == "90"
    assert attributes["distance"] == "8N"
    assert attributes["flyOver"] == "FALSE"
    assert "arcCenterFixIdent" not in attributes


def test_if_leg_does_not_emit_course_or_fly_over(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF",
        "SID01",
        "departure",
        "",
        "",
        (
            ChartTerminalLeg(
                "SID01", "", "IF", "FIX01", "fixture",
                sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.1, fix_longitude=105.1,
                course_degrees=90, fly_over=True,
            ),
        ),
        source,
    ))

    output = tmp_path / "procedures.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    attributes = ET.parse(output).getroot().find(
        "Airport/Departure/CommonRouteLegs/Leg"
    ).attrib
    assert "magneticCourse" not in attributes
    assert "trueCourse" not in attributes
    assert "flyOver" not in attributes


def test_cf_leg_without_source_distance_uses_sdk_zero_distance(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF",
        "SID01",
        "departure",
        "",
        "",
        (
            ChartTerminalLeg(
                "SID01", "", "CF", "FIX01", "fixture",
                sequence=1, fix_region="ZB", fix_type="TERMINAL_WAYPOINT",
                fix_latitude=35.1, fix_longitude=105.1, course_degrees=90,
            ),
        ),
        source,
    ))

    output = tmp_path / "procedures.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    attributes = ET.parse(output).getroot().find(
        "Airport/Departure/CommonRouteLegs/Leg"
    ).attrib
    assert attributes["distance"] == "0N"


def test_cr_leg_without_source_theta_uses_course_fallback(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF",
        "SID01",
        "departure",
        "",
        "",
        (
            ChartTerminalLeg(
                "SID01", "", "CR", "", "fixture",
                sequence=1, course_degrees=236,
                recommended_ident="SEY", recommended_region="ZB",
                recommended_type="VOR",
            ),
        ),
        source,
    ))

    output = tmp_path / "procedures.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    attributes = ET.parse(output).getroot().find(
        "Airport/Departure/CommonRouteLegs/Leg"
    ).attrib
    assert attributes["theta"] == "236"


def test_ca_leg_without_source_altitude_uses_sdk_zero_altitude(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("fixture", 1)
    model.airports["a"] = Airport(
        "a", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.procedure_segments.append(ProcedureSegment(
        "ZBCF",
        "SID01",
        "departure",
        "",
        "",
        (ChartTerminalLeg("SID01", "", "CA", None, "fixture", sequence=1),),
        source,
    ))

    output = tmp_path / "procedures.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, output, scope="airports")

    attributes = ET.parse(output).getroot().find(
        "Airport/Departure/CommonRouteLegs/Leg"
    ).attrib
    assert attributes["altitude1"] == "0F"


def test_missing_compiler_is_reported():
    info = find_compiler(Path("does-not-exist.exe"))
    assert info.path is None


def test_package_tool_project_is_deterministic(tmp_path: Path):
    source = tmp_path / "source.xml"
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    second_source = tmp_path / "ZB_airports.xml"
    second_source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    root = tmp_path / "project"
    project = write_package_project(
        root,
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source, second_source),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
        dependencies=(
            {"name": "navigraph-nav-base", "package_version": "0.1.0"},
            {"name": "navigraph-nav-jepp", "package_version": "2.26.16"},
        ),
    )
    parsed = ET.parse(project).getroot()
    assert parsed.tag == "Project"
    assert parsed.findtext("Packages/Package") == r"PackageDefinitions\test-navdata.xml"
    definition = ET.parse(root / "PackageDefinitions" / "test-navdata.xml").getroot()
    assert definition.findtext("PackageOrderHint") == "CUSTOM_NAVDATA_PATCH"
    dependencies = definition.findall("Dependencies/Dependency")
    assert [item.findtext("Name") for item in dependencies] == [
        "navigraph-nav-base",
        "navigraph-nav-jepp",
    ]
    assert [item.attrib["Version"] for item in dependencies] == ["0.1.0", "2.26.16"]
    assert definition.findtext("ItemSettings/Creator") == "PMDG DFD v2 converter"
    assert definition.findtext("AssetGroups/AssetGroup/Type") == "BGL"
    assert definition.findtext("AssetGroups/AssetGroup/OutputDir") == r"scenery\test-navdata"
    assert (root / "PackageSources" / "NavData" / "source.xml").read_bytes() == source.read_bytes()
    assert (root / "PackageSources" / "NavData" / "ZB_airports.xml").read_bytes() == second_source.read_bytes()


def test_package_tool_stages_project_in_ascii_path(tmp_path: Path, monkeypatch):
    unicode_root = tmp_path / "中文项目"
    source = unicode_root / "source.xml"
    source.parent.mkdir()
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    project = write_package_project(
        unicode_root / "project",
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )

    def fake_run(command, **kwargs):
        staged_project = Path(command[1])
        assert str(staged_project).isascii()
        package = staged_project.parent / "Packages" / "test-navdata"
        package.mkdir(parents=True)
        for name in ("manifest.json", "layout.json", "bglIndex.bout"):
            (package / name).write_bytes(b"x")
        bgl = package / "scenery" / "test-navdata" / "source.bgl"
        bgl.parent.mkdir(parents=True)
        bgl.write_bytes(b"bgl")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("fenix_default_navdata.bgl.subprocess.run", fake_run)
    monkeypatch.setattr("fenix_default_navdata.bgl._simulator_pids", lambda: set())
    report = compile_package(
        project,
        CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test"),
        package_name="test-navdata",
    )
    package_root = Path(report["package_root"])
    assert package_root.is_dir()
    assert (package_root / "bglIndex.bout").read_bytes() == b"x"
    assert list(package_root.rglob("*.bgl"))


def test_package_tool_retries_one_startup_failure_without_simulator_process(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.xml"
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    project = write_package_project(
        tmp_path / "project",
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 1, "", "")
        staged_project = Path(command[1])
        package = staged_project.parent / "Packages" / "test-navdata"
        package.mkdir(parents=True)
        for name in ("manifest.json", "layout.json", "bglIndex.bout"):
            (package / name).write_bytes(b"x")
        bgl = package / "scenery" / "test-navdata" / "source.bgl"
        bgl.parent.mkdir(parents=True)
        bgl.write_bytes(b"bgl")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("fenix_default_navdata.bgl.subprocess.run", fake_run)
    monkeypatch.setattr("fenix_default_navdata.bgl._simulator_pids", lambda: set())
    monkeypatch.setattr(
        "fenix_default_navdata.bgl._wait_for_package_tool_process",
        lambda previous_pids, **kwargs: PackageToolProcessTrace(
            simulator_started=False,
            simulator_completed=False,
            launched_pids=(),
            observations=(),
            elapsed_seconds=0.0,
        ),
    )
    report = compile_package(
        project,
        CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test"),
        package_name="test-navdata",
    )

    assert len(calls) == 2
    assert [attempt["returncode"] for attempt in report["attempts"]] == [1, 0]
    assert [attempt["simulator_started"] for attempt in report["attempts"]] == [False, False]


def test_package_tool_keeps_failed_ascii_stage_with_short_async_process_trace(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source.xml"
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    project = write_package_project(
        tmp_path / "project",
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    app_data = tmp_path / "appdata"
    builder_log = app_data / "Microsoft Flight Simulator 2024" / "BuilderLogError.txt"
    builder_log.parent.mkdir(parents=True)
    builder_log.write_text("before\n", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(app_data))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        builder_log.write_text("before\nafter\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 1, "", "")

    pid_samples = iter((set(), set(), {4242}, set()))

    def fake_pids():
        return next(pid_samples, set())

    monkeypatch.setattr("fenix_default_navdata.bgl.subprocess.run", fake_run)
    monkeypatch.setattr("fenix_default_navdata.bgl._simulator_pids", fake_pids)
    try:
        compile_package(
            project,
            CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test"),
            package_name="test-navdata",
        )
    except RuntimeError as error:
        message = str(error)
    else:
        raise AssertionError("缺失 SDK 产物时必须失败")

    stage_parent = (
        tmp_path
        / "localappdata"
        / "default_navdata_converter"
        / "sdk-builds"
    )
    stages = list(stage_parent.iterdir())
    assert len(calls) == 1
    assert len(stages) == 1
    assert "诊断目录=" in message
    assert (stages[0] / "package-tool-diagnostics.json").is_file()
    assert (stages[0] / "attempt-01-BuilderLogError.txt").read_text(
        encoding="utf-8"
    ) == "after\n"
