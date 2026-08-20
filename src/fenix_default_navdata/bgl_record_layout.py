from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .bgl_format import BglFormatError, BglHeader, parse_bgl_header

_KNOWN_SECTION_TYPES = frozenset({0x03, 0x13, 0x17, 0x22, 0x32, 0x33, 0x34, 0x35})


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _section_records(
    data: bytes,
    *,
    header: BglHeader,
) -> list[dict[str, object]]:
    table_end = header.header_size + header.section_count * 20
    ranges: list[tuple[int, int]] = []
    sections: list[dict[str, object]] = []
    occurrences: dict[int, int] = {}
    for section in header.sections:
        occurrence = occurrences.get(section.type, 0)
        occurrences[section.type] = occurrence + 1
        start = section.offset
        end = start + section.size
        if start < table_end or end < start or end > len(data):
            raise BglFormatError(
                f"section {section.type:#x}/{occurrence} is outside BGL bounds"
            )
        ranges.append((start, end))
        item: dict[str, object] = {
            "type": f"{section.type:#x}",
            "occurrence": occurrence,
            "count": section.count,
            "offset": start,
            "size": section.size,
            "known_target_section": section.type in _KNOWN_SECTION_TYPES,
        }
        if section.count == 0 and section.size == 0:
            item.update({"layout": "empty", "closed": True, "records": []})
        elif section.count > 0 and section.size % section.count == 0:
            stride = section.size // section.count
            item.update({
                "layout": "fixed_stride",
                "closed": True,
                "record_stride": stride,
                "records": [
                    {
                        "index": index,
                        "offset": start + index * stride,
                        "size": stride,
                        "sha256": _digest(data[start + index * stride:start + (index + 1) * stride]),
                    }
                    for index in range(section.count)
                ],
            })
        else:
            item.update({
                "layout": "unresolved_variable_length",
                "closed": False,
                "reason": "section size is not divisible by its declared record count",
                "records": [],
            })
        sections.append(item)
    for previous, current in zip(sorted(ranges), sorted(ranges)[1:]):
        if previous[1] > current[0]:
            raise BglFormatError("BGL sections overlap")
    return sections


def decode_bgl_record_layout(path: Path) -> dict[str, object]:
    """Decode only fixed-stride record boundaries and cryptographic summaries."""

    resolved = path.expanduser().resolve()
    data = resolved.read_bytes()
    header = parse_bgl_header(data)
    sections = _section_records(data, header=header)
    return {
        "path": str(resolved),
        "file_size": len(data),
        "header": {
            "version": f"{header.version:#x}",
            "section_count": header.section_count,
            "qmid_tile_count": len(header.qmid_tiles),
        },
        "sections": sections,
        "all_sections_closed": all(section["closed"] for section in sections),
    }


def _section_key(section: dict[str, object]) -> tuple[str, int]:
    return str(section["type"]), int(section["occurrence"])


def _sequence_digest(records: list[dict[str, object]]) -> str:
    return _digest(
        b"".join(bytes.fromhex(str(record["sha256"])) for record in records)
    )


def _section_summary(section: dict[str, object]) -> dict[str, object]:
    result = {
        key: section[key]
        for key in (
            "type",
            "occurrence",
            "count",
            "size",
            "known_target_section",
            "layout",
            "closed",
        )
    }
    if section["layout"] == "fixed_stride":
        records = section["records"]
        result.update({
            "record_stride": section["record_stride"],
            "ordered_record_sha256": _sequence_digest(records),
        })
    return result


def _compact_layout(layout: dict[str, object]) -> dict[str, object]:
    return {
        "file_size": layout["file_size"],
        "header": layout["header"],
        "sections": [_section_summary(section) for section in layout["sections"]],
        "all_sections_closed": layout["all_sections_closed"],
    }


def _section_comparison(
    candidate: dict[str, object] | None,
    reference: dict[str, object] | None,
) -> dict[str, object]:
    key_source = candidate or reference
    assert key_source is not None
    result: dict[str, object] = {
        "type": key_source["type"],
        "occurrence": key_source["occurrence"],
    }
    if candidate is None:
        result["status"] = "missing_candidate"
        return result
    if reference is None:
        result["status"] = "missing_reference"
        return result
    result["status"] = "changed"
    if (
        candidate["layout"] != "fixed_stride"
        or reference["layout"] != "fixed_stride"
    ):
        result["reason"] = "record boundary layout is not closed on both sides"
        return result
    candidate_records = candidate["records"]
    reference_records = reference["records"]
    common_count = min(len(candidate_records), len(reference_records))
    matching_positions = sum(
        candidate_records[index]["sha256"] == reference_records[index]["sha256"]
        for index in range(common_count)
    )
    first_difference = next(
        (
            index
            for index in range(common_count)
            if candidate_records[index]["sha256"] != reference_records[index]["sha256"]
        ),
        None,
    )
    ordered_equal = (
        len(candidate_records) == len(reference_records)
        and matching_positions == common_count
    )
    result.update({
        "status": "equal" if ordered_equal else "changed",
        "candidate_record_count": len(candidate_records),
        "reference_record_count": len(reference_records),
        "common_record_count": common_count,
        "matching_position_count": matching_positions,
        "first_different_record_index": first_difference,
        "candidate_trailing_records": len(candidate_records) - common_count,
        "reference_trailing_records": len(reference_records) - common_count,
        "ordered_record_sha256_equal": ordered_equal,
    })
    return result


def audit_bgl_record_layouts(candidate: Path, reference: Path) -> dict[str, object]:
    """Compare record-layout summaries without exporting reference record values."""

    candidate_layout = decode_bgl_record_layout(candidate)
    reference_layout = decode_bgl_record_layout(reference)
    candidate_sections = {
        _section_key(section): section
        for section in candidate_layout["sections"]
    }
    reference_sections = {
        _section_key(section): section
        for section in reference_layout["sections"]
    }
    comparisons = [
        _section_comparison(
            candidate_sections.get(key),
            reference_sections.get(key),
        )
        for key in sorted(set(candidate_sections) | set(reference_sections))
    ]
    return {
        "diagnostic": "bgl-record-layout-audit-v1",
        "read_only": True,
        "reference_records_exported": False,
        "candidate": _compact_layout(candidate_layout),
        "reference": _compact_layout(reference_layout),
        "section_comparisons": comparisons,
        "summary": {
            "candidate_all_sections_closed": candidate_layout["all_sections_closed"],
            "reference_all_sections_closed": reference_layout["all_sections_closed"],
            "candidate_section_count": len(candidate_layout["sections"]),
            "reference_section_count": len(reference_layout["sections"]),
            "equal_ordered_sections": sum(
                item["status"] == "equal" for item in comparisons
            ),
            "changed_or_missing_sections": sum(
                item["status"] != "equal" for item in comparisons
            ),
        },
    }


def write_bgl_record_layout_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
