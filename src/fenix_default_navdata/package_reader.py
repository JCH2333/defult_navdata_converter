from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .official_index import find_navdatareader


_READER_TARGET_TABLES = (
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
DEFAULT_READER_TIMEOUT_SECONDS = 120
DEFAULT_READER_LOG_LIMIT_BYTES = 16 * 1024 * 1024
_READER_POLL_SECONDS = 0.05


class PackageReaderError(RuntimeError):
    """完整包读取诊断无法安全完成时抛出的错误。"""


@dataclass(frozen=True)
class PackageReaderResult:
    """一份经过完整包镜像校验的 Navdatareader 输出。"""

    database: Path
    package: dict[str, object]
    reader: dict[str, object]
    scan: dict[str, object]

    def to_report(self) -> dict[str, object]:
        return {
            "database": str(self.database),
            "package": self.package,
            "reader": self.reader,
            "scan": self.scan,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_fingerprint(package: Path) -> dict[str, object]:
    package = package.expanduser().resolve()
    if not package.is_dir():
        raise PackageReaderError(f"读取器包目录不存在: {package}")
    for filename in ("manifest.json", "layout.json", "bglIndex.bout"):
        if not (package / filename).is_file():
            raise PackageReaderError(f"读取器包缺少 {filename}: {package}")
    files = sorted(
        (path for path in package.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(package).as_posix().casefold(),
    )
    if not files:
        raise PackageReaderError(f"读取器包为空: {package}")
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        before = path.stat()
        checksum = _sha256(path)
        after = path.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise PackageReaderError(f"生成读取器镜像时包文件发生变化: {path}")
        relative = path.relative_to(package).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(before.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
        total_bytes += before.st_size
    return {
        "source": str(package),
        "tree_sha256": digest.hexdigest(),
        "file_count": len(files),
        "total_bytes": total_bytes,
    }


def _normalize_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(
        pattern.strip()
        for pattern in patterns
        if pattern and pattern.strip()
    ))
    if not normalized:
        raise ValueError("至少需要一个 BGL 文件名匹配模式")
    return normalized


def _matching_bgls(package: Path, patterns: tuple[str, ...]) -> tuple[Path, ...]:
    normalized_patterns = tuple(pattern.casefold() for pattern in patterns)
    files = tuple(sorted(
        (
            path
            for path in package.rglob("*.bgl")
            if any(
                fnmatch.fnmatchcase(path.name.casefold(), pattern)
                for pattern in normalized_patterns
            )
        ),
        key=lambda path: path.relative_to(package).as_posix().casefold(),
    ))
    if not files:
        raise PackageReaderError(
            f"读取器包内没有匹配的 BGL: {package}; 模式={', '.join(patterns)}"
        )
    return files


def _cache_root(cache_root: Path | None) -> Path:
    root = cache_root or (
        Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
        / "default_navdata_converter"
        / "package-reader"
    )
    root = root.expanduser().resolve()
    if not str(root).isascii():
        raise PackageReaderError(f"读取器暂存目录必须为纯 ASCII 路径: {root}")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reader_config(
    filename_patterns: tuple[str, ...],
    object_filter: tuple[str, ...],
) -> str:
    return "\n".join((
        "[Database]",
        "Type=QSQLITE",
        "",
        "[Options]",
        "DatabaseReport=false",
        "BasicValidation=false",
        "AirportValidation=false",
        "ProcessDelete=true",
        "FilterRunways=false",
        "SaveIncomplete=true",
        "ResolveRoutes=true",
        "Verbose=false",
        "Autocommit=false",
        "Deduplicate=false",
        "DropAllIndexes=false",
        "DropTempTables=true",
        "VacuumDatabase=false",
        "AnalyzeDatabase=false",
        "SimConnectLoadDisconnected=false",
        "SimConnectLoadDisconnectedFile=false",
        "",
        "[Filter]",
        "IncludeHighPriorityFilter=",
        f"IncludeFilenames={','.join(filename_patterns)}",
        "ExcludeFilenames=",
        "IncludePathFilter=",
        "ExcludePathFilter=",
        "IncludeAirportIcaoFilter=",
        "ExcludeAirportIcaoFilter=",
        f"IncludeBglObjectFilter={','.join(object_filter)}",
        "ExcludeBglObjectFilter=APRON2,BOUNDARY",
        "IncludeAddonPathFilter=",
        "ExcludeAddonPathFilter=",
        "",
    ))


def _run_reader(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    max_log_bytes: int = DEFAULT_READER_LOG_LIMIT_BYTES,
) -> subprocess.CompletedProcess[str]:
    """运行外部读取器，并在其异常刷日志时主动收敛诊断。"""

    stdout_path = cwd / "reader.stdout.log"
    stderr_path = cwd / "reader.stderr.log"
    reader_logs = (
        cwd / "abarthel-navdatareader.log",
        cwd / "abarthel-navdatareader-err.log",
        stdout_path,
        stderr_path,
    )
    started_at = time.monotonic()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            while process.poll() is None:
                log_bytes = sum(
                    path.stat().st_size
                    for path in reader_logs
                    if path.is_file()
                )
                if log_bytes > max_log_bytes:
                    process.kill()
                    process.wait()
                    raise PackageReaderError(
                        "Navdatareader 日志超过 "
                        f"{max_log_bytes // (1024 * 1024)} MiB，已停止本次诊断"
                    )
                if time.monotonic() - started_at >= timeout_seconds:
                    process.kill()
                    process.wait()
                    raise subprocess.TimeoutExpired(command, timeout_seconds)
                time.sleep(_READER_POLL_SECONDS)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout_path.read_text(encoding="utf-8", errors="replace"),
        stderr_path.read_text(encoding="utf-8", errors="replace"),
    )


def _produced_database(requested: Path) -> Path | None:
    candidates = (
        requested,
        requested.with_stem(f"{requested.stem}_BROKEN"),
    )
    return next((path for path in candidates if path.is_file()), None)


def _scan_database(
    path: Path,
    *,
    expected_bgl_count: int | None = None,
) -> dict[str, object]:
    path = path.expanduser().resolve()
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        checks = [str(row[0]).lower() for row in connection.execute("PRAGMA integrity_check")]
    except (OSError, sqlite3.DatabaseError) as error:
        raise PackageReaderError(f"无法打开读取器 SQLite: {path}: {error}") from error
    try:
        if checks != ["ok"]:
            raise PackageReaderError(
                f"读取器 SQLite 完整性检查失败: {path}: {'; '.join(checks[:5])}"
            )
        tables = {
            str(row[0]).casefold()
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "bgl_file" not in tables:
            raise PackageReaderError(f"读取器 SQLite 缺少 bgl_file 表: {path}")
        bgl_file_rows = int(
            connection.execute('SELECT COUNT(*) FROM "bgl_file"').fetchone()[0]
        )
        if bgl_file_rows == 0:
            raise PackageReaderError(
                f"读取器没有登记任何 BGL 来源，拒绝空扫描: {path}"
            )
        if (
            expected_bgl_count is not None
            and bgl_file_rows != expected_bgl_count
        ):
            raise PackageReaderError(
                "读取器仅登记了 "
                f"{bgl_file_rows}/{expected_bgl_count} 个请求的 BGL，"
                f"拒绝不完整扫描: {path}"
            )
        table_rows = {
            table: (
                int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                if table in tables
                else 0
            )
            for table in _READER_TARGET_TABLES
        }
        if not any(table_rows.values()):
            raise PackageReaderError(
                f"读取器没有输出任何目标设施，拒绝空扫描: {path}"
            )
        return {
            "bgl_file_rows": bgl_file_rows,
            "target_rows": table_rows,
        }
    except sqlite3.DatabaseError as error:
        raise PackageReaderError(f"无法统计读取器 SQLite: {path}: {error}") from error
    finally:
        connection.close()


def read_package(
    package: Path,
    output: Path,
    *,
    reader: Path | None = None,
    cache_root: Path | None = None,
    filename_patterns: Iterable[str] = ("*.bgl",),
    object_filter: Iterable[str] = (),
    timeout_seconds: int = DEFAULT_READER_TIMEOUT_SECONDS,
    failure_artifacts: Path | None = None,
) -> PackageReaderResult:
    """镜像完整 Community 包并生成可用于只读差分的 Navdatareader SQLite。

    ``failure_artifacts`` 仅在读取失败时保存 ASCII 暂存区的运行目录，便于保留
    读取器配置、日志和可能生成的 ``_BROKEN.sqlite``，不会复制原始 Community 包。
    """

    if timeout_seconds <= 0:
        raise ValueError("读取器超时必须为正数")
    source = package.expanduser().resolve()
    target = output.expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"读取器输出已存在: {target}")
    failure_destination = (
        failure_artifacts.expanduser().resolve()
        if failure_artifacts is not None
        else None
    )
    if failure_destination is not None and failure_destination.exists():
        raise FileExistsError(f"读取器失败诊断目录已存在: {failure_destination}")
    patterns = _normalize_patterns(filename_patterns)
    objects = tuple(dict.fromkeys(
        item.strip().upper() for item in object_filter if item and item.strip()
    ))
    source_fingerprint = _package_fingerprint(source)
    selected_bgls = _matching_bgls(source, patterns)
    reader_path = find_navdatareader(reader)
    if reader_path is None:
        raise PackageReaderError(
            "未找到 Navdatareader；请通过 --reader 或 NAVDATAREADER 指定读取器"
        )
    stage_parent = _cache_root(cache_root)
    stage = Path(tempfile.mkdtemp(prefix="package-reader-stage-", dir=stage_parent))
    run: Path | None = None
    try:
        stage_root = stage / "root"
        community = stage_root / "Community"
        if not str(stage_root).isascii():
            raise PackageReaderError(f"读取器暂存目录必须为纯 ASCII 路径: {stage_root}")
        community.mkdir(parents=True)
        staged_package = community / source.name
        shutil.copytree(source, staged_package)
        staged_fingerprint = _package_fingerprint(staged_package)
        current_fingerprint = _package_fingerprint(source)
        if current_fingerprint != source_fingerprint:
            raise PackageReaderError("读取器镜像期间源包文件树发生变化，已拒绝输出")
        if staged_fingerprint["tree_sha256"] != source_fingerprint["tree_sha256"]:
            raise PackageReaderError("读取器暂存包 SHA-256 树校验失败")

        run = stage / "run"
        run.mkdir()
        config = run / "package-reader.cfg"
        config.write_text(_reader_config(patterns, objects), encoding="utf-8")
        requested_database = run / "package-reader.sqlite"
        command = [
            str(reader_path),
            "-f",
            # Navdatareader's MSFS24 mode requires a running simulator and
            # SimConnect. This diagnostic reads offline BGL packages instead.
            "MSFS",
            "-b",
            str(stage_root),
            "-o",
            str(requested_database),
            "-c",
            str(config),
        ]
        result = _run_reader(command, cwd=run, timeout_seconds=timeout_seconds)
        produced_database = _produced_database(requested_database)
        if produced_database is None:
            details = (result.stderr or result.stdout or "读取器未生成 SQLite")[-4000:]
            raise PackageReaderError(
                f"Navdatareader 未生成 SQLite，退出代码={result.returncode}: {details}"
            )
        scan = _scan_database(
            produced_database,
            expected_bgl_count=len(selected_bgls),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced_database, target)
    except subprocess.TimeoutExpired as error:
        if failure_destination is not None and run is not None and run.is_dir():
            failure_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(run, failure_destination)
        raise PackageReaderError(
            f"Navdatareader 在 {timeout_seconds} 秒内未完成"
        ) from error
    except PackageReaderError:
        if failure_destination is not None and run is not None and run.is_dir():
            failure_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(run, failure_destination)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    return PackageReaderResult(
        database=target,
        package={
            **source_fingerprint,
            "matched_bgl_count": len(selected_bgls),
            "filename_patterns": list(patterns),
        },
        reader={
            "path": str(reader_path),
            "sha256": _sha256(reader_path),
            "returncode": result.returncode,
            "reader_marked_broken": produced_database.name != requested_database.name,
        },
        scan=scan,
    )
