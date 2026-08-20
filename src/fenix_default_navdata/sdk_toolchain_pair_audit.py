from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


class SdkToolchainPairAuditError(RuntimeError):
    pass


def _load_report(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkToolchainPairAuditError(f"cannot read probe report: {path}") from error
    if not isinstance(value, dict):
        raise SdkToolchainPairAuditError(f"probe report is not an object: {path}")
    if value.get("probe") != "sdk_airway_route_child_order":
        raise SdkToolchainPairAuditError(f"unexpected probe type: {path}")
    if value.get("status") != "passed":
        raise SdkToolchainPairAuditError(f"probe did not pass: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_from_report(report: Mapping[str, object], key: str) -> Path:
    value = report.get(key)
    if not isinstance(value, str) or not value:
        raise SdkToolchainPairAuditError(f"probe report lacks {key}")
    path = Path(value)
    if not path.is_file():
        raise SdkToolchainPairAuditError(f"probe report path does not exist: {path}")
    return path


def _compiler_identity(report: Mapping[str, object]) -> dict[str, object]:
    compilation = report.get("compilation")
    if not isinstance(compilation, Mapping):
        raise SdkToolchainPairAuditError("probe report lacks compilation")
    value = compilation.get("compiler")
    if not isinstance(value, str) or not value:
        raise SdkToolchainPairAuditError("probe report lacks compiler path")
    path = Path(value)
    result: dict[str, object] = {"path": str(path)}
    if path.is_file():
        result["size"] = path.stat().st_size
        result["sha256"] = _sha256(path)
    else:
        result["available"] = False
    return result


def _bgl_summaries(report: Mapping[str, object]) -> list[dict[str, object]]:
    compilation = report.get("compilation")
    if not isinstance(compilation, Mapping):
        raise SdkToolchainPairAuditError("probe report lacks compilation")
    values = compilation.get("bgls")
    if not isinstance(values, list):
        raise SdkToolchainPairAuditError("probe report lacks compiled BGL list")
    summaries: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, str):
            raise SdkToolchainPairAuditError("compiled BGL path is not a string")
        path = Path(value)
        if not path.is_file():
            raise SdkToolchainPairAuditError(f"compiled BGL does not exist: {path}")
        summaries.append({
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return summaries


def audit_sdk_toolchain_pair(first_report: Path, second_report: Path) -> dict[str, object]:
    first = _load_report(first_report)
    second = _load_report(second_report)
    first_xml = _path_from_report(first, "xml")
    second_xml = _path_from_report(second, "xml")
    first_xml_hash = _sha256(first_xml)
    second_xml_hash = _sha256(second_xml)
    same_contract = first.get("contract") == second.get("contract")
    same_scenarios = first.get("scenarios") == second.get("scenarios")
    same_input = same_contract and same_scenarios and first_xml_hash == second_xml_hash

    first_rows = first.get("airway_rows")
    second_rows = second.get("airway_rows")
    if not isinstance(first_rows, list) or not isinstance(second_rows, list):
        raise SdkToolchainPairAuditError("probe reports lack airway_rows")
    first_bgls = _bgl_summaries(first)
    second_bgls = _bgl_summaries(second)
    bgl_equal = [
        left["sha256"] == right["sha256"]
        for left, right in zip(first_bgls, second_bgls, strict=False)
    ]
    bgl_bytes_equal = len(first_bgls) == len(second_bgls) and all(bgl_equal)
    rows_equal = first_rows == second_rows
    compiled_output_difference = same_input and not bgl_bytes_equal
    reader_only_difference = same_input and bgl_bytes_equal and not rows_equal

    if compiled_output_difference:
        status = "toolchain_difference_changes_observed_output"
        reason = (
            "The same probe XML and source scenarios produced different compiled "
            "BGL bytes. A targeted toolchain selection experiment "
            "is allowed, but this does not select the reference-matching SDK."
        )
    elif reader_only_difference:
        status = "compiled_output_equal_reader_rows_differ"
        reason = (
            "The compiled BGL bytes are identical, but the reader rows differ. "
            "This is reader or environment instability, not target-expression "
            "evidence, so no toolchain selection is authorized."
        )
    elif same_input:
        status = "toolchain_difference_not_observable_in_probe"
        reason = "The same probe input produced equal reader rows and BGL bytes."
    else:
        status = "pair_not_comparable"
        reason = "The reports do not prove identical XML, contract, and scenarios."

    first_tool = _compiler_identity(first)
    second_tool = _compiler_identity(second)
    return {
        "diagnostic": "sdk-toolchain-pair-audit-v1",
        "read_only": True,
        "reference_payload_read": False,
        "navigation_records_read": False,
        "reports": {
            "first": str(first_report.expanduser().resolve()),
            "second": str(second_report.expanduser().resolve()),
        },
        "inputs": {
            "same_contract": same_contract,
            "same_scenarios": same_scenarios,
            "first_xml_sha256": first_xml_hash,
            "second_xml_sha256": second_xml_hash,
            "same_xml": first_xml_hash == second_xml_hash,
            "same_probe_input": same_input,
        },
        "toolchains": {
            "first": first_tool,
            "second": second_tool,
            "package_tool_sha256_distinct": (
                first_tool.get("sha256") != second_tool.get("sha256")
            ),
        },
        "outputs": {
            "reader_rows_equal": rows_equal,
            "reader_only_difference": reader_only_difference,
            "first_airway_row_count": len(first_rows),
            "second_airway_row_count": len(second_rows),
            "first_bgls": first_bgls,
            "second_bgls": second_bgls,
            "compiled_bgl_bytes_equal": bgl_bytes_equal,
            "compiled_bgl_pairwise_equal": bgl_equal,
        },
        "decision": {
            "status": status,
            "targeted_toolchain_selection_experiment_authorized": (
                compiled_output_difference
            ),
            "adapter_change_authorized": False,
            "reason": reason,
        },
    }


def write_sdk_toolchain_pair_audit(
    path: Path, report: Mapping[str, object]
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
