from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .baseline import BaselineError, BaselineIndex, load_baseline_sqlite


BASE_PACKAGE = "navigraph-nav-base"
JEPP_PACKAGE = "navigraph-nav-jepp"
_PACKAGE_NAMES = (BASE_PACKAGE, JEPP_PACKAGE)
_METADATA_VERSION = 3
_READER_MIRROR_MODE = "neutral-community-bgl-mirror-v1"
_READER_MIRROR_NAMES = {
    BASE_PACKAGE: "official-core-reader-probe",
    JEPP_PACKAGE: "official-jepp-reader-probe",
}
_READER_BGL_PREFIXES = ("nax", "nvx", "atx")
_INDEXED_RECORD_TABLES = (
    ("VOR", "vor"),
    ("NDB", "ndb"),
    ("WAYPOINT", "waypoint"),
)
_WAYPOINT_REQUIRED_COLUMNS = {"file_id", "ident", "region", "laty", "lonx"}


class OfficialIndexError(RuntimeError):
    """官方双包设施索引无法证明来源或无法安全使用时抛出的错误。"""


@dataclass(frozen=True)
class PackageFingerprint:
    """一份官方 Community 包的可重复树指纹。"""

    package_name: str
    source: Path
    tree_sha256: str
    file_count: int
    total_bytes: int
    manifest_sha256: str
    layout_sha256: str
    bgl_index_sha256: str

    def to_report(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "tree_sha256": self.tree_sha256,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "manifest_sha256": self.manifest_sha256,
            "layout_sha256": self.layout_sha256,
            "bgl_index_sha256": self.bgl_index_sha256,
        }


@dataclass(frozen=True)
class _ReaderMirrorFile:
    """官方 BGL 在读取器中性包中的目标相对路径。"""

    mirror_relative: str
    source_relative: str
    source: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class _ReaderMirrorPlan:
    """只读官方 BGL 到读取器中性镜像的可验证复制计划。"""

    package_name: str
    mirror_name: str
    source: Path
    files: tuple[_ReaderMirrorFile, ...]
    source_bgl_tree_sha256: str

    @property
    def expected_paths(self) -> frozenset[str]:
        return frozenset(item.mirror_relative.casefold() for item in self.files)

    def to_report(self) -> dict[str, object]:
        return {
            "mirror_package": self.mirror_name,
            "source_bgl_count": len(self.files),
            "source_bgl_tree_sha256": self.source_bgl_tree_sha256,
        }


@dataclass(frozen=True)
class OfficialNavaidIndex:
    """已通过来源校验的官方 VOR/NDB/航点索引。"""

    database: Path
    metadata_path: Path
    baseline: BaselineIndex
    waypoints: tuple["OfficialWaypoint", ...]
    metadata: dict[str, object]
    reused: bool

    @property
    def verified(self) -> bool:
        return (
            self.metadata.get("metadata_version") == _METADATA_VERSION
            and self.metadata.get("status") == "verified"
        )

    def to_report(self) -> dict[str, object]:
        packages = self.metadata.get("packages")
        database = self.metadata.get("database")
        reader = self.metadata.get("reader")
        provenance = self.metadata.get("record_provenance")
        return {
            "verified": self.verified,
            "database": str(self.database),
            "metadata": str(self.metadata_path),
            "reused": self.reused,
            "packages": packages if isinstance(packages, dict) else {},
            "database_info": database if isinstance(database, dict) else {},
            "reader": reader if isinstance(reader, dict) else {},
            "record_provenance": provenance if isinstance(provenance, dict) else {},
            "waypoint_rows": len(self.waypoints),
            "warnings": self.metadata.get("warnings", []),
        }


@dataclass(frozen=True)
class OfficialWaypoint:
    """一条来源已验证的官方航点，仅用于区域码判定。"""

    ident: str
    region: str
    latitude: float
    longitude: float
    source: str
    row_id: int

    @property
    def sort_key(self) -> tuple[object, ...]:
        return (
            self.ident,
            self.region,
            self.latitude,
            self.longitude,
            self.source,
            self.row_id,
        )


def metadata_path_for(database: Path) -> Path:
    """返回 SQLite 索引对应的来源侧车文件路径。"""
    database = database.expanduser()
    return database.with_name(f"{database.name}.metadata.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_file(path: Path, name: str) -> Path:
    value = path / name
    if not value.is_file():
        raise OfficialIndexError(f"官方包缺少 {name}: {path}")
    return value


def fingerprint_package(package_name: str, source: Path) -> PackageFingerprint:
    """对官方包完整文件树计算稳定 SHA-256 指纹。"""
    source = source.expanduser().resolve()
    if not source.is_dir():
        raise OfficialIndexError(f"官方包目录不存在: {source}")
    manifest = _package_file(source, "manifest.json")
    layout = _package_file(source, "layout.json")
    index = _package_file(source, "bglIndex.bout")
    files = sorted(
        (path for path in source.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(source).as_posix().casefold(),
    )
    if not files:
        raise OfficialIndexError(f"官方包为空: {source}")
    tree = hashlib.sha256()
    total_bytes = 0
    for path in files:
        before = path.stat()
        checksum = _sha256(path)
        after = path.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise OfficialIndexError(f"计算指纹时官方包文件发生变化: {path}")
        relative = path.relative_to(source).as_posix()
        tree.update(relative.encode("utf-8"))
        tree.update(b"\0")
        tree.update(str(before.st_size).encode("ascii"))
        tree.update(b"\0")
        tree.update(checksum.encode("ascii"))
        tree.update(b"\n")
        total_bytes += before.st_size
    return PackageFingerprint(
        package_name=package_name,
        source=source,
        tree_sha256=tree.hexdigest(),
        file_count=len(files),
        total_bytes=total_bytes,
        manifest_sha256=_sha256(manifest),
        layout_sha256=_sha256(layout),
        bgl_index_sha256=_sha256(index),
    )


def fingerprint_official_packages(
    nav_base: Path,
    nav_jepp: Path,
) -> dict[str, PackageFingerprint]:
    """同时计算两份官方全球基线的完整树指纹。"""
    return {
        BASE_PACKAGE: fingerprint_package(BASE_PACKAGE, nav_base),
        JEPP_PACKAGE: fingerprint_package(JEPP_PACKAGE, nav_jepp),
    }


def _cache_root(cache_root: Path | None = None) -> Path:
    root = cache_root or (
        Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
        / "default_navdata_converter"
        / "official-navaid-index"
    )
    root = root.expanduser().resolve()
    if not str(root).isascii():
        raise OfficialIndexError(
            f"官方设施索引缓存目录必须是纯 ASCII 路径: {root}"
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _combined_fingerprint(fingerprints: dict[str, PackageFingerprint]) -> str:
    digest = hashlib.sha256()
    for name in _PACKAGE_NAMES:
        fingerprint = fingerprints[name]
        digest.update(name.encode("ascii"))
        digest.update(b"\0")
        digest.update(fingerprint.tree_sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def default_index_path(
    nav_base: Path,
    nav_jepp: Path,
    *,
    cache_root: Path | None = None,
) -> Path:
    """为当前两份官方包返回内容寻址的本地索引缓存路径。"""
    fingerprints = fingerprint_official_packages(nav_base, nav_jepp)
    return _default_index_path_from_fingerprints(fingerprints, cache_root=cache_root)


def _default_index_path_from_fingerprints(
    fingerprints: dict[str, PackageFingerprint],
    *,
    cache_root: Path | None = None,
) -> Path:
    return _cache_root(cache_root) / (
        f"official-navaids-{_combined_fingerprint(fingerprints)[:20]}.sqlite"
    )


def find_navdatareader(explicit: Path | None = None) -> Path | None:
    """查找本机只读使用的 Navdatareader，不将该外部工具纳入仓库。"""
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    environment = os.environ.get("NAVDATAREADER")
    if environment:
        candidates.append(Path(environment))
    repository_root = Path(__file__).resolve().parents[2]
    candidates.extend([
        repository_root
        / "diagnostics"
        / "navdatareader"
        / "app"
        / "Navdatareader-win-1.2.4"
        / "navdatareader.exe",
        Path.cwd()
        / "diagnostics"
        / "navdatareader"
        / "app"
        / "Navdatareader-win-1.2.4"
        / "navdatareader.exe",
    ])
    for candidate in candidates:
        path = candidate.expanduser()
        if path.is_file():
            return path.resolve()
    return None


def _reader_text(path: Path, name: str) -> str | None:
    value = path.parent / name
    if not value.is_file():
        return None
    text = value.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def _reader_report(
    reader: Path,
    returncode: int,
    *,
    requested_database: Path,
    produced_database: Path,
) -> dict[str, object]:
    report: dict[str, object] = {
        "path": str(reader),
        "exe_sha256": _sha256(reader),
        "version": _reader_text(reader, "version.txt"),
        "revision": _reader_text(reader, "revision.txt"),
        "command": [
            reader.name,
            "-f",
            "MSFS",
            "-b",
            "<ASCII_STAGE_ROOT>",
            "-o",
            "<INDEX_DATABASE>",
            "-c",
            "<READER_CONFIG>",
        ],
        "returncode": returncode,
    }
    if produced_database.name != requested_database.name:
        report["produced_database_name"] = produced_database.name
        report["reader_marked_broken"] = True
    return report


def _reader_config() -> str:
    return """[Database]
Type=QSQLITE

[Options]
DatabaseReport=false
BasicValidation=false
AirportValidation=false
ProcessDelete=true
FilterRunways=false
SaveIncomplete=true
ResolveRoutes=true
Verbose=false
Autocommit=false
Deduplicate=false
DropAllIndexes=false
DropTempTables=true
VacuumDatabase=false
AnalyzeDatabase=false
SimConnectLoadDisconnected=false
SimConnectLoadDisconnectedFile=false

[Filter]
IncludeHighPriorityFilter=
IncludeFilenames=NAX*.bgl,NVX*.bgl,ATX*.bgl
ExcludeFilenames=
IncludePathFilter=
ExcludePathFilter=
IncludeAirportIcaoFilter=
ExcludeAirportIcaoFilter=
IncludeBglObjectFilter=VOR,NDB,WAYPOINT,AIRWAY
ExcludeBglObjectFilter=APRON2
IncludeAddonPathFilter=
ExcludeAddonPathFilter=
"""


def _mirror_tail(source_relative: Path) -> str:
    parts = source_relative.as_posix().split("/")
    if len(parts) < 3 or parts[0].casefold() != "scenery":
        raise OfficialIndexError(
            f"官方 BGL 不在预期 scenery 目录中: {source_relative.as_posix()}"
        )
    tail = parts[2:]
    if tail and tail[0].casefold() == "scenery":
        tail = tail[1:]
    if not tail:
        raise OfficialIndexError(
            f"官方 BGL 缺少可镜像的场景相对路径: {source_relative.as_posix()}"
        )
    return "/".join(tail)


def _reader_bgl_candidate(path: Path) -> bool:
    return (
        path.suffix.casefold() == ".bgl"
        and path.name.casefold().startswith(_READER_BGL_PREFIXES)
    )


def _reader_mirror_plan(package_name: str, source: Path) -> _ReaderMirrorPlan:
    mirror_name = _READER_MIRROR_NAMES[package_name]
    digest = hashlib.sha256()
    files: list[_ReaderMirrorFile] = []
    mirror_paths: set[str] = set()
    for path in sorted(
        (item for item in source.rglob("*.bgl") if _reader_bgl_candidate(item)),
        key=lambda item: item.relative_to(source).as_posix().casefold(),
    ):
        before = path.stat()
        checksum = _sha256(path)
        after = path.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise OfficialIndexError(f"读取器镜像规划时官方 BGL 发生变化: {path}")
        source_relative = path.relative_to(source)
        mirror_relative = f"scenery/{mirror_name}/{_mirror_tail(source_relative)}"
        key = mirror_relative.casefold()
        if key in mirror_paths:
            raise OfficialIndexError(
                f"读取器镜像目标路径冲突: {package_name}: {mirror_relative}"
            )
        mirror_paths.add(key)
        digest.update(source_relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(before.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
        files.append(_ReaderMirrorFile(
            mirror_relative=mirror_relative,
            source_relative=source_relative.as_posix(),
            source=path,
            sha256=checksum,
            size=before.st_size,
        ))
    return _ReaderMirrorPlan(
        package_name=package_name,
        mirror_name=mirror_name,
        source=source,
        files=tuple(files),
        source_bgl_tree_sha256=digest.hexdigest(),
    )


def _stage_reader_mirror(plan: _ReaderMirrorPlan, community: Path) -> Path | None:
    """镜像读取器所需 BGL；任何一个副本字节不一致都会立即失败。"""
    if not plan.files:
        return None
    root = community / plan.mirror_name
    bgl_index = plan.source / "bglIndex.bout"
    if not bgl_index.is_file():
        raise OfficialIndexError(f"官方包缺少 bglIndex.bout: {plan.source}")
    root.mkdir(parents=True)
    staged_index = root / "bglIndex.bout"
    shutil.copy2(bgl_index, staged_index)
    if _sha256(staged_index) != _sha256(bgl_index):
        raise OfficialIndexError(f"读取器镜像索引校验失败: {plan.package_name}")
    content: list[dict[str, object]] = [{
        "path": "bglindex.bout",
        "size": staged_index.stat().st_size,
        "date": 0,
    }]
    for item in plan.files:
        target = root / Path(*item.mirror_relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, target)
        if target.stat().st_size != item.size or _sha256(target) != item.sha256:
            raise OfficialIndexError(
                f"读取器镜像 BGL 校验失败: {plan.package_name}: {item.source_relative}"
            )
        content.append({
            "path": item.mirror_relative.casefold(),
            "size": item.size,
            "date": 0,
        })
    (root / "layout.json").write_text(
        json.dumps({"content": content}, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps({
            "content_type": "SCENERY",
            "title": f"Official data reader mirror {plan.mirror_name}",
            "manufacturer": "Local Diagnostic",
            "creator": "Default NavData Converter",
            "package_version": "0.0.0",
            "minimum_game_version": "1.7.35",
            "minimum_compatibility_version": "7.26.0.214",
            "export_type": "Community",
            "builder": "Microsoft Flight Simulator 2024",
            "package_order_hint": "CUSTOM_NAVDATA_PATCH",
        }, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _mirror_relative_from_reader_path(
    filepath: str,
    plan: _ReaderMirrorPlan,
) -> str | None:
    normalized = filepath.replace("\\", "/").strip("/").casefold()
    marker = f"/community/{plan.mirror_name.casefold()}/"
    position = normalized.rfind(marker)
    if position < 0:
        return None
    return normalized[position + len(marker):]


def _provenance_rows(
    database: Path,
    plans: dict[str, _ReaderMirrorPlan],
) -> dict[str, object]:
    """将读取器记录来源反向映射回当前官方双包的 BGL 计划。"""
    path = database.resolve()
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.DatabaseError as error:
        raise OfficialIndexError(f"无法读取设施索引来源表: {path}: {error}") from error
    try:
        tables = {
            str(row[0]).lower()
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        expected_tables = {"bgl_file"} | {
            table for _, table in _INDEXED_RECORD_TABLES
        }
        missing_tables = sorted(expected_tables - tables)
        if missing_tables:
            raise OfficialIndexError(
                "官方索引缺少来源表: " + ", ".join(missing_tables)
            )
        columns = {
            table: {
                str(row[1]).lower()
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            for table in expected_tables
        }
        required = {
            "bgl_file": {"bgl_file_id", "filepath"},
            **{
                table: {"file_id"}
                for _, table in _INDEXED_RECORD_TABLES
            },
            "waypoint": _WAYPOINT_REQUIRED_COLUMNS | {"file_id"},
        }
        missing = {
            table: sorted(required[table] - columns[table])
            for table in required
            if required[table] - columns[table]
        }
        if missing:
            detail = "; ".join(
                f"{table}: {', '.join(names)}" for table, names in missing.items()
            )
            raise OfficialIndexError(f"官方索引来源字段不完整: {detail}")
        dangling: list[str] = []
        for kind, table in _INDEXED_RECORD_TABLES:
            count = int(connection.execute(
                f"""
                SELECT COUNT(*)
                FROM \"{table}\" AS item
                LEFT JOIN bgl_file AS source ON source.bgl_file_id = item.file_id
                WHERE source.bgl_file_id IS NULL
                """
            ).fetchone()[0])
            if count:
                dangling.append(f"{kind}={count}")
        if dangling:
            raise OfficialIndexError(
                "官方索引包含无法回溯到 BGL 的记录: " + ", ".join(dangling)
            )
        query = "\nUNION ALL\n".join(
            f"""
            SELECT '{kind}' AS kind, source.filepath AS filepath, COUNT(*) AS records
            FROM \"{table}\" AS item
            JOIN bgl_file AS source ON source.bgl_file_id = item.file_id
            GROUP BY source.filepath
            """
            for kind, table in _INDEXED_RECORD_TABLES
        )
        rows = connection.execute(query).fetchall()
    except sqlite3.DatabaseError as error:
        raise OfficialIndexError(f"读取官方索引来源时失败: {path}: {error}") from error
    finally:
        connection.close()
    if not rows:
        raise OfficialIndexError("官方索引没有可追溯的 VOR/NDB/航点 BGL 来源")
    source_counts = {
        name: {kind: 0 for kind, _ in _INDEXED_RECORD_TABLES}
        for name in _PACKAGE_NAMES
    }
    source_files: set[tuple[str, str]] = set()
    expected = {
        name: plan.expected_paths
        for name, plan in plans.items()
    }
    unexpected: list[str] = []
    for row in rows:
        filepath = str(row["filepath"] or "").strip()
        if not filepath:
            unexpected.append("<empty>")
            continue
        match = next(
            (
                (name, relative)
                for name, plan in plans.items()
                if (relative := _mirror_relative_from_reader_path(filepath, plan))
                is not None
            ),
            None,
        )
        if match is None:
            unexpected.append(filepath)
            continue
        package_name, relative = match
        if relative not in expected[package_name]:
            unexpected.append(filepath)
            continue
        source_files.add((package_name, relative))
        source_counts[package_name][str(row["kind"])] += int(row["records"])
    if unexpected:
        preview = "; ".join(unexpected[:5])
        raise OfficialIndexError(
            "设施索引包含不属于暂存官方双包的 BGL 来源: " + preview
        )
    if not source_files:
        raise OfficialIndexError("设施索引没有来自暂存官方双包的 BGL 来源")
    missing_kinds = [
        kind
        for kind, _ in _INDEXED_RECORD_TABLES
        if sum(counts[kind] for counts in source_counts.values()) == 0
    ]
    if missing_kinds:
        raise OfficialIndexError(
            "官方索引缺少可追溯的记录类型: " + ", ".join(missing_kinds)
        )
    return {
        "source_bgl_files": len(source_files),
        "record_counts": source_counts,
        "reader_mirror": {
            "mode": _READER_MIRROR_MODE,
            "packages": {
                name: plans[name].to_report() for name in _PACKAGE_NAMES
            },
        },
    }


def _load_verified_waypoints(database: Path) -> tuple[OfficialWaypoint, ...]:
    """读取已验证 SQLite 的官方航点，保留其 BGL 来源供严格区域匹配使用。"""
    path = database.resolve()
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.DatabaseError as error:
        raise OfficialIndexError(f"无法读取官方航点索引: {path}: {error}") from error
    try:
        tables = {
            str(row[0]).lower()
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"bgl_file", "waypoint"}.issubset(tables):
            raise OfficialIndexError("官方索引缺少 bgl_file 或 waypoint 表")
        columns = {
            str(row[1]).lower()
            for row in connection.execute('PRAGMA table_info("waypoint")')
        }
        missing = sorted(_WAYPOINT_REQUIRED_COLUMNS - columns)
        if missing:
            raise OfficialIndexError(
                "官方索引 waypoint 表缺少列: " + ", ".join(missing)
            )
        rows = connection.execute(
            """
            SELECT item.rowid AS _official_rowid, item.ident, item.region,
                   item.laty, item.lonx, source.filepath AS source
            FROM waypoint AS item
            JOIN bgl_file AS source ON source.bgl_file_id = item.file_id
            ORDER BY item.rowid
            """
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise OfficialIndexError(f"读取官方航点索引时失败: {path}: {error}") from error
    finally:
        connection.close()
    if not rows:
        raise OfficialIndexError("官方索引 waypoint 表为空")
    records: list[OfficialWaypoint] = []
    for row in rows:
        row_id = int(row["_official_rowid"])
        ident = str(row["ident"] or "").strip().upper()
        region = str(row["region"] or "").strip().upper()[:2]
        source = str(row["source"] or "").strip()
        if not ident or not region or not source:
            raise OfficialIndexError(
                f"官方索引 waypoint 行 {row_id} 缺少 ident、region 或 BGL 来源"
            )
        try:
            latitude = float(row["laty"])
            longitude = float(row["lonx"])
        except (TypeError, ValueError) as error:
            raise OfficialIndexError(
                f"官方索引 waypoint 行 {row_id} 坐标不是数字"
            ) from error
        if (
            not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise OfficialIndexError(
                f"官方索引 waypoint 行 {row_id} 坐标超出范围"
            )
        records.append(OfficialWaypoint(
            ident=ident,
            region=region,
            latitude=latitude,
            longitude=longitude,
            source=source,
            row_id=row_id,
        ))
    return tuple(sorted(records, key=lambda item: item.sort_key))


def _warning_lines(stdout: str, stderr: str, returncode: int) -> list[str]:
    warnings = [
        line.strip()
        for line in f"{stdout}\n{stderr}".splitlines()
        if "warn" in line.lower() or "error" in line.lower()
    ]
    if returncode != 0:
        warnings.insert(0, f"读取器退出代码为 {returncode}，但已按 SQLite 和来源契约复核结果")
    return warnings[:100]


def _reader_output_database(requested: Path) -> Path | None:
    """返回读取器生成的 SQLite，兼容其失败时的 `_BROKEN` 重命名。"""
    if requested.is_file():
        return requested
    renamed = requested.with_stem(f"{requested.stem}_BROKEN")
    if renamed.is_file():
        return renamed
    return None


def _run_reader(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    """调用外部读取器；测试会替换此窄接口，不需要真实模拟器资源。"""
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
    )


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_file_atomic(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _source_reports_match(
    metadata: dict[str, object],
    fingerprints: dict[str, PackageFingerprint],
) -> bool:
    packages = metadata.get("packages")
    if not isinstance(packages, dict):
        return False
    for name in _PACKAGE_NAMES:
        current = fingerprints[name].to_report()
        recorded = packages.get(name)
        if not isinstance(recorded, dict):
            return False
        for field in (
            "tree_sha256",
            "file_count",
            "total_bytes",
            "manifest_sha256",
            "layout_sha256",
            "bgl_index_sha256",
        ):
            if recorded.get(field) != current[field]:
                return False
    return True


def _read_metadata(database: Path) -> tuple[Path, dict[str, object]]:
    database = database.expanduser().resolve()
    metadata_path = metadata_path_for(database)
    if not database.is_file():
        raise OfficialIndexError(f"官方设施索引不存在: {database}")
    if not metadata_path.is_file():
        raise OfficialIndexError(
            f"官方设施索引缺少来源侧车文件: {metadata_path}"
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OfficialIndexError(f"无法读取官方设施索引侧车文件: {metadata_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise OfficialIndexError(f"官方设施索引侧车格式无效: {metadata_path}")
    if metadata.get("metadata_version") != _METADATA_VERSION:
        raise OfficialIndexError(
            f"官方设施索引侧车版本不支持: {metadata.get('metadata_version')!r}"
        )
    if metadata.get("status") != "verified":
        raise OfficialIndexError("官方设施索引未标记为已验证")
    return metadata_path, metadata


def load_verified_official_navaid_index(
    database: Path,
    *,
    nav_base: Path,
    nav_jepp: Path,
    reused: bool = True,
) -> OfficialNavaidIndex:
    """只在侧车、当前双包指纹和 BGL 来源全部一致时加载索引。"""
    database = database.expanduser().resolve()
    metadata_path, metadata = _read_metadata(database)
    fingerprints = fingerprint_official_packages(nav_base, nav_jepp)
    if not _source_reports_match(metadata, fingerprints):
        raise OfficialIndexError(
            "官方 nav-base/nav-jepp 文件树已变化，现有设施索引不能继续使用；请重新生成索引"
        )
    database_info = metadata.get("database")
    if not isinstance(database_info, dict):
        raise OfficialIndexError("官方设施索引侧车缺少数据库校验信息")
    if database_info.get("sha256") != _sha256(database):
        raise OfficialIndexError("官方设施索引 SQLite 的 SHA-256 与侧车不一致")
    recorded_provenance = metadata.get("record_provenance")
    if not isinstance(recorded_provenance, dict):
        raise OfficialIndexError("官方索引侧车缺少记录来源统计")
    plans = {
        name: _reader_mirror_plan(name, fingerprints[name].source)
        for name in _PACKAGE_NAMES
    }
    if not any(plan.files for plan in plans.values()):
        raise OfficialIndexError("官方双包没有可用于设施索引的 NAX/NVX/ATX BGL")
    expected_mirror = {
        "mode": _READER_MIRROR_MODE,
        "packages": {
            name: plans[name].to_report() for name in _PACKAGE_NAMES
        },
    }
    if recorded_provenance.get("reader_mirror") != expected_mirror:
        raise OfficialIndexError("官方索引的读取器镜像契约与当前官方包不一致")
    provenance = _provenance_rows(database, plans)
    for field in ("source_bgl_files", "record_counts", "reader_mirror"):
        if recorded_provenance.get(field) != provenance.get(field):
            raise OfficialIndexError(f"官方索引的 {field} 与侧车不一致")
    try:
        baseline = load_baseline_sqlite(database)
    except BaselineError as error:
        raise OfficialIndexError(str(error)) from error
    for kind, expected_key in (("VOR", "vor_rows"), ("NDB", "ndb_rows")):
        if database_info.get(expected_key) != baseline.counts_by_kind[kind]:
            raise OfficialIndexError(f"官方索引 {kind} 行数与侧车不一致")
    waypoints = _load_verified_waypoints(database)
    if database_info.get("waypoint_rows") != len(waypoints):
        raise OfficialIndexError("官方索引 WAYPOINT 行数与侧车不一致")
    recorded_waypoint_rows = sum(
        int(counts.get("WAYPOINT", 0))
        for counts in provenance["record_counts"].values()
    )
    if recorded_waypoint_rows != len(waypoints):
        raise OfficialIndexError("官方索引 WAYPOINT 来源统计与实际行数不一致")
    return OfficialNavaidIndex(
        database=database,
        metadata_path=metadata_path,
        baseline=baseline,
        waypoints=waypoints,
        metadata=metadata,
        reused=reused,
    )


def build_official_navaid_index(
    *,
    nav_base: Path,
    nav_jepp: Path,
    output: Path | None = None,
    reader: Path | None = None,
    cache_root: Path | None = None,
    force: bool = False,
    timeout_seconds: int = 3600,
) -> OfficialNavaidIndex:
    """从当前官方双包生成并验证只读 VOR/NDB/航点索引。

    读取器永远接收纯 ASCII 暂存根目录。官方包名会触发其依赖完整游戏骨架的
    专用分支，因此暂存区只创建经过逐文件 SHA-256 校验的中性 BGL 镜像。读取
    器退出代码只作为诊断信息；最终是否成功取决于 SQLite 完整性、双包树指纹
            和每条 VOR/NDB/航点记录到官方 BGL 计划的反向来源校验。
    """
    if timeout_seconds <= 0:
        raise ValueError("设施索引读取超时必须为正数")
    fingerprints = fingerprint_official_packages(nav_base, nav_jepp)
    target = (
        output.expanduser().resolve()
        if output is not None
        else _default_index_path_from_fingerprints(fingerprints, cache_root=cache_root)
    )
    metadata_path = metadata_path_for(target)
    if target.exists() or metadata_path.exists():
        if not force:
            try:
                return load_verified_official_navaid_index(
                    target,
                    nav_base=nav_base,
                    nav_jepp=nav_jepp,
                    reused=True,
                )
            except OfficialIndexError as error:
                raise OfficialIndexError(
                    f"目标索引已存在但不可复用: {error}；请使用新路径或 --force 重新生成"
                ) from error
    reader_path = find_navdatareader(reader)
    if reader_path is None:
        raise OfficialIndexError(
            "未找到 Navdatareader；请通过 --reader 或 NAVDATAREADER 指定本机读取器"
        )
    plans = {
        name: _reader_mirror_plan(name, fingerprints[name].source)
        for name in _PACKAGE_NAMES
    }
    if not any(plan.files for plan in plans.values()):
        raise OfficialIndexError("官方双包没有可用于设施索引的 NAX/NVX/ATX BGL")
    stage_parent = _cache_root(cache_root)
    stage = Path(tempfile.mkdtemp(prefix="official-index-stage-", dir=stage_parent))
    try:
        stage_root = stage / "root"
        stage_community = stage_root / "Community"
        if not str(stage_root).isascii():
            raise OfficialIndexError(f"读取器暂存目录不是纯 ASCII 路径: {stage_root}")
        stage_community.mkdir(parents=True)
        staged_mirrors = {
            name: _stage_reader_mirror(plans[name], stage_community)
            for name in _PACKAGE_NAMES
        }
        if not any(staged_mirrors.values()):
            raise OfficialIndexError("读取器中性镜像没有可解析的官方 BGL")
        run = stage / "run"
        run.mkdir()
        config = run / "official-navaids.cfg"
        config.write_text(_reader_config(), encoding="utf-8")
        staged_database = run / "official-navaids.sqlite"
        command = [
            str(reader_path),
            "-f",
            "MSFS",
            "-b",
            str(stage_root),
            "-o",
            str(staged_database),
            "-c",
            str(config),
        ]
        result = _run_reader(
            command,
            cwd=run,
            timeout_seconds=timeout_seconds,
        )
        produced_database = _reader_output_database(staged_database)
        if produced_database is None:
            details = (result.stderr or result.stdout or "读取器未生成 SQLite")[-4000:]
            raise OfficialIndexError(
                f"Navdatareader 未生成设施索引，退出代码={result.returncode}: {details}"
            )
        provenance = _provenance_rows(produced_database, plans)
        try:
            baseline = load_baseline_sqlite(produced_database)
        except BaselineError as error:
            raise OfficialIndexError(str(error)) from error
        waypoints = _load_verified_waypoints(produced_database)
        source_waypoint_rows = sum(
            int(counts.get("WAYPOINT", 0))
            for counts in provenance["record_counts"].values()
        )
        if source_waypoint_rows != len(waypoints):
            raise OfficialIndexError("官方索引 WAYPOINT 来源统计与实际行数不一致")
        current_fingerprints = fingerprint_official_packages(nav_base, nav_jepp)
        if any(
            current_fingerprints[name].tree_sha256 != fingerprints[name].tree_sha256
            for name in _PACKAGE_NAMES
        ):
            raise OfficialIndexError("生成索引期间官方双包发生变化，已拒绝写出索引")
        _copy_file_atomic(produced_database, target)
        metadata = {
            "metadata_version": _METADATA_VERSION,
            "status": "verified",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "packages": {
                name: fingerprints[name].to_report() for name in _PACKAGE_NAMES
            },
            "reader": _reader_report(
                reader_path,
                result.returncode,
                requested_database=staged_database,
                produced_database=produced_database,
            ),
            "database": {
                "sha256": _sha256(target),
                "vor_rows": baseline.counts_by_kind["VOR"],
                "ndb_rows": baseline.counts_by_kind["NDB"],
                "waypoint_rows": len(waypoints),
            },
            "record_provenance": provenance,
            "warnings": (
                ([
                    "读取器将索引标记为 BROKEN；已仅在 SQLite 完整性、设施表和官方双包 BGL 来源全部通过后接受。"
                ] if produced_database.name != staged_database.name else [])
                + _warning_lines(result.stdout, result.stderr, result.returncode)
            )[:100],
        }
        _write_json_atomic(metadata_path, metadata)
    except subprocess.TimeoutExpired as error:
        raise OfficialIndexError(f"Navdatareader 在 {timeout_seconds} 秒内未完成") from error
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return load_verified_official_navaid_index(
        target,
        nav_base=nav_base,
        nav_jepp=nav_jepp,
        reused=False,
    )
