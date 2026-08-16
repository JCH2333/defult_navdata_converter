from pathlib import Path

from fenix_default_navdata.iap_coverage import analyze_iap_coverage
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

    assert report["version"] == 6
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


def test_iap_coverage_keeps_base_sections_when_variant_is_from_another_page():
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

    assert report["procedure_groups"]["shared_section_groups"] == 0
    assert report["procedure_groups"]["status_counts"] == {
        "no_unique_primary": 1,
        "unique_chart_without_roles": 1,
    }
    assert [item["status"] for item in report["unresolved_groups"]] == [
        "no_unique_primary",
    ]


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
