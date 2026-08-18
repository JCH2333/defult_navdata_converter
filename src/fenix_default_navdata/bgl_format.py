from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

_HEADER_MAGIC = 0x19920201
_HEADER_SIZE = 0x38
_SECTION_RECORD_SIZE = 20
_QMID_COUNT = 8
MAGVAR_SECTION_TYPE = 0x20
PACKAGE_TOOL_MAGVAR_SIZE = 0x240000


class BglFormatError(ValueError):
    """Raised when a BGL header or section table cannot be parsed."""


@dataclass(frozen=True)
class BglSection:
    type: int
    field_a: int
    count: int
    offset: int
    size: int

    @property
    def is_magvar(self) -> bool:
        return self.type == MAGVAR_SECTION_TYPE


@dataclass(frozen=True)
class BglHeader:
    magic: int
    header_size: int
    version: int
    section_count: int
    qmid_tiles: tuple[int, ...]
    sections: tuple[BglSection, ...]

    @property
    def embedded_magvar_size(self) -> int:
        return sum(section.size for section in self.sections if section.is_magvar)


def parse_bgl_header(data: bytes) -> BglHeader:
    """Parse the MSFS 2024 BGL header and section table without reading payloads."""

    if len(data) < _HEADER_SIZE:
        raise BglFormatError("BGL shorter than the 0x38-byte header")
    magic, header_size, _time_low, _time_high, version, section_count = struct.unpack_from(
        "<IIIIII", data, 0
    )
    if magic != _HEADER_MAGIC:
        raise BglFormatError(f"unexpected BGL magic: {magic:#x}")
    if header_size != _HEADER_SIZE:
        raise BglFormatError(f"unexpected BGL header size: {header_size:#x}")
    qmid_tiles = struct.unpack_from("<" + "I" * _QMID_COUNT, data, 24)
    table_end = _HEADER_SIZE + section_count * _SECTION_RECORD_SIZE
    if len(data) < table_end:
        raise BglFormatError("BGL truncated before the section table ended")
    sections = []
    for index in range(section_count):
        offset = _HEADER_SIZE + index * _SECTION_RECORD_SIZE
        type_id, field_a, count, section_offset, size = struct.unpack_from(
            "<IIIII", data, offset
        )
        sections.append(
            BglSection(
                type=type_id,
                field_a=field_a,
                count=count,
                offset=section_offset,
                size=size,
            )
        )
    return BglHeader(
        magic=magic,
        header_size=header_size,
        version=version,
        section_count=section_count,
        qmid_tiles=qmid_tiles,
        sections=tuple(sections),
    )


def parse_bgl_file(path: Path) -> BglHeader:
    """Parse only the header and section table of a BGL file."""

    with path.open("rb") as handle:
        data = handle.read(_HEADER_SIZE + 32 * _SECTION_RECORD_SIZE)
    return parse_bgl_header(data)


def header_summary(header: BglHeader) -> dict[str, object]:
    return {
        "section_count": header.section_count,
        "section_types": [f"{section.type:#x}" for section in header.sections],
        "qmid_tiles": [f"{tile:#x}" for tile in header.qmid_tiles],
        "embedded_magvar_size": header.embedded_magvar_size,
        "has_embedded_magvar": header.embedded_magvar_size > 0,
    }
