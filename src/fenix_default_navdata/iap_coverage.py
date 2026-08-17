from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
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
_CHART_ROLE_EVIDENCE = frozenset({"IAF", "IF", "FAF", "MAP", "MAPT"})
_CHART_TERMINAL_ROLE_EVIDENCE = frozenset({"FAF", "MAP", "MAPT"})
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


def _direct_database_fix_idents(segment: Any) -> set[str]:
    return {
        leg.fix_ident.strip().upper()
        for leg in segment.legs
        if leg.fix_ident and leg.fix_ident.strip()
    }


def _unqualified_rnp_ar_chart(chart: Any, segment: Any) -> bool:
    """Identify an RNP AR plate whose title does not state a variant suffix."""
    title = chart.chart_name.upper()
    base_label = f"R{segment.runway}".upper()
    if (
        "RNP" not in title
        or "(AR)" not in title
        or not segment.label.upper().startswith(base_label + "-")
    ):
        return False
    title_candidates = approach_procedure_name_candidates(
        chart.chart_name,
        chart.runways,
        segment.airport,
    )
    return not any(candidate.startswith(base_label + "-") for candidate in title_candidates)


def _matching_iap_charts_with_selection(
    model: NavModel,
    segment: Any,
) -> tuple[list[Any], str | None]:
    direct_matches = [
        chart
        for chart in model.procedure_charts
        if chart.airport == segment.airport
        and chart.chart_type == "instrument-approach-index"
        and segment.runway in chart.runways
        and segment.label in approach_procedure_name_candidates(
            chart.chart_name, chart.runways, segment.airport,
        )
    ]
    if direct_matches:
        return direct_matches, None

    # Some RNP AR titles omit the database suffix even though separate plates
    # exist. This fallback only accepts a single source plate containing every
    # direct fixed point from the variant's database-coded primary segment.
    required_fixes = _direct_database_fix_idents(segment)
    if len(required_fixes) < 2:
        return [], None
    fixed_point_matches = [
        chart
        for chart in model.procedure_charts
        if chart.airport == segment.airport
        and chart.chart_type == "instrument-approach-index"
        and segment.runway in chart.runways
        and _unqualified_rnp_ar_chart(chart, segment)
        and required_fixes <= {waypoint.strip().upper() for waypoint in chart.waypoints}
    ]
    if len(fixed_point_matches) == 1:
        return fixed_point_matches, "direct_fixed_points"
    return [], None


def matching_iap_charts(model: NavModel, segment: Any) -> list:
    return _matching_iap_charts_with_selection(model, segment)[0]


def _chart_roles(chart: Any) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    for route_fix in chart.route_fixes:
        ident = route_fix.ident.strip().upper()
        role = route_fix.role.strip().upper()
        if ident and role:
            roles.setdefault(ident, set()).add(role)
    return roles


def _chart_source_file(model: NavModel, chart: Any) -> str:
    path = Path(chart.source.file)
    if path.is_absolute():
        try:
            return path.relative_to(model.root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _chart_roles_for_segment(
    model: NavModel,
    chart: Any,
    segment: Any,
) -> dict[str, set[str]]:
    roles = _chart_roles(chart)
    evidence = model.iap_ocr_role_evidence
    source_sha256 = (chart.source.sha256 or "").lower()
    if evidence is None or not source_sha256:
        return roles
    key = (
        segment.airport,
        segment.label,
        segment.runway,
        _chart_source_file(model, chart),
        source_sha256,
    )
    for ident, role_set in evidence.roles_for(key).items():
        roles.setdefault(ident, set()).update(role_set)
    return roles


def _select_iap_chart_with_roles(
    charts: list[Any],
    segment: Any,
    role_evidence,
) -> tuple[Any | None, str | None]:
    """Select one plate only when source legs prove a unique association."""
    if len(charts) == 1:
        return charts[0], "unique_chart"
    if len(charts) < 2 or not segment.legs:
        return None, None

    final_fix = segment.legs[-1].fix_ident.strip().upper() if segment.legs[-1].fix_ident else ""
    if final_fix:
        map_charts = [
            chart
            for chart in charts
            if any(
                ident == final_fix
                and role in {"MAP", "MAPT"}
                for ident, role_set in role_evidence(chart).items()
                for role in role_set
            )
        ]
        if len(map_charts) == 1:
            return map_charts[0], "final_mapt"

    leg_idents = {
        leg.fix_ident.strip().upper()
        for leg in segment.legs
        if leg.fix_ident and leg.fix_ident.strip()
    }
    evidence = {
        id(chart): {
            (ident, role)
            for ident, role_set in role_evidence(chart).items()
            for role in role_set
            if ident in leg_idents and role in _CHART_ROLE_EVIDENCE
        }
        for chart in charts
    }
    supporting = [
        chart
        for chart in charts
        if len({ident for ident, _ in evidence[id(chart)]}) >= 2
        and any(role in _CHART_TERMINAL_ROLE_EVIDENCE for _, role in evidence[id(chart)])
    ]
    if (
        len(supporting) == 1
        and all(
            not evidence[id(chart)]
            for chart in charts
            if chart is not supporting[0]
        )
    ):
        return supporting[0], "multi_role"
    dominant = [
        chart
        for chart in supporting
        if all(
            len({ident for ident, _ in evidence[id(chart)]})
            > len({ident for ident, _ in evidence[id(other)]})
            for other in charts
            if other is not chart
        )
    ]
    if len(dominant) == 1:
        return dominant[0], "dominant_multi_role"
    return None, None


def _select_iap_chart_with_direct_fixes(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select one existing title match only with a unique complete fix set."""
    required_fixes = _direct_database_fix_idents(segment)
    if len(charts) < 2 or len(required_fixes) < 2:
        return None, None
    candidates = [
        chart
        for chart in charts
        if required_fixes <= {waypoint.strip().upper() for waypoint in chart.waypoints}
    ]
    if len(candidates) == 1:
        return candidates[0], "direct_fixed_points"
    return None, None


def _select_iap_chart(
    model: NavModel,
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    direct_chart, direct_selection = _select_iap_chart_with_roles(
        charts, segment, _chart_roles,
    )
    if direct_chart is not None:
        return direct_chart, direct_selection
    direct_fix_chart, direct_fix_selection = _select_iap_chart_with_direct_fixes(
        charts, segment,
    )
    if direct_fix_chart is not None:
        return direct_fix_chart, direct_fix_selection
    if model.iap_ocr_role_evidence is None:
        return None, None
    chart, selection = _select_iap_chart_with_roles(
        charts,
        segment,
        lambda candidate: _chart_roles_for_segment(model, candidate, segment),
    )
    if chart is None or selection is None:
        return None, None
    return chart, f"ocr_{selection}"


def iap_chart_roles(model: NavModel, segment: Any) -> dict[str, set[str]]:
    """Return roles only when one printed approach plate is identifiable."""
    chart, _ = _select_iap_chart(
        model, matching_iap_charts(model, segment), segment,
    )
    if chart is None:
        return {}
    return _chart_roles_for_segment(model, chart, segment)


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


def _matching_leg_roles(segment: Any, roles: dict[str, set[str]]) -> list[dict[str, object]]:
    """Return the selected chart roles that can prove this source segment."""
    leg_idents = {
        leg.fix_ident.strip().upper()
        for leg in segment.legs
        if leg.fix_ident and leg.fix_ident.strip()
    }
    return [
        {"ident": ident, "roles": sorted(role_set & _CHART_ROLE_EVIDENCE)}
        for ident, role_set in sorted(roles.items())
        if ident in leg_idents and role_set & _CHART_ROLE_EVIDENCE
    ]


def _shared_section_group_keys(
    groups: dict[tuple[str, str, str], list[Any]],
) -> set[tuple[str, str, str]]:
    """Identify base-label sections already consumed by same-page variants."""
    primary_by_group = {
        key: [
            segment for segment in selected
            if iap_section_kind(segment) == "approach"
        ]
        for key, selected in groups.items()
    }
    shared: set[tuple[str, str, str]] = set()
    for (airport, label, runway), selected in groups.items():
        if primary_by_group[(airport, label, runway)]:
            continue
        source_pages = {
            (segment.source.file, segment.source.page)
            for segment in selected
            if iap_section_kind(segment) in {
                "approach_transition",
                "missed",
            }
        }
        if source_pages and all(
            any(
                candidate_airport == airport
                and candidate_runway == runway
                and candidate_label.startswith(label + "-")
                and len(primary_by_group[(candidate_airport, candidate_label, candidate_runway)]) == 1
                and (
                    primary_by_group[(candidate_airport, candidate_label, candidate_runway)][0].source.file,
                    primary_by_group[(candidate_airport, candidate_label, candidate_runway)][0].source.page,
                ) == source_page
                for candidate_airport, candidate_label, candidate_runway in groups
            )
            for source_page in source_pages
        ):
            shared.add((airport, label, runway))
    return shared


def analyze_iap_coverage(model: NavModel) -> dict[str, object]:
    """Classify IAP evidence without claiming complete chart decoding."""
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in model.procedure_segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    shared_section_groups = _shared_section_group_keys(groups)

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
    ocr_role_selections: list[dict[str, object]] = []
    source_fixed_point_selections: list[dict[str, object]] = []
    selected_role_pages: set[tuple[str, str, int]] = set()
    matched_pages: set[tuple[str, str, int]] = set()
    complete_primary_groups = 0
    role_groups = 0

    for airport, label, runway in sorted(groups):
        if (airport, label, runway) in shared_section_groups:
            continue
        selected = groups[(airport, label, runway)]
        primary = [
            segment for segment in selected
            if iap_section_kind(segment) == "approach"
        ]
        matching: list[Any] = []
        roles: dict[str, set[str]] = {}
        primary_legs = 0
        match_selection: str | None = None
        if len(primary) != 1:
            status = "no_unique_primary"
        elif not primary[0].legs:
            status = "empty_primary"
        else:
            complete_primary_groups += 1
            primary_legs = len(primary[0].legs)
            matching, match_selection = _matching_iap_charts_with_selection(
                model, primary[0],
            )
            matched_pages.update(
                (chart.airport, chart.filename, chart.page)
                for chart in matching
            )
            selected_chart, selection = _select_iap_chart(
                model, matching, primary[0],
            )
            roles = (
                _chart_roles_for_segment(model, selected_chart, primary[0])
                if selected_chart is not None
                else {}
            )
            matching_roles = _matching_leg_roles(primary[0], roles)
            direct_fixed_selection = (
                match_selection == "direct_fixed_points"
                or selection == "direct_fixed_points"
            )
            if matching_roles:
                role_groups += 1
                status = (
                    "roles_source_fixed_point_chart"
                    if direct_fixed_selection
                    else (
                        "roles_ocr_unique_chart"
                        if selection == "ocr_unique_chart"
                        else (
                            "roles_unique_chart"
                            if selection == "unique_chart"
                            else (
                                "roles_ocr_final_mapt_disambiguated"
                                if selection == "ocr_final_mapt"
                                else (
                                    "roles_final_mapt_disambiguated"
                                    if selection == "final_mapt"
                                    else (
                                        "roles_ocr_multi_role_disambiguated"
                                        if selection == "ocr_multi_role"
                                        else (
                                            "roles_multi_role_disambiguated"
                                            if selection == "multi_role"
                                            else (
                                                "roles_ocr_dominant_multi_role_disambiguated"
                                                if selection == "ocr_dominant_multi_role"
                                                else "roles_dominant_multi_role_disambiguated"
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
                selected_role_pages.add(
                    (selected_chart.airport, selected_chart.filename, selected_chart.page)
                )
                if selection and selection.startswith("ocr_"):
                    ocr_role_selections.append({
                        "airport": airport,
                        "label": label,
                        "runway": runway,
                        "selection": selection,
                        "matching_charts": len(matching),
                        "chart_name": selected_chart.chart_name,
                        "source": _source_report(selected_chart.source),
                        "matching_leg_roles": matching_roles,
                    })
                for evidence in matching_roles:
                    role_counts.update(evidence["roles"])
            if direct_fixed_selection and selected_chart is not None:
                source_fixed_point_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "direct_fixed_points",
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "required_fixes": sorted(_direct_database_fix_idents(primary[0])),
                })
            if not matching_roles and not matching:
                status = "no_matching_chart"
            elif not matching_roles and selected_chart is not None:
                status = "unique_chart_without_roles"
            elif not matching_roles:
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
        "version": 8,
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
            "shared_section_groups": len(shared_section_groups),
            "complete_primary_legs": complete_primary_groups,
            "role_evidence_used": role_groups,
            "status_counts": dict(sorted(status_counts.items())),
            "unresolved": len(unresolved),
        },
        "role_evidence_counts": dict(sorted(role_counts.items())),
        "ocr_role_selections": ocr_role_selections,
        "source_fixed_point_selections": source_fixed_point_selections,
        "unresolved_groups": unresolved,
    }
