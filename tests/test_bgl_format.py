from __future__ import annotations

import struct

import pytest

from fenix_default_navdata.bgl_format import (
    MAGVAR_SECTION_TYPE,
    PACKAGE_TOOL_MAGVAR_SIZE,
    BglFormatError,
    audit_bgl_layouts,
    header_summary,
    parse_bgl_header,
)


def _header(
    *,
    section_count: int,
    qmid: tuple[int, ...],
    sections: tuple[tuple[int, int, int, int, int], ...],
) -> bytes:
    payload = struct.pack(
        "<IIIIII",
        0x19920201,
        0x38,
        0,
        0,
        0x08051803,
        section_count,
    )
    padded = qmid + (0,) * (8 - len(qmid))
    payload += struct.pack("<" + "I" * 8, *padded[:8])
    for section in sections:
        payload += struct.pack("<IIIII", *section)
    return payload


def test_parse_bgl_header_reads_package_tool_magvar_section() -> None:
    data = _header(
        section_count=2,
        qmid=(0x20, 0x21, 0x22, 0x23, 0x24, 0x26, 0, 0),
        sections=(
            (0x03, 1, 1, 0x74, 0x10),
            (MAGVAR_SECTION_TYPE, 2, 0x18000, 0x84, PACKAGE_TOOL_MAGVAR_SIZE),
        ),
    )

    header = parse_bgl_header(data)

    assert header.section_count == 2
    assert [section.type for section in header.sections] == [0x03, MAGVAR_SECTION_TYPE]
    assert header.sections[1].count == 0x18000
    assert header.embedded_magvar_size == PACKAGE_TOOL_MAGVAR_SIZE
    assert header_summary(header)["has_embedded_magvar"] is True


def test_parse_bgl_header_detects_reference_airport_without_magvar() -> None:
    data = _header(
        section_count=3,
        qmid=(0x924, 0x925, 0x926, 0x927, 0x24B, 0x930, 0x932, 0x24E),
        sections=(
            (0x03, 1, 4, 0xC4, 0x40),
            (0x13, 1, 3, 0x104, 0x30),
            (0x22, 1, 17, 0x134, 0x110),
        ),
    )

    header = parse_bgl_header(data)

    assert MAGVAR_SECTION_TYPE not in [section.type for section in header.sections]
    assert header.embedded_magvar_size == 0
    assert header_summary(header)["has_embedded_magvar"] is False


def test_parse_bgl_header_rejects_truncated_section_table() -> None:
    data = _header(
        section_count=2,
        qmid=(0x20, 0x21, 0x22, 0x23, 0x24, 0x26, 0, 0),
        sections=((0x03, 1, 1, 0x74, 0x10),),
    )

    with pytest.raises(BglFormatError, match="truncated"):
        parse_bgl_header(data)


def test_bgl_layout_audit_reports_only_file_and_header_contract(tmp_path) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    candidate_bgl = candidate / "pkg" / "scenery" / "changed.bgl"
    reference_bgl = reference / "pkg" / "scenery" / "changed.bgl"
    candidate_bgl.parent.mkdir(parents=True)
    reference_bgl.parent.mkdir(parents=True)
    candidate_bgl.write_bytes(_header(
        section_count=2,
        qmid=(0x20, 0x21),
        sections=((0x03, 1, 1, 0x7C, 0x10), (0x22, 1, 2, 0x8C, 0x20)),
    ))
    reference_bgl.write_bytes(_header(
        section_count=3,
        qmid=(0x20, 0x21),
        sections=(
            (0x03, 1, 1, 0x90, 0x10),
            (0x17, 1, 2, 0xA0, 0x20),
            (0x22, 1, 2, 0xC0, 0x20),
        ),
    ))
    only_candidate = candidate / "pkg" / "scenery" / "only-candidate.bgl"
    only_candidate.write_bytes(_header(
        section_count=1,
        qmid=(0x20,),
        sections=((0x03, 1, 1, 0x6C, 0x10),),
    ))

    report = audit_bgl_layouts(candidate, reference)

    assert report["diagnostic"] == "bgl-layout-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["scope"] == {
        "reference_package_roots": ["pkg"],
        "candidate_excluded_sdk_work_bgl_files": 0,
        "candidate_excluded_support_package_bgl_files": 0,
        "reference_excluded_sdk_work_bgl_files": 0,
    }
    assert report["summary"] == {
        "candidate_bgl_files": 2,
        "reference_bgl_files": 1,
        "equal_files": 0,
        "equal_layouts": 0,
        "changed_or_missing": 2,
    }
    rows = {row["path"]: row for row in report["files"]}
    changed = rows["pkg/scenery/changed.bgl"]
    assert changed["status"] == "changed"
    assert changed["candidate_layout"]["section_types"] == ["0x3", "0x22"]
    assert changed["reference_layout"]["section_types"] == ["0x3", "0x17", "0x22"]
    assert changed["candidate_layout"]["section_counts"] == [1, 2]
    assert "sha256" not in changed
    assert rows["pkg/scenery/only-candidate.bgl"] == {
        "path": "pkg/scenery/only-candidate.bgl",
        "status": "missing_reference",
        "candidate_size": only_candidate.stat().st_size,
    }


def test_bgl_layout_audit_ignores_sdk_work_area(tmp_path) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    final_bgl = candidate / "pkg" / "scenery" / "final.bgl"
    reference_bgl = reference / "pkg" / "scenery" / "final.bgl"
    intermediate_bgl = candidate / "_work" / "pkg" / "scenery" / "intermediate.bgl"
    for path in (final_bgl, reference_bgl, intermediate_bgl):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_header(
            section_count=1,
            qmid=(0x20,),
            sections=((0x03, 1, 1, 0x6C, 0x10),),
        ))

    report = audit_bgl_layouts(candidate, reference)

    assert report["summary"] == {
        "candidate_bgl_files": 1,
        "reference_bgl_files": 1,
        "equal_files": 1,
        "equal_layouts": 1,
        "changed_or_missing": 0,
    }
    assert report["scope"]["candidate_excluded_sdk_work_bgl_files"] == 1
    assert [row["path"] for row in report["files"]] == ["pkg/scenery/final.bgl"]


def test_bgl_layout_audit_excludes_candidate_support_packages(tmp_path) -> None:
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    final_bgl = candidate / "final-package" / "scenery" / "final.bgl"
    reference_bgl = reference / "final-package" / "scenery" / "final.bgl"
    support_bgl = candidate / "support-package" / "scenery" / "baseline.bgl"
    for path in (final_bgl, reference_bgl, support_bgl):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_header(
            section_count=1,
            qmid=(0x20,),
            sections=((0x03, 1, 1, 0x6C, 0x10),),
        ))

    report = audit_bgl_layouts(candidate, reference)

    assert report["summary"]["candidate_bgl_files"] == 1
    assert report["scope"]["reference_package_roots"] == ["final-package"]
    assert report["scope"]["candidate_excluded_support_package_bgl_files"] == 1
    assert [row["path"] for row in report["files"]] == [
        "final-package/scenery/final.bgl",
    ]
