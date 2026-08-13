from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .package import AIRPORT_PACKAGE, BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, sha256


_REQUIRED_AIRPORTS = ("ZBCF", "ZUNZ", "ZUUU")
_REQUIRED_AIRPORT_CHECKS = ("airport_input", "runways", "procedures")
_REQUIRED_EXIT_CHECKS = ("exit_flight", "exit_simulator")


def _file_map(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix().lower(): (path.stat().st_size, sha256(path))
        for path in root.rglob("*") if path.is_file()
    }


def compare_trees(candidate: Path, reference: Path) -> dict[str, object]:
    left, right = _file_map(candidate), _file_map(reference)
    names = sorted(set(left) | set(right))
    equal = [name for name in names if name in left and name in right and left[name] == right[name]]
    changed = [name for name in names if name in left and name in right and left[name] != right[name]]
    return {
        "byte_equal": left == right,
        "candidate_files": len(left),
        "reference_files": len(right),
        "equal_files": len(equal),
        "changed_files": changed[:100],
        "missing_files": [name for name in names if name not in left][:100],
        "extra_files": [name for name in names if name not in right][:100],
    }


def _configured_reference(report: dict[str, object]) -> Path | None:
    value = report.get("reference")
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser()


def _flight_validation_status(report: dict[str, object]) -> dict[str, object]:
    evidence = report.get("flight_validation")
    if not isinstance(evidence, dict):
        return {
            "verified": False,
            "missing_checks": ["flight_validation"],
        }
    missing: list[str] = []
    airports = evidence.get("airports")
    if not isinstance(airports, dict):
        missing.append("airports")
        airports = {}
    for airport in _REQUIRED_AIRPORTS:
        checks = airports.get(airport)
        if not isinstance(checks, dict):
            missing.extend(f"{airport}.{check}" for check in _REQUIRED_AIRPORT_CHECKS)
            continue
        missing.extend(
            f"{airport}.{check}"
            for check in _REQUIRED_AIRPORT_CHECKS
            if checks.get(check) is not True
        )
    missing.extend(
        check for check in _REQUIRED_EXIT_CHECKS
        if evidence.get(check) is not True
    )
    return {
        "verified": not missing,
        "missing_checks": missing,
    }


def validate_candidate(candidate: Path, reference: Path | None = None) -> dict[str, object]:
    candidate = candidate.resolve()
    report_path = candidate / "conversion-report.json"
    if not candidate.is_dir() or not report_path.is_file():
        raise FileNotFoundError(f"不是候选目录或缺少 conversion-report.json: {candidate}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = [candidate / BASE_PACKAGE, candidate / JEPP_PACKAGE]
    missing = [str(path) for path in required if not path.is_dir()]
    if missing:
        raise RuntimeError("候选缺少官方基线包: " + ", ".join(missing))
    package_dirs = [candidate / NAV_PACKAGE, candidate / AIRPORT_PACKAGE]
    bgls = [path for package_dir in package_dirs if package_dir.is_dir() for path in package_dir.rglob("*.bgl")]
    package_contract = all(
        package_dir.is_dir()
        and (package_dir / "manifest.json").is_file()
        and (package_dir / "layout.json").is_file()
        and (package_dir / "bglIndex.bout").is_file()
        and bool(list(package_dir.rglob("*.bgl")))
        for package_dir in package_dirs
    )
    navaid_diff = report.get("navaid_diff")
    navaid_diff_verified = bool(
        isinstance(navaid_diff, dict)
        and navaid_diff.get("navaid_diff_verified")
    )
    navaid_selection = report.get("navaid_selection")
    navaid_selection_verified = bool(
        isinstance(navaid_selection, dict)
        and navaid_selection.get("navaid_selection_verified")
    )
    official_baseline = report.get("official_baseline")
    index_verification = (
        official_baseline.get("navaid_index_verification")
        if isinstance(official_baseline, dict)
        else None
    )
    navaid_index_verified = bool(
        isinstance(index_verification, dict)
        and index_verification.get("verified")
    )
    official_region_resolution = report.get("official_region_resolution")
    official_region_resolution_verified = bool(
        isinstance(official_region_resolution, dict)
        and official_region_resolution.get("verified")
    )
    local_contract_verified = (
        package_contract
        and navaid_diff_verified
        and navaid_selection_verified
        and navaid_index_verified
        and official_region_resolution_verified
    )
    flight_validation = _flight_validation_status(report)
    selected_reference = reference or _configured_reference(report)
    result = {
        "valid": not missing and package_contract,
        "deployable": False,
        "official_baseline_present": not missing,
        "navaid_diff_verified": navaid_diff_verified,
        "navaid_selection_verified": navaid_selection_verified,
        "navaid_index_verified": navaid_index_verified,
        "official_region_resolution_verified": official_region_resolution_verified,
        "local_contract_verified": local_contract_verified,
        "package_contract": package_contract,
        "bgl_count": len(bgls),
        "report_status": report.get("status"),
        "test_build": bool(report.get("test_build")),
        "compiler": report.get("compiler"),
        "flight_validation": flight_validation,
        "flight_validation_verified": bool(flight_validation["verified"]),
        "reference": None,
        "byte_equal_reference": False,
    }
    if selected_reference is not None and selected_reference.is_dir():
        result["reference"] = {
            NAV_PACKAGE: compare_trees(candidate / NAV_PACKAGE, selected_reference / NAV_PACKAGE)
            if (candidate / NAV_PACKAGE).is_dir() and (selected_reference / NAV_PACKAGE).is_dir() else None,
            AIRPORT_PACKAGE: compare_trees(candidate / AIRPORT_PACKAGE, selected_reference / AIRPORT_PACKAGE)
            if (candidate / AIRPORT_PACKAGE).is_dir() and (selected_reference / AIRPORT_PACKAGE).is_dir() else None,
        }
        result["byte_equal_reference"] = all(
            item is not None and item["byte_equal"]
            for item in result["reference"].values()
        )
    elif selected_reference is not None:
        result["reference"] = {"error": f"参考目录不存在: {selected_reference}"}
    result["deployable"] = (
        local_contract_verified
        and result["byte_equal_reference"]
        and result["flight_validation_verified"]
        and not result["test_build"]
        and result["report_status"] == "release"
    )
    return result
