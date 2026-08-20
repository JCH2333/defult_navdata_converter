from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Mapping, Sequence

from .package_reader import (
    DEFAULT_READER_TIMEOUT_SECONDS,
    PackageReaderResult,
    read_package,
)


class ReaderRepeatabilityAuditError(RuntimeError):
    pass


DEFAULT_TABLES = (
    "airport",
    "runway",
    "vor",
    "ndb",
    "waypoint",
    "airway",
    "approach",
    "approach_leg",
    "transition",
    "transition_leg",
    "ils",
    "holding",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    if not value or "\x00" in value:
        raise ReaderRepeatabilityAuditError(f"invalid SQLite identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def _table_snapshot(database: Path, table: str) -> dict[str, object]:
    try:
        connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if table not in tables:
            return {"present": False, "row_count": 0, "sha256": None}
        columns = [
            str(row[1])
            for row in connection.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            )
        ]
        rows = connection.execute(
            f"SELECT * FROM {_quote_identifier(table)} ORDER BY rowid"
        ).fetchall()
    except (OSError, sqlite3.DatabaseError) as error:
        raise ReaderRepeatabilityAuditError(
            f"cannot snapshot reader table {table}: {database}"
        ) from error
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass
    payload = json.dumps(
        {"columns": columns, "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        "present": True,
        "row_count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _run_report(
    result: PackageReaderResult,
    *,
    tables: Sequence[str],
) -> dict[str, object]:
    return {
        "database": str(result.database),
        "database_sha256": _sha256(result.database),
        "reader": result.reader,
        "scan": result.scan,
        "tables": {
            table: _table_snapshot(result.database, table)
            for table in tables
        },
    }


def audit_reader_repeatability(
    package: Path,
    *,
    reader: Path,
    output_directory: Path,
    repeats: int = 3,
    filename_patterns: Sequence[str] = ("*.bgl",),
    tables: Sequence[str] = DEFAULT_TABLES,
    cache_root: Path | None = None,
    timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    if repeats < 2:
        raise ValueError("reader repeatability audit requires at least two repeats")
    if not filename_patterns:
        raise ValueError("at least one BGL filename pattern is required")
    if not tables:
        raise ValueError("at least one SQLite table is required")

    package = package.expanduser().resolve()
    reader = reader.expanduser().resolve()
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, object]] = []
    for index in range(1, repeats + 1):
        database = output_directory / f"reader-{index}.sqlite"
        result = read_package(
            package,
            database,
            reader=reader,
            cache_root=(
                cache_root.expanduser().resolve() / f"run-{index}"
                if cache_root is not None
                else None
            ),
            filename_patterns=filename_patterns,
            timeout_seconds=timeout_seconds,
            failure_artifacts=output_directory / f"failure-{index}",
        )
        runs.append(_run_report(result, tables=tables))

    first = runs[0]
    scan_equal = all(run["scan"] == first["scan"] for run in runs[1:])
    table_equal = all(run["tables"] == first["tables"] for run in runs[1:])
    database_bytes_equal = all(
        run["database_sha256"] == first["database_sha256"] for run in runs[1:]
    )
    repeatable = scan_equal and table_equal
    return {
        "diagnostic": "reader-repeatability-audit-v1",
        "read_only": True,
        "package": str(package),
        "reader": str(reader),
        "repeats": repeats,
        "filename_patterns": list(filename_patterns),
        "tables": list(tables),
        "runs": runs,
        "comparison": {
            "scan_equal": scan_equal,
            "table_snapshots_equal": table_equal,
            "database_bytes_equal": database_bytes_equal,
            "repeatable": repeatable,
        },
        "decision": {
            "status": (
                "reader_repeatable"
                if repeatable
                else "reader_output_not_repeatable"
            ),
            "projection_evidence_allowed": repeatable,
            "reason": (
                "All selected reader scans and table snapshots are identical."
                if repeatable
                else "The same package produced different reader scan or table snapshots."
            ),
        },
    }


def write_reader_repeatability_audit(
    path: Path, report: Mapping[str, object]
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
