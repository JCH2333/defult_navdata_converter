from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


class SemanticDiffError(RuntimeError):
    """读取器 SQLite 无法安全用于只读语义差分时抛出的错误。"""


@dataclass(frozen=True)
class TableSpec:
    """一个 Navdatareader 表的稳定逻辑身份与可比语义字段。"""

    table: str
    logical_fields: tuple[str, ...]
    semantic_fields: tuple[str, ...]


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        table="vor",
        logical_fields=("ident", "region", "airport_ident"),
        semantic_fields=(
            "ident",
            "name",
            "region",
            "airport_ident",
            "type",
            "frequency",
            "channel",
            "range",
            "mag_var",
            "dme_only",
            "dme_altitude",
            "dme_lonx",
            "dme_laty",
            "altitude",
            "lonx",
            "laty",
        ),
    ),
    TableSpec(
        table="ndb",
        logical_fields=("ident", "region", "airport_ident"),
        semantic_fields=(
            "ident",
            "name",
            "region",
            "airport_ident",
            "type",
            "frequency",
            "range",
            "mag_var",
            "altitude",
            "lonx",
            "laty",
        ),
    ),
    TableSpec(
        table="waypoint",
        logical_fields=("ident", "region", "airport_ident"),
        semantic_fields=(
            "ident",
            "name",
            "region",
            "airport_ident",
            "artificial",
            "type",
            "arinc_type",
            "num_victor_airway",
            "num_jet_airway",
            "mag_var",
            "lonx",
            "laty",
        ),
    ),
    TableSpec(
        table="airway",
        logical_fields=(
            "airway_name",
            "airway_type",
            "route_type",
            "airway_fragment_no",
            "sequence_no",
        ),
        semantic_fields=(
            "airway_name",
            "airway_type",
            "route_type",
            "airway_fragment_no",
            "sequence_no",
            "direction",
            "minimum_altitude",
            "maximum_altitude",
            "left_lonx",
            "top_laty",
            "right_lonx",
            "bottom_laty",
            "from_lonx",
            "from_laty",
            "to_lonx",
            "to_laty",
        ),
    ),
)
SUPPORTED_TABLES = tuple(spec.table for spec in TABLE_SPECS)

_IDENTIFIER_FIELDS = {
    "ident",
    "region",
    "airport_ident",
    "type",
    "arinc_type",
    "airway_name",
    "airway_type",
    "route_type",
    "direction",
    "channel",
}
_FLOAT_PRECISION = 6


@dataclass(frozen=True)
class _SemanticRow:
    logical_key: tuple[object, ...]
    values: tuple[object, ...]
    digest: str


def _open_readonly(path: Path, label: str) -> sqlite3.Connection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise SemanticDiffError(f"{label} SQLite 不存在: {path}")
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        checks = [str(row[0]).lower() for row in connection.execute("PRAGMA integrity_check")]
    except (OSError, sqlite3.DatabaseError) as error:
        raise SemanticDiffError(f"无法以只读方式打开{label} SQLite: {path}: {error}") from error
    if checks != ["ok"]:
        connection.close()
        detail = "; ".join(checks[:5]) or "unknown error"
        raise SemanticDiffError(f"{label} SQLite 完整性检查失败: {path}: {detail}")
    return connection


def _resolve_specs(tables: Sequence[str] | None) -> tuple[TableSpec, ...]:
    by_name = {spec.table: spec for spec in TABLE_SPECS}
    if tables is None:
        return TABLE_SPECS
    requested = tuple(str(item).strip().lower() for item in tables)
    if not requested:
        raise ValueError("至少需要选择一张 Navdatareader 表")
    unknown = sorted(set(requested) - set(by_name))
    if unknown:
        raise ValueError(f"不支持的 Navdatareader 表: {', '.join(unknown)}")
    return tuple(by_name[name] for name in SUPPORTED_TABLES if name in requested)


def _table_columns(
    connection: sqlite3.Connection,
    table: str,
    *,
    label: str,
    path: Path,
) -> set[str]:
    try:
        return {
            str(row[1]).lower()
            for row in connection.execute(f'PRAGMA table_info("{table}")')
        }
    except sqlite3.DatabaseError as error:
        raise SemanticDiffError(
            f"无法读取{label} SQLite 表结构 {table}: {path}: {error}"
        ) from error


def _reader_output_summary(
    connection: sqlite3.Connection,
    path: Path,
    label: str,
    *,
    expected_bgl_count: int,
) -> dict[str, object]:
    """确认 SQLite 确实是有读取结果的 Navdatareader 输出。

    Navdatareader 在扫描失败时可能仍会留下完整、可查询的 SQLite。仅依赖
    ``integrity_check`` 会把这种空结果误当成有效语义差分输入，因此这里额外
    要求存在非空的 BGL 来源表，并至少有一类目标设施记录。
    """
    try:
        tables = {
            str(row[0]).lower()
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    except sqlite3.DatabaseError as error:
        raise SemanticDiffError(
            f"无法读取{label} SQLite 的表目录: {path}: {error}"
        ) from error

    if "bgl_file" not in tables:
        raise SemanticDiffError(f"{label} SQLite 缺少 Navdatareader bgl_file 表: {path}")

    try:
        bgl_file_rows = int(
            connection.execute('SELECT COUNT(*) FROM "bgl_file"').fetchone()[0]
        )
        target_rows = {
            spec.table: (
                int(connection.execute(f'SELECT COUNT(*) FROM "{spec.table}"').fetchone()[0])
                if spec.table in tables
                else 0
            )
            for spec in TABLE_SPECS
        }
    except sqlite3.DatabaseError as error:
        raise SemanticDiffError(
            f"无法读取{label} SQLite 的 Navdatareader 输出统计: {path}: {error}"
        ) from error

    if bgl_file_rows == 0:
        raise SemanticDiffError(f"{label} SQLite 的 bgl_file 表为空，读取器没有输出 BGL 来源: {path}")
    if bgl_file_rows != expected_bgl_count:
        raise SemanticDiffError(
            f"{label} SQLite 仅登记了 {bgl_file_rows}/{expected_bgl_count} 个请求的 BGL，"
            f"拒绝不完整扫描: {path}"
        )
    if not any(target_rows.values()):
        raise SemanticDiffError(
            f"{label} SQLite 的目标设施表均为空，读取器没有输出有效设施: {path}"
        )
    return {
        "expected_bgl_count": expected_bgl_count,
        "bgl_file_rows": bgl_file_rows,
        "target_rows": target_rows,
    }


def _normalize(
    value: object,
    field: str,
    *,
    table: str,
    row_id: int,
    path: Path,
) -> object:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.hex()
    if isinstance(value, str):
        result = value.strip()
        return result.upper() if field in _IDENTIFIER_FIELDS else result
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SemanticDiffError(
                f"SQLite 数值不是有限数: {path} 的 {table} 行 {row_id} 字段 {field}"
            )
        return round(value, _FLOAT_PRECISION)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if not math.isfinite(numeric):
        raise SemanticDiffError(
            f"SQLite 数值不是有限数: {path} 的 {table} 行 {row_id} 字段 {field}"
        )
    if numeric.is_integer():
        return int(numeric)
    return round(numeric, _FLOAT_PRECISION)


def _digest(values: tuple[object, ...]) -> str:
    encoded = json.dumps(
        values,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _logical_sort_key(key: tuple[object, ...]) -> tuple[tuple[int, str], ...]:
    """允许空值和文本并存的逻辑身份按可重复文本顺序排序。"""
    return tuple(
        (0, "") if value is None else (
            1,
            json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
        )
        for value in key
    )


def _load_rows(
    connection: sqlite3.Connection,
    path: Path,
    label: str,
    spec: TableSpec,
) -> tuple[_SemanticRow, ...]:
    columns = _table_columns(connection, spec.table, label=label, path=path)
    missing = sorted(set(spec.semantic_fields) - columns)
    if missing:
        raise SemanticDiffError(
            f"{label} SQLite 的 {spec.table} 表缺少列: {', '.join(missing)}"
        )
    names = ", ".join(f'"{field}"' for field in spec.semantic_fields)
    try:
        rows = connection.execute(
            f'SELECT rowid AS "_semantic_rowid", {names} FROM "{spec.table}"'
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise SemanticDiffError(f"无法读取{label} SQLite 的 {spec.table} 表: {error}") from error
    logical_positions = tuple(spec.semantic_fields.index(field) for field in spec.logical_fields)
    result: list[_SemanticRow] = []
    for row in rows:
        row_id = int(row["_semantic_rowid"])
        values = tuple(
            _normalize(row[field], field, table=spec.table, row_id=row_id, path=path)
            for field in spec.semantic_fields
        )
        logical_key = tuple(values[position] for position in logical_positions)
        result.append(_SemanticRow(
            logical_key=logical_key,
            values=values,
            digest=_digest(values),
        ))
    return tuple(sorted(result, key=lambda item: (_logical_sort_key(item.logical_key), item.digest)))


def _logical_key_payload(spec: TableSpec, key: tuple[object, ...]) -> dict[str, object]:
    return {field: value for field, value in zip(spec.logical_fields, key, strict=True)}


def _sample(
    items: list[dict[str, object]],
    sample_limit: int,
) -> tuple[list[dict[str, object]], int]:
    return items[:sample_limit], max(0, len(items) - sample_limit)


def _table_report(
    spec: TableSpec,
    candidate_rows: Iterable[_SemanticRow],
    reference_rows: Iterable[_SemanticRow],
    *,
    sample_limit: int,
) -> dict[str, object]:
    candidate = tuple(candidate_rows)
    reference = tuple(reference_rows)
    candidate_by_key: dict[tuple[object, ...], list[_SemanticRow]] = defaultdict(list)
    reference_by_key: dict[tuple[object, ...], list[_SemanticRow]] = defaultdict(list)
    for row in candidate:
        candidate_by_key[row.logical_key].append(row)
    for row in reference:
        reference_by_key[row.logical_key].append(row)

    candidate_only_keys = sorted(
        set(candidate_by_key) - set(reference_by_key),
        key=_logical_sort_key,
    )
    reference_only_keys = sorted(
        set(reference_by_key) - set(candidate_by_key),
        key=_logical_sort_key,
    )
    candidate_only_samples = [
        {
            "logical_key": _logical_key_payload(spec, key),
            "candidate_rows": len(candidate_by_key[key]),
        }
        for key in candidate_only_keys
    ]
    reference_only_samples = [
        {
            "logical_key": _logical_key_payload(spec, key),
            "reference_rows": len(reference_by_key[key]),
        }
        for key in reference_only_keys
    ]

    field_deltas: list[dict[str, object]] = []
    ambiguous_keys: list[dict[str, object]] = []
    for key in sorted(set(candidate_by_key) & set(reference_by_key), key=_logical_sort_key):
        candidate_group = candidate_by_key[key]
        reference_group = reference_by_key[key]
        if len(candidate_group) != 1 or len(reference_group) != 1:
            ambiguous_keys.append({
                "logical_key": _logical_key_payload(spec, key),
                "candidate_rows": len(candidate_group),
                "reference_rows": len(reference_group),
            })
            continue
        candidate_row, reference_row = candidate_group[0], reference_group[0]
        changed_fields = [
            field
            for field, candidate_value, reference_value in zip(
                spec.semantic_fields,
                candidate_row.values,
                reference_row.values,
                strict=True,
            )
            if candidate_value != reference_value
        ]
        if changed_fields:
            field_deltas.append({
                "logical_key": _logical_key_payload(spec, key),
                "fields": changed_fields,
            })

    candidate_counts = Counter(row.digest for row in candidate)
    reference_counts = Counter(row.digest for row in reference)
    candidate_samples, candidate_omitted = _sample(candidate_only_samples, sample_limit)
    reference_samples, reference_omitted = _sample(reference_only_samples, sample_limit)
    field_samples, field_omitted = _sample(field_deltas, sample_limit)
    ambiguity_samples, ambiguity_omitted = _sample(ambiguous_keys, sample_limit)
    return {
        "candidate_rows": len(candidate),
        "reference_rows": len(reference),
        "strict_equal_rows": sum((candidate_counts & reference_counts).values()),
        "candidate_only_strict_rows": sum((candidate_counts - reference_counts).values()),
        "reference_only_strict_rows": sum((reference_counts - candidate_counts).values()),
        "candidate_only_logical_keys": len(candidate_only_keys),
        "reference_only_logical_keys": len(reference_only_keys),
        "field_delta_rows": len(field_deltas),
        "ambiguous_logical_keys": len(ambiguous_keys),
        "candidate_only_samples": candidate_samples,
        "candidate_only_samples_omitted": candidate_omitted,
        "reference_only_samples": reference_samples,
        "reference_only_samples_omitted": reference_omitted,
        "field_delta_samples": field_samples,
        "field_delta_samples_omitted": field_omitted,
        "ambiguous_logical_key_samples": ambiguity_samples,
        "ambiguous_logical_key_samples_omitted": ambiguity_omitted,
    }


def _row_multiset_fingerprint(rows: Iterable[_SemanticRow]) -> str:
    """Return a deterministic fingerprint without exposing semantic values."""

    counts = Counter(row.digest for row in rows)
    payload = [
        [digest, counts[digest]]
        for digest in sorted(counts)
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def semantic_reproducibility_audit(
    databases: Sequence[Path],
    *,
    expected_bgl_count: int,
    tables: Sequence[str] | None = None,
) -> dict[str, object]:
    """Compare repeated reader outputs without exposing facility values."""

    if len(databases) < 2:
        raise ValueError("至少需要两个重复读取 SQLite 才能审计可重复性")
    if expected_bgl_count <= 0:
        raise ValueError("预期 BGL 数必须为正整数")
    specs = _resolve_specs(tables)
    inputs: list[dict[str, object]] = []
    fingerprints_by_table: dict[str, list[str]] = {
        spec.table: []
        for spec in specs
    }
    rows_by_table: dict[str, list[int]] = {
        spec.table: []
        for spec in specs
    }
    for index, value in enumerate(databases, start=1):
        path = value.expanduser().resolve()
        label = f"重复读取 {index}"
        connection = _open_readonly(path, label)
        try:
            reader_output = _reader_output_summary(
                connection,
                path,
                label,
                expected_bgl_count=expected_bgl_count,
            )
            table_report: dict[str, object] = {}
            for spec in specs:
                rows = _load_rows(connection, path, label, spec)
                fingerprint = _row_multiset_fingerprint(rows)
                table_report[spec.table] = {
                    "rows": len(rows),
                    "semantic_fingerprint": fingerprint,
                }
                fingerprints_by_table[spec.table].append(fingerprint)
                rows_by_table[spec.table].append(len(rows))
        finally:
            connection.close()
        inputs.append({
            "database": str(path),
            "reader_output": reader_output,
            "tables": table_report,
        })
    table_summary = {
        spec.table: {
            "input_rows": rows_by_table[spec.table],
            "distinct_semantic_fingerprints": len(
                set(fingerprints_by_table[spec.table])
            ),
            "reproducible": len(set(fingerprints_by_table[spec.table])) == 1,
        }
        for spec in specs
    }
    return {
        "diagnostic": "navdatareader-semantic-reproducibility-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "expected_bgl_count": expected_bgl_count,
        "input_count": len(inputs),
        "tables": table_summary,
        "reproducible": all(
            bool(table_summary[spec.table]["reproducible"])
            for spec in specs
        ),
        "inputs": inputs,
    }


def write_semantic_reproducibility_audit(
    path: Path,
    report: dict[str, object],
) -> Path:
    """Persist a reproducibility audit using the standard atomic JSON writer."""

    return write_semantic_diff(path, report)


def semantic_diff(
    candidate_db: Path,
    reference_db: Path,
    *,
    expected_candidate_bgl_count: int,
    expected_reference_bgl_count: int,
    tables: Sequence[str] | None = None,
    sample_limit: int = 50,
) -> dict[str, object]:
    """只读比较两个 Navdatareader SQLite 的导航语义，不回传参考字段值。

    差分报告仅暴露逻辑身份、字段名与行数。参考 SQLite 的坐标、频率、名称等值
    仅在进程内用于比较，不会进入输出，因此诊断不能作为候选内容的反向输入。
    """
    if sample_limit <= 0:
        raise ValueError("样本上限必须为正整数")
    if expected_candidate_bgl_count <= 0 or expected_reference_bgl_count <= 0:
        raise ValueError("预期 BGL 数必须为正整数")
    specs = _resolve_specs(tables)
    candidate_path = candidate_db.expanduser().resolve()
    reference_path = reference_db.expanduser().resolve()
    candidate_connection = _open_readonly(candidate_path, "候选")
    try:
        candidate_reader_output = _reader_output_summary(
            candidate_connection,
            candidate_path,
            "候选",
            expected_bgl_count=expected_candidate_bgl_count,
        )
        reference_connection = _open_readonly(reference_path, "参考")
        try:
            reference_reader_output = _reader_output_summary(
                reference_connection,
                reference_path,
                "参考",
                expected_bgl_count=expected_reference_bgl_count,
            )
            reports = {
                spec.table: _table_report(
                    spec,
                    _load_rows(candidate_connection, candidate_path, "候选", spec),
                    _load_rows(reference_connection, reference_path, "参考", spec),
                    sample_limit=sample_limit,
                )
                for spec in specs
            }
        finally:
            reference_connection.close()
    finally:
        candidate_connection.close()
    summary_fields = (
        "candidate_rows",
        "reference_rows",
        "strict_equal_rows",
        "candidate_only_strict_rows",
        "reference_only_strict_rows",
        "candidate_only_logical_keys",
        "reference_only_logical_keys",
        "field_delta_rows",
        "ambiguous_logical_keys",
    )
    summary = {
        field: sum(int(table[field]) for table in reports.values())
        for field in summary_fields
    }
    has_differences = any(
        summary[field]
        for field in (
            "candidate_only_strict_rows",
            "reference_only_strict_rows",
            "field_delta_rows",
            "ambiguous_logical_keys",
        )
    )
    return {
        "diagnostic": "navdatareader-semantic-diff-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "sample_limit": sample_limit,
        "reader_output": {
            "candidate": candidate_reader_output,
            "reference": reference_reader_output,
        },
        "tables": reports,
        "summary": summary,
        "has_differences": has_differences,
    }


def write_semantic_diff(path: Path, report: dict[str, object]) -> Path:
    """原子写入本地诊断 JSON；调用者负责把它放到忽略目录。"""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path
