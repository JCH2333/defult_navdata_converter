import json
from pathlib import Path

from fenix_default_navdata.package import BASE_PACKAGE, JEPP_PACKAGE
from fenix_default_navdata.validation import validate_candidate


def test_candidate_requires_both_official_baselines(tmp_path: Path):
    (tmp_path / BASE_PACKAGE).mkdir()
    (tmp_path / JEPP_PACKAGE).mkdir()
    (tmp_path / "conversion-report.json").write_text(json.dumps({"deployable": False}), encoding="utf-8")
    result = validate_candidate(tmp_path)
    assert result["official_baseline_present"] is True
    assert result["valid"] is False
    assert result["deployable"] is False


def test_candidate_with_packages_but_unverified_navaid_diff_is_not_deployable(tmp_path: Path):
    from fenix_default_navdata.package import AIRPORT_PACKAGE, NAV_PACKAGE

    for package in (NAV_PACKAGE, AIRPORT_PACKAGE):
        root = tmp_path / package
        (root / "scenery").mkdir(parents=True)
        (root / "manifest.json").write_text("{}", encoding="utf-8")
        (root / "layout.json").write_text("{}", encoding="utf-8")
        (root / "bglIndex.bout").write_bytes(b"index")
        (root / "scenery" / "data.bgl").write_bytes(b"bgl")
    (tmp_path / "navigraph-nav-base").mkdir()
    (tmp_path / "navigraph-nav-jepp").mkdir()
    (tmp_path / "conversion-report.json").write_text(
        json.dumps({
            "deployable": True,
            "navaid_diff": {"navaid_diff_verified": False},
        }),
        encoding="utf-8",
    )

    result = validate_candidate(tmp_path)

    assert result["valid"] is True
    assert result["navaid_diff_verified"] is False
    assert result["deployable"] is False


def test_candidate_with_unverified_default_navaid_selection_is_not_deployable(tmp_path: Path):
    from fenix_default_navdata.package import AIRPORT_PACKAGE, NAV_PACKAGE

    for package in (NAV_PACKAGE, AIRPORT_PACKAGE):
        root = tmp_path / package
        (root / "scenery").mkdir(parents=True)
        (root / "manifest.json").write_text("{}", encoding="utf-8")
        (root / "layout.json").write_text("{}", encoding="utf-8")
        (root / "bglIndex.bout").write_bytes(b"index")
        (root / "scenery" / "data.bgl").write_bytes(b"bgl")
    (tmp_path / "navigraph-nav-base").mkdir()
    (tmp_path / "navigraph-nav-jepp").mkdir()
    (tmp_path / "conversion-report.json").write_text(
        json.dumps({
            "deployable": True,
            "navaid_diff": {"navaid_diff_verified": True},
            "navaid_selection": {"navaid_selection_verified": False},
            "official_baseline": {
                "navaid_index_verification": {"verified": True},
            },
            "official_region_resolution": {"verified": True},
        }),
        encoding="utf-8",
    )

    result = validate_candidate(tmp_path)

    assert result["valid"] is True
    assert result["navaid_selection_verified"] is False
    assert result["deployable"] is False


def test_candidate_requires_verified_official_region_resolution_for_deployment(tmp_path: Path):
    from fenix_default_navdata.package import AIRPORT_PACKAGE, NAV_PACKAGE

    for package in (NAV_PACKAGE, AIRPORT_PACKAGE):
        root = tmp_path / package
        (root / "scenery").mkdir(parents=True)
        (root / "manifest.json").write_text("{}", encoding="utf-8")
        (root / "layout.json").write_text("{}", encoding="utf-8")
        (root / "bglIndex.bout").write_bytes(b"index")
        (root / "scenery" / "data.bgl").write_bytes(b"bgl")
    (tmp_path / "navigraph-nav-base").mkdir()
    (tmp_path / "navigraph-nav-jepp").mkdir()
    (tmp_path / "conversion-report.json").write_text(
        json.dumps({
            "deployable": True,
            "navaid_diff": {"navaid_diff_verified": True},
            "official_baseline": {
                "navaid_index_verification": {"verified": True},
            },
            "official_region_resolution": {"verified": False},
        }),
        encoding="utf-8",
    )

    result = validate_candidate(tmp_path)

    assert result["valid"] is True
    assert result["navaid_diff_verified"] is True
    assert result["navaid_index_verified"] is True
    assert result["official_region_resolution_verified"] is False
    assert result["deployable"] is False
