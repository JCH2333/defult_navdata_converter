from pathlib import Path

from fenix_default_navdata.iap_coverage import (
    analyze_iap_coverage,
    iap_multi_primary_section_assignments,
)
from fenix_default_navdata.model import (
    Airport,
    ChartRouteFix,
    ChartTerminalLeg,
    IapOcrRoleEvidence,
    NavModel,
    ProcedureChart,
    ProcedureSegment,
    Runway,
    SourceRef,
)


def _model_with_iap_segments() -> NavModel:
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model = NavModel(Path("source"))
    model.airports["airport"] = Airport(
        "airport", "ZBCF", "ZBCF", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(
        Runway("runway", "airport", "03", 30.0, 10000, 150, "ASP", 1000, source),
    )
    model.procedure_segments.extend([
        ProcedureSegment(
            "ZBCF", "R03", "approach", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "FINAL", "fixture", sequence=1),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "R03", "missed", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "MAHF", "fixture", sequence=1),
            ), source,
        ),
    ])
    return model


def _model_with_unqualified_rnp_ar_variant() -> NavModel:
    source = SourceRef("Terminal/ZUNP/ZUNP-4Z04.pdf", 1, 1, "database-hash")
    model = NavModel(Path("source"))
    model.airports["airport"] = Airport(
        "airport", "ZUNP", "ZUNP", 35.0, 105.0, 1000, 18000, 180, source,
    )
    model.runways.append(
        Runway("runway", "airport", "24", 30.0, 10000, 150, "ASP", 1000, source),
    )
    model.procedure_segments.append(
        ProcedureSegment(
            "ZUNP", "R24-Y", "approach", "24", "", (
                ChartTerminalLeg("R24-Y", "24", "TF", "NP716", "fixture", sequence=1),
                ChartTerminalLeg("R24-Y", "24", "TF", "NP714", "fixture", sequence=2),
            ), source,
        ),
    )
    return model


def _unqualified_rnp_ar_chart(
    filename: str,
    waypoints: tuple[str, ...],
    source: SourceRef,
    chart_name: str = "RNP RWY24(AR)",
    route_fixes: tuple[ChartRouteFix, ...] = (),
) -> ProcedureChart:
    return ProcedureChart(
        "ZUNP", filename, 1, "instrument-approach-index", chart_name,
        "text", (), ("24",), waypoints, (), (), source, route_fixes=route_fixes,
    )


def test_iap_coverage_counts_unique_map_disambiguation():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("FINAL", "MAPT"),),
        ),
        ProcedureChart(
            "ZBCF", "other.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("OTHER", "MAPT"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["version"] == 12
    assert report["chart_pages"]["total"] == 2
    assert report["chart_pages"]["matched_to_primary_group"] == 2
    assert report["chart_pages"]["selected_for_role_projection"] == 1
    assert report["procedure_groups"]["complete_primary_legs"] == 1
    assert report["procedure_groups"]["role_evidence_used"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "roles_final_mapt_disambiguated": 1,
    }
    assert report["role_evidence_counts"] == {"MAPT": 1}
    assert report["ocr_role_selections"] == []
    assert report["unresolved_groups"] == []


def test_iap_coverage_selects_unqualified_rnp_ar_chart_by_complete_direct_fixes():
    model = _model_with_unqualified_rnp_ar_variant()
    selected_source = SourceRef("Terminal/ZUNP/ZUNP-9D.pdf", 1, 1, "selected-hash")
    model.procedure_charts.extend([
        _unqualified_rnp_ar_chart(
            "ZUNP-9C.pdf", ("NP706", "NP708", "NP710"), selected_source,
        ),
        _unqualified_rnp_ar_chart(
            "ZUNP-9D.pdf",
            ("NP714", "NP716", "NP718"),
            selected_source,
            route_fixes=(ChartRouteFix("NP900", "IAF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "unique_chart_without_roles": 1,
    }
    assert report["procedure_groups"]["role_evidence_used"] == 0
    assert report["role_evidence_counts"] == {}
    assert report["source_fixed_point_selections"] == [{
        "airport": "ZUNP",
        "label": "R24-Y",
        "runway": "24",
        "selection": "direct_fixed_points",
        "chart_name": "RNP RWY24(AR)",
        "source": {
            "file": "Terminal/ZUNP/ZUNP-9D.pdf",
            "row": 1,
            "page": 1,
            "sha256": "selected-hash",
        },
        "required_fixes": ["NP714", "NP716"],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_splits_same_label_rnp_and_rnp_ar_primaries_by_direct_fixes():
    model = _model_with_iap_segments()
    normal_source = SourceRef("Terminal/ZBCF/ZBCF-4H.pdf", 1, 1, "normal-db")
    ar_source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "ar-db")
    model.procedure_segments[:] = [
        ProcedureSegment(
            "ZBCF", "R03", "approach", "03", "", (
                ChartTerminalLeg("R03", "03", "TF", "NORMAL1", "fixture", sequence=1),
                ChartTerminalLeg("R03", "03", "TF", "NORMAL2", "fixture", sequence=2),
            ), normal_source, approach_family="RNP",
        ),
        ProcedureSegment(
            "ZBCF", "R03", "approach_transition", "03", "VIA", (
                ChartTerminalLeg("R03", "03", "IF", "NORMAL1", "fixture", sequence=1),
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
            ), SourceRef("Terminal/ZBCF/ZBCF-4J.pdf", 1, 1, "normal-missed"),
        ),
        ProcedureSegment(
            "ZBCF", "R03", "approach_transition", "03", "OFFPAGE", (
                ChartTerminalLeg("R03", "03", "IF", "SOURCE1", "fixture", sequence=1),
                ChartTerminalLeg("R03", "03", "TF", "SOURCE2", "fixture", sequence=2),
            ), SourceRef("Terminal/ZBCF/ZBCF-4K.pdf", 1, 1, "normal-transition"),
            approach_family="RNP",
        ),
    ]
    normal_chart_source = SourceRef("Terminal/ZBCF/ZBCF-9A.pdf", 1, 1, "normal-chart")
    ar_chart_source = SourceRef("Terminal/ZBCF/ZBCF-9C.pdf", 1, 1, "ar-chart")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ZBCF-9A.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("NORMAL1", "NORMAL2", "NMHF1", "NML1"), (), (), normal_chart_source,
            route_fixes=(ChartRouteFix("NORMAL1", "FAF"),),
        ),
        ProcedureChart(
            "ZBCF", "ZBCF-9C.pdf", 1, "instrument-approach-index", "RNP RWY03(AR)",
            "text", (), ("03",), ("ARFIX1", "ARFIX2"), (), (), ar_chart_source,
            route_fixes=(ChartRouteFix("ARFIX1", "FAF"),),
            has_missed_approach=True,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "multiple_primary_direct_fixed_points": 1,
    }
    assert report["unresolved_groups"] == []
    assert [
        (item["family"], item["rnp_ar"], item["source"]["file"])
        for item in report["multi_primary_variant_assignments"]
    ] == [
        ("RNP", False, "Terminal/ZBCF/ZBCF-4H.pdf"),
        ("RNP_AR", True, "Terminal/ZBCF/ZBCF-4L.pdf"),
    ]
    assignments = iap_multi_primary_section_assignments(model)
    assert assignments[id(model.procedure_segments[-2])].family == "RNP"
    assert assignments[id(model.procedure_segments[-2])].chart.chart_name == "RNP RWY03"
    assert assignments[id(model.procedure_segments[-1])].family == "RNP"


def test_iap_coverage_rejects_equal_unqualified_rnp_ar_direct_fix_candidates():
    model = _model_with_unqualified_rnp_ar_variant()
    source = SourceRef("Terminal/ZUNP/ZUNP-9C.pdf", 1, 1, "chart-hash")
    model.procedure_charts.extend([
        _unqualified_rnp_ar_chart(
            "ZUNP-9C.pdf", ("NP714", "NP716"), source,
        ),
        _unqualified_rnp_ar_chart(
            "ZUNP-9D.pdf", ("NP714", "NP716"), source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "no_matching_chart": 1,
    }
    assert report["source_fixed_point_selections"] == []
    assert report["unresolved_groups"][0]["status"] == "no_matching_chart"


def test_iap_coverage_selects_ambiguous_title_match_by_complete_direct_fixes():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/database.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FIRST", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FINAL", "fixture", sequence=2),
        ), source,
    )
    incomplete_source = SourceRef("Terminal/ZBCF/incomplete.pdf", 1, 1, "incomplete-hash")
    selected_source = SourceRef("Terminal/ZBCF/selected.pdf", 1, 1, "selected-hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "incomplete.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("FIRST",), (), (), incomplete_source,
        ),
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("FINAL", "FIRST"), (), (), selected_source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "unique_chart_without_roles": 1,
    }
    assert report["role_evidence_counts"] == {}
    assert report["source_fixed_point_selections"] == [{
        "airport": "ZBCF",
        "label": "R03",
        "runway": "03",
        "selection": "direct_fixed_points",
        "chart_name": "RNP RWY03",
        "source": {
            "file": "Terminal/ZBCF/selected.pdf",
            "row": 1,
            "page": 1,
            "sha256": "selected-hash",
        },
        "required_fixes": ["FINAL", "FIRST"],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_prefers_unique_plain_ils_title_for_database_i_label():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZPNL/ZPNL-4H.pdf", 1, 1, "database-hash")
    model.procedure_segments[:] = [
        ProcedureSegment(
            "ZPNL", "I23", "approach", "23", "", (
                ChartTerminalLeg("I23", "23", "IF", "NL706", "fixture", sequence=1),
            ), source, approach_family="ILS",
        ),
    ]
    rnp_ils_source = SourceRef("Terminal/ZPNL/ZPNL-5A.pdf", 1, 1, "rnp-ils-hash")
    plain_ils_source = SourceRef("Terminal/ZPNL/ZPNL-5B.pdf", 1, 1, "plain-ils-hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZPNL", "ZPNL-5A.pdf", 1, "instrument-approach-index",
            "RNP ILS/DME z RWY23", "text", (), ("23",), (), (), (),
            rnp_ils_source, route_fixes=(ChartRouteFix("NL706", "IF"),),
        ),
        ProcedureChart(
            "ZPNL", "ZPNL-5B.pdf", 1, "instrument-approach-index",
            "ILS/DME y RWY23", "text", (), ("23",), (), (), (),
            plain_ils_source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["chart_pages"]["matched_to_primary_group"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "unique_chart_without_roles": 1,
    }
    assert report["unresolved_groups"] == []


def test_iap_coverage_selects_unique_rnp_ar_title_qualifier_matching_primary_leg():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZUNZ/ZUNZ-4G05.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZUNZ", "R05", "approach", "05", "", (
            ChartTerminalLeg("R05", "05", "TF", "LZ250", "fixture", sequence=1),
            ChartTerminalLeg("R05", "05", "TF", "LZ302", "fixture", sequence=2),
        ), source,
    )
    model.procedure_segments[1] = ProcedureSegment(
        "ZUNZ", "R05", "missed", "05", "", (), source,
    )
    other_source = SourceRef("Terminal/ZUNZ/ZUNZ-9A.pdf", 1, 1, "other-hash")
    selected_source = SourceRef("Terminal/ZUNZ/ZUNZ-9C.pdf", 1, 1, "selected-hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZUNZ", "ZUNZ-9A.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(DUMIX)", "text", (), ("05",), (), (), (), other_source,
        ),
        ProcedureChart(
            "ZUNZ", "ZUNZ-9C.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(LZ302)", "text", (), ("05",), (), (), (), selected_source,
            route_fixes=(ChartRouteFix("LZ302", "IAF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_source_title_qualifier_chart": 1,
    }
    assert report["role_evidence_counts"] == {"IAF": 1}
    assert report["source_title_qualifier_selections"] == [{
        "airport": "ZUNZ",
        "label": "R05",
        "runway": "05",
        "selection": "rnp_ar_title_qualifier",
        "matching_charts": 2,
        "chart_name": "RNP RWY05(AR)(LZ302)",
        "source": {
            "file": "Terminal/ZUNZ/ZUNZ-9C.pdf",
            "row": 1,
            "page": 1,
            "sha256": "selected-hash",
        },
        "title_qualifier_fixes": ["LZ302"],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_rejects_nonunique_or_mixed_rnp_ar_title_qualifier_matches():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZUNZ/ZUNZ-4G05.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZUNZ", "R05", "approach", "05", "", (
            ChartTerminalLeg("R05", "05", "TF", "LZ250", "fixture", sequence=1),
            ChartTerminalLeg("R05", "05", "TF", "LZ302", "fixture", sequence=2),
        ), source,
    )
    model.procedure_segments[1] = ProcedureSegment(
        "ZUNZ", "R05", "missed", "05", "", (), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZUNZ", "first.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(LZ250)", "text", (), ("05",), (), (), (), source,
        ),
        ProcedureChart(
            "ZUNZ", "second.pdf", 1, "instrument-approach-index",
            "RNP RWY05(AR)(LZ302)", "text", (), ("05",), (), (), (), source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {"ambiguous_chart": 1}
    assert report["source_title_qualifier_selections"] == []
    assert report["unresolved_groups"][0]["status"] == "ambiguous_chart"

    model.procedure_charts[1] = ProcedureChart(
        "ZUNZ", "second.pdf", 1, "instrument-approach-index",
        "RNP RWY05", "text", (), ("05",), (), (), (), source,
    )
    mixed_report = analyze_iap_coverage(model)
    assert mixed_report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert mixed_report["source_title_qualifier_selections"] == []


def test_iap_coverage_selects_unqualified_rnp_ar_chart_by_unique_direct_role():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FIRST", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "LAST", "fixture", sequence=2),
        ), source,
    )
    model.procedure_segments[1] = ProcedureSegment(
        "ZBCF", "R03", "missed", "03", "", (), source,
    )
    other_source = SourceRef("Terminal/ZBCF/ZBCF-9A.pdf", 1, 1, "other-hash")
    selected_source = SourceRef("Terminal/ZBCF/ZBCF-9B.pdf", 1, 1, "selected-hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ZBCF-9A.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)", "text", (), ("03",), ("FIRST", "LAST"), (), (),
            other_source, route_fixes=(ChartRouteFix("OTHER", "IAF"),),
        ),
        ProcedureChart(
            "ZBCF", "ZBCF-9B.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)", "text", (), ("03",), ("FIRST", "LAST"), (), (),
            selected_source, route_fixes=(ChartRouteFix("LAST", "IAF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_source_unqualified_rnp_ar_direct_role_chart": 1,
    }
    assert report["role_evidence_counts"] == {"IAF": 1}
    assert report["source_unqualified_rnp_ar_direct_role_selections"] == [{
        "airport": "ZBCF",
        "label": "R03",
        "runway": "03",
        "selection": "rnp_ar_unique_direct_role",
        "matching_charts": 2,
        "chart_name": "RNP RWY03(AR)",
        "source": {
            "file": "Terminal/ZBCF/ZBCF-9B.pdf",
            "row": 1,
            "page": 1,
            "sha256": "selected-hash",
        },
        "matching_roles": [{"ident": "LAST", "roles": ["IAF"]}],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_rejects_qualified_or_nonunique_rnp_ar_direct_role_matches():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FIRST", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "LAST", "fixture", sequence=2),
        ), source,
    )
    model.procedure_segments[1] = ProcedureSegment(
        "ZBCF", "R03", "missed", "03", "", (), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ZBCF-9A.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("FIRST", "IAF"),),
        ),
        ProcedureChart(
            "ZBCF", "ZBCF-9B.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("LAST", "IAF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {"ambiguous_chart": 1}
    assert report["source_unqualified_rnp_ar_direct_role_selections"] == []

    model.procedure_charts[0] = ProcedureChart(
        "ZBCF", "ZBCF-9A.pdf", 1, "instrument-approach-index",
        "RNP RWY03(AR)(OTHER)", "text", (), ("03",), (), (), (), source,
        route_fixes=(ChartRouteFix("OTHER", "IAF"),),
    )
    qualified_report = analyze_iap_coverage(model)

    assert qualified_report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert qualified_report["source_unqualified_rnp_ar_direct_role_selections"] == []


def test_iap_coverage_selects_unique_direct_source_role_without_ar_title_mixing():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "DIRECT", "fixture", sequence=1),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "ils.pdf", 1, "instrument-approach-index",
            "RNP ILS/DME z RWY03", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("OTHER", "IF"),),
        ),
        ProcedureChart(
            "ZBCF", "rnp.pdf", 1, "instrument-approach-index",
            "RNP RWY03", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("DIRECT", "IF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_source_unique_direct_role_chart": 1,
    }
    assert report["role_evidence_counts"] == {"IF": 1}
    assert report["source_unique_direct_role_selections"] == [{
        "airport": "ZBCF",
        "label": "R03",
        "runway": "03",
        "selection": "unique_direct_role",
        "matching_charts": 2,
        "chart_name": "RNP RWY03",
        "source": {
            "file": "Terminal/ZBCF/ZBCF-4L.pdf",
            "row": 1,
            "page": 1,
            "sha256": "database-hash",
        },
        "matching_roles": [{"ident": "DIRECT", "roles": ["IF"]}],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_selects_uniform_qualified_rnp_ar_by_unique_direct_role():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/ZBCF-4L.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "DIRECT", "fixture", sequence=1),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "first.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)(FIRST)", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("DIRECT", "IAF"),),
        ),
        ProcedureChart(
            "ZBCF", "second.pdf", 1, "instrument-approach-index",
            "RNP RWY03(AR)(SECOND)", "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("SECOND", "IAF"),),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_source_unique_direct_role_chart": 1,
    }
    assert report["source_unique_direct_role_selections"][0]["chart_name"] == (
        "RNP RWY03(AR)(FIRST)"
    )
    assert report["unresolved_groups"] == []


def test_iap_coverage_prefers_direct_role_selection_before_complete_direct_fixes():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/database.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FIRST", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FINAL", "fixture", sequence=2),
        ), source,
    )
    role_source = SourceRef("Terminal/ZBCF/role.pdf", 1, 1, "role-hash")
    fixed_source = SourceRef("Terminal/ZBCF/fixed.pdf", 1, 1, "fixed-hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "role.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("FIRST",), (), (), role_source,
            route_fixes=(ChartRouteFix("FINAL", "MAPT"),),
        ),
        ProcedureChart(
            "ZBCF", "fixed.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("FINAL", "FIRST"), (), (), fixed_source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_final_mapt_disambiguated": 1,
    }
    assert report["source_fixed_point_selections"] == []
    assert report["role_evidence_counts"] == {"MAPT": 1}


def test_iap_coverage_keeps_equal_complete_direct_fix_title_matches_ambiguous():
    model = _model_with_iap_segments()
    source = SourceRef("Terminal/ZBCF/database.pdf", 1, 1, "database-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "FIRST", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FINAL", "fixture", sequence=2),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", filename, 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), ("FINAL", "FIRST"), (), (), source,
        )
        for filename in ("first.pdf", "second.pdf")
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert report["source_fixed_point_selections"] == []


def test_iap_coverage_rejects_unqualified_rnp_ar_chart_with_only_one_direct_fix():
    model = _model_with_unqualified_rnp_ar_variant()
    source = SourceRef("Terminal/ZUNP/ZUNP-9D.pdf", 1, 1, "chart-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZUNP", "R24-Y", "approach", "24", "", (
            ChartTerminalLeg("R24-Y", "24", "TF", "NP716", "fixture", sequence=1),
        ), source,
    )
    model.procedure_charts.append(
        _unqualified_rnp_ar_chart("ZUNP-9D.pdf", ("NP716",), source),
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "no_matching_chart": 1,
    }
    assert report["source_fixed_point_selections"] == []


def test_iap_coverage_does_not_use_fixed_points_when_rnp_ar_title_declares_variant():
    model = _model_with_unqualified_rnp_ar_variant()
    source = SourceRef("Terminal/ZUNP/ZUNP-9C.pdf", 1, 1, "chart-hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZUNP", "R24-Z", "approach", "24", "", (
            ChartTerminalLeg("R24-Z", "24", "TF", "NP706", "fixture", sequence=1),
            ChartTerminalLeg("R24-Z", "24", "TF", "NP708", "fixture", sequence=2),
        ), source,
    )
    model.procedure_charts.append(
        _unqualified_rnp_ar_chart(
            "ZUNP-9C.pdf",
            ("NP706", "NP708"),
            source,
            chart_name="RNP Y RWY24(AR)",
        ),
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "no_matching_chart": 1,
    }
    assert report["source_fixed_point_selections"] == []


def test_iap_coverage_uses_unique_multi_role_evidence_when_final_leg_is_not_mapt():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "MAP_FIX", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FAF_FIX", "fixture", sequence=2),
            ChartTerminalLeg("R03", "03", "TF", "IF_FIX", "fixture", sequence=3),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(
                ChartRouteFix("MAP_FIX", "MAPT"),
                ChartRouteFix("FAF_FIX", "FAF"),
                ChartRouteFix("IF_FIX", "IF"),
            ),
        ),
        ProcedureChart(
            "ZBCF", "other.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["chart_pages"]["selected_for_role_projection"] == 1
    assert report["procedure_groups"]["role_evidence_used"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "roles_multi_role_disambiguated": 1,
    }
    assert report["role_evidence_counts"] == {"FAF": 1, "IF": 1, "MAPT": 1}
    assert report["unresolved_groups"] == []


def test_iap_coverage_does_not_select_a_chart_with_only_one_matching_role():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "MAP_FIX", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "IF_FIX", "fixture", sequence=2),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "weak.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("IF_FIX", "IF"),),
        ),
        ProcedureChart(
            "ZBCF", "other.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert report["unresolved_groups"][0]["status"] == "ambiguous_chart"


def test_iap_coverage_selects_strictly_dominant_multi_role_chart():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "IF_FIX", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FAF_FIX", "fixture", sequence=2),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "partial.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("IF_FIX", "IF"),),
        ),
        ProcedureChart(
            "ZBCF", "dominant.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(
                ChartRouteFix("IF_FIX", "IF"),
                ChartRouteFix("FAF_FIX", "FAF"),
            ),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["chart_pages"]["selected_for_role_projection"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "roles_dominant_multi_role_disambiguated": 1,
    }
    assert report["role_evidence_counts"] == {"FAF": 1, "IF": 1}


def test_iap_coverage_keeps_equal_multi_role_charts_ambiguous():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_segments[0] = ProcedureSegment(
        "ZBCF", "R03", "approach", "03", "", (
            ChartTerminalLeg("R03", "03", "TF", "IF_FIX", "fixture", sequence=1),
            ChartTerminalLeg("R03", "03", "TF", "FAF_FIX", "fixture", sequence=2),
            ChartTerminalLeg("R03", "03", "TF", "FINAL_FIX", "fixture", sequence=3),
        ), source,
    )
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "first.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(
                ChartRouteFix("IF_FIX", "IF"),
                ChartRouteFix("FAF_FIX", "FAF"),
            ),
        ),
        ProcedureChart(
            "ZBCF", "second.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(
                ChartRouteFix("IF_FIX", "IF"),
                ChartRouteFix("FAF_FIX", "MAPT"),
            ),
        ),
    ])

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert report["unresolved_groups"][0]["status"] == "ambiguous_chart"


def test_iap_coverage_uses_consensus_ocr_mapt_only_for_one_matching_chart():
    model = _model_with_iap_segments()
    selected_source = SourceRef(
        "Terminal/ZBCF/selected.pdf", 1, 1, "selected-sha256",
    )
    other_source = SourceRef(
        "Terminal/ZBCF/other.pdf", 1, 1, "other-sha256",
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

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "roles_ocr_final_mapt_disambiguated": 1,
    }
    assert report["role_evidence_counts"] == {"MAPT": 1}
    assert report["ocr_role_selections"] == [{
        "airport": "ZBCF",
        "label": "R03",
        "runway": "03",
        "selection": "ocr_final_mapt",
        "matching_charts": 2,
        "chart_name": "RNP RWY03",
        "source": {
            "file": "Terminal/ZBCF/selected.pdf",
            "row": 1,
            "page": 1,
            "sha256": "selected-sha256",
        },
        "matching_leg_roles": [{"ident": "FINAL", "roles": ["MAPT"]}],
    }]
    assert report["unresolved_groups"] == []


def test_iap_coverage_keeps_two_consensus_ocr_mapt_candidates_ambiguous():
    model = _model_with_iap_segments()
    first_source = SourceRef("first.pdf", 1, 1, "first-sha256")
    second_source = SourceRef("second.pdf", 1, 1, "second-sha256")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "first.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), first_source,
        ),
        ProcedureChart(
            "ZBCF", "second.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), second_source,
        ),
    ])
    model.iap_ocr_role_evidence = IapOcrRoleEvidence(
        candidate_roles={
            ("ZBCF", "R03", "03", "first.pdf", "first-sha256"): frozenset({
                ("FINAL", "MAPT"),
            }),
            ("ZBCF", "R03", "03", "second.pdf", "second-sha256"): frozenset({
                ("FINAL", "MAPT"),
            }),
        },
        report={"accepted": True},
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
    }
    assert report["unresolved_groups"][0]["status"] == "ambiguous_chart"


def test_iap_coverage_does_not_reject_same_page_shared_variant_sections():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_segments = [
        ProcedureSegment(
            "ZBCF", "R03", "approach_transition", "03", "TRANS", (
                ChartTerminalLeg("R03", "03", "IF", "TRANS", "fixture", sequence=1),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "R03", "missed", "03", "", (
                ChartTerminalLeg("R03", "03", "DF", "MISSED", "fixture", sequence=1),
            ), source,
        ),
        ProcedureSegment(
            "ZBCF", "R03-Z", "approach", "03", "", (
                ChartTerminalLeg("R03-Z", "03", "TF", "FINAL", "fixture", sequence=1),
            ), source,
        ),
    ]
    model.procedure_charts.append(
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP z RWY03",
            "text", (), ("03",), (), (), (), source,
        ),
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["shared_section_groups"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "unique_chart_without_roles": 1,
    }
    assert report["unresolved_groups"] == []


def test_iap_coverage_resolves_ordered_cross_page_base_sections():
    model = _model_with_iap_segments()
    base_source = SourceRef("approach.pdf", 1, 1, "hash")
    variant_source = SourceRef("approach.pdf", 2, 2, "hash")
    model.procedure_segments = [
        ProcedureSegment(
            "ZBCF", "R03", "approach_transition", "03", "TRANS", (
                ChartTerminalLeg("R03", "03", "IF", "TRANS", "fixture", sequence=1),
            ), base_source,
        ),
        ProcedureSegment(
            "ZBCF", "R03-Z", "approach", "03", "", (
                ChartTerminalLeg("R03-Z", "03", "TF", "FINAL", "fixture", sequence=1),
            ), variant_source,
        ),
    ]
    model.procedure_charts.append(
        ProcedureChart(
            "ZBCF", "selected.pdf", 1, "instrument-approach-index", "RNP z RWY03",
            "text", (), ("03",), (), (), (), variant_source,
        ),
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["shared_section_groups"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "unique_chart_without_roles": 1,
    }
    assert report["unresolved_groups"] == []
    assert report["shared_section_assignments"] == [{
        "airport": "ZBCF",
        "label": "R03",
        "runway": "03",
        "section": "approach_transition",
        "target_label": "R03-Z",
        "selection": "ordered_next",
        "source": {
            "file": "approach.pdf",
            "row": 1,
            "page": 1,
            "sha256": "hash",
        },
    }]


def test_iap_coverage_keeps_ambiguous_and_missing_primary_groups_auditable():
    model = _model_with_iap_segments()
    source = SourceRef("approach.pdf", 1, 1, "hash")
    model.procedure_charts.extend([
        ProcedureChart(
            "ZBCF", "first.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("OTHER", "MAPT"),),
        ),
        ProcedureChart(
            "ZBCF", "second.pdf", 1, "instrument-approach-index", "RNP RWY03",
            "text", (), ("03",), (), (), (), source,
            route_fixes=(ChartRouteFix("OTHER", "MAPT"),),
        ),
    ])
    model.procedure_segments.append(
        ProcedureSegment("ZBCF", "R24", "missed", "24", "", (), source),
    )

    report = analyze_iap_coverage(model)

    assert report["procedure_groups"]["status_counts"] == {
        "ambiguous_chart": 1,
        "no_unique_primary": 1,
    }
    assert [item["status"] for item in report["unresolved_groups"]] == [
        "ambiguous_chart",
        "no_unique_primary",
    ]
