from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .package import AIRPORT_PACKAGE, BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, sha256


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
    result = {
        "valid": not missing and package_contract,
        "deployable": bool(report.get("deployable")) and package_contract and navaid_diff_verified,
        "official_baseline_present": not missing,
        "navaid_diff_verified": navaid_diff_verified,
        "package_contract": package_contract,
        "bgl_count": len(bgls),
        "report_status": report.get("status"),
        "test_build": bool(report.get("test_build")),
        "compiler": report.get("compiler"),
        "reference": None,
    }
    if reference:
        result["reference"] = {
            NAV_PACKAGE: compare_trees(candidate / NAV_PACKAGE, reference / NAV_PACKAGE)
            if (candidate / NAV_PACKAGE).is_dir() and (reference / NAV_PACKAGE).is_dir() else None,
            AIRPORT_PACKAGE: compare_trees(candidate / AIRPORT_PACKAGE, reference / AIRPORT_PACKAGE)
            if (candidate / AIRPORT_PACKAGE).is_dir() and (reference / AIRPORT_PACKAGE).is_dir() else None,
        }
        result["byte_equal_reference"] = all(
            item is not None and item["byte_equal"]
            for item in result["reference"].values()
        )
    return result
