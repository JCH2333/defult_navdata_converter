from __future__ import annotations

import struct

import pytest

from fenix_default_navdata.bgl_format import (
    MAGVAR_SECTION_TYPE,
    PACKAGE_TOOL_MAGVAR_SIZE,
    BglFormatError,
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
