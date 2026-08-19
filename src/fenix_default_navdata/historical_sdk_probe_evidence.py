from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class HistoricalSdkProbeEvidenceError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HistoricalSdkProbeEvidenceError(f"cannot read probe report: {path}") from error
    if not isinstance(value, dict):
        raise HistoricalSdkProbeEvidenceError(f"probe report is not an object: {path}")
    return value


def _layouts(report: Mapping[str, object]) -> list[dict[str, object]]:
    layouts = report.get("bgl_layouts")
    if not isinstance(layouts, list) or not layouts:
        raise HistoricalSdkProbeEvidenceError("probe report lacks BGL layouts")
    return [item for item in layouts if isinstance(item, dict)]


def _reader_ok(report: Mapping[str, object]) -> bool:
    reader = report.get("reader")
    return isinstance(reader, Mapping) and reader.get("ok") is True


def summarize_probe_pair(
    *,
    identifier: str,
    baseline: Path,
    variant: Path,
    disposition: str,
) -> dict[str, object]:
    left = _load(baseline)
    right = _load(variant)
    left_layouts = _layouts(left)
    right_layouts = _layouts(right)
    if len(left_layouts) != len(right_layouts):
        raise HistoricalSdkProbeEvidenceError("probe variants have different BGL file counts")
    rows: list[dict[str, object]] = []
    for left_item, right_item in zip(left_layouts, right_layouts, strict=True):
        if left_item.get("path") != right_item.get("path"):
            raise HistoricalSdkProbeEvidenceError("probe variants have different BGL paths")
        left_layout = left_item.get("layout")
        right_layout = right_item.get("layout")
        if not isinstance(left_layout, Mapping) or not isinstance(right_layout, Mapping):
            raise HistoricalSdkProbeEvidenceError("probe report has an unreadable BGL layout")
        rows.append({
            "path": left_item["path"],
            "size_changed": left_item.get("size") != right_item.get("size"),
            "section_types_changed": left_layout.get("section_types") != right_layout.get("section_types"),
            "section_counts_changed": left_layout.get("section_counts") != right_layout.get("section_counts"),
            "section_sizes_changed": left_layout.get("section_sizes") != right_layout.get("section_sizes"),
        })
    return {
        "identifier": identifier,
        "baseline_report": str(baseline.expanduser().resolve()),
        "variant_report": str(variant.expanduser().resolve()),
        "reader_complete": _reader_ok(left) and _reader_ok(right),
        "bgl_files": rows,
        "disposition": disposition,
    }


def audit_historical_sdk_probe_evidence(cases: list[dict[str, object]]) -> dict[str, object]:
    if not cases:
        raise ValueError("at least one probe case is required")
    rows = [
        summarize_probe_pair(
            identifier=str(case["identifier"]),
            baseline=Path(str(case["baseline"])),
            variant=Path(str(case["variant"])),
            disposition=str(case["disposition"]),
        )
        for case in cases
    ]
    return {
        "diagnostic": "historical-sdk-probe-evidence-v1",
        "read_only": True,
        "reference_payload_read": False,
        "cases": rows,
        "all_reader_complete": all(row["reader_complete"] for row in rows),
    }


def write_historical_sdk_probe_evidence(path: Path, report: Mapping[str, object]) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
