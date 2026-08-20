from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


class SdkToolchainAuditError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_version(root: Path) -> str | None:
    version_path = root / "version.txt"
    if not version_path.is_file():
        return None
    value = version_path.read_text(encoding="utf-8-sig").strip()
    return value or None


def _toolchain(root: Path) -> dict[str, object]:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise SdkToolchainAuditError(f"SDK root does not exist: {resolved}")
    tool = resolved / "Tools" / "bin" / "fspackagetool.exe"
    if not tool.is_file():
        raise SdkToolchainAuditError(f"Package Tool does not exist: {tool}")
    return {
        "sdk_root": str(resolved),
        "sdk_version": _read_version(resolved),
        "package_tool": {
            "path": str(tool),
            "size": tool.stat().st_size,
            "sha256": _sha256(tool),
        },
    }


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkToolchainAuditError(f"cannot read JSON report: {path}") from error
    if not isinstance(value, dict):
        raise SdkToolchainAuditError(f"JSON report is not an object: {path}")
    return value


def _historical_summary(path: Path) -> dict[str, object]:
    report = _load_json(path)
    if report.get("diagnostic") != "historical-sdk-probe-evidence-v1":
        raise SdkToolchainAuditError(f"unexpected historical evidence report: {path}")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise SdkToolchainAuditError("historical evidence report lacks cases")
    rows: list[dict[str, object]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise SdkToolchainAuditError("historical evidence case is not an object")
        files = case.get("bgl_files")
        if not isinstance(files, list):
            raise SdkToolchainAuditError("historical evidence case lacks bgl_files")
        rows.append({
            "identifier": case.get("identifier"),
            "disposition": case.get("disposition"),
            "reader_complete": case.get("reader_complete") is True,
            "layout_changed": any(
                isinstance(item, Mapping)
                and any(
                    item.get(key) is True
                    for key in (
                        "size_changed",
                        "section_types_changed",
                        "section_counts_changed",
                        "section_sizes_changed",
                    )
                )
                for item in files
            ),
        })
    return {
        "path": str(path.expanduser().resolve()),
        "all_reader_complete": report.get("all_reader_complete") is True,
        "cases": rows,
    }


def audit_sdk_toolchains(
    sdk_roots: list[Path],
    *,
    historical_evidence: Path | None = None,
) -> dict[str, object]:
    if not sdk_roots:
        raise SdkToolchainAuditError("at least one SDK root is required")
    toolchains = [_toolchain(root) for root in sdk_roots]
    hashes = {
        item["package_tool"]["sha256"]
        for item in toolchains
        if isinstance(item.get("package_tool"), Mapping)
    }
    evidence = (
        _historical_summary(historical_evidence)
        if historical_evidence is not None
        else None
    )
    return {
        "diagnostic": "sdk-toolchain-audit-v1",
        "read_only": True,
        "reference_payload_read": False,
        "navigation_records_read": False,
        "toolchains": toolchains,
        "package_tool_hashes_distinct": len(hashes) > 1,
        "historical_probe_evidence": evidence,
        "decision": {
            "status": "toolchain_difference_without_target_expression_evidence",
            "adapter_change_authorized": False,
            "reason": (
                "Package Tool binaries may differ, but a toolchain change is not "
                "a target-expression contract. Historical probes must demonstrate "
                "a stable, source-backed output change before selecting an adapter variable."
            ),
        },
    }


def write_sdk_toolchain_audit(path: Path, report: Mapping[str, object]) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
