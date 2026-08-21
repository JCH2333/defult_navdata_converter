from pathlib import Path
import hashlib
import json

import pytest

from fenix_default_navdata.source import (
    _load_general_document_airway_minimum_altitudes,
    _load_terminal_landing_aids,
    _promote_shared_terminal_coordinate_waypoints,
    _project_same_page_rnp_primary_to_ils,
    _retain_database_referenced_terminal_waypoints,
    _surface,
    audit_enroute_navaid_ocr_source,
    load_naip,
    navaid_country,
    summarize_airway_source_metadata,
    waypoint_country,
)
from fenix_default_navdata.general_docs import (
    ENROUTE_AIRWAY_MINIMUM_ALTITUDE_DOCUMENTS,
    ENROUTE_KEY_POINT_DOCUMENT,
    ENROUTE_NAVAID_DOCUMENT,
)
from fenix_default_navdata.model import (
    Ad219Vor,
    AirwayLeg,
    ChartRouteFix,
    ChartStandardProcedureRoute,
    ChartTerminalLeg,
    NavModel,
    Navaid,
    ProcedureChart,
    ProcedureSegment,
    SourceRef,
    TerminalWaypoint,
    Waypoint,
)
from fenix_default_navdata.iap_coverage import analyze_iap_coverage


def test_general_document_airway_minimum_altitude_projects_only_unique_424_leg(
    tmp_path: Path,
) -> None:
    document = next(
        value
        for value, prefix in ENROUTE_AIRWAY_MINIMUM_ALTITUDE_DOCUMENTS.items()
        if prefix == "H"
    )
    root = tmp_path / "raw"
    source_pdf = root / document
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"source-pdf")
    cache = tmp_path / "general-doc-cache" / "enr-3.2.4-h"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": document,
        "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": "\n".join((
            "H2[[83, 218, 111, 231]]",
            "HFE[[83, 236, 156, 250]]",
            'N31°46\'34"E117°18\'01"[[471, 236, 626, 250]]',
            "1200[[392, 262, 435, 279]]",
            "VILID[[83, 293, 156, 308]]",
            'N31°33\'27"E117°17\'23"[[471, 293, 626, 308]]',
        ))}]},
    }), encoding="utf-8")
    model = NavModel(root=root)
    model.airway_legs.append(AirwayLeg(
        "H2",
        1,
        "HFE",
        "VILID",
        SourceRef("RTE_SEG.csv", 2),
    ))

    _load_general_document_airway_minimum_altitudes(
        model,
        cache.parent,
        cache_directories=(cache.name,),
    )

    assert model.airway_legs[0].minimum_altitude_ft == 3937
    assert [
        (
            item.airway,
            item.start_ident,
            item.end_ident,
            item.minimum_altitude_meters,
        )
        for item in model.enroute_airway_minimum_altitude_evidence
    ] == [("H2", "HFE", "VILID", 1200)]
    assert model.general_document_evidence["airway_minimum_altitudes"] == {
        "available": True,
        "documents": [{
            "available": True,
            "cache": str(cache),
            "document": document,
            "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
            "pages": 1,
            "route_prefix": "H",
            "parsed_records": 1,
            "cache_directory": "enr-3.2.4-h",
        }],
        "parsed_records": 1,
        "projected": 1,
        "already_projected": 0,
        "direct_424_leg_missing": 0,
        "direct_424_leg_ambiguous": 0,
        "direct_424_conflict": 0,
        "conflicting_evidence": 0,
        "unavailable_cache": 0,
    }


def test_load_naip_keeps_ad219_vor_evidence_separate_from_direct_vor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    airport_directory = root / "Terminal" / "ZBCF"
    airport_directory.mkdir(parents=True)
    (airport_directory / "Charts.csv").write_text("", encoding="utf-8")
    source_pdf = airport_directory / "airport.pdf"
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "vor,DMX,VOR,N350000,E1050000,113.1,-2.0,100,M,ZBCF,",
    )))
    evidence = Ad219Vor(
        "ZBCF", "DMX", 113.1, 35.0, 105.0, 123.4,
        SourceRef(str(source_pdf), 14, 14, "hash"),
    )
    monkeypatch.setattr(
        "fenix_default_navdata.source.extract_airport_ad219_landing_aids",
        lambda _: ([], [evidence]),
    )

    model = load_naip(root)

    navaid = next(item for item in model.navaids if item.ident == "DMX")
    assert navaid.elevation_ft == 328
    assert model.ad219_vors == [
        Ad219Vor(
            "ZBCF", "DMX", 113.1, 35.0, 105.0, 123.4,
            SourceRef("Terminal/ZBCF/airport.pdf", 14, 14, "hash"),
        ),
    ]


def _write_csv(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


def test_promotes_shared_terminal_coordinate_waypoint_to_global_model() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("one", "ZBAA", "SHARED", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("two", "ZBAD", "SHARED", 40.1, 116.1, source, "ZB"),
    ))

    _promote_shared_terminal_coordinate_waypoints(model)

    assert [
        (point.key, point.ident, point.country, point.latitude, point.longitude)
        for point in model.waypoints
    ] == [
        ("terminal-coordinate:ZB:SHARED", "SHARED", "ZB", 40.1, 116.1),
    ]
    assert model.terminal_coordinate_waypoint_promotion == {
        "source": "Terminal/*/Charts.csv coordinate pages",
        "coordinate_points": 2,
        "identity_groups": 1,
        "promoted": 1,
        "rejected": {
            "empty_identifier": 0,
            "identifier_variants": 0,
            "identifier_too_long": 0,
            "multiple_coordinates": 0,
            "single_airport": 0,
            "existing_global_identity": 0,
        },
    }


def test_shared_terminal_coordinate_waypoint_requires_two_airports() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("one", "ZBAA", "LOCAL", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("two", "ZBAA", "LOCAL", 40.1, 116.1, source, "ZB"),
    ))

    _promote_shared_terminal_coordinate_waypoints(model)

    assert model.waypoints == []
    assert model.terminal_coordinate_waypoint_promotion["rejected"][
        "single_airport"
    ] == 1


def test_shared_terminal_coordinate_waypoint_rejects_coordinate_conflicts() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("one", "ZBAA", "AMBIG", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("two", "ZBAD", "AMBIG", 40.2, 116.1, source, "ZB"),
    ))

    _promote_shared_terminal_coordinate_waypoints(model)

    assert model.waypoints == []
    assert model.terminal_coordinate_waypoint_promotion["rejected"][
        "multiple_coordinates"
    ] == 1


def test_direct_iap_role_alone_does_not_retain_terminal_coordinate_waypoint() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("keep", "ZBAA", "FAF01", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("vector", "ZBAA", "VECTOR", 40.2, 116.2, source, "ZB"),
        TerminalWaypoint("unused", "ZBAA", "UNUSED", 40.3, 116.3, source, "ZB"),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZBAA", "ZBAA-approach.pdf", 1, "instrument-approach-index",
        "RNP RWY01", "text", (), ("01",), (), (), (), source,
        route_fixes=(
            ChartRouteFix("FAF01", "FAF"),
            ChartRouteFix("VECTOR", "VECTOR"),
        ),
    ))

    _retain_database_referenced_terminal_waypoints(model)

    assert model.terminal_waypoints == []


def test_projects_same_page_rnp_primary_to_ils_without_rnp_missed_legs() -> None:
    model = NavModel(Path("raw"))
    database_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "database-hash",
    )
    ils_chart_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02", "approach", "02", "", (
                ChartTerminalLeg(
                    "R02", "02", "IF", "LJ601", "fixture",
                    procedure_kind="approach", approach_family="RNP",
                ),
                ChartTerminalLeg(
                    "R02", "02", "TF", "RW02", "fixture",
                    procedure_kind="approach", approach_family="RNP",
                ),
            ),
            database_source,
        ),
        ProcedureSegment(
            "ZPLJ", "R02", "missed", "02", "", (
                ChartTerminalLeg(
                    "R02", "02", "DF", "RNPMA", "fixture",
                    procedure_kind="missed", approach_family="RNP",
                ),
            ), database_source, approach_family="RNP",
        ),
        ProcedureSegment(
            "ZPLJ", "I02", "missed", "02", "", (
                ChartTerminalLeg(
                    "I02", "02", "DF", "ILSMA", "fixture",
                    procedure_kind="missed", approach_family="ILS",
                ),
            ), database_source, approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
        ils_chart_source,
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z03.pdf", 1, "instrument-approach-index",
        "ILS/DME y RWY02", "text", (), ("02",), (), (), (),
        SourceRef("Terminal/ZPLJ/ZPLJ-5Z03.pdf", 1, 1, "ils-y-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    projected = [
        segment
        for segment in model.procedure_segments
        if segment.label == "I02" and segment.kind == "approach"
    ]
    assert len(projected) == 1
    assert projected[0].approach_family == "ILS"
    assert [leg.fix_ident for leg in projected[0].legs] == ["LJ601", "RW02"]
    assert all(leg.procedure_label == "I02" for leg in projected[0].legs)
    assert all(leg.approach_family == "ILS" for leg in projected[0].legs)
    assert "RNPMA" not in [leg.fix_ident for leg in projected[0].legs]
    assert model.shared_ils_primary_projections == [{
        "airport": "ZPLJ",
        "label": "I02",
        "runway": "02",
        "selection": "same_database_page_unique_rnp_primary",
        "rnp_label": "R02",
        "rnp_approach_family": "implicit_rnp_label",
        "primary_legs": 2,
        "database_source": {
            "file": "Terminal/ZPLJ/ZPLJ-0C-04.pdf",
            "row": 1,
            "page": 1,
            "sha256": "database-hash",
        },
        "ils_missed_source": {
            "file": "Terminal/ZPLJ/ZPLJ-0C-04.pdf",
            "row": 1,
            "page": 1,
            "sha256": "database-hash",
        },
        "chart_name": "RNP ILS/DME z RWY02",
        "chart_source": {
            "file": "Terminal/ZPLJ/ZPLJ-5Z02.pdf",
            "row": 1,
            "page": 1,
            "sha256": "ils-chart-hash",
        },
    }]
    report = analyze_iap_coverage(model)
    assert report["shared_ils_primary_projection_count"] == 1
    assert report["unresolved_groups"] == []


def test_projects_same_page_rnp_primary_to_ils_from_rnav_ils_title_support() -> None:
    model = NavModel(Path("raw"))
    database_source = SourceRef(
        "Terminal/ZSNJ/ZSNJ-4L.pdf", 1, 1, "database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZSNJ", "R07", "approach", "07", "", (
                ChartTerminalLeg("R07", "07", "IF", "NJ106", "fixture"),
                ChartTerminalLeg("R07", "07", "TF", "RW07", "fixture"),
            ),
            database_source,
        ),
        ProcedureSegment(
            "ZSNJ", "R07", "missed", "07", "", (
                ChartTerminalLeg("R07", "07", "DF", "RNPMA", "fixture"),
            ),
            database_source,
            approach_family="RNP",
        ),
        ProcedureSegment(
            "ZSNJ", "I07", "missed", "07", "", (
                ChartTerminalLeg("I07", "07", "DF", "ILSMA", "fixture"),
            ),
            database_source,
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.extend((
        ProcedureChart(
            "ZSNJ", "ZSNJ-5C.pdf", 1, "instrument-approach-index",
            "RNAV ILS/DME z RWY07", "text", (), ("07",), (), (), (),
            SourceRef("Terminal/ZSNJ/ZSNJ-5C.pdf", 1, 1, "ils-z-hash"),
        ),
        ProcedureChart(
            "ZSNJ", "ZSNJ-5J.pdf", 1, "instrument-approach-index",
            "RNAV CAT-II ILS/DME x RWY07", "text", (), ("07",), (), (), (),
            SourceRef("Terminal/ZSNJ/ZSNJ-5J.pdf", 1, 1, "ils-x-hash"),
        ),
        ProcedureChart(
            "ZSNJ", "ZSNJ-5D.pdf", 1, "instrument-approach-index",
            "ILS/DME y RWY07", "text", (), ("07",), (), (), (),
            SourceRef("Terminal/ZSNJ/ZSNJ-5D.pdf", 1, 1, "ils-y-hash"),
        ),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    projected = [
        segment
        for segment in model.procedure_segments
        if segment.label == "I07" and segment.kind == "approach"
    ]
    assert len(projected) == 1
    assert [leg.fix_ident for leg in projected[0].legs] == ["NJ106", "RW07"]
    assert model.shared_ils_primary_projections == [{
        "airport": "ZSNJ",
        "label": "I07",
        "runway": "07",
        "selection": (
            "same_database_page_unique_rnp_primary_with_rnav_ils_support"
        ),
        "rnp_label": "R07",
        "rnp_approach_family": "implicit_rnp_label",
        "primary_legs": 2,
        "database_source": {
            "file": "Terminal/ZSNJ/ZSNJ-4L.pdf",
            "row": 1,
            "page": 1,
            "sha256": "database-hash",
        },
        "ils_missed_source": {
            "file": "Terminal/ZSNJ/ZSNJ-4L.pdf",
            "row": 1,
            "page": 1,
            "sha256": "database-hash",
        },
        "chart_names": [
            "RNAV CAT-II ILS/DME x RWY07",
            "RNAV ILS/DME z RWY07",
        ],
        "chart_sources": [
            {
                "file": "Terminal/ZSNJ/ZSNJ-5J.pdf",
                "row": 1,
                "page": 1,
                "sha256": "ils-x-hash",
            },
            {
                "file": "Terminal/ZSNJ/ZSNJ-5C.pdf",
                "row": 1,
                "page": 1,
                "sha256": "ils-z-hash",
            },
        ],
    }]


def test_rnav_ils_title_does_not_project_cross_page_rnp_primary() -> None:
    model = NavModel(Path("raw"))
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZSNJ", "R25", "approach", "25", "", (
                ChartTerminalLeg("R25", "25", "IF", "NJ206", "fixture"),
            ),
            SourceRef("Terminal/ZSNJ/ZSNJ-4N.pdf", 1, 1, "rnp-hash"),
        ),
        ProcedureSegment(
            "ZSNJ", "I25", "missed", "25", "", (
                ChartTerminalLeg("I25", "25", "DF", "NJ216", "fixture"),
            ),
            SourceRef("Terminal/ZSNJ/ZSNJ-4P.pdf", 1, 1, "ils-hash"),
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZSNJ", "ZSNJ-5G.pdf", 1, "instrument-approach-index",
        "RNAV ILS/DME z RWY25", "text", (), ("25",), (), (), (),
        SourceRef("Terminal/ZSNJ/ZSNJ-5G.pdf", 1, 1, "chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    assert [
        segment
        for segment in model.procedure_segments
        if segment.label == "I25" and segment.kind == "approach"
    ] == []
    assert model.shared_ils_primary_projections == []


def test_projects_same_page_ils_suffix_from_unique_combined_rnp_candidate() -> None:
    model = NavModel(Path("raw"))
    database_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02", "approach", "02", "", (
                ChartTerminalLeg("R02", "02", "IF", "LJ601", "fixture"),
                ChartTerminalLeg("R02", "02", "TF", "RW02", "fixture"),
            ),
            database_source,
        ),
        ProcedureSegment(
            "ZPLJ", "I02-Z", "missed", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "DF", "ILSMA", "fixture"),
            ),
            database_source,
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
        SourceRef("Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    projected = [
        segment
        for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ]
    assert len(projected) == 1
    assert projected[0].approach_family == "ILS"
    assert [leg.fix_ident for leg in projected[0].legs] == ["LJ601", "RW02"]
    assert model.shared_ils_primary_projections[0]["rnp_label"] == "R02"


def test_projects_same_page_ils_lettered_runway_suffix_from_combined_title() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef(
        "Terminal/ZYQQ/ZYQQ-0C-05.pdf", 1, 1, "database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZYQQ", "R17L", "approach", "17L", "", (
                ChartTerminalLeg("R17L", "17L", "IF", "QQ601", "fixture"),
                ChartTerminalLeg("R17L", "17L", "TF", "RW17L", "fixture"),
            ),
            source,
        ),
        ProcedureSegment(
            "ZYQQ", "I17L-Z", "missed", "17L", "", (
                ChartTerminalLeg(
                    "I17L-Z", "17L", "DF", "ILSMA", "fixture",
                ),
            ),
            source,
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZYQQ", "ZYQQ-5L-1.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY17L", "text", (), ("17L",), (), (), (),
        SourceRef("Terminal/ZYQQ/ZYQQ-5L-1.pdf", 1, 1, "ils-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    projected = [
        segment
        for segment in model.procedure_segments
        if segment.label == "I17L-Z" and segment.kind == "approach"
    ]
    assert len(projected) == 1
    assert [leg.fix_ident for leg in projected[0].legs] == ["QQ601", "RW17L"]
    assert model.shared_ils_primary_projections[0]["rnp_label"] == "R17L"


def test_projects_cross_page_unique_combined_rnp_primary_to_ils() -> None:
    model = NavModel(Path("raw"))
    rnp_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-03.pdf", 1, 1, "rnp-database-hash",
    )
    ils_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "ils-database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02", "approach", "02", "", (
                ChartTerminalLeg("R02", "02", "IF", "LJ601", "fixture"),
                ChartTerminalLeg("R02", "02", "TF", "RW02", "fixture"),
            ),
            rnp_source,
        ),
        ProcedureSegment(
            "ZPLJ", "I02-Z", "missed", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "DF", "ILSMA", "fixture"),
            ),
            ils_source,
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
        SourceRef("Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    projected = [
        segment
        for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ]
    assert len(projected) == 1
    assert [leg.fix_ident for leg in projected[0].legs] == ["LJ601", "RW02"]
    assert model.shared_ils_primary_projections[0]["selection"] == (
        "cross_database_page_unique_rnp_primary"
    )


def test_same_page_ils_suffix_rejects_multiple_combined_rnp_candidates() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "database-hash")
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02", "approach", "02", "", (
                ChartTerminalLeg("R02", "02", "TF", "RW02", "fixture"),
            ),
            source,
        ),
        ProcedureSegment(
            "ZPLJ", "R02-Z", "approach", "02", "", (
                ChartTerminalLeg("R02-Z", "02", "TF", "RW02Z", "fixture"),
            ),
            source,
        ),
        ProcedureSegment(
            "ZPLJ", "I02-Z", "missed", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "DF", "ILSMA", "fixture"),
            ),
            source,
            approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
        SourceRef("Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    assert [
        segment
        for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ] == []
    assert model.shared_ils_primary_projections == []


@pytest.mark.parametrize(
    ("add_second_rnp", "add_ils_chart", "add_ils_primary"),
    (
        (
            True,
            True,
            False,
        ),
        (
            False,
            False,
            False,
        ),
        (
            False,
            True,
            True,
        ),
    ),
)
def test_same_page_rnp_primary_to_ils_rejects_nonunique_or_incomplete_evidence(
    add_second_rnp: bool,
    add_ils_chart: bool,
    add_ils_primary: bool,
) -> None:
    model = NavModel(Path("raw"))
    ils_source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02-Z", "approach", "02", "", (
                ChartTerminalLeg("R02-Z", "02", "TF", "RW02", "fixture"),
            ), ils_source, approach_family="RNP",
        ),
        ProcedureSegment(
            "ZPLJ", "I02-Z", "missed", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "DF", "ILSMA", "fixture"),
            ), ils_source, approach_family="ILS",
        ),
    ))
    if add_second_rnp:
        model.procedure_segments.append(ProcedureSegment(
            "ZPLJ", "R02-Z", "approach", "02", "", (
                ChartTerminalLeg("R02-Z", "02", "TF", "RW02B", "fixture"),
            ), ils_source, approach_family="RNP",
        ))
    if add_ils_primary:
        model.procedure_segments.append(ProcedureSegment(
            "ZPLJ", "I02-Z", "approach", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "TF", "RW02", "fixture"),
            ), ils_source, approach_family="ILS",
        ))
    if add_ils_chart:
        model.procedure_charts.append(ProcedureChart(
            "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
            "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
            SourceRef("Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash"),
        ))

    existing_ils_primaries = [
        segment for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ]
    _project_same_page_rnp_primary_to_ils(model)

    assert [
        segment for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ] == existing_ils_primaries
    assert model.shared_ils_primary_projections == []


def test_same_page_rnp_primary_to_ils_rejects_explicit_rnp_ar_primary() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef(
        "Terminal/ZPLJ/ZPLJ-0C-04.pdf", 1, 1, "database-hash",
    )
    model.procedure_segments.extend((
        ProcedureSegment(
            "ZPLJ", "R02-Z", "approach", "02", "", (
                ChartTerminalLeg("R02-Z", "02", "TF", "RW02", "fixture"),
            ), source, approach_family="RNP_AR",
        ),
        ProcedureSegment(
            "ZPLJ", "I02-Z", "missed", "02", "", (
                ChartTerminalLeg("I02-Z", "02", "DF", "ILSMA", "fixture"),
            ), source, approach_family="ILS",
        ),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZPLJ", "ZPLJ-5Z02.pdf", 1, "instrument-approach-index",
        "RNP ILS/DME z RWY02", "text", (), ("02",), (), (), (),
        SourceRef("Terminal/ZPLJ/ZPLJ-5Z02.pdf", 1, 1, "ils-chart-hash"),
    ))

    _project_same_page_rnp_primary_to_ils(model)

    assert [
        segment for segment in model.procedure_segments
        if segment.label == "I02-Z" and segment.kind == "approach"
    ] == []
    assert model.shared_ils_primary_projections == []
def test_standard_route_table_retains_matching_terminal_coordinate_waypoint() -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("route", "ZBAA", "ROUTE01", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("unused", "ZBAA", "UNUSED", 40.2, 116.2, source, "ZB"),
    ))
    model.procedure_charts.append(ProcedureChart(
        "ZBAA", "ZBAA-2P-1.pdf", 1, "standard-terminal-procedure",
        "标准仪表离场图", "text", (), (), (), (), (), source,
        standard_routes=(
            ChartStandardProcedureRoute(
                "ROUTE01-01", "ROUTE011", ("ROUTE01", "GLOBAL01"),
            ),
        ),
    ))

    _retain_database_referenced_terminal_waypoints(model)

    assert [point.ident for point in model.terminal_waypoints] == ["ROUTE01"]


@pytest.mark.parametrize("kind", ("waypoint", "navaid"))
def test_shared_terminal_coordinate_waypoint_keeps_existing_global_identity(
    kind: str,
) -> None:
    model = NavModel(Path("raw"))
    source = SourceRef("Terminal/ZBAA/Charts.csv", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("one", "ZBAA", "OCCUPIED", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("two", "ZBAD", "OCCUPIED", 40.1, 116.1, source, "ZB"),
    ))
    if kind == "waypoint":
        model.waypoints.append(Waypoint(
            "existing", "OCCUPIED", "OCCUPIED", 35.0, 105.0, source, "ZB",
        ))
    else:
        model.navaids.append(Navaid(
            "existing", "OCCUPIED", "VOR", "OCCUPIED", 35.0, 105.0, 113.1,
            0.0, 0, "ZB", source,
        ))

    _promote_shared_terminal_coordinate_waypoints(model)

    assert len(model.waypoints) == (1 if kind == "waypoint" else 0)
    assert model.terminal_coordinate_waypoint_promotion["rejected"][
        "existing_global_identity"
    ] == 1


def _minimal_naip_root(tmp_path: Path, composition: str, *, include_second_airport: bool = False) -> Path:
    root = tmp_path / "raw"
    root.mkdir()
    airports = [
        "AD_HP_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_ELEV,VAL_MAG_VAR,VAL_TRANSITION_ALT,VAL_TRANSITION_LEVEL",
        "airport,ZBCF,TEST,N350000.00,E1050000.00,100,-9.1,5486,5486",
    ]
    runways = [
        "RWY_ID,AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION",
        f"runway,airport,3048,45,{composition}",
    ]
    runway_directions = [
        "RWY_DIRECTION_ID,RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV",
        "end03,runway,03,30,100",
        "end21,runway,21,210,100",
    ]
    if include_second_airport:
        airports.append("airport-two,ZGAA,SECOND,N230000.00,E1130000.00,20,-5.0,5486,5486")
        runways.append(f"runway-two,airport-two,1828.8,30,{composition}")
        runway_directions.append("end09,runway-two,09,90,20")
    _write_csv(root, "AD_HP.csv", "\n".join(airports))
    _write_csv(root, "RWY.csv", "\n".join(runways))
    _write_csv(root, "RWY_DIRECTION.csv", "\n".join(runway_directions))
    for name, header in (
        ("VOR.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR"),
        ("NDB.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR"),
        ("DESIGNATED_POINT.csv", "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR"),
        ("RTE_SEG.csv", "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END"),
    ):
        _write_csv(root, name, header)
    return root


def test_load_naip_preserves_airport_magnetic_variation(tmp_path: Path) -> None:
    model = load_naip(_minimal_naip_root(tmp_path, "ASP"))

    assert model.airports["airport"].magnetic_variation == -9.1


@pytest.mark.parametrize(("composition", "expected"), (
    ("\u6c34\u6ce5\u6df7\u51dd\u571f", "CON"),
    ("\u6ca5\u9752", "ASP"),
    ("\u6c34\u6ce5\u6df7\u51dd\u571f/\u6ca5\u9752", "CON"),
    ("\u6ca5\u9752/\u6c34\u6ce5\u6df7\u51dd\u571f", "ASP"),
    ("GRASS", "GRE"),
    ("WATER", "WAT"),
))
def test_surface_retains_first_expressible_source_component(composition: str, expected: str) -> None:
    assert _surface(composition) == expected


def test_navaid_country_prefers_single_source_fir_when_airport_conflicts() -> None:
    assert navaid_country("ZBES", "沈阳情报区") == "ZY"


def test_navaid_country_uses_serviced_airport_for_multi_fir_boundary() -> None:
    assert navaid_country("ZSAA", "武汉情报区，上海情报区") == "ZS"


def test_navaid_country_uses_serviced_airport_when_fir_is_blank() -> None:
    assert navaid_country("ZBES", "") == "ZB"


def test_navaid_country_rejects_cross_region_fir_without_serviced_airport() -> None:
    with pytest.raises(ValueError, match="ambiguous navaid FIR"):
        navaid_country("", "武汉情报区，上海情报区")


def test_waypoint_country_keeps_primary_source_fir_for_multi_fir_point() -> None:
    assert waypoint_country("武汉情报区，上海情报区") == "ZH"


def test_waypoint_country_prefers_valid_serviced_airport_over_fir() -> None:
    assert waypoint_country("北京情报区", ident="FIX", serviced_airport="ZGAA") == "ZG"


def test_load_naip_derives_runway_end_coordinates_from_airport_reference(tmp_path: Path) -> None:
    model = load_naip(
        _minimal_naip_root(tmp_path, "\u6c34\u6ce5\u6df7\u51dd\u571f"),
        include_terminal_documents=False,
    )

    runway_03, runway_21 = model.runways
    assert runway_03.surface == "CON"
    assert runway_21.surface == "CON"
    assert runway_03.latitude is not None and runway_03.longitude is not None
    assert runway_21.latitude is not None and runway_21.longitude is not None
    assert runway_03.latitude < 35.0 < runway_21.latitude
    assert runway_03.longitude < 105.0 < runway_21.longitude
    assert (runway_03.latitude + runway_21.latitude) / 2 == pytest.approx(35.0, abs=0.00001)
    assert (runway_03.longitude + runway_21.longitude) / 2 == pytest.approx(105.0, abs=0.00001)


def test_ad219_vor_evidence_is_not_promoted_to_a_navaid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "raw"
    airport_directory = root / "Terminal" / "ZBCF"
    airport_directory.mkdir(parents=True)
    source_pdf = airport_directory / "airport.pdf"
    evidence = Ad219Vor(
        "ZBCF", "CZW", 111.2, 36.276556, 113.130778, 942.0,
        SourceRef(str(source_pdf), 14, 14, "hash"),
    )
    monkeypatch.setattr(
        "fenix_default_navdata.source.extract_airport_ad219_landing_aids",
        lambda _: ([], [evidence]),
    )
    model = NavModel(root)

    _load_terminal_landing_aids(model)

    assert model.navaids == []
    assert model.ad219_vors == [
        Ad219Vor(
            "ZBCF", "CZW", 111.2, 36.276556, 113.130778, 942.0,
            SourceRef("Terminal/ZBCF/airport.pdf", 14, 14, "hash"),
        ),
    ]


def test_load_naip_retains_each_runways_own_airport_key(tmp_path: Path) -> None:
    model = load_naip(
        _minimal_naip_root(tmp_path, "\u6ca5\u9752", include_second_airport=True),
        include_terminal_documents=False,
    )

    assert [(runway.ident, runway.airport_key) for runway in model.runways] == [
        ("03", "airport"),
        ("21", "airport"),
        ("09", "airport-two"),
    ]


def test_load_naip_converts_vor_elevation_meters_and_keeps_raw_navaid_name(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "kns,KNS,喀纳斯,N481315,E0870030,111.2,-5.2,1200,M,ZWKN,乌鲁木齐情报区",
        "cka,CKA,茶卡,N364653,E0990656,115.9,-7.0,3146,,,兰州情报区",
    )))
    _write_csv(root, "NDB.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "dm,DM,泽当,N291522,E0914551,435,-0.5,,,,昆明情报区",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert [(item.kind, item.ident, item.name, item.elevation_ft) for item in model.navaids] == [
        ("VOR", "KNS", "喀纳斯", 3937),
        ("VOR", "CKA", "茶卡", 10322),
        ("NDB", "DM", "泽当", 0),
    ]


def test_load_naip_retains_raw_navaid_selection_attributes(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,CODE_IN_AIRWAY,PURPOSE,IS_REP_ATC,ROUTE_RESTRICT,IS_TRANS_POINT,IS_BORDER_POINT,SERVICED_AIRPORT,CODE_FIR",
        "vor,VOR1,VOR,N230000,E1130000,113.1,-2,0,Y,AE,Y,Y,N,Y,ZGAA,广州情报区",
    )))

    model = load_naip(root, include_terminal_documents=False)

    navaid = next(item for item in model.navaids if item.ident == "VOR1")
    assert (
        navaid.code_in_airway,
        navaid.purpose,
        navaid.is_rep_atc,
        navaid.route_restrict,
        navaid.is_trans_point,
        navaid.is_border_point,
        navaid.serviced_airport,
        navaid.code_fir,
    ) == ("Y", "AE", "Y", "Y", "N", "Y", "ZGAA", "广州情报区")


def test_load_naip_recovers_blank_route_endpoint_firs_from_matching_424_records(tmp_path: Path) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "point,DP01,DESIGNATED,N350000,E1050000,北京情报区",
        "nofir,NOFIR,UNRESOLVED,N360000,E1060000,",
    )))
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "vor,VOR1,VOR,N230000,E1130000,113.1,0,0,ZGAA,广州情报区",
    )))
    _write_csv(root, "NDB.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "ndb,NDB1,NDB,N290000,E0910000,350,0,0,ZULS,昆明情报区",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END",
        "R1,1,DP01,VOR1,N350000,E1050000,N230000,E1130000,,,B,L,DESIGNATED_POINT,VORDME",
        "R2,2,NDB1,DP01,N290000,E0910000,N350000,E1050000,,,B,L,NDB,地名点",
        "R3,3,DP01,NOFIR,N350000,E1050000,N360000,E1060000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [
        ("ZB", "ZG"),
        ("ZP", "ZB"),
        ("ZB", "ZB"),
    ]
    assert next(point.country for point in model.waypoints if point.ident == "NOFIR") == "ZB"


def test_load_naip_recovers_blank_waypoint_region_from_unambiguous_source_acc(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
        "beijing,FIR,ZBPE,北京飞行情报区",
        "guangzhou,FIR,ZGZU,广州飞行情报区",
    )))
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "anchor,ANCHOR,ANCHOR,N350000,E1050000,北京情报区",
        "unique,UNIQUE,UNIQUE,N360000,E1060000,",
        "unknown,UNKNOWN,UNKNOWN,N370000,E1070000,",
        "multiple,MULTIPLE,MULTIPLE,N380000,E1080000,",
        "below,BELOW,BELOW,N385000,E1083000,",
        "unused,UNUSED,UNUSED,N390000,E1090000,",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END,Airspace_Remark",
        "R1,1,UNIQUE,ANCHOR,N360000,E1060000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,广州ACC",
        "R2,2,UNKNOWN,ANCHOR,N370000,E1070000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,哈尔滨ACC",
        "R3,3,MULTIPLE,ANCHOR,N380000,E1080000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,以上北京ACC",
        "R4,4,MULTIPLE,ANCHOR,N380000,E1080000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,以下广州ACC",
        "R5,5,BELOW,ANCHOR,N385000,E1083000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,以下广州ACC",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "ANCHOR": "ZB",
        "UNIQUE": "ZG",
        "UNKNOWN": "ZB",
        "MULTIPLE": "",
        "BELOW": "ZG",
        "UNUSED": "",
    }
    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [
        ("ZG", "ZB"),
        ("ZB", "ZB"),
        ("", "ZB"),
        ("", "ZB"),
        ("ZG", "ZB"),
    ]
    assert model.source_acc_region_resolution == {
        "source": {
            "airspace": "AIRSPACE.csv",
            "airway_segments": "RTE_SEG.csv",
        },
        "fir_acc_names": 2,
        "waypoints": {
            "blank_before": 5,
            "airway_connected": 4,
            "not_airway_connected": 1,
            "explicit_endpoint_labeled": 0,
            "recovered": 2,
            "recovered_from_explicit_endpoint_label": 0,
            "unknown_acc": 1,
            "no_mapped_acc": 0,
            "multiple_acc_regions": 1,
            "blank_after": 3,
        },
    }


def test_load_naip_prefers_explicit_endpoint_acc_label_over_generic_leg_accs(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
        "beijing,FIR,ZBPE,\u5317\u4eac\u98de\u884c\u60c5\u62a5\u533a",
        "guangzhou,FIR,ZGZU,\u5e7f\u5dde\u98de\u884c\u60c5\u62a5\u533a",
    )))
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "anchor,ANCHOR,ANCHOR,N350000,E1050000,\u5317\u4eac\u60c5\u62a5\u533a",
        "slash,SLASH/ID,SLASH/ID,N360000,E1060000,",
        "conflict,CONFLICT,CONFLICT,N370000,E1070000,",
        "unknown,UNKNOWN,UNKNOWN,N380000,E1080000,",
        "alias,ALIAS,ALIAS,N390000,E1090000,",
    )))
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "hch,HCH,\u9ec4\u57ce,N391000,E1091000,113.1,0,0,ZBAA,\u5317\u4eac\u60c5\u62a5\u533a",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END,Airspace_Remark",
        "R1,1,SLASH/ID,ANCHOR,N360000,E1060000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,SLASH/ID:\u5e7f\u5ddeACCANCHOR:\u5317\u4eacACC",
        "R2,2,CONFLICT,ANCHOR,N370000,E1070000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,CONFLICT:\u5317\u4eacACCANCHOR:\u5317\u4eacACC",
        "R3,3,CONFLICT,ANCHOR,N370000,E1070000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,CONFLICT:\u5e7f\u5ddeACCANCHOR:\u5317\u4eacACC",
        "R4,4,UNKNOWN,ANCHOR,N380000,E1080000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,UNKNOWN:\u54c8\u5c14\u6ee8ACCANCHOR:\u5317\u4eacACC",
        "R5,5,ALIAS,HCH,N390000,E1090000,N391000,E1091000,,,B,L,DESIGNATED_POINT,VORDME,ALIAS:\u5317\u4eacACC\u9ec4\u57ceVOR/DME:\u5e7f\u5ddeACC",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "ANCHOR": "ZB",
        "SLASH/ID": "ZG",
        "CONFLICT": "",
        "UNKNOWN": "ZB",
        "ALIAS": "ZB",
    }
    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [
        ("ZG", "ZB"),
        ("", "ZB"),
        ("", "ZB"),
        ("ZB", "ZB"),
        ("ZB", "ZB"),
    ]
    assert model.source_acc_region_resolution["waypoints"] == {
        "blank_before": 4,
        "airway_connected": 4,
        "not_airway_connected": 0,
        "explicit_endpoint_labeled": 4,
        "recovered": 2,
        "recovered_from_explicit_endpoint_label": 2,
        "unknown_acc": 1,
        "no_mapped_acc": 0,
        "multiple_acc_regions": 1,
        "blank_after": 2,
    }



def test_load_naip_recovers_blank_waypoint_region_from_unanimous_airway_neighbors(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID,TXT_NAME",
        "beijing,FIR,ZBPE,\u5317\u4eac\u98de\u884c\u60c5\u62a5\u533a",
        "guangzhou,FIR,ZGZU,\u5e7f\u5dde\u98de\u884c\u60c5\u62a5\u533a",
    )))
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "anchor,ANCHOR,ANCHOR,N350000,E1050000,\u5317\u4eac\u60c5\u62a5\u533a",
        "unique,UNIQUE,UNIQUE,N360000,E1060000,",
        "blanknb,BLANKNB,BLANKNB,N361000,E1061000,",
        "multi,MULTI,MULTI,N370000,E1070000,",
        "south,SOUTH,SOUTH,N230000,E1130000,\u5e7f\u5dde\u60c5\u62a5\u533a",
        "conflict,CONFLICT,CONFLICT,N380000,E1080000,",
        "ghostless,GHOSTLESS,GHOSTLESS,N390000,E1090000,",
    )))
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,SERVICED_AIRPORT,CODE_FIR",
        "vor,THY,THY,N414800,E1252800,113.1,0,0,ZYTX,\u6c88\u9633\u60c5\u62a5\u533a",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END,Airspace_Remark",
        "R1,1,UNIQUE,ANCHOR,N360000,E1060000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,\u54c8\u5c14\u6ee8ACC",
        "R2,2,BLANKNB,ANCHOR,N361000,E1061000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,",
        "R8,8,BLANKNB,UNIQUE,N361000,E1061000,N360000,E1060000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,",
        "R3,3,MULTI,ANCHOR,N370000,E1070000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,",
        "R4,4,MULTI,SOUTH,N370000,E1070000,N230000,E1130000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,",
        "R5,5,CONFLICT,ANCHOR,N380000,E1080000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT,\u5e7f\u5ddeACC\u54c8\u5c14\u6ee8ACC",
        "R6,6,THY,GHOSTLESS,N414800,E1252800,N390000,E1090000,,,B,L,VORDME,DESIGNATED_POINT,",
        "R7,7,****,ANCHOR,N145400,E1115530,N350000,E1050000,,,B,L,\u5730\u540d\u70b9,DESIGNATED_POINT,\u4e09\u4e9aACC",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "ANCHOR": "ZB",
        "UNIQUE": "ZB",
        "BLANKNB": "ZB",
        "MULTI": "",
        "SOUTH": "ZG",
        "CONFLICT": "",
        "GHOSTLESS": "ZY",
    }
    assert not any(point.ident == "****" for point in model.waypoints)
    legs = {
        (leg.airway, leg.sequence): (leg.start_ident, leg.start_country, leg.end_ident, leg.end_country)
        for leg in model.airway_legs
    }
    assert legs[("R1", 1)] == ("UNIQUE", "ZB", "ANCHOR", "ZB")
    assert legs[("R2", 2)] == ("BLANKNB", "ZB", "ANCHOR", "ZB")
    assert legs[("R8", 8)] == ("BLANKNB", "ZB", "UNIQUE", "ZB")
    assert legs[("R3", 3)][1] == ""
    assert legs[("R4", 4)][1] == ""
    assert legs[("R5", 5)][1] == ""
    assert legs[("R6", 6)] == ("THY", "ZY", "GHOSTLESS", "ZY")
    assert legs[("R7", 7)][0] == "****"
    assert legs[("R7", 7)][1] == ""
    assert model.source_neighbor_region_resolution["waypoints"]["recovered"] == 3
    assert model.source_neighbor_region_resolution["waypoints"]["multiple_neighbor_regions"] == 1
    assert model.source_neighbor_region_resolution["waypoints"]["acc_disagrees_with_neighbors"] == 1


def test_load_naip_uses_strict_serviced_airport_prefix_for_blank_waypoint_fir(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "娌ラ潚")
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,SERVICED_AIRPORT,CODE_FIR",
        "valid,P216,VALID,N350000,E1050000,ZUHY,",
        "short,SHORT,SHORT,N360000,E1060000,ZU,",
        "foreign,FOREIGN,FOREIGN,N370000,E1070000,EDDF,",
        "explicit,EXPLICIT,EXPLICIT,N380000,E1080000,ZGAA,\u5317\u4eac\u60c5\u62a5\u533a",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "P216": "ZU",
        "SHORT": "",
        "FOREIGN": "",
        "EXPLICIT": "ZG",
    }


def test_load_naip_recovers_blank_waypoint_fir_only_when_source_geometry_is_unambiguous(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID",
        "beijing,FIR,ZBPE",
        "guangzhou,FIR,ZGZU",
    )))
    _write_csv(root, "AIRSPACE_BORDER_VERTEX.csv", "\n".join((
        "VERTEX_ID,AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG",
        "1,beijing,1,N340000,E1040000",
        "2,beijing,2,N340000,E1060000",
        "3,beijing,3,N360000,E1060000",
        "4,beijing,4,N360000,E1040000",
        "5,guangzhou,1,N343000,E1043000",
        "6,guangzhou,2,N343000,E1053000",
        "7,guangzhou,3,N353000,E1053000",
        "8,guangzhou,4,N353000,E1043000",
    )))
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "safe,SAFE,SAFE,N350000,E1041500,",
        "ambiguous,AMB,AMB,N350000,E1050000,",
        "boundary,BOUNDARY,BOUNDARY,N340100,E1050000,",
        "outside,OUTSIDE,OUTSIDE,N380000,E1080000,",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END",
        "R1,1,SAFE,OUTSIDE,N350000,E1041500,N380000,E1080000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT",
    )))

    model = load_naip(root, include_terminal_documents=False)

    assert {
        point.ident: point.country
        for point in model.waypoints
    } == {
        "SAFE": "ZB",
        "AMB": "",
        "BOUNDARY": "",
        "OUTSIDE": "ZB",
    }
    assert (model.airway_legs[0].start_country, model.airway_legs[0].end_country) == (
        "ZB",
        "ZB",
    )
    assert model.source_fir_region_resolution == {
        "source": {
            "airspace": "AIRSPACE.csv",
            "vertices": "AIRSPACE_BORDER_VERTEX.csv",
        },
        "minimum_boundary_distance_nm": 5.0,
        "polygons_loaded": 2,
        "vertices_loaded": 8,
        "waypoints": {
            "blank_before": 4,
            "recovered": 1,
            "ambiguous": 1,
            "near_boundary": 1,
            "outside": 1,
            "blank_after": 3,
        },
    }


def test_load_naip_adds_only_unambiguous_general_document_waypoints(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID",
        "beijing,FIR,ZBPE",
    )))
    _write_csv(root, "AIRSPACE_BORDER_VERTEX.csv", "\n".join((
        "VERTEX_ID,AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG",
        "1,beijing,1,N340000,E1040000",
        "2,beijing,2,N340000,E1060000",
        "3,beijing,3,N360000,E1060000",
        "4,beijing,4,N360000,E1040000",
    )))
    source_pdf = root / ENROUTE_KEY_POINT_DOCUMENT
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"general-document")
    cache = tmp_path / "general-doc-cache" / "enr-4.4"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {
            "documents": [{
                "markdown": (
                    "SAFEN35\u00b000\u203200\u2033E104\u00b015\u203200\u2033"
                    "OUTN38\u00b000\u203200\u2033E108\u00b000\u203200\u2033"
                ),
            }],
        },
    }), encoding="utf-8")

    model = load_naip(
        root,
        general_doc_cache=cache.parent,
        include_terminal_documents=False,
    )

    assert [
        (point.ident, point.country, point.source.file, point.source.page)
        for point in model.waypoints
    ] == [
        ("SAFE", "ZB", ENROUTE_KEY_POINT_DOCUMENT, 1),
    ]
    assert model.general_document_evidence["waypoints"] == {
        "accepted": 1,
        "already_present": 0,
        "identity_conflict": 0,
        "region_ambiguous": 0,
        "region_near_boundary": 0,
        "region_outside": 1,
    }
    assert [(item.key, item.reason) for item in model.rejected_records] == [
        ("OUT", "general document region outside"),
    ]


def test_load_naip_general_document_waypoint_does_not_ambiguate_direct_airway_endpoint(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "AIRSPACE.csv", "\n".join((
        "AIRSPACE_ID,CODE_TYPE,CODE_ID",
        "beijing,FIR,ZBPE",
        "guangzhou,FIR,ZGZU",
    )))
    _write_csv(root, "AIRSPACE_BORDER_VERTEX.csv", "\n".join((
        "VERTEX_ID,AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG",
        "1,guangzhou,1,N340000,E1040000",
        "2,guangzhou,2,N340000,E1060000",
        "3,guangzhou,3,N360000,E1060000",
        "4,guangzhou,4,N360000,E1040000",
    )))
    _write_csv(root, "DESIGNATED_POINT.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,CODE_FIR",
        "direct,TOGOG,DIRECT,N350000,E1050000,北京情报区",
    )))
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END",
        "V1,1,TOGOG,TOGOG,N350000,E1050000,N350000,E1050000,,,B,L,DESIGNATED_POINT,DESIGNATED_POINT",
    )))
    source_pdf = root / ENROUTE_KEY_POINT_DOCUMENT
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"general-document")
    cache = tmp_path / "general-doc-cache" / "enr-4.4"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {
            "documents": [{
                "markdown": "TOGOGN35\u00b000\u203200\u2033E105\u00b000\u203200\u2033",
            }],
        },
    }), encoding="utf-8")

    model = load_naip(
        root,
        general_doc_cache=cache.parent,
        include_terminal_documents=False,
    )

    assert [
        (point.ident, point.country, point.source.file)
        for point in model.waypoints
    ] == [
        ("TOGOG", "ZB", "DESIGNATED_POINT.csv"),
        ("TOGOG", "ZG", ENROUTE_KEY_POINT_DOCUMENT),
    ]
    assert [
        (leg.start_country, leg.end_country)
        for leg in model.airway_legs
    ] == [("ZB", "ZB")]
    assert model.general_document_evidence["waypoints"]["accepted"] == 1


def test_load_naip_keeps_verified_general_document_navaids_as_audit_evidence(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "vor,KQS,source-vor,N411538,E0801934,112.1,-9.0,1188,M,ZBHZ,",
    )))
    key_point_pdf = root / ENROUTE_KEY_POINT_DOCUMENT
    navaid_pdf = root / ENROUTE_NAVAID_DOCUMENT
    key_point_pdf.parent.mkdir(parents=True)
    key_point_pdf.write_bytes(b"key-points")
    navaid_pdf.write_bytes(b"navaids")
    cache_root = tmp_path / "general-doc-cache"
    key_point_cache = cache_root / "enr-4.4"
    navaid_cache = cache_root / "enr-4.1-navaids"
    key_point_cache.mkdir(parents=True)
    navaid_cache.mkdir(parents=True)
    (key_point_cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(key_point_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (key_point_cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": ""}]},
    }), encoding="utf-8")
    (navaid_cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(navaid_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (navaid_cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": "\n".join((
            "KQS[[192, 304, 232, 319]]",
            "112.1MHz[[256, 299, 336, 313]]",
            "N41\ufffd\ufffd15'38\"[[433, 299, 512, 313]]",
            "1188[[551, 305, 591, 320]]",
            "VOR/DME[[92, 317, 167, 331]]",
            "E080\ufffd\ufffd19'34\"[[433, 317, 514, 331]]",
        ))}]},
    }), encoding="utf-8")

    model = load_naip(
        root,
        general_doc_cache=cache_root,
        include_terminal_documents=False,
    )

    assert [(item.ident, item.magnetic_variation) for item in model.navaids] == [
        ("KQS", -9.0),
    ]
    assert [
        (item.kind, item.ident, item.frequency, item.source.file, item.source.page)
        for item in model.enroute_navaid_evidence
    ] == [
        ("VOR", "KQS", 112.1, ENROUTE_NAVAID_DOCUMENT, 1),
    ]
    assert model.general_document_evidence["navaids"] == {
        "available": True,
        "cache": str(navaid_cache),
        "document": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(navaid_pdf.read_bytes()).hexdigest(),
        "pages": 1,
        "parsed_records": 1,
        "matched_424": 1,
        "ocr_identifier_reconciled": 0,
        "ocr_identifier_reconciliations": [],
        "direct_identity_missing": 0,
        "direct_identity_ambiguous": 0,
        "physical_identity_ambiguous": 0,
        "identity_conflict": 0,
    }


def test_load_naip_reconciles_unique_general_document_ocr_identifier_misread(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "vor,NLT,source-vor,N432600,E0832246,115.5,3.25,935,M,ZWNL,",
    )))
    source_pdf = root / ENROUTE_NAVAID_DOCUMENT
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"navaids")
    key_point_pdf = root / ENROUTE_KEY_POINT_DOCUMENT
    key_point_pdf.write_bytes(b"key-points")
    cache_root = tmp_path / "general-doc-cache"
    key_point_cache = cache_root / "enr-4.4"
    cache = cache_root / "enr-4.1-navaids"
    key_point_cache.mkdir(parents=True)
    cache.mkdir(parents=True)
    (key_point_cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(key_point_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (key_point_cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": ""}]},
    }), encoding="utf-8")
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": "\n".join((
            "NL7[[192, 304, 232, 319]]",
            "115.5MHz[[256, 299, 336, 313]]",
            "N43\ufffd\ufffd26'00\"[[433, 299, 512, 313]]",
            "935[[551, 305, 591, 320]]",
            "VOR/DME[[92, 317, 167, 331]]",
            "E083\ufffd\ufffd22'46\"[[433, 317, 514, 331]]",
        ))}]},
    }), encoding="utf-8")

    model = load_naip(
        root,
        general_doc_cache=cache_root,
        include_terminal_documents=False,
    )

    assert [(item.ident, item.magnetic_variation) for item in model.navaids] == [
        ("NLT", 3.25),
    ]
    assert [(item.ident, item.source.page) for item in model.enroute_navaid_evidence] == [
        ("NL7", 1),
    ]
    assert model.general_document_evidence["navaids"][
        "ocr_identifier_reconciliations"
    ] == [{
        "page": 1,
        "kind": "VOR",
        "ocr_ident": "NL7",
        "direct_424_ident": "NLT",
        "source_file": "VOR.csv",
        "source_row": 2,
    }]
    assert model.general_document_evidence["navaids"]["direct_identity_missing"] == 0
    assert not [
        item for item in model.rejected_records
        if item.kind == "general-document-navaid"
    ]


def test_audit_enroute_navaid_ocr_source_uses_an_explicit_complete_cache(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "ASP")
    _write_csv(root, "VOR.csv", "\n".join((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,VAL_FREQ,VAL_MAG_VAR,VAL_ELEV,UOM_DIST_VER,SERVICED_AIRPORT,CODE_FIR",
        "vor,KQS,source-vor,N411538,E0801934,112.1,-9.0,1188,M,ZBHZ,",
    )))
    source_pdf = root / ENROUTE_NAVAID_DOCUMENT
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"navaids")
    cache = tmp_path / "general-doc-cache" / "enr-4.1-navaids-rerun"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps({
        "ok": True,
        "data": {"documents": [{"markdown": "\n".join((
            "KQS[[192, 304, 232, 319]]",
            "112.1MHz[[256, 299, 336, 313]]",
            "N41\ufffd\ufffd15'38\"[[433, 299, 512, 313]]",
            "1188[[551, 305, 591, 320]]",
            "VOR/DME[[92, 317, 167, 331]]",
            "E080\ufffd\ufffd19'34\"[[433, 317, 514, 331]]",
        ))}]},
    }), encoding="utf-8")

    report = audit_enroute_navaid_ocr_source(root, cache)

    assert report["diagnostic"] == "enroute-navaid-ocr-source-audit-v1"
    assert report["evidence_only"] is True
    assert report["navaids"]["matched_424"] == 1
    assert report["navaids"]["direct_identity_missing"] == 0
    assert report["unresolved_evidence"] == []


def test_load_naip_separates_source_pbn_from_target_route_type_and_links_airway_tables(
    tmp_path: Path,
) -> None:
    root = _minimal_naip_root(tmp_path, "沥青")
    _write_csv(root, "RTE_SEG.csv", "\n".join((
        "RTE_SEG_ID,EN_ROUTE_RTE_ID,SEGMENT_ID,TXT_DESIG,VAL_SORT,CODE_POINT_START,CODE_POINT_END,GEO_LAT_START_ACCURACY,GEO_LONG_START_ACCURACY,GEO_LAT_END_ACCURACY,GEO_LONG_END_ACCURACY,CODE_FIR_START,CODE_FIR_END,CODE_DIR,CODE_TYPE,CODE_TYPE_START,CODE_TYPE_END,Airspace_Remark",
        "rte-seg-1,route-1,segment-1,R1,1,DP01,DP02,N350000,E1050000,N360000,E1060000,,,B,RNAV2,DESIGNATED_POINT,DESIGNATED_POINT,ACC-A",
        "rte-seg-2,route-1,missing-segment,R1,2,DP02,DP03,N360000,E1060000,N370000,E1070000,,,B,RNP4,DESIGNATED_POINT,DESIGNATED_POINT,",
    )))
    _write_csv(root, "SEGMENT.csv", "\n".join((
        "SEGMENT_ID,TXT_DESIG_RNP,VAL_MTCA",
        "segment-1,P4,2300",
    )))
    _write_csv(root, "EN_ROUTE_RTE.csv", "\n".join((
        "EN_ROUTE_RTE_ID,TXT_LOC_TYPE,VAL_MTCA",
        "route-1,国际区域导航航路,2600",
    )))

    model = load_naip(root, include_terminal_documents=False)

    first, second = model.airway_legs
    assert first.route_type == ""
    assert first.source_code_type == "RNAV2"
    assert first.source_airspace_remark == "ACC-A"
    assert first.source_segment_rnp_designator == "P4"
    assert first.source_enroute_location_type == "国际区域导航航路"
    assert first.source_segment_minimum_crossing_altitude == "2300"
    assert first.source_route_minimum_crossing_altitude == "2600"
    assert first.source_rte_seg_id == "rte-seg-1"
    assert first.source_segment_id == "segment-1"
    assert first.source_en_route_rte_id == "route-1"
    assert first.source_segment_found is True
    assert first.source_en_route_rte_found is True
    assert second.source_segment_found is False
    assert second.source_en_route_rte_found is True

    summary = summarize_airway_source_metadata(model)
    assert summary["source_code_type"] == {"RNAV2": 1, "RNP4": 1}
    assert summary["target_route_type_hint"] == {"<unresolved>": 2}
    assert summary["source_airspace_remark"] == {
        "populated": 1,
        "blank": 1,
        "distinct_nonblank": 1,
    }
    assert summary["links"] == {
        "segment_found": 1,
        "segment_missing": 1,
        "en_route_rte_found": 2,
        "en_route_rte_missing": 0,
    }
