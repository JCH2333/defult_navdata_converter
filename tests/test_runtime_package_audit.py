import json

from fenix_default_navdata.runtime_package_audit import audit_runtime_package_set


def _write_package(root, name, dependencies=()):
    package = root / name
    package.mkdir()
    (package / "manifest.json").write_text(
        json.dumps({"dependencies": [
            {"name": dependency, "package_version": "1"}
            for dependency in dependencies
        ]}),
        encoding="utf-8",
    )


def test_canonical_package_dependency_closure(tmp_path):
    for name in ("navigraph-nav-base", "navigraph-nav-jepp"):
        _write_package(tmp_path, name)
    _write_package(
        tmp_path,
        "zzz-pmdg-china-navdata",
        ("navigraph-nav-base", "navigraph-nav-jepp"),
    )
    _write_package(
        tmp_path,
        "zzz-pmdg-china-navdata-airport-patch",
        ("zzz-pmdg-china-navdata",),
    )
    report = audit_runtime_package_set(tmp_path)
    assert report["valid"] is True


def test_alias_patch_must_depend_on_alias_navigation_package(tmp_path):
    for name in ("navigraph-nav-base", "navigraph-nav-jepp"):
        _write_package(tmp_path, name)
    _write_package(
        tmp_path,
        "JCH-pmdg-china-navdata",
        ("navigraph-nav-base", "navigraph-nav-jepp"),
    )
    _write_package(
        tmp_path,
        "JCH-pmdg-china-navdata-airport-patch",
        ("zzz-pmdg-china-navdata",),
    )
    report = audit_runtime_package_set(tmp_path, candidate_alias=True)
    assert report["valid"] is False
    assert any(
        item.get("expected_dependency") == "JCH-pmdg-china-navdata"
        for item in report["dependency_errors"]
    )
