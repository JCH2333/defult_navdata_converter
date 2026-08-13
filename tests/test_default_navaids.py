from __future__ import annotations

from dataclasses import replace

from fenix_default_navdata.baseline import BaselineIndex, BaselineNavaid
from fenix_default_navdata.default_navaids import select_default_navaids
from fenix_default_navdata.model import Navaid, SourceRef


def _raw(
    key: str,
    ident: str,
    kind: str,
    *,
    latitude: float,
    longitude: float,
    frequency: float,
    country: str,
    source_file: str = "fixture.csv",
) -> Navaid:
    return Navaid(
        key=key,
        ident=ident,
        kind=kind,
        name=ident,
        latitude=latitude,
        longitude=longitude,
        frequency=frequency,
        magnetic_variation=0.0,
        elevation_ft=0,
        country=country,
        source=SourceRef(source_file, 2),
        code_in_airway="Y",
        purpose="AE",
        is_rep_atc="Y",
    )


def _baseline(
    kind: str,
    ident: str,
    region: str,
    frequency_khz: float,
    latitude: float,
    longitude: float,
    row_id: int,
) -> BaselineNavaid:
    return BaselineNavaid(
        kind=kind,
        ident=ident,
        region=region,
        frequency_khz=frequency_khz,
        latitude=latitude,
        longitude=longitude,
        name=ident,
        magnetic_variation=0.0,
        elevation_ft=0,
        source="official.bgl",
        row_id=row_id,
    )


def _index(*records: BaselineNavaid) -> BaselineIndex:
    return BaselineIndex(
        records=tuple(records),
        sources=("official.sqlite",),
        database_counts=(),
        verified=True,
    )


def test_default_selection_suppresses_cross_region_physical_duplicate() -> None:
    raw = _raw(
        "raw", "CHF", "VOR", latitude=42.188889, longitude=118.810833,
        frequency=115.5, country="ZB",
    )
    baseline = _index(_baseline(
        "VOR", "CHF", "ZY", 115500, 42.190000, 118.811676, 1,
    ))

    result = select_default_navaids([raw], baseline)

    assert result.strict_diff.selected_navaids == (raw,)
    assert result.selected_navaids == ()
    assert result.navaid_selection_verified is True
    assert len(result.suppressed_physical_duplicates) == 1
    match = result.suppressed_physical_duplicates[0]
    assert (match.raw.ident, match.baseline.region) == ("CHF", "ZY")
    report = result.to_report()
    assert report["suppressed_physical_duplicates"] == 1
    assert report["suppressed_records"][0]["raw"]["source_attributes"] == {
        "code_in_airway": "Y",
        "purpose": "AE",
        "is_rep_atc": "Y",
        "route_restrict": "",
        "is_trans_point": "",
        "is_border_point": "",
        "serviced_airport": "",
        "code_fir": "",
    }


def test_default_selection_keeps_source_facility_without_physical_official_match() -> None:
    raw = _raw(
        "raw", "NEW", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZB",
    )
    baseline = _index(_baseline(
        "NDB", "NEW", "ZY", 44500, 37.0, 107.0, 1,
    ))

    result = select_default_navaids([raw], baseline)

    assert result.navaid_selection_verified is True
    assert result.selected_missing_navaids == (raw,)
    assert result.property_corrections == ()
    assert result.selected_navaids[0] == raw
    assert [item.baseline.region for item in result.baseline_preservations] == ["ZY"]
    assert len(result.selected_navaids) == 2
    assert result.suppressed_physical_duplicates == ()


def test_default_selection_keeps_same_ident_with_different_frequency() -> None:
    raw = _raw(
        "raw", "ABC", "VOR", latitude=35.0, longitude=105.0,
        frequency=112.3, country="ZB",
    )
    baseline = _index(_baseline(
        "VOR", "ABC", "ZY", 111200, 35.0, 105.0, 1,
    ))

    result = select_default_navaids([raw], baseline)

    assert result.navaid_selection_verified is True
    assert result.selected_navaids == (raw,)


def test_default_selection_projects_source_backed_ndb_property_correction() -> None:
    raw = _raw(
        "raw", "DM", "NDB", latitude=29.256111, longitude=91.764167,
        frequency=435, country="ZU", source_file="NDB.csv",
    )
    baseline = _index(_baseline(
        "NDB", "DM", "ZU", 43500, 29.255000, 91.765000, 1,
    ))

    result = select_default_navaids([raw], baseline)

    assert result.navaid_selection_verified is True
    assert result.selected_navaids == (raw,)
    assert result.selected_missing_navaids == ()
    assert len(result.property_corrections) == 1
    assert result.baseline_preservations == ()
    correction = result.property_corrections[0]
    assert correction.raw == raw
    assert correction.property_delta == ("coordinates",)
    report = result.to_report()
    assert report["selected_total"] == 1
    assert report["selected_missing"] == 0
    assert report["selected_property_corrections"] == 1
    assert report["property_corrections_by_kind"] == {"VOR": 0, "NDB": 1}
    assert report["property_correction_records"][0]["reason"] == (
        "source_backed_ndb_property_delta"
    )


def test_default_selection_preserves_unreplaced_official_china_ndb() -> None:
    baseline_ndb = _baseline(
        "NDB", "OLD", "ZB", 34500, 40.0, 116.0, 1,
    )

    result = select_default_navaids([], _index(baseline_ndb))

    assert result.navaid_selection_verified is True
    assert result.selected_missing_navaids == ()
    assert result.property_corrections == ()
    assert len(result.baseline_preservations) == 1
    preserved = result.baseline_preservations[0]
    assert preserved.baseline == baseline_ndb
    assert preserved.projected == Navaid(
        key="official-baseline-ndb:ZB:OLD:34500.000:40.00000:116.00000",
        ident="OLD",
        kind="NDB",
        name="OLD",
        latitude=40.0,
        longitude=116.0,
        frequency=345.0,
        magnetic_variation=0.0,
        elevation_ft=0,
        country="ZB",
        source=SourceRef("official-baseline-navaid-index", 1),
    )
    assert result.selected_navaids == (preserved.projected,)
    report = result.to_report()
    assert report["projection_categories"] == {
        "raw_424_addition": 0,
        "raw_424_correction": 0,
        "official_baseline_preservation": 1,
        "rejected_ambiguous": 0,
        "official_baseline_precedence": 0,
        "rejected_sdk_identity_conflict": 0,
    }
    assert report["official_baseline_preservation_records"][0]["reason"] == (
        "official_baseline_preservation"
    )


def test_default_selection_preserves_other_same_ident_official_ndb_entity() -> None:
    raw = _raw(
        "raw", "D", "NDB", latitude=30.0, longitude=120.0,
        frequency=300, country="ZS", source_file="NDB.csv",
    )
    matching = _baseline("NDB", "D", "ZS", 30000, 30.001, 120.0, 1)
    separate = _baseline("NDB", "D", "ZY", 21600, 42.0, 123.0, 2)

    result = select_default_navaids([raw], _index(matching, separate))

    assert result.navaid_selection_verified is True
    assert result.selected_navaids[0] == raw
    assert [item.baseline for item in result.baseline_preservations] == [separate]
    assert len(result.selected_navaids) == 2


def test_default_selection_preserves_official_ndb_on_cross_region_raw_match() -> None:
    raw = _raw(
        "raw", "CROSS", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZB", source_file="NDB.csv",
    )
    baseline = _baseline("NDB", "CROSS", "ZY", 44500, 36.0, 106.0, 1)

    result = select_default_navaids([raw], _index(baseline))

    assert result.navaid_selection_verified is True
    assert result.selected_missing_navaids == ()
    assert result.property_corrections == ()
    assert len(result.suppressed_physical_duplicates) == 1
    assert [item.baseline for item in result.baseline_preservations] == [baseline]
    assert result.selected_navaids == (result.baseline_preservations[0].projected,)


def test_default_selection_rejects_multiple_raw_ndbs_for_one_official_entity() -> None:
    first = _raw(
        "first", "AMB", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZB", source_file="NDB.csv",
    )
    second = _raw(
        "second", "AMB", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZY", source_file="NDB.csv",
    )
    baseline = _baseline("NDB", "AMB", "ZB", 44500, 36.0, 106.0, 1)

    result = select_default_navaids([first, second], _index(baseline))

    assert result.navaid_selection_verified is False
    assert result.selected_navaids == ()
    assert len(result.baseline_raw_ambiguities) == 1
    assert result.to_report()["projection_categories"]["rejected_ambiguous"] == 1


def test_default_selection_rejects_nonrepresentable_official_baseline_ndb() -> None:
    baseline = _baseline("NDB", "NULL", "ZB", 44500, 36.0, 106.0, 1)
    baseline = replace(baseline, magnetic_variation=None)

    result = select_default_navaids([], _index(baseline))

    assert result.navaid_selection_verified is False
    assert result.selected_navaids == ()
    assert len(result.baseline_projection_rejections) == 1


def test_default_selection_uses_verified_official_precedence_for_2608_gj_conflict() -> None:
    raw = _raw(
        "gj-raw", "GJ", "NDB", latitude=28.0738888889, longitude=112.2113888889,
        frequency=245, country="ZG", source_file="NDB.csv",
    )
    baseline = _baseline(
        "NDB", "GJ", "ZG", 24500, 28.0833358765, 112.2166748047, 1,
    )

    result = select_default_navaids([raw], _index(baseline))

    assert result.navaid_selection_verified is True
    assert result.selected_missing_navaids == ()
    assert len(result.baseline_preservations) == 1
    assert result.selected_navaids == (
        result.baseline_preservations[0].projected,
    )
    assert len(result.sdk_identity_conflicts) == 1
    assert result.sdk_identity_conflicts[0].resolution == (
        "official_baseline_precedence"
    )
    report = result.to_report()
    assert report["resolved_sdk_identity_conflicts"] == 1
    assert report["unresolved_sdk_identity_conflicts"] == 0


def test_default_selection_rejects_unlisted_sdk_identity_conflict() -> None:
    raw = _raw(
        "unknown-raw", "XX", "NDB", latitude=30.0, longitude=110.0,
        frequency=245, country="ZG", source_file="NDB.csv",
    )
    baseline = _baseline(
        "NDB", "XX", "ZG", 24500, 31.0, 111.0, 1,
    )

    result = select_default_navaids([raw], _index(baseline))

    assert result.navaid_selection_verified is False
    assert result.selected_navaids == ()
    assert len(result.sdk_identity_conflicts) == 1
    assert result.sdk_identity_conflicts[0].resolution == "unresolved"
    assert result.to_report()["projection_categories"][
        "rejected_sdk_identity_conflict"
    ] == 1


def test_default_selection_does_not_project_unchanged_ndb_or_vor_delta() -> None:
    unchanged_ndb = _raw(
        "ndb", "EQ", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZB",
    )
    vor_delta = _raw(
        "vor", "VOR", "VOR", latitude=35.0, longitude=105.0,
        frequency=112.3, country="ZB",
    )
    baseline = _index(
        _baseline("NDB", "EQ", "ZB", 44500, 36.0, 106.0, 1),
        _baseline("VOR", "VOR", "ZB", 112300, 35.001, 105.0, 2),
    )

    result = select_default_navaids([unchanged_ndb, vor_delta], baseline)

    assert result.navaid_selection_verified is True
    assert len(result.selected_navaids) == 1
    assert result.selected_missing_navaids == ()
    assert result.property_corrections == ()
    assert [item.baseline.ident for item in result.baseline_preservations] == ["EQ"]
    report = result.to_report()
    assert report["strict_property_delta"] == 1
    assert report["unselected_property_deltas"] == 1


def test_default_selection_requires_direct_ndb_csv_provenance_for_correction() -> None:
    raw = _raw(
        "raw", "DM", "NDB", latitude=29.256111, longitude=91.764167,
        frequency=435, country="ZU", source_file="NDB.csv",
    )
    raw = replace(raw, source=SourceRef("derived-ndb.csv", 2))
    baseline = _index(_baseline(
        "NDB", "DM", "ZU", 43500, 29.255000, 91.765000, 1,
    ))

    result = select_default_navaids([raw], baseline)

    assert result.navaid_selection_verified is True
    assert len(result.selected_navaids) == 1
    assert result.property_corrections == ()
    assert [item.baseline.ident for item in result.baseline_preservations] == ["DM"]
    assert result.to_report()["unselected_property_deltas"] == 1


def test_default_selection_blocks_on_multiple_physical_official_identities() -> None:
    raw = _raw(
        "raw", "AMB", "VOR", latitude=35.0, longitude=105.0,
        frequency=113.1, country="ZB",
    )
    baseline = _index(
        _baseline("VOR", "AMB", "ZG", 113100, 35.0000, 105.0010, 1),
        _baseline("VOR", "AMB", "ZH", 113100, 35.0000, 105.0020, 2),
    )

    result = select_default_navaids([raw], baseline)

    assert result.navaid_selection_verified is False
    assert result.selected_navaids == ()
    assert len(result.physical_ambiguities) == 1


def test_default_selection_is_independent_of_input_order() -> None:
    duplicate = _raw(
        "duplicate", "CHF", "VOR", latitude=42.188889, longitude=118.810833,
        frequency=115.5, country="ZB",
    )
    selected = _raw(
        "selected", "NEW", "NDB", latitude=36.0, longitude=106.0,
        frequency=445, country="ZB",
    )
    baseline = _index(_baseline(
        "VOR", "CHF", "ZY", 115500, 42.190000, 118.811676, 1,
    ))

    first = select_default_navaids([duplicate, selected], baseline)
    second = select_default_navaids([selected, duplicate], baseline)

    assert first.selected_navaids == second.selected_navaids == (selected,)
    assert first.suppressed_physical_duplicates == second.suppressed_physical_duplicates
