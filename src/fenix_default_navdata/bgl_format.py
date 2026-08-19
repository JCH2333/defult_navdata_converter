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


def _package_files(
    root: Path,
    *,
    package_roots: set[str] | None = None,
) -> tuple[dict[str, Path], dict[str, int]]:
    if not root.is_dir():
        raise FileNotFoundError(f"包根目录不存在: {root}")
    files: dict[str, Path] = {}
    excluded = {
        "sdk_work_files": 0,
        "support_package_files": 0,
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        top_level = relative.parts[0].casefold()
        if top_level == "_work":
            excluded["sdk_work_files"] += 1
            continue
        if package_roots is not None and top_level not in package_roots:
            excluded["support_package_files"] += 1
            continue
        files[relative.as_posix().lower()] = path
    return files, excluded


def _file_role(relative_path: str) -> tuple[str, str]:
    parts = relative_path.split("/")
    filename = parts[-1]
    if filename == "00_enroute.bgl":
        return "enroute_bgl", "424_enroute"
    if filename.endswith("_airports.bgl"):
        prefix = filename.split("_", 1)[0].upper()
        if "airport-patch" in relative_path:
            return "airport_patch_bgl", f"424_airports_{prefix}"
        return "regional_airport_bgl", f"424_airports_{prefix}"
    if filename == "bglindex.bout":
        return "package_index", "package_generated"
    if filename == "layout.json":
        return "package_layout", "package_generated"
    if filename == "manifest.json":
        return "package_manifest", "package_generated"
    if filename == "contenthistory.json":
        return "content_history", "package_generated"
    return "package_file", "package_generated"


def _convergence_file_summary(path: Path) -> dict[str, object]:
    summary: dict[str, object] = {
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if path.suffix.lower() == ".bgl":
        try:
            summary["bgl_layout"] = _layout_summary(path)
        except BglFormatError as error:
            summary["bgl_layout_error"] = str(error)
    return summary


def audit_file_convergence(
    candidate_root: Path,
    reference_root: Path,
    *,
    repeat_candidate_root: Path | None = None,
) -> dict[str, object]:
    """Create a per-file convergence board without reading navigation records."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    repeat_root = (
        repeat_candidate_root.expanduser().resolve()
        if repeat_candidate_root is not None
        else None
    )
    reference_files, reference_excluded = _package_files(reference_root)
    package_roots = {path.split("/", 1)[0] for path in reference_files}
    candidate_files, candidate_excluded = _package_files(
        candidate_root,
        package_roots=package_roots or None,
    )
    repeat_files: dict[str, Path] = {}
    repeat_excluded = {"sdk_work_files": 0, "support_package_files": 0}
    if repeat_root is not None:
        repeat_files, repeat_excluded = _package_files(
            repeat_root,
            package_roots=package_roots or None,
        )

    rows: list[dict[str, object]] = []
    equal_reference_files = 0
    equal_repeat_files = 0
    for relative_path in sorted(set(candidate_files) | set(reference_files) | set(repeat_files)):
        role, source_group = _file_role(relative_path)
        row: dict[str, object] = {
            "path": relative_path,
            "role": role,
            "source_group": source_group,
        }
        candidate = candidate_files.get(relative_path)
        reference = reference_files.get(relative_path)
        repeat = repeat_files.get(relative_path)
        if candidate is not None:
            row["candidate"] = _convergence_file_summary(candidate)
        if reference is not None:
            row["reference"] = _convergence_file_summary(reference)
        if repeat is not None:
            row["repeat"] = _convergence_file_summary(repeat)
        if candidate is None:
            row["reference_status"] = "missing_candidate"
        elif reference is None:
            row["reference_status"] = "missing_reference"
        else:
            equal = row["candidate"]["sha256"] == row["reference"]["sha256"]
            row["reference_status"] = "equal" if equal else "changed"
            if equal:
                equal_reference_files += 1
        if repeat_root is not None:
            if candidate is None:
                row["repeat_status"] = "missing_candidate"
            elif repeat is None:
                row["repeat_status"] = "missing_repeat_candidate"
            else:
                equal = row["candidate"]["sha256"] == row["repeat"]["sha256"]
                row["repeat_status"] = "equal" if equal else "changed"
                if equal:
                    equal_repeat_files += 1
        rows.append(row)

    reference_scope = len(set(candidate_files) | set(reference_files))
    repeat_scope = len(set(candidate_files) | set(repeat_files))
    return {
        "diagnostic": "file-convergence-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "repeat_candidate_root": str(repeat_root) if repeat_root else None,
        "scope": {
            "reference_package_roots": sorted(package_roots),
            "candidate_excluded_sdk_work_files": candidate_excluded["sdk_work_files"],
            "candidate_excluded_support_package_files": candidate_excluded[
                "support_package_files"
            ],
            "reference_excluded_sdk_work_files": reference_excluded["sdk_work_files"],
            "repeat_excluded_sdk_work_files": repeat_excluded["sdk_work_files"],
            "repeat_excluded_support_package_files": repeat_excluded[
                "support_package_files"
            ],
        },
        "summary": {
            "reference_scope_files": reference_scope,
            "reference_equal_files": equal_reference_files,
            "reference_changed_or_missing_files": reference_scope - equal_reference_files,
            "repeat_scope_files": repeat_scope if repeat_root else None,
            "repeat_equal_files": equal_repeat_files if repeat_root else None,
            "repeat_changed_or_missing_files": (
                repeat_scope - equal_repeat_files if repeat_root else None
            ),
        },
        "files": rows,
    }


def write_file_convergence_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
