from pathlib import Path

from fenix_default_navdata.iap_coverage import analyze_iap_coverage
from fenix_default_navdata.model import (
    Airport,
    ChartRouteFix,
    ChartTerminalLeg,
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

    assert report["chart_pages"]["total"] == 2
    assert report["chart_pages"]["matched_to_primary_group"] == 2
    assert report["chart_pages"]["selected_for_role_projection"] == 1
    assert report["procedure_groups"]["complete_primary_legs"] == 1
    assert report["procedure_groups"]["role_evidence_used"] == 1
    assert report["procedure_groups"]["status_counts"] == {
        "roles_final_mapt_disambiguated": 1,
    }
    assert report["role_evidence_counts"] == {"MAPT": 1}
    assert report["unresolved_groups"] == []


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
