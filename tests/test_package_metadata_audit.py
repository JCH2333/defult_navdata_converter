import json
from pathlib import Path

from fenix_default_navdata.package_metadata_audit import (
    audit_package_derived_metadata,
)


def _filetime_bytes(value: int) -> bytes:
    high = (value >> 32) & 0xFFFFFFFF
    low = value & 0xFFFFFFFF
    return high.to_bytes(4, "little") + low.to_bytes(4, "little")


def _write_package(
    root: Path,
    *,
    package_name: str = "zzz-pmdg-china-navdata",
    date: int = 0,
    bgl_size: int = 12,
    title: str = "China NavData",
) -> Path:
    package = root / package_name
    package.mkdir(parents=True)
    (package / "manifest.json").write_text(json.dumps({
        "content_type": "SCENERY",
        "title": title,
        "package_version": "0.1.0",
        "minimum_game_version": "1.7.35",
    }), encoding="utf-8")
    (package / "layout.json").write_text(json.dumps({
        "content": [
            {
                "path": "scenery/pmdg-china-navdata/00_enroute.bgl",
                "size": bgl_size,
                "date": date,
            },
            {"path": "bglindex.bout", "size": 17, "date": 0},
        ],
    }), encoding="utf-8")
    index = b"prefix" + (_filetime_bytes(date) if date else b"\0" * 8) + b"tail"
    (package / "bglIndex.bout").write_bytes(index)
    history = package / "ContentInfo" / package_name / "ContentHistory.json"
    history.parent.mkdir(parents=True)
    history.write_text(json.dumps({
        "package-name": package_name,
        "items": [],
    }), encoding="utf-8")
    return package


def test_package_metadata_audit_identifies_time_normalization_without_payload_read(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    _write_package(candidate, date=0)
    _write_package(reference, date=132_000_000_000_000_000)

    report = audit_package_derived_metadata(candidate, reference)

    assert report["diagnostic"] == "package-derived-metadata-audit-v1"
    assert report["read_only"] is True
    assert report["reference_payload_read"] is False
    assert report["reference_records_exported"] is False
    assert report["summary"]["reference_package_roots"] == [
        "zzz-pmdg-china-navdata"
    ]
    assert report["summary"]["candidate_excluded_support_packages"] == 0
    package = report["packages"][0]
    assert package["disposition"] == "controlled_by_current_normalization"
    assert (
        package["artifacts"]["layout"]["comparison"]["disposition"]
        == "controlled_by_current_normalization"
    )
    assert (
        package["artifacts"]["index"]["comparison"]["disposition"]
        == "controlled_by_current_normalization"
    )
    reference_index = package["artifacts"]["index"]["reference"]
    assert reference_index["filetime_linkage_exact"] is True
    assert reference_index["unexplained_range_count"] == 2


def test_package_metadata_audit_identifies_project_definition_difference(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    _write_package(candidate, title="Candidate")
    _write_package(reference, title="Reference")

    report = audit_package_derived_metadata(candidate, reference)

    package = report["packages"][0]
    comparison = package["artifacts"]["manifest"]["comparison"]
    assert comparison["status"] == "changed"
    assert comparison["top_level_keys_equal"] is True
    assert comparison["shape_equal"] is True
    assert comparison["contract_field_equal"]["title"] is False
    assert comparison["changed_top_level_fields"] == ["title"]
    assert comparison["disposition"] == "controlled_by_project_definition"
    assert package["disposition"] == "controlled_by_project_definition"


def test_package_metadata_audit_keeps_layout_size_difference_unexplained(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    _write_package(candidate, bgl_size=11)
    _write_package(reference, bgl_size=12)

    report = audit_package_derived_metadata(candidate, reference)

    package = report["packages"][0]
    assert (
        package["artifacts"]["layout"]["comparison"]["disposition"]
        == "unexplained_without_content_inference"
    )
    assert package["disposition"] == "unexplained_without_content_inference"
