from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fenix_default_navdata.baseline import (
    BaselineError,
    BaselineIndex,
    diff_navaids,
    load_baseline_index,
    load_baseline_sqlite,
)
from fenix_default_navdata.model import Navaid, SourceRef


def _write_index(
    path: Path,
    *,
    vors: list[tuple[object, ...]] | None = None,
    ndbs: list[tuple[object, ...]] | None = None,
    include_vor: bool = True,
    include_ndb: bool = True,
) -> Path:
    connection = sqlite3.connect(path)
    if include_vor:
        connection.execute(
            """
            CREATE TABLE vor (
                vor_id INTEGER PRIMARY KEY,
                ident TEXT,
                region TEXT,
                frequency INTEGER,
                mag_var REAL,
                altitude INTEGER,
                lonx REAL,
                laty REAL,
                name TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO vor(ident, region, frequency, mag_var, altitude, lonx, laty, name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            vors or [],
        )
    if include_ndb:
        connection.execute(
            """
            CREATE TABLE ndb (
                ndb_id INTEGER PRIMARY KEY,
                ident TEXT,
                region TEXT,
                frequency INTEGER,
                mag_var REAL,
                altitude INTEGER,
                lonx REAL,
                laty REAL,
                name TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO ndb(ident, region, frequency, mag_var, altitude, lonx, laty, name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ndbs or [],
        )
    connection.commit()
    connection.close()
    return path


def _navaid(
    key: str,
    ident: str,
    kind: str,
    *,
    latitude: float,
    longitude: float,
    frequency: float,
    country: str = "ZB",
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
        elevation_ft=100,
        country=country,
        source=SourceRef("fixture", 1),
    )


def test_exact_facility_is_matched_and_not_selected(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("N1", "ZB", 44500, 0.0, 0, 105.5, 35.5, "N1")],
    ))

    result = diff_navaids(
        [
            _navaid("v", "ABC", "VOR", latitude=35.0, longitude=105.0, frequency=111.2),
            _navaid("n", "N1", "NDB", latitude=35.5, longitude=105.5, frequency=445),
        ],
        baseline,
    )

    assert result.selected_navaids == ()
    assert len(result.matched_existing) == 2
    assert result.navaid_diff_verified is True


def test_missing_facility_is_selected(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    missing = _navaid(
        "missing", "MISS", "VOR", latitude=36.0, longitude=106.0, frequency=112.3,
    )

    result = diff_navaids([missing], baseline)

    assert result.selected_navaids == (missing,)
    assert result.matched_existing == ()


def test_same_ident_but_far_away_facility_is_not_suppressed(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    raw = _navaid(
        "far", "ABC", "VOR", latitude=40.0, longitude=110.0, frequency=111.2,
    )

    result = diff_navaids([raw], baseline)

    assert result.selected_navaids == (raw,)


def test_same_ident_but_different_frequency_is_not_suppressed(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    raw = _navaid(
        "different-frequency", "ABC", "VOR",
        latitude=35.0, longitude=105.0, frequency=112.3,
    )

    result = diff_navaids([raw], baseline)

    assert result.selected_navaids == (raw,)


def test_same_ident_but_different_kind_is_not_suppressed(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    raw = _navaid(
        "different-kind", "ABC", "NDB",
        latitude=35.0, longitude=105.0, frequency=1112,
    )

    result = diff_navaids([raw], baseline)

    assert result.selected_navaids == (raw,)


def test_multiple_same_ident_ndbs_are_retained_as_distinct_records(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("BASE", "ZB", 111200, 0.0, 100, 105.0, 35.0, "BASE")],
        ndbs=[("DUP", "ZB", 44500, 0.0, 0, 105.0, 35.0, "DUP")],
    ))
    first = _navaid(
        "first", "DUP", "NDB", latitude=36.0, longitude=106.0, frequency=446,
    )
    second = _navaid(
        "second", "DUP", "NDB", latitude=37.0, longitude=107.0, frequency=447,
    )

    result = diff_navaids([second, first], baseline)

    assert result.selected_navaids == (first, second)
    assert result.suppressed_duplicates == ()


def test_duplicate_raw_rows_are_suppressed_deterministically(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[("ABC", "ZB", 111200, 0.0, 100, 105.0, 35.0, "ABC")],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    first = _navaid(
        "first", "NEW", "VOR", latitude=36.0, longitude=106.0, frequency=112.3,
    )
    duplicate = _navaid(
        "duplicate", "NEW", "VOR", latitude=36.0, longitude=106.0, frequency=112.3,
    )

    result = diff_navaids([duplicate, first], baseline)

    assert result.selected_navaids == (duplicate,)
    assert result.suppressed_duplicates == (first,)


def test_ambiguous_close_matches_block_verified_diff(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[
            ("AMB", "ZB", 111200, 0.0, 100, 105.0040, 35.0000, "A"),
            ("AMB", "ZB", 111200, 0.0, 100, 105.0080, 35.0000, "B"),
        ],
        ndbs=[("BASE", "ZB", 44500, 0.0, 0, 105.5, 35.5, "BASE")],
    ))
    raw = _navaid(
        "ambiguous", "AMB", "VOR", latitude=35.0, longitude=105.006, frequency=111.2,
    )

    result = diff_navaids([raw], baseline)

    assert len(result.ambiguous) == 1
    assert result.selected_navaids == ()
    assert result.navaid_diff_verified is False


def test_missing_required_table_fails_explicitly(tmp_path: Path):
    path = _write_index(
        tmp_path / "missing.sqlite",
        vors=[("BASE", "ZB", 111200, 0.0, 100, 105.0, 35.0, "BASE")],
        include_ndb=False,
    )

    with pytest.raises(BaselineError, match="ndb"):
        load_baseline_sqlite(path)


def test_empty_required_table_fails_explicitly(tmp_path: Path):
    path = _write_index(tmp_path / "empty.sqlite", vors=[])

    with pytest.raises(BaselineError, match="vor"):
        load_baseline_sqlite(path)


def test_corrupt_sqlite_fails_explicitly(tmp_path: Path):
    path = tmp_path / "corrupt.sqlite"
    path.write_bytes(b"not sqlite")

    with pytest.raises(BaselineError):
        load_baseline_sqlite(path)


def test_unverified_or_empty_index_never_falls_back_to_all_raw_navaids():
    raw = _navaid(
        "raw", "RAW", "VOR", latitude=35.0, longitude=105.0, frequency=111.2,
    )
    baseline = BaselineIndex(records=(), sources=(), database_counts=(), verified=False)

    with pytest.raises(BaselineError, match="未通过验证"):
        diff_navaids([raw], baseline)


def test_matching_result_is_independent_of_input_order(tmp_path: Path):
    baseline = load_baseline_sqlite(_write_index(
        tmp_path / "baseline.sqlite",
        vors=[
            ("B", "ZB", 112300, 0.0, 100, 106.0, 36.0, "B"),
            ("A", "ZB", 111200, 0.0, 100, 105.0, 35.0, "A"),
        ],
        ndbs=[("N", "ZB", 44500, 0.0, 0, 107.0, 37.0, "N")],
    ))
    items = [
        _navaid("n", "N", "NDB", latitude=37.0, longitude=107.0, frequency=445),
        _navaid("b", "B", "VOR", latitude=36.0, longitude=106.0, frequency=112.3),
        _navaid("new", "NEW", "VOR", latitude=38.0, longitude=108.0, frequency=113.4),
        _navaid("a", "A", "VOR", latitude=35.0, longitude=105.0, frequency=111.2),
    ]

    first = diff_navaids(items, baseline)
    second = diff_navaids(reversed(items), baseline)

    assert first.selected_navaids == second.selected_navaids
    assert [item.raw.key for item in first.matched_existing] == [
        item.raw.key for item in second.matched_existing
    ]


def test_load_and_merge_multiple_baseline_indexes_deduplicates_exact_rows(tmp_path: Path):
    first = _write_index(
        tmp_path / "first.sqlite",
        vors=[("A", "ZB", 111200, 0.0, 100, 105.0, 35.0, "A")],
        ndbs=[("N", "ZB", 44500, 0.0, 0, 106.0, 36.0, "N")],
    )
    second = _write_index(
        tmp_path / "second.sqlite",
        vors=[("A", "ZB", 111200, 0.0, 100, 105.0, 35.0, "A")],
        ndbs=[("M", "ZB", 44600, 0.0, 0, 107.0, 37.0, "M")],
    )

    merged = load_baseline_index((first, second))

    assert merged.counts_by_kind == {"VOR": 1, "NDB": 2}
    assert len(merged.sources) == 2
