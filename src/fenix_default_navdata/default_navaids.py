from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .baseline import (
    BaselineIndex,
    BaselineNavaid,
    NavaidDiff,
    NavaidMatch,
    _distance_nm,
    _source_frequency_khz,
    diff_navaids,
)
from .model import CN_PREFIXES, Navaid, SourceRef


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
class BaselineNavaidPreservation:
    """One official Chinese NDB reprojected without changing its source fields."""

    baseline: BaselineNavaid
    projected: Navaid


@dataclass(frozen=True)
class BaselineNavaidRawAmbiguity:
    """More than one raw NDB claims to replace the same official NDB."""

    baseline: BaselineNavaid
    candidates: tuple[PhysicalNavaidMatch, ...]


@dataclass(frozen=True)
class BaselineNavaidProjectionRejection:
    """An official baseline NDB cannot be represented without inventing data."""

    baseline: BaselineNavaid
    reason: str


@dataclass(frozen=True)
class SdkNavaidIdentityConflict:
    """A raw and official facility share an SDK identity but are far apart."""

    raw: Navaid
    baseline: BaselineNavaid
    distance_nm: float
    resolution: str


# 2608R1 has one source-backed identity collision that the reference overlay
# resolves by retaining the official baseline entity.  Keep the exception
# exact and cycle-specific; an unlisted collision remains a hard validation
# failure instead of silently dropping a raw facility.
_KNOWN_OFFICIAL_PRECEDENCE_CONFLICTS = frozenset({
    (
        "NDB",
        "GJ",
        "ZG",
        24500.0,
        28.073889,
        112.211389,
        28.083336,
        112.216675,
    ),
})

# The 2608R1 source record below is a published ZUWS VOR. The official
# baseline still carries a nearby, otherwise matching ZH identity, while the
# reference overlay preserves the direct 424 ZU identity. Keep the exception
# fully source- and cycle-specific; every other cross-region physical match
# remains suppressed until equivalent evidence exists.
_KNOWN_VERIFIED_CROSS_REGION_ADDITIONS = frozenset({
    (
        "VOR",
        "SNF",
        "ZU",
        112150.0,
        31.073611,
        109.710556,
        "ZH",
        112150.0,
        31.075001,
        109.71167,
    ),
})


@dataclass(frozen=True)
class DefaultNavaidSelection:
    """Default-overlay navaid selection with an audit trail for every outcome.

    ``diff_navaids`` deliberately keeps its historical, region-strict meaning.
    This adapter layer keeps three source-backed projection categories:

    * ``raw_424_addition``: rows missing from the official baseline;
    * ``raw_424_correction``: direct NDB.csv rows that uniquely match an
      official entity but carry an expressible 424 property change; and
    * ``official_baseline_preservation``: China-region NDBs already present
      in the verified official baseline that are not replaced by a correction.

    It adds a second pass only for rows that strict matching considered
    missing: it suppresses a row when the verified official index already
    contains the same physical facility under a different region key.
    """

    strict_diff: NavaidDiff
    selected_navaids: tuple[Navaid, ...]
    selected_missing_navaids: tuple[Navaid, ...]
    property_corrections: tuple[NavaidMatch, ...]
    baseline_preservations: tuple[BaselineNavaidPreservation, ...]
    suppressed_physical_duplicates: tuple[PhysicalNavaidMatch, ...]
    verified_cross_region_additions: tuple[PhysicalNavaidMatch, ...]
    physical_ambiguities: tuple[PhysicalNavaidAmbiguity, ...]
    baseline_raw_ambiguities: tuple[BaselineNavaidRawAmbiguity, ...]
    baseline_projection_rejections: tuple[BaselineNavaidProjectionRejection, ...]
    sdk_identity_conflicts: tuple[SdkNavaidIdentityConflict, ...]
    coordinate_tolerance_nm: float

    @property
    def navaid_selection_verified(self) -> bool:
        return (
            self.strict_diff.navaid_diff_verified
            and not self.physical_ambiguities
            and not self.baseline_raw_ambiguities
            and not self.baseline_projection_rejections
            and all(
                item.resolution == "official_baseline_precedence"
                for item in self.sdk_identity_conflicts
            )
        )

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
            "strategy": (
                "strict_region_diff_then_source_backed_ndb_corrections_"
                "official_baseline_ndb_preservation_and_physical_duplicate_suppression"
            ),
            "source_records": len(self.strict_diff.raw),
            "strict_matched_existing": len(self.strict_diff.matched_existing),
            "strict_selected_missing": len(self.strict_diff.selected_navaids),
            "strict_property_delta": len(self.strict_diff.property_deltas),
            "selected_total": len(self.selected_navaids),
            "selected_missing": len(self.selected_missing_navaids),
            "selected_property_corrections": len(self.property_corrections),
            "official_baseline_preservations": len(self.baseline_preservations),
            "unselected_property_deltas": (
                len(self.strict_diff.property_deltas) - len(self.property_corrections)
            ),
            "suppressed_physical_duplicates": len(self.suppressed_physical_duplicates),
            "verified_cross_region_additions": len(
                self.verified_cross_region_additions
            ),
            "physical_ambiguities": len(self.physical_ambiguities),
            "baseline_raw_ambiguities": len(self.baseline_raw_ambiguities),
            "baseline_projection_rejections": len(self.baseline_projection_rejections),
            "sdk_identity_conflicts": len(self.sdk_identity_conflicts),
            "resolved_sdk_identity_conflicts": sum(
                item.resolution == "official_baseline_precedence"
                for item in self.sdk_identity_conflicts
            ),
            "unresolved_sdk_identity_conflicts": sum(
                item.resolution == "unresolved"
                for item in self.sdk_identity_conflicts
            ),
            "strict_ambiguities": len(self.strict_diff.ambiguous),
            "coordinate_tolerance_nm": self.coordinate_tolerance_nm,
            "projection_categories": {
                "raw_424_addition": len(self.selected_missing_navaids),
                "raw_424_correction": len(self.property_corrections),
                "official_baseline_preservation": len(self.baseline_preservations),
                "rejected_ambiguous": (
                    len(self.physical_ambiguities)
                    + len(self.baseline_raw_ambiguities)
                ),
                "official_baseline_precedence": sum(
                    item.resolution == "official_baseline_precedence"
                    for item in self.sdk_identity_conflicts
                ),
                "verified_cross_region_raw_addition": len(
                    self.verified_cross_region_additions
                ),
                "rejected_sdk_identity_conflict": sum(
                    item.resolution == "unresolved"
                    for item in self.sdk_identity_conflicts
                ),
            },
            "selected_by_kind": {
                kind: sum(1 for item in self.selected_navaids if item.kind == kind)
                for kind in ("VOR", "NDB")
            },
            "selected_missing_by_kind": {
                kind: sum(
                    1
                    for item in self.selected_missing_navaids
                    if item.kind == kind
                )
                for kind in ("VOR", "NDB")
            },
            "property_corrections_by_kind": {
                kind: sum(
                    1
                    for item in self.property_corrections
                    if item.raw.kind == kind
                )
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
                for item in self.selected_missing_navaids[:100]
            ],
            "property_correction_records": [
                {
                    "reason": "source_backed_ndb_property_delta",
                    "raw": raw_payload(item.raw),
                    "baseline": baseline_payload(item.baseline),
                    "distance_nm": item.distance_nm,
                    "fields": list(item.property_delta),
                }
                for item in self.property_corrections[:100]
            ],
            "official_baseline_preservation_records": [
                {
                    "reason": "official_baseline_preservation",
                    "baseline": baseline_payload(item.baseline),
                    "projected": raw_payload(item.projected),
                }
                for item in self.baseline_preservations[:100]
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
            "verified_cross_region_addition_records": [
                {
                    "reason": "verified_cross_region_raw_addition",
                    "raw": raw_payload(item.raw),
                    "baseline": baseline_payload(item.baseline),
                    "distance_nm": item.distance_nm,
                }
                for item in self.verified_cross_region_additions[:100]
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
            "baseline_raw_ambiguity_records": [
                {
                    "baseline": baseline_payload(item.baseline),
                    "raw_candidates": [
                        {
                            "raw": raw_payload(candidate.raw),
                            "distance_nm": candidate.distance_nm,
                        }
                        for candidate in item.candidates
                    ],
                }
                for item in self.baseline_raw_ambiguities[:100]
            ],
            "baseline_projection_rejection_records": [
                {
                    "baseline": baseline_payload(item.baseline),
                    "reason": item.reason,
                }
                for item in self.baseline_projection_rejections[:100]
            ],
            "sdk_identity_conflict_records": [
                {
                    "raw": raw_payload(item.raw),
                    "baseline": baseline_payload(item.baseline),
                    "distance_nm": item.distance_nm,
                    "resolution": item.resolution,
                }
                for item in self.sdk_identity_conflicts[:100]
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


def _raw_physical_identity(item: Navaid) -> tuple[object, ...]:
    """Stable raw identity used only to collapse identical source duplicates."""
    return (
        item.kind.upper(),
        item.ident.strip().upper(),
        item.country.strip().upper()[:2],
        round(_source_frequency_khz(item), 3),
        round(item.latitude, 5),
        round(item.longitude, 5),
    )


def _sdk_identity(item: Navaid) -> tuple[object, ...]:
    """Return the facility identity enforced by the SDK's duplicate check."""
    return (
        item.kind.upper(),
        item.ident.strip().upper(),
        item.country.strip().upper()[:2],
        round(_source_frequency_khz(item), 3),
    )


def _baseline_sdk_identity(item: BaselineNavaid) -> tuple[object, ...]:
    return (
        item.kind.upper(),
        item.ident.strip().upper(),
        item.region.strip().upper()[:2],
        round(item.frequency_khz, 3),
    )


def _known_identity_conflict(
    raw: Navaid,
    baseline: BaselineNavaid,
) -> bool:
    return (
        raw.source.file.strip().casefold() == "ndb.csv"
        and (
            _sdk_identity(raw)
            + (
                round(raw.latitude, 6),
                round(raw.longitude, 6),
                round(baseline.latitude, 6),
                round(baseline.longitude, 6),
            )
        ) in _KNOWN_OFFICIAL_PRECEDENCE_CONFLICTS
    )


def _known_cross_region_addition(
    raw: Navaid,
    baseline: BaselineNavaid,
) -> bool:
    return (
        raw.source.file.strip().casefold() == "vor.csv"
        and (
            raw.kind.upper(),
            raw.ident.strip().upper(),
            raw.country.strip().upper()[:2],
            round(_source_frequency_khz(raw), 3),
            round(raw.latitude, 6),
            round(raw.longitude, 6),
            baseline.region.strip().upper()[:2],
            round(baseline.frequency_khz, 3),
            round(baseline.latitude, 6),
            round(baseline.longitude, 6),
        ) in _KNOWN_VERIFIED_CROSS_REGION_ADDITIONS
    )


def _sdk_identity_conflicts(
    raw: Iterable[Navaid],
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float,
) -> tuple[SdkNavaidIdentityConflict, ...]:
    """Find raw/official rows the SDK cannot represent simultaneously."""
    result: list[SdkNavaidIdentityConflict] = []
    seen: set[tuple[object, ...]] = set()
    for raw_item in sorted(tuple(raw), key=_sort_raw):
        raw_identity = _sdk_identity(raw_item)
        for baseline_item in baseline.records:
            if raw_identity != _baseline_sdk_identity(baseline_item):
                continue
            distance = _distance_nm(raw_item, baseline_item)
            if distance <= coordinate_tolerance_nm:
                continue
            identity = (
                raw_item.key,
                baseline_item.identity,
            )
            if identity in seen:
                continue
            seen.add(identity)
            result.append(SdkNavaidIdentityConflict(
                raw=raw_item,
                baseline=baseline_item,
                distance_nm=distance,
                resolution=(
                    "official_baseline_precedence"
                    if _known_identity_conflict(raw_item, baseline_item)
                    else "unresolved"
                ),
            ))
    return tuple(sorted(
        result,
        key=lambda item: (
            _sort_raw(item.raw),
            item.baseline.sort_key,
            item.resolution,
        ),
    ))


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


def _project_baseline_ndb(item: BaselineNavaid) -> Navaid:
    """Turn one verified baseline NDB into a target-ready neutral record.

    The field values remain the official baseline values.  The synthetic key
    and ``SourceRef`` only encode that this is a baseline-preservation record,
    rather than pretending it came from a 424 CSV row.
    """
    if item.kind != "NDB":
        raise ValueError(f"官方基线保留仅支持 NDB，收到: {item.kind}")
    if item.magnetic_variation is None:
        raise ValueError("官方基线 NDB 缺少磁差")
    if item.elevation_ft is None:
        raise ValueError("官方基线 NDB 缺少高程")
    values = (
        item.frequency_khz,
        item.latitude,
        item.longitude,
        item.magnetic_variation,
        float(item.elevation_ft),
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("官方基线 NDB 含有非有限数值")
    if item.frequency_khz <= 0:
        raise ValueError("官方基线 NDB 频率必须为正数")
    key = (
        "official-baseline-ndb:"
        f"{item.region}:{item.ident}:{item.frequency_khz:.3f}:"
        f"{item.latitude:.5f}:{item.longitude:.5f}"
    )
    return Navaid(
        key=key,
        ident=item.ident,
        kind="NDB",
        name=item.name,
        latitude=item.latitude,
        longitude=item.longitude,
        frequency=item.frequency_khz / 100,
        magnetic_variation=item.magnetic_variation,
        elevation_ft=item.elevation_ft,
        country=item.region,
        source=SourceRef("official-baseline-navaid-index", item.row_id),
    )


def select_default_navaids(
    navaids: Iterable[Navaid],
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float = 0.25,
) -> DefaultNavaidSelection:
    """Select source-backed navaid additions and NDB property corrections.

    The first pass remains region-strict to preserve diagnostics.  The second
    pass prevents an overlay from recreating a physical facility just because
    the source and baseline assign different region keys.  A uniquely matched
    424 NDB with an expressible property delta is selected as a correction;
    VOR corrections remain report-only until their own source rule is proven.
    The full China-region official NDB set is represented exactly once: a
    qualifying direct 424 correction replaces a baseline record, while all
    remaining verified baseline NDBs are preserved.  One-to-many or
    many-to-one physical matches are hard stops: no navaid output is returned
    for an unverified selection.
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
            selected_missing_navaids=(),
            property_corrections=(),
            baseline_preservations=(),
            suppressed_physical_duplicates=(),
            verified_cross_region_additions=(),
            physical_ambiguities=(),
            baseline_raw_ambiguities=(),
            baseline_projection_rejections=(),
            sdk_identity_conflicts=(),
            coordinate_tolerance_nm=coordinate_tolerance_nm,
        )

    selected_missing: list[Navaid] = []
    suppressed: list[PhysicalNavaidMatch] = []
    verified_cross_region_additions: list[PhysicalNavaidMatch] = []
    sdk_identity_conflicts = _sdk_identity_conflicts(
        strict_diff.raw,
        baseline,
        coordinate_tolerance_nm=coordinate_tolerance_nm,
    )
    unresolved_sdk_conflicts = tuple(
        item
        for item in sdk_identity_conflicts
        if item.resolution == "unresolved"
    )
    physical_ambiguities: dict[tuple[object, ...], PhysicalNavaidAmbiguity] = {}
    raw_ndbs: dict[tuple[object, ...], Navaid] = {}
    for raw_item in sorted(
        (item for item in strict_diff.raw if item.kind.upper() == "NDB"),
        key=_sort_raw,
    ):
        raw_ndbs.setdefault(_raw_physical_identity(raw_item), raw_item)

    ndb_candidates: dict[tuple[object, ...], tuple[PhysicalNavaidMatch, ...]] = {}
    baseline_raw_matches: dict[
        tuple[object, ...],
        list[PhysicalNavaidMatch],
    ] = {}
    for identity, raw_item in raw_ndbs.items():
        candidates = _physical_candidates(
            raw_item,
            baseline,
            coordinate_tolerance_nm=coordinate_tolerance_nm,
        )
        ndb_candidates[identity] = candidates
        if len(candidates) > 1:
            physical_ambiguities[identity] = PhysicalNavaidAmbiguity(
                raw_item,
                candidates,
            )
            continue
        if len(candidates) == 1 and candidates[0].baseline.region in CN_PREFIXES:
            baseline_raw_matches.setdefault(candidates[0].baseline.identity, []).append(
                candidates[0]
            )

    def candidates_for(raw_item: Navaid) -> tuple[PhysicalNavaidMatch, ...]:
        if raw_item.kind.upper() == "NDB":
            return ndb_candidates.get(
                _raw_physical_identity(raw_item),
                (),
            )
        return _physical_candidates(
            raw_item,
            baseline,
            coordinate_tolerance_nm=coordinate_tolerance_nm,
        )

    for raw_item in strict_diff.selected_navaids:
        if any(
            item.raw.key == raw_item.key
            and item.resolution == "official_baseline_precedence"
            for item in sdk_identity_conflicts
        ):
            continue
        candidates = candidates_for(raw_item)
        if len(candidates) == 1:
            if _known_cross_region_addition(raw_item, candidates[0].baseline):
                selected_missing.append(raw_item)
                verified_cross_region_additions.append(candidates[0])
            else:
                suppressed.append(candidates[0])
        elif len(candidates) > 1:
            physical_ambiguities.setdefault(
                _raw_physical_identity(raw_item),
                PhysicalNavaidAmbiguity(raw_item, candidates),
            )
        else:
            selected_missing.append(raw_item)

    # Unlike VORs, every 2608 424 NDB row in the normalized model is a direct
    # NDB.csv record.  When strict matching has already established exactly one
    # same-region, same-frequency physical entity, an expressible field delta
    # is enough source evidence to emit a replacement facility.  The baseline
    # record is used only to prove identity and to audit the changed fields.
    property_corrections = [
        match
        for match in strict_diff.property_deltas
        if (
            match.raw.kind.upper() == "NDB"
            and match.raw.source.file.strip().casefold() == "ndb.csv"
            and len(candidates_for(match.raw)) == 1
            and candidates_for(match.raw)[0].baseline.identity == match.baseline.identity
        )
    ]

    correction_identities = {
        match.baseline.identity for match in property_corrections
    }
    baseline_raw_ambiguities = tuple(sorted(
        (
            BaselineNavaidRawAmbiguity(
                candidates[0].baseline,
                tuple(sorted(
                    candidates,
                    key=lambda item: (_sort_raw(item.raw), item.distance_nm),
                )),
            )
            for candidates in baseline_raw_matches.values()
            if len(candidates) > 1
        ),
        key=lambda item: item.baseline.sort_key,
    ))
    baseline_preservations: list[BaselineNavaidPreservation] = []
    baseline_projection_rejections: list[BaselineNavaidProjectionRejection] = []
    for baseline_item in sorted(
        (
            item
            for item in baseline.records
            if item.kind == "NDB" and item.region in CN_PREFIXES
        ),
        key=lambda item: item.sort_key,
    ):
        if baseline_item.identity in correction_identities:
            continue
        try:
            projected = _project_baseline_ndb(baseline_item)
        except ValueError as error:
            baseline_projection_rejections.append(
                BaselineNavaidProjectionRejection(baseline_item, str(error))
            )
            continue
        baseline_preservations.append(BaselineNavaidPreservation(
            baseline=baseline_item,
            projected=projected,
        ))

    # An ambiguous or nonrepresentable physical identity must never leave a
    # partly trusted set for the caller to accidentally project into a loadable
    # overlay.
    if (
        physical_ambiguities
        or baseline_raw_ambiguities
        or baseline_projection_rejections
    ):
        selected_missing = []
        property_corrections = []
        baseline_preservations = []
    if unresolved_sdk_conflicts:
        selected_missing = []
        property_corrections = []
        baseline_preservations = []
    selected = tuple(sorted(
        (
            *selected_missing,
            *(item.raw for item in property_corrections),
            *(item.projected for item in baseline_preservations),
        ),
        key=_sort_raw,
    ))
    return DefaultNavaidSelection(
        strict_diff=strict_diff,
        selected_navaids=selected,
        selected_missing_navaids=tuple(sorted(selected_missing, key=_sort_raw)),
        property_corrections=tuple(sorted(
            property_corrections,
            key=lambda item: (_sort_raw(item.raw), item.baseline.sort_key),
        )),
        baseline_preservations=tuple(sorted(
            baseline_preservations,
            key=lambda item: item.baseline.sort_key,
        )),
        suppressed_physical_duplicates=tuple(sorted(
            suppressed,
            key=lambda item: (_sort_raw(item.raw), item.baseline.sort_key),
        )),
        verified_cross_region_additions=tuple(sorted(
            verified_cross_region_additions,
            key=lambda item: (_sort_raw(item.raw), item.baseline.sort_key),
        )),
        physical_ambiguities=tuple(sorted(
            physical_ambiguities.values(),
            key=lambda item: _sort_raw(item.raw),
        )),
        baseline_raw_ambiguities=baseline_raw_ambiguities,
        baseline_projection_rejections=tuple(sorted(
            baseline_projection_rejections,
            key=lambda item: item.baseline.sort_key,
        )),
        sdk_identity_conflicts=sdk_identity_conflicts,
        coordinate_tolerance_nm=coordinate_tolerance_nm,
    )
