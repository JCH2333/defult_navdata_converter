from __future__ import annotations

import json
import argparse
from pathlib import Path


OFFICIAL_PACKAGES = ("navigraph-nav-base", "navigraph-nav-jepp")
CANONICAL_CUSTOM_PACKAGES = (
    "zzz-pmdg-china-navdata",
    "zzz-pmdg-china-navdata-airport-patch",
)
CANDIDATE_ALIAS_PACKAGES = (
    "JCH-pmdg-china-navdata",
    "JCH-pmdg-china-navdata-airport-patch",
)


def _manifest(package_root: Path) -> dict[str, object]:
    path = package_root / "manifest.json"
    if not path.is_file():
        raise ValueError(f"包缺少 manifest.json: {package_root}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"包 manifest 不是对象: {path}")
    return payload


def _dependency_names(payload: dict[str, object]) -> set[str]:
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        return set()
    return {
        str(item.get("name") or "").strip()
        for item in dependencies
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def audit_runtime_package_set(
    root: Path,
    *,
    candidate_alias: bool = False,
) -> dict[str, object]:
    """Audit package names, manifests and dependency closure without mutation."""
    root = root.expanduser().resolve()
    expected_custom = (
        CANDIDATE_ALIAS_PACKAGES
        if candidate_alias
        else CANONICAL_CUSTOM_PACKAGES
    )
    expected = (*OFFICIAL_PACKAGES, *expected_custom)
    present = {
        path.name: path
        for path in root.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    } if root.is_dir() else {}
    missing = [name for name in expected if name not in present]
    unexpected_custom = [
        name
        for name in sorted(present)
        if name.startswith(("JCH-pmdg-china-navdata", "zzz-pmdg-china-navdata"))
        and name not in expected_custom
    ]
    manifest_reports: dict[str, object] = {}
    dependency_errors: list[dict[str, object]] = []
    for name in expected:
        if name not in present:
            continue
        payload = _manifest(present[name])
        dependencies = sorted(_dependency_names(payload))
        missing_dependencies = [
            dependency for dependency in dependencies if dependency not in present
        ]
        if missing_dependencies:
            dependency_errors.append({
                "package": name,
                "missing_dependencies": missing_dependencies,
            })
        manifest_reports[name] = {
            "folder": str(present[name]),
            "dependencies": dependencies,
            "package_order_hint": payload.get("package_order_hint"),
            "package_version": payload.get("package_version"),
        }
    canonical_patch = (
        CANDIDATE_ALIAS_PACKAGES[1]
        if candidate_alias
        else CANONICAL_CUSTOM_PACKAGES[1]
    )
    canonical_nav = (
        CANDIDATE_ALIAS_PACKAGES[0]
        if candidate_alias
        else CANONICAL_CUSTOM_PACKAGES[0]
    )
    patch_report = manifest_reports.get(canonical_patch)
    if isinstance(patch_report, dict):
        dependencies = patch_report.get("dependencies", [])
        if canonical_nav not in dependencies:
            dependency_errors.append({
                "package": canonical_patch,
                "expected_dependency": canonical_nav,
                "actual_dependencies": dependencies,
            })
    return {
        "root": str(root),
        "candidate_alias": candidate_alias,
        "expected_packages": list(expected),
        "present_packages": sorted(present),
        "missing_packages": missing,
        "unexpected_custom_packages": unexpected_custom,
        "dependency_errors": dependency_errors,
        "manifests": manifest_reports,
        "valid": not missing and not unexpected_custom and not dependency_errors,
    }


def normalize_candidate_alias(root: Path) -> dict[str, object]:
    """Repair generated JCH package metadata without touching canonical packages."""
    root = root.expanduser().resolve()
    old_nav, old_patch = CANONICAL_CUSTOM_PACKAGES
    new_nav, new_patch = CANDIDATE_ALIAS_PACKAGES
    for old_name, new_name in ((old_nav, new_nav), (old_patch, new_patch)):
        package = root / new_name
        if not package.is_dir():
            raise FileNotFoundError(package)
        manifest = _manifest(package)
        if old_name == old_patch:
            manifest["dependencies"] = [
                {
                    **item,
                    "name": new_nav if item.get("name") == old_nav else item.get("name"),
                }
                for item in manifest.get("dependencies", [])
                if isinstance(item, dict)
            ]
        (package / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        content_info = package / "ContentInfo"
        old_content = content_info / old_name
        new_content = content_info / new_name
        if old_content.is_dir() and not new_content.exists():
            old_content.rename(new_content)
        history = new_content / "ContentHistory.json"
        if history.is_file():
            payload = json.loads(history.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                payload["package-name"] = new_name
                history.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        layout = package / "layout.json"
        if layout.is_file():
            payload = json.loads(layout.read_text(encoding="utf-8-sig"))
            for item in payload.get("content", []):
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    item["path"] = item["path"].replace(
                        old_name.lower(), new_name.lower()
                    )
            layout.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    return audit_runtime_package_set(root, candidate_alias=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit or normalize generated Default navdata package metadata"
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--candidate-alias", action="store_true")
    parser.add_argument("--normalize-candidate-alias", action="store_true")
    args = parser.parse_args()
    report = (
        normalize_candidate_alias(args.root)
        if args.normalize_candidate_alias
        else audit_runtime_package_set(
            args.root,
            candidate_alias=args.candidate_alias,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
