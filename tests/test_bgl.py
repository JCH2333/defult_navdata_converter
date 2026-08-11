import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from fenix_default_navdata.bgl import (
    CompilerInfo,
    compile_package,
    find_compiler,
    write_bglcomp_xml,
    write_package_project,
)
from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    ChartTerminalLeg,
    Ils,
    NavModel,
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


def test_enroute_projection_preserves_route_endpoint_types(tmp_path: Path):
    model = NavModel(Path("source"))
    source = SourceRef("RTE_SEG.csv", 2)
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
    assert start.attrib["waypointType"] == "VOR"
    assert end.attrib["waypointType"] == "NDB"
    assert start.find("Route/Next").attrib["waypointType"] == "NDB"
    assert end.find("Route/Previous").attrib["waypointType"] == "VOR"


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
        dependencies=("navigraph-nav-base", "navigraph-nav-jepp"),
    )
    parsed = ET.parse(project).getroot()
    assert parsed.tag == "Project"
    assert parsed.findtext("Packages/Package") == r"PackageDefinitions\test-navdata.xml"
    definition = ET.parse(root / "PackageDefinitions" / "test-navdata.xml").getroot()
    assert definition.findtext("PackageOrderHint") == "CUSTOM_NAVDATA_PATCH"
    assert [
        item.findtext("Name")
        for item in definition.findall("Dependencies/Dependency")
    ] == ["navigraph-nav-base", "navigraph-nav-jepp"]
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
