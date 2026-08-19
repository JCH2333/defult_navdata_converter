from __future__ import annotations

import hashlib
import json
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bgl_paths(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        raise FileNotFoundError(f"BGL 包根目录不存在: {root}")
    return tuple(path for path in sorted(root.rglob("*.bgl")) if path.is_file())


def _bgl_files(
    root: Path,
    *,
    package_roots: set[str] | None = None,
) -> tuple[dict[str, Path], dict[str, int]]:
    files: dict[str, Path] = {}
    excluded = {
        "sdk_work_bgl_files": 0,
        "support_package_bgl_files": 0,
    }
    for path in _bgl_paths(root):
        relative = path.relative_to(root)
        top_level = relative.parts[0].casefold()
        if top_level == "_work":
            excluded["sdk_work_bgl_files"] += 1
            continue
        if package_roots is not None and top_level not in package_roots:
            excluded["support_package_bgl_files"] += 1
            continue
        files[relative.as_posix().lower()] = path
    return files, excluded


def _layout_summary(path: Path) -> dict[str, object]:
    header = parse_bgl_file(path)
    return {
        **header_summary(header),
        "version": f"{header.version:#x}",
        "section_counts": [section.count for section in header.sections],
        "section_sizes": [section.size for section in header.sections],
    }


def audit_bgl_layouts(candidate_root: Path, reference_root: Path) -> dict[str, object]:
    """Compare BGL file layouts without reading or exporting navigation records."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    reference_files, reference_excluded = _bgl_files(reference_root)
    reference_package_roots = {
        relative_path.split("/", 1)[0]
        for relative_path in reference_files
    }
    candidate_files, candidate_excluded = _bgl_files(
        candidate_root,
        package_roots=reference_package_roots or None,
    )
    rows: list[dict[str, object]] = []
    equal_files = 0
    equal_layouts = 0

    for relative_path in sorted(set(candidate_files) | set(reference_files)):
        candidate = candidate_files.get(relative_path)
        reference = reference_files.get(relative_path)
        row: dict[str, object] = {"path": relative_path}
        if candidate is None:
            row.update({
                "status": "missing_candidate",
                "reference_size": reference.stat().st_size,
            })
            rows.append(row)
            continue
        if reference is None:
            row.update({
                "status": "missing_reference",
                "candidate_size": candidate.stat().st_size,
            })
            rows.append(row)
            continue

        candidate_hash = _sha256(candidate)
        reference_hash = _sha256(reference)
        row.update({
            "status": "equal" if candidate_hash == reference_hash else "changed",
            "candidate_size": candidate.stat().st_size,
            "reference_size": reference.stat().st_size,
            "size_delta": candidate.stat().st_size - reference.stat().st_size,
            "sha256_equal": candidate_hash == reference_hash,
        })
        if candidate_hash == reference_hash:
            equal_files += 1
        try:
            row["candidate_layout"] = _layout_summary(candidate)
        except BglFormatError as error:
            row["candidate_layout_error"] = str(error)
        try:
            row["reference_layout"] = _layout_summary(reference)
        except BglFormatError as error:
            row["reference_layout_error"] = str(error)
        candidate_layout = row.get("candidate_layout")
        reference_layout = row.get("reference_layout")
        if candidate_layout is not None and candidate_layout == reference_layout:
            equal_layouts += 1
        rows.append(row)

    return {
        "diagnostic": "bgl-layout-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "scope": {
            "reference_package_roots": sorted(reference_package_roots),
            "candidate_excluded_sdk_work_bgl_files": candidate_excluded["sdk_work_bgl_files"],
            "candidate_excluded_support_package_bgl_files": (
                candidate_excluded["support_package_bgl_files"]
            ),
            "reference_excluded_sdk_work_bgl_files": reference_excluded["sdk_work_bgl_files"],
        },
        "summary": {
            "candidate_bgl_files": len(candidate_files),
            "reference_bgl_files": len(reference_files),
            "equal_files": equal_files,
            "equal_layouts": equal_layouts,
            "changed_or_missing": len(rows) - equal_files,
        },
        "files": rows,
    }


def write_bgl_layout_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
