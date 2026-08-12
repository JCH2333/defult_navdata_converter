from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .baseline import (
    BaselineIndex,
    BaselineNavaid,
    NavaidDiff,
    _distance_nm,
    _source_frequency_khz,
    diff_navaids,
)
from .model import Navaid


@dataclass(frozen=True)
class PhysicalNavaidMatch:
    """A source facility physically equivalent to one official baseline row."""

    raw: Navaid
    baseline: BaselineNavaid
    distance_nm: float


@dataclass(frozen=True)
class PhysicalNavaidAmbiguity:
    """More than one official physical identity fits one raw facility."""

    raw: Navaid
    candidates: tuple[PhysicalNavaidMatch, ...]


@dataclass(frozen=True)
class DefaultNavaidSelection:
    """Default-overlay navaid selection with an audit trail for every outcome.

    ``diff_navaids`` deliberately keeps its historical, region-strict meaning.
    This adapter layer adds a second pass only for rows that strict matching
    considered missing: it suppresses a row when the verified official index
    already contains the same physical facility under a different region key.
    """

    strict_diff: NavaidDiff
    selected_navaids: tuple[Navaid, ...]
    suppressed_physical_duplicates: tuple[PhysicalNavaidMatch, ...]
    physical_ambiguities: tuple[PhysicalNavaidAmbiguity, ...]
    coordinate_tolerance_nm: float

    @property
    def navaid_selection_verified(self) -> bool:
        return self.strict_diff.navaid_diff_verified and not self.physical_ambiguities

    def to_report(self) -> dict[str, object]:
        def source_payload(item: Navaid) -> dict[str, object]:
            return {
                "file": item.source.file,
                "row": item.source.row,
                "page": item.source.page,
            }

        def raw_payload(item: Navaid) -> dict[str, object]:
            return {
                "key": item.key,
                "kind": item.kind,
                "ident": item.ident,
                "region": item.country[:2],
                "frequency": item.frequency,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "source": source_payload(item),
                "source_attributes": {
                    "code_in_airway": item.code_in_airway,
                    "purpose": item.purpose,
                    "is_rep_atc": item.is_rep_atc,
                    "route_restrict": item.route_restrict,
                    "is_trans_point": item.is_trans_point,
                    "is_border_point": item.is_border_point,
                    "serviced_airport": item.serviced_airport,
                    "code_fir": item.code_fir,
                },
            }

        def baseline_payload(item: BaselineNavaid) -> dict[str, object]:
            return {
                "kind": item.kind,
                "ident": item.ident,
                "region": item.region,
                "frequency_khz": item.frequency_khz,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "source": item.source,
                "row_id": item.row_id,
            }

        return {
            "navaid_selection_verified": self.navaid_selection_verified,
            "strategy": "strict_region_diff_then_physical_duplicate_suppression",
            "source_records": len(self.strict_diff.raw),
            "strict_matched_existing": len(self.strict_diff.matched_existing),
            "strict_selected_missing": len(self.strict_diff.selected_navaids),
            "selected_missing": len(self.selected_navaids),
            "suppressed_physical_duplicates": len(self.suppressed_physical_duplicates),
            "physical_ambiguities": len(self.physical_ambiguities),
            "strict_ambiguities": len(self.strict_diff.ambiguous),
            "coordinate_tolerance_nm": self.coordinate_tolerance_nm,
            "selected_by_kind": {
                kind: sum(1 for item in self.selected_navaids if item.kind == kind)
                for kind in ("VOR", "NDB")
            },
            "suppressed_by_kind": {
                kind: sum(
                    1
                    for item in self.suppressed_physical_duplicates
                    if item.raw.kind == kind
                )
                for kind in ("VOR", "NDB")
            },
            "selected_records": [
                {
                    "reason": "no_physical_official_match",
                    "raw": raw_payload(item),
                }
                for item in self.selected_navaids[:100]
            ],
            "suppressed_records": [
                {
                    "reason": "official_physical_duplicate_with_different_region",
                    "raw": raw_payload(item.raw),
                    "baseline": baseline_payload(item.baseline),
                    "distance_nm": item.distance_nm,
                }
                for item in self.suppressed_physical_duplicates[:100]
            ],
            "physical_ambiguity_records": [
                {
                    "raw": raw_payload(item.raw),
                    "candidates": [
                        {
                            "baseline": baseline_payload(candidate.baseline),
                            "distance_nm": candidate.distance_nm,
                        }
                        for candidate in item.candidates
                    ],
                }
                for item in self.physical_ambiguities[:100]
            ],
        }


def _sort_raw(item: Navaid) -> tuple[object, ...]:
    return (
        item.kind.upper(),
        item.ident.upper(),
        item.country.upper(),
        item.frequency,
        item.latitude,
        item.longitude,
        item.key,
    )


def _physical_candidates(
    raw: Navaid,
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float,
) -> tuple[PhysicalNavaidMatch, ...]:
    """Return region-independent official identities for one raw facility."""
    frequency = _source_frequency_khz(raw)
    unique: dict[tuple[object, ...], PhysicalNavaidMatch] = {}
    for item in baseline.records:
        if item.kind != raw.kind.upper() or item.ident != raw.ident.strip().upper():
            continue
        if abs(item.frequency_khz - frequency) > 1:
            continue
        distance = _distance_nm(raw, item)
        if distance > coordinate_tolerance_nm:
            continue
        match = PhysicalNavaidMatch(raw=raw, baseline=item, distance_nm=distance)
        previous = unique.get(item.identity)
        if previous is None or (match.distance_nm, item.sort_key) < (
            previous.distance_nm,
            previous.baseline.sort_key,
        ):
            unique[item.identity] = match
    return tuple(sorted(
        unique.values(),
        key=lambda item: (item.distance_nm, item.baseline.sort_key),
    ))


def select_default_navaids(
    navaids: Iterable[Navaid],
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float = 0.25,
) -> DefaultNavaidSelection:
    """Select only source navaids absent from the official default baseline.

    The first pass remains region-strict to preserve diagnostics.  The second
    pass prevents an overlay from recreating a physical facility just because
    the source and baseline assign different region keys.  A physical ambiguity
    is a hard stop: no navaid output is returned for an unverified selection.
    """
    raw = tuple(navaids)
    strict_diff = diff_navaids(
        raw,
        baseline,
        coordinate_tolerance_nm=coordinate_tolerance_nm,
    )
    if not strict_diff.navaid_diff_verified:
        return DefaultNavaidSelection(
            strict_diff=strict_diff,
            selected_navaids=(),
            suppressed_physical_duplicates=(),
            physical_ambiguities=(),
            coordinate_tolerance_nm=coordinate_tolerance_nm,
        )

    selected: list[Navaid] = []
    suppressed: list[PhysicalNavaidMatch] = []
    ambiguities: list[PhysicalNavaidAmbiguity] = []
    for raw_item in strict_diff.selected_navaids:
        candidates = _physical_candidates(
            raw_item,
            baseline,
            coordinate_tolerance_nm=coordinate_tolerance_nm,
        )
        if len(candidates) == 1:
            suppressed.append(candidates[0])
        elif len(candidates) > 1:
            ambiguities.append(PhysicalNavaidAmbiguity(raw_item, candidates))
        else:
            selected.append(raw_item)

    # An ambiguous physical identity must never leave a partly trusted set for
    # the caller to accidentally project into a loadable overlay.
    if ambiguities:
        selected = []
    return DefaultNavaidSelection(
        strict_diff=strict_diff,
        selected_navaids=tuple(sorted(selected, key=_sort_raw)),
        suppressed_physical_duplicates=tuple(sorted(
            suppressed,
            key=lambda item: (_sort_raw(item.raw), item.baseline.sort_key),
        )),
        physical_ambiguities=tuple(sorted(
            ambiguities,
            key=lambda item: _sort_raw(item.raw),
        )),
        coordinate_tolerance_nm=coordinate_tolerance_nm,
    )
