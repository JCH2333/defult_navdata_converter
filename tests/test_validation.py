import json
from pathlib import Path

from fenix_default_navdata.package import AIRPORT_PACKAGE, BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE
from fenix_default_navdata.validation import validate_candidate


def _write_overlay_packages(root: Path) -> None:
    for package in (NAV_PACKAGE, AIRPORT_PACKAGE):
        package_root = root / package
        (package_root / "scenery").mkdir(parents=True)
        (package_root / "manifest.json").write_text("{}", encoding="utf-8")
        (package_root / "layout.json").write_text("{}", encoding="utf-8")
        (package_root / "bglIndex.bout").write_bytes(b"index")
        (package_root / "scenery" / "data.bgl").write_bytes(b"bgl")


def _source_checks() -> dict[str, object]:
    return {
        "navaid_diff": {"navaid_diff_verified": True},
        "navaid_selection": {"navaid_selection_verified": True},
        "official_baseline": {
            "navaid_index_verification": {"verified": True},
        },
        "official_region_resolution": {"verified": True},
    }


def _flight_validation() -> dict[str, object]:
    return {
        "airports": {
            airport: {
                "airport_input": True,
                "runways": True,
                "procedures": True,
            }
            for airport in ("ZBCF", "ZUNZ", "ZUUU")
        },
        "exit_flight": True,
        "exit_simulator": True,
    }


def test_candidate_requires_both_official_baselines(tmp_path: Path):
    (tmp_path / BASE_PACKAGE).mkdir()
    (tmp_path / JEPP_PACKAGE).mkdir()
    (tmp_path / "conversion-report.json").write_text(json.dumps({"deployable": False}), encoding="utf-8")
    result = validate_candidate(tmp_path)
    assert result["official_baseline_present"] is True
    assert result["valid"] is False
    assert result["deployable"] is False


def test_candidate_with_packages_but_unverified_navaid_diff_is_not_deployable(tmp_path: Path):
    _write_overlay_packages(tmp_path)
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
    _write_overlay_packages(tmp_path)
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
    _write_overlay_packages(tmp_path)
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


def test_complete_test_build_remains_non_deployable(tmp_path: Path):
    _write_overlay_packages(tmp_path)
    (tmp_path / BASE_PACKAGE).mkdir()
    (tmp_path / JEPP_PACKAGE).mkdir()
    report = {
        **_source_checks(),
        "status": "candidate",
        "test_build": True,
        "flight_validation": _flight_validation(),
    }
    (tmp_path / "conversion-report.json").write_text(
        json.dumps(report), encoding="utf-8",
    )

    result = validate_candidate(tmp_path)

    assert result["local_contract_verified"] is True
    assert result["flight_validation_verified"] is True
    assert result["byte_equal_reference"] is False
    assert result["deployable"] is False


def test_release_requires_matching_reference_and_complete_flight_validation(tmp_path: Path):
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    candidate.mkdir()
    reference.mkdir()
    _write_overlay_packages(candidate)
    _write_overlay_packages(reference)
    for root in (candidate, reference):
        (root / BASE_PACKAGE).mkdir()
        (root / JEPP_PACKAGE).mkdir()
    report = {
        **_source_checks(),
        "status": "release",
        "test_build": False,
        "reference": str(reference),
        "flight_validation": _flight_validation(),
    }
    (candidate / "conversion-report.json").write_text(
        json.dumps(report), encoding="utf-8",
    )

    result = validate_candidate(candidate)

    assert result["local_contract_verified"] is True
    assert result["byte_equal_reference"] is True
    assert result["flight_validation_verified"] is True
    assert result["deployable"] is True
