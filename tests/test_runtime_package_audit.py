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
    return package


def _write_bgl(package, relative_path):
    target = package / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"BGL")


def _write_valid_package_set(root):
    for name in ("navigraph-nav-base", "navigraph-nav-jepp"):
        _write_package(root, name)
    nav = _write_package(
        root,
        "zzz-pmdg-china-navdata",
        ("navigraph-nav-base", "navigraph-nav-jepp"),
    )
    patch = _write_package(
        root,
        "zzz-pmdg-china-navdata-airport-patch",
        ("zzz-pmdg-china-navdata",),
    )
    _write_bgl(nav, "scenery/pmdg-china-navdata/00_enroute.bgl")
    for region in ("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"):
        _write_bgl(
            patch,
            f"scenery/pmdg-china-airport-patch/{region}_airports.bgl",
        )


def test_canonical_package_dependency_closure(tmp_path):
    _write_valid_package_set(tmp_path)
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


def test_navigation_package_rejects_duplicate_airport_bgls(tmp_path):
    _write_valid_package_set(tmp_path)
    nav = tmp_path / "zzz-pmdg-china-navdata"
    _write_bgl(nav, "scenery/pmdg-china-navdata/ZU_airports.bgl")

    report = audit_runtime_package_set(tmp_path)

    assert report["valid"] is False
    assert report["content_errors"] == [{
        "package": "zzz-pmdg-china-navdata",
        "expected_bgl_paths": ["scenery/pmdg-china-navdata/00_enroute.bgl"],
        "actual_bgl_paths": [
            "scenery/pmdg-china-navdata/00_enroute.bgl",
            "scenery/pmdg-china-navdata/ZU_airports.bgl",
        ],
        "reason": "navigation_package_must_contain_enroute_only",
    }]
