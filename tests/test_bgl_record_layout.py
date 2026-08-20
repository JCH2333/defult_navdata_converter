import struct
from pathlib import Path

import pytest

from fenix_default_navdata.bgl_format import BglFormatError
from fenix_default_navdata.bgl_record_layout import (
    audit_bgl_record_layouts,
    decode_bgl_record_layout,
)


def _bgl(sections: tuple[tuple[int, int, bytes], ...]) -> bytes:
    header_size = 0x38
    table_size = len(sections) * 20
    offset = header_size + table_size
    table = []
    payload = bytearray()
    for type_id, count, content in sections:
        table.append((type_id, 1, count, offset, len(content)))
        payload.extend(content)
        offset += len(content)
    return (
        struct.pack("<IIIIII", 0x19920201, header_size, 0, 0, 0x8040103, len(sections))
        + struct.pack("<8I", *([0] * 8))
        + b"".join(struct.pack("<IIIII", *item) for item in table)
        + bytes(payload)
    )


def test_decode_bgl_record_layout_closes_fixed_stride_sections(tmp_path: Path) -> None:
    path = tmp_path / "fixture.bgl"
    path.write_bytes(_bgl(((0x03, 2, b"AAAABBBB"), (0x17, 1, b"CCCC"))))

    report = decode_bgl_record_layout(path)

    assert report["all_sections_closed"] is True
    assert report["sections"][0]["layout"] == "fixed_stride"
    assert report["sections"][0]["record_stride"] == 4
    assert [record["size"] for record in report["sections"][0]["records"]] == [4, 4]
    assert report["sections"][1]["known_target_section"] is True


def test_decode_bgl_record_layout_rejects_truncated_section(tmp_path: Path) -> None:
    path = tmp_path / "truncated.bgl"
    path.write_bytes(_bgl(((0x03, 1, b"AAAA"),))[:-1])

    with pytest.raises(BglFormatError, match="outside BGL bounds"):
        decode_bgl_record_layout(path)


def test_decode_bgl_record_layout_marks_nondivisible_sections_unresolved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "variable.bgl"
    path.write_bytes(_bgl(((0x33, 2, b"AAAAA"),)))

    report = decode_bgl_record_layout(path)

    section = report["sections"][0]
    assert report["all_sections_closed"] is False
    assert section["layout"] == "unresolved_variable_length"
    assert section["records"] == []


def test_record_layout_audit_compares_only_structural_summaries(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.bgl"
    reference = tmp_path / "reference.bgl"
    candidate.write_bytes(_bgl(((0x03, 1, b"AAAA"),)))
    reference.write_bytes(_bgl(((0x03, 1, b"BBBB"),)))

    report = audit_bgl_record_layouts(candidate, reference)

    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["candidate"]["sections"][0]["records"][0]["sha256"] != (
        report["reference"]["sections"][0]["records"][0]["sha256"]
    )
