from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable, Mapping


class RuntimeContractAuditError(RuntimeError):
    """运行时二进制契约审计失败。"""


_SQL_START_RE = re.compile(
    r"^(?:select(?:\s|\*)|insert\s+into\b|update\s+\S|delete\s+from\b|"
    r"pragma\s+\S|create\s+(?:table|index)\b)",
    re.IGNORECASE,
)
_TABLE_RE = re.compile(r"\btbl_[a-z0-9_]+", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:[\\/][\w .-]+){1,}(?:\.s3db|\.db3|\.json|\.txt)|"
    r"(?:NavigationData|ProcedureLegs|Runways\.json|Navaids\.json|Airways\.json)",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize(line: str) -> str:
    return " ".join(line.replace("\x00", "").split())


def classify_runtime_strings(lines: Iterable[str]) -> dict[str, object]:
    """从 strings 输出中提取可审计的 SQL、表名和路径契约。"""

    sql: list[str] = []
    tables: set[str] = set()
    paths: list[str] = []
    for raw_line in lines:
        line = _normalize(raw_line)
        if not line:
            continue
        if _SQL_START_RE.match(line.lstrip(" ?<>")):
            sql.append(line)
        tables.update(match.group(0).lower() for match in _TABLE_RE.finditer(line))
        if _PATH_RE.search(line):
            paths.append(line)
    return {
        "sql_strings": sorted(set(sql)),
        "table_names": sorted(tables),
        "path_strings": sorted(set(paths)),
        "summary": {
            "sql_string_count": len(set(sql)),
            "table_name_count": len(tables),
            "path_string_count": len(set(paths)),
        },
    }


def _run_strings(
    binary: Path,
    strings_executable: Path,
    *,
    minimum_length: int,
) -> list[str]:
    try:
        completed = subprocess.run(
            [
                str(strings_executable),
                "-n",
                str(minimum_length),
                str(binary),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeContractAuditError(
            f"无法运行 strings.exe: {strings_executable}"
        ) from error
    return completed.stdout.splitlines()


def audit_runtime_contract_binaries(
    binaries: Mapping[str, Path],
    *,
    strings_executable: Path,
    minimum_length: int = 6,
) -> dict[str, object]:
    """审计目标运行时二进制中的可见加载契约字符串。"""

    if not binaries:
        raise RuntimeContractAuditError("至少需要一个运行时二进制")
    strings_executable = strings_executable.expanduser().resolve()
    if not strings_executable.is_file():
        raise RuntimeContractAuditError(
            f"strings 工具不存在: {strings_executable}"
        )

    reports: list[dict[str, object]] = []
    total_tables: set[str] = set()
    total_sql = 0
    total_paths = 0
    for name, raw_binary in binaries.items():
        binary = raw_binary.expanduser().resolve()
        if not binary.is_file():
            raise RuntimeContractAuditError(f"运行时二进制不存在: {binary}")
        extracted = classify_runtime_strings(
            _run_strings(
                binary,
                strings_executable,
                minimum_length=minimum_length,
            )
        )
        total_tables.update(extracted["table_names"])
        total_sql += int(extracted["summary"]["sql_string_count"])
        total_paths += int(extracted["summary"]["path_string_count"])
        reports.append({
            "name": str(name),
            "binary": str(binary),
            "size": binary.stat().st_size,
            "sha256": _sha256(binary),
            **extracted,
        })

    return {
        "diagnostic": "runtime-contract-string-audit-v1",
        "read_only": True,
        "navigation_records_read": False,
        "reference_payload_read": False,
        "strings_executable": str(strings_executable),
        "minimum_string_length": minimum_length,
        "summary": {
            "binary_count": len(reports),
            "total_sql_strings": total_sql,
            "total_path_strings": total_paths,
            "distinct_table_names": sorted(total_tables),
            "distinct_table_name_count": len(total_tables),
        },
        "decision": {
            "status": "runtime_contract_evidence_only",
            "default_bgl_projection_authorized": False,
            "reason": (
                "运行时字符串可记录目标格式的真实查询和文件契约，"
                "但不能把其他机模的 SQLite 查询反推为默认 BGL 内容规则。"
            ),
        },
        "binaries": reports,
    }


def write_runtime_contract_audit(
    path: Path,
    report: Mapping[str, object],
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
