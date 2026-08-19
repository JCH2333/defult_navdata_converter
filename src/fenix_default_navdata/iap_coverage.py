from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
import re
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
_RNP_AR_TITLE_QUALIFIER = re.compile(
    r"\((?P<idents>[A-Z][A-Z0-9]{1,7}(?:/[A-Z][A-Z0-9]{1,7})*)\)",
)
_RUNWAY_FIX_IDENT = re.compile(r"RW\d{2}[LRC]?$")
_VARIANT_LABEL = re.compile(
    r"^(?P<base>[A-Z]\d{2}[LRC]?)-(?P<variant>[WXYZ])$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IapPrimaryVariant:
    """A source-proven identity for a same-label RNP/RNP AR primary."""

    chart: Any
    family: str
    rnp_ar: bool
    rnp_ar_missed: bool
    selection: str
    charts: tuple[Any, ...] = ()


def procedure_kind(kind: str) -> str:
    return _PROCEDURE_KIND_MAP.get((kind or "").strip(), "")


def iap_section_kind(segment: Any) -> str:
    kind = procedure_kind(segment.kind)
    if kind == "approach" and segment.transition:
        return "approach_transition"
    return kind


def shared_iap_section_assignments(
    segments: list[Any],
) -> dict[int, tuple[tuple[str, str, str], str]]:
    """Map source-labelled base sections to one uniquely ordered variant.

    CAAC database coding pages often print common transitions or missed
    sections under a base label such as ``R18L``, while the immediately
    following or preceding primary section is explicitly labelled ``R18L-Y``.
    A same-page singleton primary is already sufficient evidence.  When a
    page contains several variants, or the table continues onto the next PDF,
    retain an assignment only if contiguous database-table order reaches one
    primary whose label is the base label plus a suffix.  Any unrelated
    procedure, runway, airport, or non-IAP segment terminates the search.
    """
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    primary_by_group = {
        key: [
            segment for segment in selected
            if iap_section_kind(segment) == "approach"
        ]
        for key, selected in groups.items()
    }
    assignments: dict[int, tuple[tuple[str, str, str], str]] = {}

    def ordered_variant_primary(
        index: int,
        segment: Any,
        direction: int,
    ) -> tuple[Any | None, str | None]:
        cursor = index + direction
        while 0 <= cursor < len(segments):
            candidate = segments[cursor]
            if iap_section_kind(candidate) not in IAP_KINDS:
                return None, None
            if candidate.airport != segment.airport:
                return None, None
            if candidate.runway != segment.runway:
                return None, None
            if candidate.label == segment.label:
                cursor += direction
                continue
            if (
                candidate.label.startswith(segment.label + "-")
                and iap_section_kind(candidate) == "approach"
            ):
                return candidate, (
                    "ordered_next" if direction > 0 else "ordered_previous"
                )
            return None, None
        return None, None

    for index, segment in enumerate(segments):
        kind = iap_section_kind(segment)
        key = (segment.airport, segment.label, segment.runway)
        if (
            kind not in {"approach_transition", "missed"}
            or key not in groups
            or primary_by_group[key]
        ):
            continue
        variants = [
            primary
            for (airport, label, runway), primary_segments in primary_by_group.items()
            if airport == segment.airport
            and runway == segment.runway
            and label.startswith(segment.label + "-")
            for primary in primary_segments
        ]
        same_page = [
            primary for primary in variants
            if (
                primary.source.file == segment.source.file
                and primary.source.page == segment.source.page
            )
        ]
        if len(same_page) == 1:
            selected, selection = same_page[0], "same_page_unique"
        else:
            selected, selection = ordered_variant_primary(
                index,
                segment,
                1 if kind == "approach_transition" else -1,
            )
        if selected is not None and selection is not None:
            assignments[id(segment)] = (
                (selected.airport, selected.label, selected.runway),
                selection,
            )
    return assignments


def inherited_base_primary_assignments(
    segments: list[Any],
) -> dict[tuple[str, str, str], tuple[Any, str]]:
    """Give a missed-only variant the unique unsuffixed same-page primary.

    CAAC database pages may print one unlabelled final approach, then
    separately titled ``复飞 y`` / ``复飞 z`` rows.  Those suffix groups have
    no primary of their own.  Inherit the unique base primary only when the
    variant label is exactly the unsuffixed identity plus a single W/X/Y/Z
    letter, the variant group has no approach section, the unsuffixed group
    has exactly one non-empty approach section, and every variant section
    shares that primary's source page.  Cross-page or non-unique donors stay
    unresolved.
    """
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    primaries = {
        key: [
            segment for segment in selected
            if iap_section_kind(segment) == "approach" and segment.legs
        ]
        for key, selected in groups.items()
    }
    assignments: dict[tuple[str, str, str], tuple[Any, str]] = {}
    for key, selected in groups.items():
        airport, label, runway = key
        match = _VARIANT_LABEL.fullmatch(label)
        if (
            match is None
            or not selected
            or primaries[key]
            or any(iap_section_kind(segment) == "approach" for segment in selected)
        ):
            continue
        donor_key = (airport, match["base"].upper(), runway)
        donors = primaries.get(donor_key, [])
        if len(donors) != 1:
            continue
        donor = donors[0]
        if not all(
            segment.source.file == donor.source.file
            and segment.source.page == donor.source.page
            for segment in selected
        ):
            continue
        assignments[key] = (donor, "same_page_unique_base_primary")
    return assignments


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


def _plain_ils_chart(chart: Any) -> bool:
    """Identify a chart explicitly titled as ILS without an RNAV/RNP qualifier."""
    title = chart.chart_name.upper()
    return "ILS" in title and "RNAV" not in title and "RNP" not in title


def _plain_rnp_chart(chart: Any) -> bool:
    """Identify a non-AR RNP chart without an ILS title component."""
    title = chart.chart_name.upper()
    return "RNP" in title and "ILS" not in title and "(AR)" not in title


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
        # ``RNP ILS/DME`` titles deliberately expose both RNP and ILS name
        # candidates.  A database-coded ``Ixx`` primary is nevertheless an
        # explicit ILS identity.  When the source also contains exactly one
        # non-RNP ILS plate, retain that narrower direct title match instead
        # of treating an RNP ILS plate as the same primary.
        if segment.label.upper().startswith("I"):
            plain_ils_matches = [
                chart for chart in direct_matches if _plain_ils_chart(chart)
            ]
            if len(plain_ils_matches) == 1:
                return plain_ils_matches, "plain_ils_title"
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


def _rnp_ar_title_qualifier_idents(chart: Any) -> tuple[str, ...]:
    """Return explicit non-runway fix names printed after a RNP AR marker."""
    title = chart.chart_name.upper()
    marker = title.find("(AR)")
    if "RNP" not in title or marker < 0:
        return ()
    return tuple(
        ident
        for match in _RNP_AR_TITLE_QUALIFIER.finditer(title[marker + len("(AR)"):])
        for ident in match["idents"].split("/")
        if not _RUNWAY_FIX_IDENT.fullmatch(ident)
    )


def _title_qualifier_matching_fixes(chart: Any, segment: Any) -> tuple[str, ...]:
    required_fixes = _direct_database_fix_idents(segment)
    return tuple(
        ident
        for ident in _rnp_ar_title_qualifier_idents(chart)
        if ident in required_fixes
    )


def _direct_chart_roles_for_segment(chart: Any, segment: Any) -> dict[str, set[str]]:
    """Return direct printed role labels that intersect source primary legs."""
    required_fixes = _direct_database_fix_idents(segment)
    return {
        ident: roles & _CHART_ROLE_EVIDENCE
        for ident, roles in _chart_roles(chart).items()
        if ident in required_fixes and roles & _CHART_ROLE_EVIDENCE
    }


def _pure_rnp_family_role_charts(charts: list[Any]) -> bool:
    """True when every candidate is one ILS-free RNP family."""
    if len(charts) < 2:
        return False
    titles = [chart.chart_name.upper() for chart in charts]
    if not all("RNP" in title and "ILS" not in title for title in titles):
        return False
    ar_titles = {"(AR)" in title for title in titles}
    if len(ar_titles) != 1:
        return False
    if ar_titles == {False} and len(set(titles)) != len(titles):
        return False
    return True


def _consensus_direct_chart_roles(
    charts: list[Any],
    segment: Any,
) -> dict[str, set[str]]:
    """Return role flags every compatible source chart prints identically.

    A database primary can be shared by separately titled pure RNP chart
    variants. When every page belongs to one RNP family (all AR or all
    non-AR) and marks the same source legs with exactly the same non-empty
    roles, the flags do not depend on choosing one variant. This permits role
    projection without inferring a chart-to-variant mapping. Mixed RNP/ILS
    and mixed AR/non-AR candidates retain their stricter existing selection
    rules.
    """
    if not _pure_rnp_family_role_charts(charts):
        return {}
    evidence = [
        _direct_chart_roles_for_segment(chart, segment)
        for chart in charts
    ]
    if not evidence or not evidence[0]:
        return {}
    if any(candidate != evidence[0] for candidate in evidence[1:]):
        return {}
    return evidence[0]


def _intersecting_direct_chart_roles(
    charts: list[Any],
    segment: Any,
) -> dict[str, set[str]]:
    """Return shared primary-leg roles after unique chart selection failed.

    A remaining RNP family may still agree on a non-empty subset of source
    roles even when the complete maps differ. Project that intersection
    without selecting a variant. An ident assigned disjoint roles is a
    conflict and rejects the group. Extra roles printed on only some pages
    are omitted. Mixed ILS, mixed AR/non-AR, duplicate non-AR titles, a
    roleless candidate, or an empty intersection leave the group unresolved.
    """
    if not _pure_rnp_family_role_charts(charts):
        return {}
    evidence = [
        _direct_chart_roles_for_segment(chart, segment)
        for chart in charts
    ]
    if not evidence or any(not candidate for candidate in evidence):
        return {}
    shared: dict[str, set[str]] = {}
    for ident in sorted(set().union(*(candidate.keys() for candidate in evidence))):
        role_sets = [candidate[ident] for candidate in evidence if ident in candidate]
        common = set.intersection(*role_sets)
        if not common:
            if len(role_sets) >= 2:
                return {}
            continue
        if len(role_sets) != len(evidence):
            continue
        shared[ident] = common
    return shared


def _rnp_subset_direct_chart_roles(chart: Any, segment: Any) -> dict[str, set[str]]:
    """Discard a mixed RNP/ILS page's IF marker when no source IF leg exists.

    A combined RNP/ILS plate can print an IF marker for its ILS path while the
    same fixed point occurs as an RF leg in an RNP database primary. That
    marker cannot identify the RNP primary's IF leg, so it must not veto an
    otherwise unanimous pure-RNP subset. This narrow compatibility filter is
    intentionally limited to the combined-title case and the IF role.
    """
    roles = _direct_chart_roles_for_segment(chart, segment)
    title = chart.chart_name.upper()
    if "RNP" not in title or "ILS" not in title:
        return roles
    source_leg_types: dict[str, set[str]] = {}
    for leg in segment.legs:
        if leg.fix_ident:
            source_leg_types.setdefault(leg.fix_ident.strip().upper(), set()).add(
                leg.leg_type.upper()
            )
    compatible: dict[str, set[str]] = {}
    for ident, role_set in roles.items():
        retained = set(role_set)
        if "IF" in retained and "IF" not in source_leg_types.get(ident, set()):
            retained.remove("IF")
        if retained:
            compatible[ident] = retained
    return compatible


def _rnp_subset_consensus_direct_chart_roles(
    charts: list[Any],
    segment: Any,
) -> dict[str, set[str]]:
    """Return a pure-RNP consensus when remaining charts prove no primary roles.

    Some database primaries explicitly encode every leg as RNP while the chart
    index lists several procedures for the same runway. If at least two
    pure-RNP pages agree on non-empty direct roles and every remaining
    title-compatible candidate contributes no direct role for the primary, the
    shared flags are safe to project without selecting a chart variant. A
    role-bearing page that disagrees with the consensus remains a conflict and
    leaves the group unresolved.
    """
    rnp_charts = [
        chart
        for chart in charts
        if "RNP" in chart.chart_name.upper()
        and "ILS" not in chart.chart_name.upper()
    ]
    other_charts = [chart for chart in charts if chart not in rnp_charts]
    if len(rnp_charts) < 2:
        return {}
    if not segment.legs or not all(
        "RNP" in (leg.raw or "").upper()
        for leg in segment.legs
    ):
        return {}
    titles = [chart.chart_name.upper() for chart in rnp_charts]
    ar_titles = {"(AR)" in title for title in titles}
    if len(ar_titles) != 1:
        return {}
    if ar_titles == {False} and len(set(titles)) != len(titles):
        return {}
    evidence = [
        _rnp_subset_direct_chart_roles(chart, segment)
        for chart in rnp_charts
    ]
    supporting = [candidate for candidate in evidence if candidate]
    if len(supporting) < 2:
        return {}
    if any(candidate and candidate != supporting[0] for candidate in evidence):
        return {}
    if any(
        _rnp_subset_direct_chart_roles(chart, segment)
        for chart in other_charts
    ):
        return {}
    return supporting[0]


def _select_iap_chart_with_rnp_ar_title_qualifier(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select only one RNP AR chart whose printed qualifier is a source leg.

    Some RNP AR chart titles distinguish otherwise title-compatible plates by
    an additional parenthesized terminal fix.  This is usable only when every
    candidate is an RNP AR title carrying such a qualifier, and exactly one
    candidate's qualifier occurs in the ordered primary database legs.
    """
    if len(charts) < 2:
        return None, None
    qualifiers = {
        id(chart): _rnp_ar_title_qualifier_idents(chart)
        for chart in charts
    }
    if not all(qualifiers[id(chart)] for chart in charts):
        return None, None
    matching = [
        chart
        for chart in charts
        if _title_qualifier_matching_fixes(chart, segment)
    ]
    if len(matching) == 1:
        return matching[0], "rnp_ar_title_qualifier"
    return None, None


def _unqualified_rnp_ar_direct_roles(chart: Any, segment: Any) -> dict[str, set[str]]:
    """Return direct chart roles that intersect one unqualified RNP AR primary."""
    title = chart.chart_name.upper()
    if (
        "RNP" not in title
        or "(AR)" not in title
        or _rnp_ar_title_qualifier_idents(chart)
    ):
        return {}
    return _direct_chart_roles_for_segment(chart, segment)


def _select_iap_chart_with_unqualified_rnp_ar_direct_role(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select one unqualified RNP AR plate by a unique direct role intersection.

    This covers otherwise identical RNP AR titles only when every candidate is
    unqualified and exactly one source chart explicitly assigns an IAF, IF,
    FAF, MAP, or MAPT role to a database primary leg. A title qualifier, a
    non-RNP AR candidate, or more than one direct role match remains ambiguous.
    """
    if len(charts) < 2:
        return None, None
    if not all(
        "RNP" in chart.chart_name.upper()
        and "(AR)" in chart.chart_name.upper()
        and not _rnp_ar_title_qualifier_idents(chart)
        for chart in charts
    ):
        return None, None
    matching = [
        chart
        for chart in charts
        if _unqualified_rnp_ar_direct_roles(chart, segment)
    ]
    if len(matching) == 1:
        return matching[0], "rnp_ar_unique_direct_role"
    return None, None


def _select_iap_chart_with_unique_direct_role(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select one title-compatible plate by a unique direct source-role match.

    A direct role label is usable when exactly one distinct title candidate
    intersects the source primary legs. RNP AR candidates must not be mixed
    with non-AR titles, and qualified/unqualified AR plates remain separate
    categories.
    """
    if len(charts) < 2:
        return None, None
    titles = {
        re.sub(r"\s+", " ", chart.chart_name or "").strip().upper()
        for chart in charts
    }
    if len(titles) != len(charts):
        return None, None
    rnp_ar = ["RNP" in chart.chart_name.upper() and "(AR)" in chart.chart_name.upper() for chart in charts]
    if any(rnp_ar) and not all(rnp_ar):
        return None, None
    if all(rnp_ar) and len({bool(_rnp_ar_title_qualifier_idents(chart)) for chart in charts}) != 1:
        return None, None
    matching = [
        chart
        for chart in charts
        if _direct_chart_roles_for_segment(chart, segment)
    ]
    if len(matching) == 1:
        return matching[0], "unique_direct_role"
    return None, None


def _select_iap_chart_with_dominant_direct_role(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select one title-compatible plate only for a strict direct-role superset."""
    if len(charts) < 2:
        return None, None
    titles = {
        re.sub(r"\s+", " ", chart.chart_name or "").strip().upper()
        for chart in charts
    }
    if len(titles) != len(charts):
        return None, None
    rnp_ar = ["RNP" in chart.chart_name.upper() and "(AR)" in chart.chart_name.upper() for chart in charts]
    if any(rnp_ar) and not all(rnp_ar):
        return None, None
    if all(rnp_ar) and len({bool(_rnp_ar_title_qualifier_idents(chart)) for chart in charts}) != 1:
        return None, None
    evidence = {
        id(chart): {
            (ident, role)
            for ident, roles in _direct_chart_roles_for_segment(chart, segment).items()
            for role in roles
        }
        for chart in charts
    }
    dominant = [
        chart
        for chart in charts
        if evidence[id(chart)] and all(
            evidence[id(other)] < evidence[id(chart)]
            for other in charts
            if other is not chart
        )
    ]
    if len(dominant) == 1:
        return dominant[0], "dominant_direct_role"
    return None, None


def _select_iap_chart_with_unique_first_if(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Select only one chart that directly marks the first source IF leg."""
    if len(charts) < 2 or not segment.legs:
        return None, None
    first_leg = segment.legs[0]
    first_ident = (first_leg.fix_ident or "").strip().upper()
    if first_leg.leg_type != "IF" or not first_ident:
        return None, None
    matches = [
        chart
        for chart in charts
        if "IF" in _direct_chart_roles_for_segment(chart, segment).get(
            first_ident, set(),
        )
    ]
    if len(matches) == 1:
        return matches[0], "unique_first_if"
    return None, None


def _select_iap_chart_with_plain_rnp_title(
    charts: list[Any],
    segment: Any,
) -> tuple[Any | None, str | None]:
    """Resolve one plain RNP plate only after equivalent direct evidence."""
    if len(charts) != 2 or not segment.label.upper().startswith("R"):
        return None, None
    plain_rnp = [chart for chart in charts if _plain_rnp_chart(chart)]
    rnp_ils = [
        chart
        for chart in charts
        if (
            "RNP" in chart.chart_name.upper()
            and "ILS" in chart.chart_name.upper()
            and "(AR)" not in chart.chart_name.upper()
        )
    ]
    direct_evidence = [
        {
            (ident, role)
            for ident, roles in _direct_chart_roles_for_segment(chart, segment).items()
            for role in roles
        }
        for chart in charts
    ]
    if (
        len(plain_rnp) == len(rnp_ils) == 1
        and direct_evidence[0]
        and direct_evidence[0] == direct_evidence[1]
    ):
        return plain_rnp[0], "plain_rnp_title"
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
    title_qualifier_chart, title_qualifier_selection = (
        _select_iap_chart_with_rnp_ar_title_qualifier(charts, segment)
    )
    if title_qualifier_chart is not None:
        return title_qualifier_chart, title_qualifier_selection
    direct_role_chart, direct_role_selection = (
        _select_iap_chart_with_unqualified_rnp_ar_direct_role(charts, segment)
    )
    if direct_role_chart is not None:
        return direct_role_chart, direct_role_selection
    unique_direct_role_chart, unique_direct_role_selection = (
        _select_iap_chart_with_unique_direct_role(charts, segment)
    )
    if unique_direct_role_chart is not None:
        return unique_direct_role_chart, unique_direct_role_selection
    dominant_direct_role_chart, dominant_direct_role_selection = (
        _select_iap_chart_with_dominant_direct_role(charts, segment)
    )
    if dominant_direct_role_chart is not None:
        return dominant_direct_role_chart, dominant_direct_role_selection
    first_if_chart, first_if_selection = _select_iap_chart_with_unique_first_if(
        charts, segment,
    )
    if first_if_chart is not None:
        return first_if_chart, first_if_selection
    plain_rnp_chart, plain_rnp_selection = _select_iap_chart_with_plain_rnp_title(
        charts, segment,
    )
    if plain_rnp_chart is not None:
        return plain_rnp_chart, plain_rnp_selection
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


def _chart_approach_family(chart: Any) -> str:
    title = chart.chart_name.upper()
    if "RNP" in title:
        return "RNP_AR" if "(AR)" in title else "RNP"
    if "ILS" in title:
        return "ILS"
    return ""


def _direct_primary_variant(
    model: NavModel,
    segment: Any,
) -> IapPrimaryVariant | None:
    """Accept a multiple-primary identity only through direct fixed points."""
    matching, match_selection = _matching_iap_charts_with_selection(model, segment)
    chart, selection = _select_iap_chart_with_direct_fixes(matching, segment)
    if (
        chart is None
        and match_selection == "direct_fixed_points"
        and len(matching) == 1
    ):
        chart, selection = matching[0], match_selection
    if chart is None or selection != "direct_fixed_points":
        return None
    family = _chart_approach_family(chart)
    if family not in {"RNP", "RNP_AR"}:
        return None
    return IapPrimaryVariant(
        chart=chart,
        family=family,
        rnp_ar=family == "RNP_AR",
        rnp_ar_missed=family == "RNP_AR" and bool(chart.has_missed_approach),
        selection=selection,
    )


def _section_variant_owner(
    section: Any,
    primary: list[Any],
    variants: dict[int, IapPrimaryVariant | None],
) -> IapPrimaryVariant | None:
    """Map one non-primary section to an already proven primary identity.

    A same database-coding page is the strongest association.  Some CAAC
    pages print an otherwise complete missed approach on a separate page, so
    permit that only when every direct database fixed point appears on exactly
    one of the already selected source approach plates.  This never creates a
    chart association from OCR or a partial fixed-point overlap.
    """
    source_owners = [
        candidate
        for candidate in primary
        if (
            section.source.file == candidate.source.file
            and section.source.page == candidate.source.page
            and (
                not section.approach_family
                or section.approach_family == variants[id(candidate)].family
            )
        )
    ]
    if len(source_owners) == 1:
        return variants[id(source_owners[0])]

    if section.approach_family:
        family_owners = [
            candidate
            for candidate in primary
            if variants[id(candidate)].family == section.approach_family
        ]
        if len(family_owners) == 1:
            return variants[id(family_owners[0])]

    required_fixes = _direct_database_fix_idents(section)
    if len(required_fixes) < 2:
        return None
    fixed_point_owners = [
        candidate
        for candidate in primary
        if (
            not section.approach_family
            or section.approach_family == variants[id(candidate)].family
        )
        and required_fixes <= {
            waypoint.strip().upper()
            for waypoint in variants[id(candidate)].chart.waypoints
        }
    ]
    if len(fixed_point_owners) == 1:
        return variants[id(fixed_point_owners[0])]
    return None



def _owned_variant_charts(variant: IapPrimaryVariant) -> tuple[Any, ...]:
    return variant.charts or ((variant.chart,) if variant.chart is not None else ())


def _roles_from_owned_charts(charts: tuple[Any, ...] | list[Any], segment: Any) -> dict[str, set[str]]:
    """Project roles from charts already owned by one partitioned primary.

    A single owned plate contributes its printed roles. Two or more plates may
    only contribute identical consensus roles or, failing that, the non-empty
    intersection of direct primary-leg roles. This never selects a chart.
    """
    owned = list(charts)
    if not owned:
        return {}
    if len(owned) == 1:
        return _direct_chart_roles_for_segment(owned[0], segment)
    consensus = _consensus_direct_chart_roles(owned, segment)
    if consensus:
        return consensus
    return _intersecting_direct_chart_roles(owned, segment)


def _qualifier_owned_rnp_ar_variants(
    model: NavModel,
    primary: list[Any],
    selected: list[Any],
) -> dict[int, IapPrimaryVariant] | None:
    """Partition same-label RNP AR primaries by unique title-qualifier owners.

    Every matching plate must be an ILS-free RNP AR chart whose title names a
    non-runway fix, and each of those fixes may appear on exactly one chart.
    Each primary must occupy a distinct database page. Each named transition
    must sit on one of those pages and uniquely own one chart, every chart
    must be owned, and remaining IAP sections must share a primary page.
    Overlapping ownership, leftover charts, mixed ILS, or two primaries on
    the same page keep the complete group unresolved.
    """
    if len(primary) < 2 or any(not segment.legs for segment in primary):
        return None
    if any(
        segment.approach_family and segment.approach_family != "RNP_AR"
        for segment in selected
    ):
        return None
    primary_pages = {
        (segment.source.file, segment.source.page): segment
        for segment in primary
    }
    if len(primary_pages) != len(primary):
        return None
    matching = matching_iap_charts(model, primary[0])
    if not matching or any(
        matching_iap_charts(model, segment) != matching for segment in primary[1:]
    ):
        return None
    if any(
        "RNP" not in chart.chart_name.upper()
        or "ILS" in chart.chart_name.upper()
        or "(AR)" not in chart.chart_name.upper()
        or not _rnp_ar_title_qualifier_idents(chart)
        for chart in matching
    ):
        return None
    ident_to_charts: dict[str, list[Any]] = {}
    for chart in matching:
        for ident in _rnp_ar_title_qualifier_idents(chart):
            ident_to_charts.setdefault(ident, []).append(chart)
    if any(len(charts) != 1 for charts in ident_to_charts.values()):
        return None
    ident_to_chart = {ident: charts[0] for ident, charts in ident_to_charts.items()}
    transitions = [
        section for section in selected
        if iap_section_kind(section) == "approach_transition"
    ]
    claimed_charts: dict[int, int] = {}
    owned_by_primary: dict[int, list[Any]] = {id(segment): [] for segment in primary}
    seen_names: set[str] = set()
    for transition in transitions:
        name = (transition.transition or "").strip().upper()
        page = (transition.source.file, transition.source.page)
        if (
            not name
            or name in seen_names
            or name not in ident_to_chart
            or page not in primary_pages
        ):
            return None
        seen_names.add(name)
        owner = primary_pages[page]
        chart = ident_to_chart[name]
        previous = claimed_charts.get(id(chart))
        if previous is not None and previous != id(owner):
            return None
        claimed_charts[id(chart)] = id(owner)
        if chart not in owned_by_primary[id(owner)]:
            owned_by_primary[id(owner)].append(chart)
    if len(claimed_charts) != len(matching):
        return None
    if any(not owned_by_primary[id(segment)] for segment in primary):
        return None
    for section in selected:
        if iap_section_kind(section) == "approach":
            continue
        if (section.source.file, section.source.page) not in primary_pages:
            return None
    assignments: dict[int, IapPrimaryVariant] = {}
    for segment in primary:
        owned = tuple(
            sorted(
                owned_by_primary[id(segment)],
                key=lambda chart: (chart.filename, chart.chart_name),
            )
        )
        assignments[id(segment)] = IapPrimaryVariant(
            chart=owned[0],
            family="RNP_AR",
            rnp_ar=True,
            rnp_ar_missed=any(chart.has_missed_approach for chart in owned),
            selection="rnp_ar_title_qualifier",
            charts=owned,
        )
    for section in selected:
        if iap_section_kind(section) == "approach":
            continue
        owner = primary_pages[(section.source.file, section.source.page)]
        assignments[id(section)] = assignments[id(owner)]
    return assignments


def _variant_for_segment(model: NavModel, segment: Any) -> IapPrimaryVariant | None:
    """Recover a partitioned identity without depending on object identity.

    BGL projection copies primary segments with replace(), so callers must
    match airport, label, runway, and the original database page.
    """
    assignments = iap_multi_primary_section_assignments(model)
    for assigned in model.procedure_segments:
        variant = assignments.get(id(assigned))
        if variant is None:
            continue
        if (
            assigned.airport == segment.airport
            and assigned.label == segment.label
            and assigned.runway == segment.runway
            and assigned.source.file == segment.source.file
            and assigned.source.page == segment.source.page
        ):
            return variant
    return None


def iap_multi_primary_section_assignments(
    model: NavModel,
) -> dict[int, IapPrimaryVariant]:
    """Resolve a group only when every source section has exactly one owner.

    Generic ``Rxx`` rows can represent both RNP and RNP AR.  Each primary must
    have a distinct chart family selected by complete direct fixed points.  A
    transition or missed section must then share a page with a compatible
    target family or fully match one selected chart by direct fixed points.
    Same-label RNP AR primaries may instead be partitioned by unique chart
    title qualifiers and same-page ownership. Partial evidence keeps the
    complete group out.
    """
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in model.procedure_segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    assignments: dict[int, IapPrimaryVariant] = {}
    for selected in groups.values():
        primary = [
            segment for segment in selected
            if iap_section_kind(segment) == "approach"
        ]
        if len(primary) < 2:
            continue
        variants = {
            id(segment): _direct_primary_variant(model, segment)
            for segment in primary
        }
        resolved = [variant for variant in variants.values() if variant is not None]
        if len(resolved) != len(primary) or len({variant.family for variant in resolved}) != len(primary):
            qualifier = _qualifier_owned_rnp_ar_variants(model, primary, selected)
            if qualifier is not None:
                assignments.update(qualifier)
            continue
        group_assignments = {
            id(segment): variants[id(segment)]
            for segment in primary
        }
        for section in selected:
            if iap_section_kind(section) == "approach":
                continue
            owner = _section_variant_owner(section, primary, variants)
            if owner is None:
                break
            group_assignments[id(section)] = owner
        else:
            assignments.update(group_assignments)
            continue
        qualifier = _qualifier_owned_rnp_ar_variants(model, primary, selected)
        if qualifier is not None:
            assignments.update(qualifier)
    return assignments


def iap_multi_primary_variants(model: NavModel) -> dict[int, IapPrimaryVariant]:
    """Return only proven primary identities for same-label IAP groups."""
    assignments = iap_multi_primary_section_assignments(model)
    return {
        id(segment): variant
        for segment in model.procedure_segments
        if iap_section_kind(segment) == "approach"
        if (variant := assignments.get(id(segment))) is not None
    }


def iap_chart_roles(model: NavModel, segment: Any) -> dict[str, set[str]]:
    """Return roles only when one printed approach plate is identifiable."""
    variant = _variant_for_segment(model, segment)
    if variant is not None and variant.selection == "rnp_ar_title_qualifier":
        return _roles_from_owned_charts(_owned_variant_charts(variant), segment)
    charts = matching_iap_charts(model, segment)
    consensus = _consensus_direct_chart_roles(charts, segment)
    if consensus:
        return consensus
    rnp_subset_consensus = _rnp_subset_consensus_direct_chart_roles(
        charts,
        segment,
    )
    if rnp_subset_consensus:
        return rnp_subset_consensus
    chart, _ = _select_iap_chart(model, charts, segment)
    if chart is not None:
        return _chart_roles_for_segment(model, chart, segment)
    intersecting = _intersecting_direct_chart_roles(charts, segment)
    if intersecting:
        return intersecting
    return {}


def _iap_role_status(selection: str | None, direct_fixed_selection: bool) -> str:
    if direct_fixed_selection:
        return "roles_source_fixed_point_chart"
    if selection == "rnp_ar_title_qualifier":
        return "roles_source_title_qualifier_chart"
    if selection == "rnp_ar_unique_direct_role":
        return "roles_source_unqualified_rnp_ar_direct_role_chart"
    if selection == "unique_direct_role":
        return "roles_source_unique_direct_role_chart"
    if selection == "dominant_direct_role":
        return "roles_source_dominant_direct_role_chart"
    if selection == "consensus_direct_roles":
        return "roles_source_consensus_direct_chart"
    if selection == "rnp_subset_consensus_direct_roles":
        return "roles_source_rnp_subset_consensus_direct_chart"
    if selection == "intersecting_direct_roles":
        return "roles_source_intersecting_direct_chart"
    if selection == "plain_rnp_title":
        return "roles_source_plain_rnp_title_chart"
    if selection == "unique_first_if":
        return "roles_source_unique_first_if_chart"
    return {
        "ocr_unique_chart": "roles_ocr_unique_chart",
        "unique_chart": "roles_unique_chart",
        "ocr_final_mapt": "roles_ocr_final_mapt_disambiguated",
        "final_mapt": "roles_final_mapt_disambiguated",
        "ocr_multi_role": "roles_ocr_multi_role_disambiguated",
        "multi_role": "roles_multi_role_disambiguated",
        "ocr_dominant_multi_role": "roles_ocr_dominant_multi_role_disambiguated",
    }.get(selection, "roles_dominant_multi_role_disambiguated")


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
    assignments: dict[int, tuple[tuple[str, str, str], str]],
) -> set[tuple[str, str, str]]:
    """Identify base groups whose every source section has a unique target."""
    return {
        key for key, selected in groups.items()
        if not any(iap_section_kind(segment) == "approach" for segment in selected)
        and bool(selected)
        and all(id(segment) in assignments for segment in selected)
    }


def analyze_iap_coverage(model: NavModel) -> dict[str, object]:
    """Classify IAP evidence without claiming complete chart decoding."""
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for segment in model.procedure_segments:
        if iap_section_kind(segment) in IAP_KINDS:
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    shared_assignments = shared_iap_section_assignments(model.procedure_segments)
    shared_section_groups = _shared_section_group_keys(groups, shared_assignments)
    multi_primary_variants = iap_multi_primary_variants(model)
    inherited_base_primaries = inherited_base_primary_assignments(
        model.procedure_segments,
    )

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
    source_title_qualifier_selections: list[dict[str, object]] = []
    source_unqualified_rnp_ar_direct_role_selections: list[dict[str, object]] = []
    source_unique_direct_role_selections: list[dict[str, object]] = []
    source_dominant_direct_role_selections: list[dict[str, object]] = []
    source_consensus_direct_role_selections: list[dict[str, object]] = []
    source_rnp_subset_consensus_direct_role_selections: list[dict[str, object]] = []
    source_intersecting_direct_role_selections: list[dict[str, object]] = []
    source_plain_rnp_title_selections: list[dict[str, object]] = []
    source_unique_first_if_selections: list[dict[str, object]] = []
    source_incomplete_chart_title_matches: list[dict[str, object]] = []
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
        resolved_multi_primary = (
            len(primary) > 1
            and all(id(segment) in multi_primary_variants for segment in primary)
        )
        if (
            not resolved_multi_primary
            and len(primary) != 1
            and (inherited := inherited_base_primaries.get((airport, label, runway)))
            and not primary
        ):
            donor, _inherited_selection = inherited
            primary = [replace(donor, label=label)]
        if not primary:
            title_matches = [
                chart
                for chart in charts
                if chart.airport == airport
                and runway in chart.runways
                and label in approach_procedure_name_candidates(
                    chart.chart_name,
                    chart.runways,
                    airport,
                )
            ]
            if title_matches:
                source_incomplete_chart_title_matches.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "source_sections": sorted({
                        iap_section_kind(segment) for segment in selected
                    }),
                    "charts": [
                        {
                            "chart_name": chart.chart_name,
                            "source": _source_report(chart.source),
                        }
                        for chart in title_matches
                    ],
                })
        if resolved_multi_primary:
            title_qualifier_partition = all(
                multi_primary_variants[id(segment)].selection == "rnp_ar_title_qualifier"
                for segment in primary
            )
            status = (
                "multiple_primary_rnp_ar_title_qualifier"
                if title_qualifier_partition
                else "multiple_primary_direct_fixed_points"
            )
            complete_primary_groups += len(primary)
            for segment in primary:
                variant = multi_primary_variants[id(segment)]
                owned_charts = _owned_variant_charts(variant)
                selected_chart = variant.chart
                matched_pages.update(
                    (chart.airport, chart.filename, chart.page)
                    for chart in owned_charts
                )
                if title_qualifier_partition:
                    roles = _roles_from_owned_charts(owned_charts, segment)
                else:
                    roles = _chart_roles_for_segment(model, selected_chart, segment)
                matching_roles = _matching_leg_roles(segment, roles)
                if matching_roles:
                    role_groups += 1
                    if not title_qualifier_partition:
                        selected_role_pages.add((
                            selected_chart.airport,
                            selected_chart.filename,
                            selected_chart.page,
                        ))
                    for evidence in matching_roles:
                        role_counts.update(evidence["roles"])
                if title_qualifier_partition:
                    continue
                source_fixed_point_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "direct_fixed_points",
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "required_fixes": sorted(_direct_database_fix_idents(segment)),
                })
        elif len(primary) != 1:
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
            consensus_roles = _consensus_direct_chart_roles(matching, primary[0])
            if consensus_roles:
                selected_chart, selection, roles = (
                    None,
                    "consensus_direct_roles",
                    consensus_roles,
                )
            else:
                rnp_subset_consensus_roles = _rnp_subset_consensus_direct_chart_roles(
                    matching,
                    primary[0],
                )
                if rnp_subset_consensus_roles:
                    selected_chart, selection, roles = (
                        None,
                        "rnp_subset_consensus_direct_roles",
                        rnp_subset_consensus_roles,
                    )
                else:
                    selected_chart, selection = _select_iap_chart(
                        model, matching, primary[0],
                    )
                    if selected_chart is not None:
                        roles = _chart_roles_for_segment(
                            model, selected_chart, primary[0],
                        )
                    else:
                        intersecting_roles = _intersecting_direct_chart_roles(
                            matching,
                            primary[0],
                        )
                        if intersecting_roles:
                            selected_chart, selection, roles = (
                                None,
                                "intersecting_direct_roles",
                                intersecting_roles,
                            )
                        else:
                            roles = {}
            matching_roles = _matching_leg_roles(primary[0], roles)
            direct_fixed_selection = (
                match_selection == "direct_fixed_points"
                or selection == "direct_fixed_points"
            )
            title_qualifier_selection = selection == "rnp_ar_title_qualifier"
            unqualified_rnp_ar_direct_role_selection = (
                selection == "rnp_ar_unique_direct_role"
            )
            unique_direct_role_selection = selection == "unique_direct_role"
            dominant_direct_role_selection = selection == "dominant_direct_role"
            plain_rnp_title_selection = selection == "plain_rnp_title"
            unique_first_if_selection = selection == "unique_first_if"
            if matching_roles:
                role_groups += 1
                status = _iap_role_status(selection, direct_fixed_selection)
                if selected_chart is not None:
                    selected_role_pages.add(
                        (
                            selected_chart.airport,
                            selected_chart.filename,
                            selected_chart.page,
                        )
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
            if title_qualifier_selection and selected_chart is not None:
                source_title_qualifier_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "rnp_ar_title_qualifier",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "title_qualifier_fixes": list(
                        _title_qualifier_matching_fixes(selected_chart, primary[0])
                    ),
                })
            if unqualified_rnp_ar_direct_role_selection and selected_chart is not None:
                source_unqualified_rnp_ar_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "rnp_ar_unique_direct_role",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(roles),
                        }
                        for ident, roles in sorted(
                            _unqualified_rnp_ar_direct_roles(
                                selected_chart, primary[0],
                            ).items()
                        )
                    ],
                })
            if unique_direct_role_selection and selected_chart is not None:
                source_unique_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "unique_direct_role",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(roles),
                        }
                        for ident, roles in sorted(
                            _direct_chart_roles_for_segment(
                                selected_chart, primary[0],
                            ).items()
                        )
                    ],
                })
            if dominant_direct_role_selection and selected_chart is not None:
                source_dominant_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "dominant_direct_role",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(roles),
                        }
                        for ident, roles in sorted(
                            _direct_chart_roles_for_segment(
                                selected_chart, primary[0],
                            ).items()
                        )
                    ],
                })
            if selection == "consensus_direct_roles":
                source_consensus_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "consensus_direct_roles",
                    "matching_charts": len(matching),
                    "candidates": [
                        {
                            "chart_name": chart.chart_name,
                            "source": _source_report(chart.source),
                        }
                        for chart in matching
                    ],
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(role_set),
                        }
                        for ident, role_set in sorted(roles.items())
                    ],
                })
            if selection == "intersecting_direct_roles":
                source_intersecting_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "intersecting_direct_roles",
                    "matching_charts": len(matching),
                    "candidates": [
                        {
                            "chart_name": chart.chart_name,
                            "source": _source_report(chart.source),
                        }
                        for chart in matching
                    ],
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(role_set),
                        }
                        for ident, role_set in sorted(roles.items())
                    ],
                })
            if selection == "rnp_subset_consensus_direct_roles":
                rnp_candidates = [
                    chart
                    for chart in matching
                    if "RNP" in chart.chart_name.upper()
                    and "ILS" not in chart.chart_name.upper()
                ]
                source_rnp_subset_consensus_direct_role_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "rnp_subset_consensus_direct_roles",
                    "matching_charts": len(matching),
                    "rnp_candidates": [
                        {
                            "chart_name": chart.chart_name,
                            "source": _source_report(chart.source),
                        }
                        for chart in rnp_candidates
                    ],
                    "other_candidates_without_direct_roles": [
                        {
                            "chart_name": chart.chart_name,
                            "source": _source_report(chart.source),
                        }
                        for chart in matching
                        if chart not in rnp_candidates
                    ],
                    "matching_roles": [
                        {
                            "ident": ident,
                            "roles": sorted(role_set),
                        }
                        for ident, role_set in sorted(roles.items())
                    ],
                })
            if plain_rnp_title_selection and selected_chart is not None:
                source_plain_rnp_title_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "plain_rnp_title",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                })
            if unique_first_if_selection and selected_chart is not None:
                source_unique_first_if_selections.append({
                    "airport": airport,
                    "label": label,
                    "runway": runway,
                    "selection": "unique_first_if",
                    "matching_charts": len(matching),
                    "chart_name": selected_chart.chart_name,
                    "source": _source_report(selected_chart.source),
                    "first_leg": {
                        "type": primary[0].legs[0].leg_type,
                        "ident": primary[0].legs[0].fix_ident,
                    },
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
        "version": 24,
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
        "shared_section_assignments": [
            {
                "airport": segment.airport,
                "label": segment.label,
                "runway": segment.runway,
                "section": iap_section_kind(segment),
                "target_label": target[1],
                "selection": selection,
                "source": _source_report(segment.source),
            }
            for segment in model.procedure_segments
            if (assignment := shared_assignments.get(id(segment))) is not None
            for target, selection in (assignment,)
        ],
        "inherited_base_primary_assignments": [
            {
                "airport": airport,
                "label": label,
                "runway": runway,
                "base_label": donor.label,
                "selection": selection,
                "primary_legs": len(donor.legs),
                "source": _source_report(donor.source),
            }
            for (airport, label, runway), (donor, selection) in sorted(
                inherited_base_primaries.items()
            )
        ],
        "multi_primary_variant_assignments": [
            {
                "airport": segment.airport,
                "label": segment.label,
                "runway": segment.runway,
                "family": variant.family,
                "rnp_ar": variant.rnp_ar,
                "rnp_ar_missed": variant.rnp_ar_missed,
                "selection": variant.selection,
                "chart_name": variant.chart.chart_name,
                "chart_names": [
                    chart.chart_name
                    for chart in _owned_variant_charts(variant)
                ],
                "source": _source_report(segment.source),
                "chart_source": _source_report(variant.chart.source),
                "required_fixes": sorted(_direct_database_fix_idents(segment)),
            }
            for segment in model.procedure_segments
            if (variant := multi_primary_variants.get(id(segment))) is not None
        ],
        "ocr_role_selections": ocr_role_selections,
        "source_fixed_point_selections": source_fixed_point_selections,
        "source_title_qualifier_selections": source_title_qualifier_selections,
        "source_unqualified_rnp_ar_direct_role_selections": (
            source_unqualified_rnp_ar_direct_role_selections
        ),
        "source_unique_direct_role_selections": source_unique_direct_role_selections,
        "source_dominant_direct_role_selections": source_dominant_direct_role_selections,
        "source_consensus_direct_role_selections": (
            source_consensus_direct_role_selections
        ),
        "source_rnp_subset_consensus_direct_role_selections": (
            source_rnp_subset_consensus_direct_role_selections
        ),
        "source_intersecting_direct_role_selections": (
            source_intersecting_direct_role_selections
        ),
        "source_plain_rnp_title_selections": source_plain_rnp_title_selections,
        "source_unique_first_if_selections": source_unique_first_if_selections,
        "source_incomplete_chart_title_matches": (
            source_incomplete_chart_title_matches
        ),
        "shared_ils_primary_projection_count": len(
            model.shared_ils_primary_projections,
        ),
        "shared_ils_primary_projections": model.shared_ils_primary_projections,
        "unresolved_groups": unresolved,
    }
