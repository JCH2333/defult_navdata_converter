from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


_METADATA_FILES = ("manifest.json", "layout.json", "bglIndex.bout")
_MANIFEST_FIELDS = (
    "content_type",
    "title",
    "manufacturer",
    "creator",
    "package_version",
    "minimum_game_version",
    "minimum_compatibility_version",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _public_summary(summary: dict[str, object] | None) -> dict[str, object] | None:
    if summary is None:
        return None
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def _json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        item_shapes = {_shape_key(_json_shape(item)) for item in value}
        return {"list_item_shapes": sorted(item_shapes), "length": len(value)}
    return type(value).__name__


def _shape_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _filetime_bytes(value: int) -> bytes:
    high = (value >> 32) & 0xFFFFFFFF
    low = value & 0xFFFFFFFF
    return high.to_bytes(4, "little") + low.to_bytes(4, "little")


def _all_positions(data: bytes, needle: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = data.find(needle, start)
        if position < 0:
            return positions
        positions.append(position)
        start = position + len(needle)


def _remaining_ranges(total_size: int, positions: list[int]) -> dict[str, int]:
    spans = sorted((position, position + 8) for position in positions)
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    remaining_ranges = 0
    remaining_bytes = 0
    cursor = 0
    for start, end in merged:
        if cursor < start:
            remaining_ranges += 1
            remaining_bytes += start - cursor
        cursor = end
    if cursor < total_size:
        remaining_ranges += 1
        remaining_bytes += total_size - cursor
    return {
        "known_filetime_spans": len(merged),
        "unexplained_range_count": remaining_ranges,
        "unexplained_bytes": remaining_bytes,
    }


def _layout_summary(path: Path) -> dict[str, object]:
    payload = _load_json(path)
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, list):
        raise ValueError(f"layout.json 缺少 content 数组: {path}")
    entries: list[dict[str, object]] = []
    invalid_entries = 0
    for entry in content:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            invalid_entries += 1
            continue
        normalized_path = entry["path"].replace("\\", "/").casefold()
        size = entry.get("size")
        date = entry.get("date")
        entries.append({
            "path": normalized_path,
            "size": size,
            "date": date,
            "is_bgl": normalized_path.endswith(".bgl"),
        })
    entries.sort(key=lambda entry: str(entry["path"]))
    stable_entries = [
        {"path": entry["path"], "size": entry["size"]}
        for entry in entries
    ]
    return {
        "sha256": _sha256(path),
        "top_level_keys": sorted(payload) if isinstance(payload, dict) else [],
        "shape": _json_shape(payload),
        "content_count": len(entries),
        "invalid_content_entries": invalid_entries,
        "bgl_content_count": sum(bool(entry["is_bgl"]) for entry in entries),
        "entries": entries,
        "stable_entries": stable_entries,
    }


def _manifest_summary(path: Path) -> dict[str, object]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"manifest.json 不是对象: {path}")
    return {
        "_payload": payload,
        "sha256": _sha256(path),
        "top_level_keys": sorted(payload),
        "shape": _json_shape(payload),
        "contract_fields": {key: payload.get(key) for key in _MANIFEST_FIELDS if key in payload},
        "dependency_count": len(payload.get("dependencies", []))
        if isinstance(payload.get("dependencies"), list)
        else None,
    }


def _content_history_paths(package_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(
        path for path in package_root.rglob("ContentHistory.json") if path.is_file()
    ))


def _content_history_summary(path: Path, package_root: Path) -> dict[str, object]:
    payload = _load_json(path)
    items = payload.get("items") if isinstance(payload, dict) else None
    item_keys = Counter(
        tuple(sorted(item))
        for item in items
        if isinstance(items, list) and isinstance(item, dict)
    )
    return {
        "_payload": payload,
        "path": path.relative_to(package_root).as_posix(),
        "sha256": _sha256(path),
        "top_level_keys": sorted(payload) if isinstance(payload, dict) else [],
        "shape": _json_shape(payload),
        "package_name": payload.get("package-name") if isinstance(payload, dict) else None,
        "item_count": len(items) if isinstance(items, list) else None,
        "item_field_sets": [
            {"fields": list(keys), "count": count}
            for keys, count in sorted(item_keys.items())
        ],
    }


def _index_summary(path: Path, layout: dict[str, object]) -> dict[str, object]:
    data = path.read_bytes()
    bgl_dates = Counter(
        int(entry["date"])
        for entry in layout["entries"]
        if entry["is_bgl"]
        and isinstance(entry["date"], int)
        and int(entry["date"]) > 0
    )
    matches: list[dict[str, object]] = []
    all_positions: list[int] = []
    for timestamp, expected_count in sorted(bgl_dates.items()):
        positions = _all_positions(data, _filetime_bytes(timestamp))
        all_positions.extend(positions)
        matches.append({
            "filetime": timestamp,
            "layout_bgl_entries": expected_count,
            "index_occurrences": len(positions),
            "exact": len(positions) == expected_count,
        })
    return {
        "size": len(data),
        "sha256": _sha256(path),
        "layout_nonzero_bgl_filetimes": sum(bgl_dates.values()),
        "filetime_matches": matches,
        "filetime_linkage_exact": bool(matches) and all(item["exact"] for item in matches),
        **_remaining_ranges(len(data), all_positions),
    }


def _package_roots(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"包根目录不存在: {root}")
    packages: dict[str, Path] = {}
    for manifest in sorted(root.rglob("manifest.json")):
        package_root = manifest.parent
        relative = package_root.relative_to(root)
        if not relative.parts or relative.parts[0].casefold() == "_work":
            continue
        if all((package_root / name).is_file() for name in _METADATA_FILES):
            packages[relative.as_posix().casefold()] = package_root
    return packages


def _layout_comparison(
    candidate: dict[str, object] | None,
    reference: dict[str, object] | None,
) -> dict[str, object]:
    if candidate is None or reference is None:
        return {"status": "missing", "disposition": "unexplained_without_content_inference"}
    stable_equal = candidate["stable_entries"] == reference["stable_entries"]
    raw_equal = candidate["sha256"] == reference["sha256"]
    dates_equal = [
        entry["date"] for entry in candidate["entries"]
    ] == [
        entry["date"] for entry in reference["entries"]
    ]
    if raw_equal:
        disposition = "equal"
    elif stable_equal and not dates_equal:
        disposition = "controlled_by_current_normalization"
    elif stable_equal:
        disposition = "controlled_by_project_definition"
    else:
        disposition = "unexplained_without_content_inference"
    return {
        "status": "equal" if raw_equal else "changed",
        "stable_path_and_size_equal": stable_equal,
        "dates_equal": dates_equal,
        "disposition": disposition,
    }


def _metadata_comparison(
    candidate: dict[str, object] | None,
    reference: dict[str, object] | None,
) -> dict[str, object]:
    if candidate is None or reference is None:
        return {"status": "missing", "disposition": "unexplained_without_content_inference"}
    raw_equal = candidate["sha256"] == reference["sha256"]
    candidate_fields = dict(candidate.get("contract_fields", {}))
    reference_fields = dict(reference.get("contract_fields", {}))
    contract_field_equal = {
        key: candidate_fields.get(key) == reference_fields.get(key)
        for key in sorted(set(candidate_fields) | set(reference_fields))
    }
    candidate_payload = candidate.get("_payload")
    reference_payload = reference.get("_payload")
    changed_top_level_fields = []
    if isinstance(candidate_payload, dict) and isinstance(reference_payload, dict):
        changed_top_level_fields = [
            key
            for key in sorted(set(candidate_payload) | set(reference_payload))
            if candidate_payload.get(key) != reference_payload.get(key)
        ]
    return {
        "status": "equal" if raw_equal else "changed",
        "top_level_keys_equal": candidate["top_level_keys"] == reference["top_level_keys"],
        "shape_equal": candidate["shape"] == reference["shape"],
        "contract_field_equal": contract_field_equal,
        "changed_top_level_fields": changed_top_level_fields,
        "disposition": "equal" if raw_equal else "controlled_by_project_definition",
    }


def _index_comparison(
    candidate: dict[str, object] | None,
    reference: dict[str, object] | None,
    layout: dict[str, object],
) -> dict[str, object]:
    if candidate is None or reference is None:
        return {"status": "missing", "disposition": "unexplained_without_content_inference"}
    raw_equal = candidate["sha256"] == reference["sha256"]
    if raw_equal:
        disposition = "equal"
    elif layout["disposition"] == "controlled_by_current_normalization":
        disposition = "controlled_by_current_normalization"
    elif candidate["filetime_linkage_exact"] and reference["filetime_linkage_exact"]:
        disposition = "requires_sdk_or_template_version_probe"
    else:
        disposition = "unexplained_without_content_inference"
    return {
        "status": "equal" if raw_equal else "changed",
        "disposition": disposition,
    }


def _package_disposition(artifacts: dict[str, dict[str, object]]) -> str:
    dispositions = {
        str(
            artifact.get("disposition")
            or dict(artifact.get("comparison", {})).get("disposition")
        )
        for artifact in artifacts.values()
    }
    if "unexplained_without_content_inference" in dispositions:
        return "unexplained_without_content_inference"
    if "requires_sdk_or_template_version_probe" in dispositions:
        return "requires_sdk_or_template_version_probe"
    if "controlled_by_project_definition" in dispositions:
        return "controlled_by_project_definition"
    if "controlled_by_current_normalization" in dispositions:
        return "controlled_by_current_normalization"
    return "equal"


def _history_comparison(
    candidate: list[dict[str, object]],
    reference: list[dict[str, object]],
) -> dict[str, object]:
    candidate_map = {str(item["path"]).casefold(): item for item in candidate}
    reference_map = {str(item["path"]).casefold(): item for item in reference}
    rows = []
    for path in sorted(set(candidate_map) | set(reference_map)):
        rows.append({
            "path": path,
            "comparison": _metadata_comparison(candidate_map.get(path), reference_map.get(path)),
            "candidate": _public_summary(candidate_map.get(path)),
            "reference": _public_summary(reference_map.get(path)),
        })
    return {
        "status": "equal" if rows and all(
            row["comparison"]["status"] == "equal" for row in rows
        ) else "changed",
        "disposition": (
            "equal"
            if rows and all(row["comparison"]["status"] == "equal" for row in rows)
            else "controlled_by_project_definition"
        ),
        "files": rows,
    }


def audit_package_derived_metadata(
    candidate_root: Path,
    reference_root: Path,
) -> dict[str, object]:
    """Compare package metadata without reading BGL navigation payloads."""

    candidate_root = candidate_root.expanduser().resolve()
    reference_root = reference_root.expanduser().resolve()
    reference_packages = _package_roots(reference_root)
    reference_package_names = set(reference_packages)
    candidate_packages = {
        name: package
        for name, package in _package_roots(candidate_root).items()
        if name in reference_package_names
    }
    rows: list[dict[str, object]] = []
    for package_name in sorted(reference_package_names):
        candidate_package = candidate_packages.get(package_name)
        reference_package = reference_packages.get(package_name)
        candidate_layout = (
            _layout_summary(candidate_package / "layout.json")
            if candidate_package is not None
            else None
        )
        reference_layout = (
            _layout_summary(reference_package / "layout.json")
            if reference_package is not None
            else None
        )
        candidate_manifest = (
            _manifest_summary(candidate_package / "manifest.json")
            if candidate_package is not None
            else None
        )
        reference_manifest = (
            _manifest_summary(reference_package / "manifest.json")
            if reference_package is not None
            else None
        )
        artifacts: dict[str, dict[str, object]] = {
            "layout": {
                "candidate": candidate_layout,
                "reference": reference_layout,
                "comparison": _layout_comparison(candidate_layout, reference_layout),
            },
            "manifest": {
                "candidate": _public_summary(candidate_manifest),
                "reference": _public_summary(reference_manifest),
            },
        }
        artifacts["manifest"]["comparison"] = _metadata_comparison(
            candidate_manifest,
            reference_manifest,
        )
        candidate_history = [
            _content_history_summary(path, candidate_package)
            for path in _content_history_paths(candidate_package)
        ] if candidate_package is not None else []
        reference_history = [
            _content_history_summary(path, reference_package)
            for path in _content_history_paths(reference_package)
        ] if reference_package is not None else []
        artifacts["content_history"] = _history_comparison(
            candidate_history,
            reference_history,
        )
        candidate_index = (
            _index_summary(candidate_package / "bglIndex.bout", candidate_layout)
            if candidate_package is not None and candidate_layout is not None
            else None
        )
        reference_index = (
            _index_summary(reference_package / "bglIndex.bout", reference_layout)
            if reference_package is not None and reference_layout is not None
            else None
        )
        artifacts["index"] = {
            "candidate": candidate_index,
            "reference": reference_index,
            "comparison": _index_comparison(
                candidate_index,
                reference_index,
                artifacts["layout"]["comparison"],
            ),
        }
        rows.append({
            "package": package_name,
            "candidate_present": candidate_package is not None,
            "reference_present": reference_package is not None,
            "artifacts": artifacts,
            "disposition": _package_disposition(artifacts),
        })
    disposition_counts = Counter(str(row["disposition"]) for row in rows)
    return {
        "diagnostic": "package-derived-metadata-audit-v1",
        "read_only": True,
        "reference_payload_read": False,
        "reference_records_exported": False,
        "candidate_root": str(candidate_root),
        "reference_root": str(reference_root),
        "summary": {
            "package_scope": len(rows),
            "reference_package_roots": sorted(reference_package_names),
            "candidate_excluded_support_packages": len(
                set(_package_roots(candidate_root)) - reference_package_names
            ),
            "dispositions": dict(sorted(disposition_counts.items())),
        },
        "packages": rows,
    }


def write_package_derived_metadata_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
