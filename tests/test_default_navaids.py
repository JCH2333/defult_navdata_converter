from __future__ import annotations

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
        source=SourceRef("fixture.csv", 2),
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
    assert result.selected_navaids == (raw,)
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
