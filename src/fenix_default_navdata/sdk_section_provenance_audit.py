from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .bgl_format import BglFormatError, parse_bgl_file


class SdkSectionProvenanceAuditError(RuntimeError):
    """Raised when a section provenance manifest is malformed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_path(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SdkSectionProvenanceAuditError(f"{label} must be a non-empty path")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise SdkSectionProvenanceAuditError(f"{label} does not exist: {path}")
    return path


def _section_summary(path: Path) -> dict[str, object]:
    try:
        header = parse_bgl_file(path)
    except (OSError, BglFormatError) as error:
        raise SdkSectionProvenanceAuditError(
            f"cannot parse BGL header: {path}"
        ) from error
    return {
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "version": f"{header.version:#x}",
        "qmid_tiles": [f"{tile:#x}" for tile in header.qmid_tiles],
        "sections": [
            {
                "type": section.type,
                "field_a": section.field_a,
                "count": section.count,
                "size": section.size,
            }
            for section in header.sections
        ],
    }


def _section_delta(
    baseline: Mapping[str, object], variant: Mapping[str, object]
) -> dict[str, object]:
    baseline_sections = baseline["sections"]
    variant_sections = variant["sections"]
    if not isinstance(baseline_sections, list) or not isinstance(variant_sections, list):
        raise SdkSectionProvenanceAuditError("BGL summary lacks sections")
    baseline_by_type: dict[int, list[Mapping[str, object]]] = {}
    variant_by_type: dict[int, list[Mapping[str, object]]] = {}
    for section in baseline_sections:
        if isinstance(section, Mapping) and isinstance(section.get("type"), int):
            baseline_by_type.setdefault(section["type"], []).append(section)
    for section in variant_sections:
        if isinstance(section, Mapping) and isinstance(section.get("type"), int):
            variant_by_type.setdefault(section["type"], []).append(section)
    rows: list[dict[str, object]] = []
    for section_type in sorted(set(baseline_by_type) | set(variant_by_type)):
        left = baseline_by_type.get(section_type, [])
        right = variant_by_type.get(section_type, [])
        rows.append({
            "type": section_type,
            "baseline_occurrences": len(left),
            "variant_occurrences": len(right),
            "baseline_counts": [item.get("count") for item in left],
            "variant_counts": [item.get("count") for item in right],
            "baseline_sizes": [item.get("size") for item in left],
            "variant_sizes": [item.get("size") for item in right],
        })
    return {
        "section_table_equal": baseline_sections == variant_sections,
        "section_types_equal": {
            "baseline": sorted(baseline_by_type),
            "variant": sorted(variant_by_type),
        },
        "by_type": rows,
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkSectionProvenanceAuditError(
            f"cannot read provenance manifest: {path}"
        ) from error
    if not isinstance(value, dict) or value.get("diagnostic") != "sdk-section-provenance-manifest-v1":
        raise SdkSectionProvenanceAuditError(
            "manifest diagnostic must be sdk-section-provenance-manifest-v1"
        )
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SdkSectionProvenanceAuditError("manifest cases must be a non-empty list")
    return value


def _same_input_output_replays(
    case_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize repeated XML inputs without requiring them to be baselines."""

    replays: list[dict[str, object]] = []
    for case in case_rows:
        baseline = case["baseline"]
        variants = case["variants"]
        if not isinstance(baseline, Mapping) or not isinstance(variants, list):
            raise SdkSectionProvenanceAuditError("audit case lacks result rows")
        entries = [("baseline", baseline)]
        entries.extend(
            (str(variant["name"]), variant)
            for variant in variants
            if isinstance(variant, Mapping)
        )
        by_xml_hash: dict[str, list[tuple[str, Mapping[str, object]]]] = {}
        for name, entry in entries:
            xml = entry.get("xml")
            if not isinstance(xml, Mapping) or not isinstance(xml.get("sha256"), str):
                raise SdkSectionProvenanceAuditError("audit result lacks XML hash")
            by_xml_hash.setdefault(xml["sha256"], []).append((name, entry))
        for xml_hash, grouped_entries in sorted(by_xml_hash.items()):
            if len(grouped_entries) < 2:
                continue
            bgl_hashes: set[str] = set()
            for _, entry in grouped_entries:
                bgl = entry.get("bgl")
                if not isinstance(bgl, Mapping) or not isinstance(bgl.get("sha256"), str):
                    raise SdkSectionProvenanceAuditError("audit result lacks BGL hash")
                bgl_hashes.add(bgl["sha256"])
            replays.append({
                "case": case["name"],
                "xml_sha256": xml_hash,
                "entries": [name for name, _ in grouped_entries],
                "bgl_sha256": sorted(bgl_hashes),
                "output_consistent": len(bgl_hashes) == 1,
            })
    return replays


def audit_sdk_section_provenance(manifest_path: Path) -> dict[str, object]:
    """Audit deterministic XML-to-BGL Section deltas without navigation semantics."""

    manifest_path = manifest_path.expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    case_rows: list[dict[str, object]] = []
    for index, raw_case in enumerate(manifest["cases"]):
        if not isinstance(raw_case, Mapping):
            raise SdkSectionProvenanceAuditError(f"case {index} is not an object")
        name = raw_case.get("name")
        if not isinstance(name, str) or not name:
            raise SdkSectionProvenanceAuditError(f"case {index} lacks name")
        baseline = raw_case.get("baseline")
        if not isinstance(baseline, Mapping):
            raise SdkSectionProvenanceAuditError(f"case {name} lacks baseline")
        baseline_xml = _required_path(baseline.get("xml"), label=f"{name}.baseline.xml")
        baseline_bgl = _required_path(baseline.get("bgl"), label=f"{name}.baseline.bgl")
        baseline_summary = _section_summary(baseline_bgl)
        variants = raw_case.get("variants")
        if not isinstance(variants, list) or not variants:
            raise SdkSectionProvenanceAuditError(f"case {name} variants must be non-empty")
        variant_rows: list[dict[str, object]] = []
        for variant_index, raw_variant in enumerate(variants):
            if not isinstance(raw_variant, Mapping):
                raise SdkSectionProvenanceAuditError(
                    f"case {name} variant {variant_index} is not an object"
                )
            variant_name = raw_variant.get("name")
            if not isinstance(variant_name, str) or not variant_name:
                raise SdkSectionProvenanceAuditError(
                    f"case {name} variant {variant_index} lacks name"
                )
            variant_xml = _required_path(
                raw_variant.get("xml"),
                label=f"{name}.{variant_name}.xml",
            )
            variant_bgl = _required_path(
                raw_variant.get("bgl"),
                label=f"{name}.{variant_name}.bgl",
            )
            variant_summary = _section_summary(variant_bgl)
            variant_rows.append({
                "name": variant_name,
                "xml": {
                    "path": str(variant_xml),
                    "sha256": _sha256(variant_xml),
                },
                "bgl": {
                    "path": str(variant_bgl),
                    **variant_summary,
                },
                "same_xml_as_baseline": _sha256(variant_xml) == _sha256(baseline_xml),
                "section_delta": _section_delta(baseline_summary, variant_summary),
            })
        case_rows.append({
            "name": name,
            "baseline": {
                "xml": {"path": str(baseline_xml), "sha256": _sha256(baseline_xml)},
                "bgl": {"path": str(baseline_bgl), **baseline_summary},
            },
            "variants": variant_rows,
        })
    same_input_output_replays = _same_input_output_replays(case_rows)
    section_effects: dict[int, dict[str, list[str]]] = {}
    same_input_replays = 0
    for case in case_rows:
        baseline_bgl = case["baseline"]["bgl"]
        for variant in case["variants"]:
            delta = variant["section_delta"]
            if (
                variant["same_xml_as_baseline"]
                and delta["section_table_equal"]
                and variant["bgl"]["sha256"] == baseline_bgl["sha256"]
            ):
                same_input_replays += 1
            for row in delta["by_type"]:
                section_type = int(row["type"])
                effect = section_effects.setdefault(
                    section_type,
                    {"added_or_increased": [], "removed_or_decreased": []},
                )
                baseline_counts = row["baseline_counts"]
                variant_counts = row["variant_counts"]
                if baseline_counts != variant_counts:
                    if sum(variant_counts) > sum(baseline_counts):
                        effect["added_or_increased"].append(
                            f"{case['name']}:{variant['name']}"
                        )
                    else:
                        effect["removed_or_decreased"].append(
                            f"{case['name']}:{variant['name']}"
                        )
    return {
        "diagnostic": "sdk-section-provenance-audit-v1",
        "read_only": True,
        "navigation_records_read": False,
        "reference_payload_read": False,
        "manifest": str(manifest_path),
        "summary": {
            "case_count": len(case_rows),
            "variant_count": sum(len(case["variants"]) for case in case_rows),
            "same_input_replay_count": same_input_replays,
            "same_input_output_replay_count": sum(
                len(item["entries"]) - 1
                for item in same_input_output_replays
                if item["output_consistent"]
            ),
            "same_input_output_mismatch_count": sum(
                1
                for item in same_input_output_replays
                if not item["output_consistent"]
            ),
            "same_input_output_replays": same_input_output_replays,
            "section_effects": {
                f"{section_type:#x}": {
                    key: sorted(values)
                    for key, values in sorted(effect.items())
                }
                for section_type, effect in sorted(section_effects.items())
            },
        },
        "cases": case_rows,
        "decision": {
            "section_type_semantics_inferred": False,
            "projection_authorized": False,
            "reason": (
                "Section deltas establish reproducible SDK output effects only. "
                "They do not identify navigation object semantics or authorize "
                "formal adapter changes."
            ),
        },
    }


def write_sdk_section_provenance_audit(
    path: Path, report: Mapping[str, object]
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
