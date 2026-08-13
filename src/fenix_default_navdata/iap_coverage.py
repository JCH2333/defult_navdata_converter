from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .model import NavModel
from .pdf_charts import approach_procedure_name_candidates


_PROCEDURE_KIND_MAP = {
    "离场": "departure",
    "departure": "departure",
    "进场": "arrival",
    "arrival": "arrival",
    "进近过渡": "approach_transition",
    "approach_transition": "approach_transition",
    "进近": "approach",
    "approach": "approach",
    "复飞": "missed",
    "missed": "missed",
}
IAP_KINDS = frozenset({"approach_transition", "approach", "missed"})
_UNRESOLVED_STATUSES = frozenset({
    "no_unique_primary",
    "empty_primary",
    "no_matching_chart",
    "ambiguous_chart",
})


def procedure_kind(kind: str) -> str:
    return _PROCEDURE_KIND_MAP.get((kind or "").strip(), "")


def iap_section_kind(segment: Any) -> str:
    kind = procedure_kind(segment.kind)
    if kind == "approach" and segment.transition:
        return "approach_transition"
    return kind


def matching_iap_charts(model: NavModel, segment: Any) -> list:
    return [
        chart
        for chart in model.procedure_charts
        if chart.airport == segment.airport
        and chart.chart_type == "instrument-approach-index"
        and segment.runway in chart.runways
        and segment.label in approach_procedure_name_candidates(
            chart.chart_name, chart.runways, segment.airport,
        )
    ]


def iap_chart_roles(model: NavModel, segment: Any) -> dict[str, set[str]]:
    """Return roles only when one printed approach plate is identifiable."""
    charts = matching_iap_charts(model, segment)
    if len(charts) > 1 and segment.legs and segment.legs[-1].fix_ident:
        final_fix = segment.legs[-1].fix_ident.upper()
        map_charts = [
            chart
            for chart in charts
            if any(
                route_fix.ident.upper() == final_fix
                and route_fix.role.upper() in {"MAP", "MAPT"}
                for route_fix in chart.route_fixes
            )
        ]
        if len(map_charts) == 1:
            charts = map_charts
    if len(charts) != 1:
        return {}
    roles: dict[str, set[str]] = {}
    for route_fix in charts[0].route_fixes:
        ident = route_fix.ident.strip().upper()
        role = route_fix.role.strip().upper()
        if ident and role:
            roles.setdefault(ident, set()).add(role)
    return roles


def _source_report(source: Any) -> dict[str, object]:
    return {
        "file": source.file,
        "row": source.row,
        "page": source.page,
        "sha256": source.sha256,
    }


def _group_source(primary: list[Any], selected: list[Any]) -> dict[str, object]:
    if primary:
        return _source_report(primary[0].source)
    if selected:
        return _source_report(selected[0].source)
    return {"file": None, "row": None, "page": None, "sha256": None}


def analyze_iap_coverage(model: NavModel) -> dict[str, object]:
    """Classify IAP evidence without claiming complete chart decoding."""
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in model.procedure_segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)

    charts = sorted(
        (
            chart for chart in model.procedure_charts
            if chart.chart_type == "instrument-approach-index"
        ),
        key=lambda chart: (chart.airport, chart.filename, chart.page, chart.chart_name),
    )
    status_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    unresolved: list[dict[str, object]] = []
    selected_role_pages: set[tuple[str, str, int]] = set()
    matched_pages: set[tuple[str, str, int]] = set()
    complete_primary_groups = 0
    role_groups = 0

    for airport, label, runway in sorted(groups):
        selected = groups[(airport, label, runway)]
        primary = [
            segment for segment in selected
            if iap_section_kind(segment) == "approach"
        ]
        matching: list[Any] = []
        roles: dict[str, set[str]] = {}
        primary_legs = 0
        if len(primary) != 1:
            status = "no_unique_primary"
        elif not primary[0].legs:
            status = "empty_primary"
        else:
            complete_primary_groups += 1
            primary_legs = len(primary[0].legs)
            matching = matching_iap_charts(model, primary[0])
            matched_pages.update(
                (chart.airport, chart.filename, chart.page)
                for chart in matching
            )
            roles = iap_chart_roles(model, primary[0])
            if roles:
                role_groups += 1
                status = (
                    "roles_unique_chart"
                    if len(matching) == 1
                    else "roles_final_mapt_disambiguated"
                )
                selected_chart = next(
                    (
                        chart for chart in matching
                        if all(
                            any(
                                route_fix.ident.strip().upper() == ident
                                and route_fix.role.strip().upper() in role_set
                                for route_fix in chart.route_fixes
                            )
                            for ident, role_set in roles.items()
                        )
                    ),
                    None,
                )
                if selected_chart is not None:
                    selected_role_pages.add(
                        (selected_chart.airport, selected_chart.filename, selected_chart.page)
                    )
                for role_set in roles.values():
                    role_counts.update(role_set)
            elif not matching:
                status = "no_matching_chart"
            elif len(matching) == 1:
                status = "unique_chart_without_roles"
            else:
                status = "ambiguous_chart"

        status_counts[status] += 1
        if status in _UNRESOLVED_STATUSES:
            unresolved.append({
                "airport": airport,
                "label": label,
                "runway": runway,
                "status": status,
                "matching_charts": len(matching),
                "primary_segments": len(primary),
                "primary_legs": primary_legs,
                "source": _group_source(primary, selected),
            })

    role_evidence_pages = sum(bool(chart.route_fixes) for chart in charts)
    missed_evidence_pages = sum(bool(chart.has_missed_approach) for chart in charts)
    return {
        "version": 1,
        "chart_pages": {
            "total": len(charts),
            "with_route_role_evidence": role_evidence_pages,
            "with_missed_approach_evidence": missed_evidence_pages,
            "matched_to_primary_group": len(matched_pages),
            "selected_for_role_projection": len(selected_role_pages),
            "unmatched_to_primary_group": max(0, len(charts) - len(matched_pages)),
        },
        "procedure_groups": {
            "total": len(groups),
            "complete_primary_legs": complete_primary_groups,
            "role_evidence_used": role_groups,
            "status_counts": dict(sorted(status_counts.items())),
            "unresolved": len(unresolved),
        },
        "role_evidence_counts": dict(sorted(role_counts.items())),
        "unresolved_groups": unresolved,
    }
