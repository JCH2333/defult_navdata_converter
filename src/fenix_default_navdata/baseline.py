from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .model import Navaid


class BaselineError(RuntimeError):
    """官方设施基线无法作为差分依据时抛出的错误。"""


_REQUIRED_COLUMNS = {
    "vor": {
        "ident",
        "region",
        "frequency",
        "mag_var",
        "altitude",
        "lonx",
        "laty",
        "name",
    },
    "ndb": {
        "ident",
        "region",
        "frequency",
        "mag_var",
        "altitude",
        "lonx",
        "laty",
        "name",
    },
}

_KIND_TABLES = (("VOR", "vor"), ("NDB", "ndb"))
_EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True)
class BaselineNavaid:
    """从官方 BGL 索引 SQLite 读取的一条导航台记录。"""

    kind: str
    ident: str
    region: str
    frequency_khz: float
    latitude: float
    longitude: float
    name: str
    magnetic_variation: float | None
    elevation_ft: int | None
    source: str
    row_id: int

    @property
    def identity(self) -> tuple[str, str, str, float, float, float]:
        return (
            self.kind,
            self.ident,
            self.region,
            round(self.frequency_khz, 3),
            round(self.latitude, 5),
            round(self.longitude, 5),
        )

    @property
    def sort_key(self) -> tuple[object, ...]:
        return (
            self.kind,
            self.ident,
            self.region,
            self.frequency_khz,
            self.latitude,
            self.longitude,
            self.source,
            self.row_id,
        )


@dataclass(frozen=True)
class BaselineIndex:
    """合并后的只读官方设施索引。"""

    records: tuple[BaselineNavaid, ...]
    sources: tuple[str, ...]
    database_counts: tuple[tuple[str, int, int], ...]
    verified: bool = True

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def counts_by_kind(self) -> dict[str, int]:
        return {
            kind: sum(1 for record in self.records if record.kind == kind)
            for kind, _ in _KIND_TABLES
        }

    def candidates(
        self,
        kind: str,
        ident: str,
        region: str,
    ) -> tuple[BaselineNavaid, ...]:
        normalized = (kind.upper(), ident.strip().upper(), region.strip().upper()[:2])
        return tuple(
            record
            for record in self.records
            if (record.kind, record.ident, record.region) == normalized
        )


@dataclass(frozen=True)
class NavaidMatch:
    raw: Navaid
    baseline: BaselineNavaid
    distance_nm: float
    property_delta: tuple[str, ...]


@dataclass(frozen=True)
class NavaidAmbiguity:
    raw: Navaid
    candidates: tuple[BaselineNavaid, ...]


@dataclass(frozen=True)
class NavaidDiff:
    """424 导航台相对于官方全球基线的确定性差分结果。"""

    raw: tuple[Navaid, ...]
    selected_navaids: tuple[Navaid, ...]
    matched_existing: tuple[NavaidMatch, ...]
    unmatched: tuple[Navaid, ...]
    ambiguous: tuple[NavaidAmbiguity, ...]
    property_deltas: tuple[NavaidMatch, ...]
    suppressed_duplicates: tuple[Navaid, ...]
    baseline_count: int
    baseline_counts_by_kind: dict[str, int]
    coordinate_tolerance_nm: float
    verified: bool

    @property
    def navaid_diff_verified(self) -> bool:
        return self.verified

    def to_report(self) -> dict[str, object]:
        def raw_payload(item: Navaid) -> dict[str, object]:
            return {
                "key": item.key,
                "kind": item.kind,
                "ident": item.ident,
                "region": item.country[:2],
                "frequency": item.frequency,
                "latitude": item.latitude,
                "longitude": item.longitude,
            }

        def baseline_payload(item: BaselineNavaid) -> dict[str, object]:
            return {
                "kind": item.kind,
                "ident": item.ident,
                "region": item.region,
                "frequency_khz": item.frequency_khz,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "source": item.source,
                "row_id": item.row_id,
            }

        return {
            "navaid_diff_verified": self.verified,
            "raw_count": len(self.raw),
            "baseline_count": self.baseline_count,
            "baseline_counts_by_kind": self.baseline_counts_by_kind,
            "matched_existing": len(self.matched_existing),
            "selected_missing": len(self.selected_navaids),
            "unmatched": len(self.unmatched),
            "ambiguous": len(self.ambiguous),
            "property_delta": len(self.property_deltas),
            "suppressed": len(self.suppressed_duplicates),
            "selected_by_kind": {
                kind: sum(1 for item in self.selected_navaids if item.kind == kind)
                for kind, _ in _KIND_TABLES
            },
            "coordinate_tolerance_nm": self.coordinate_tolerance_nm,
            "ambiguous_records": [
                {
                    "raw": raw_payload(item.raw),
                    "candidates": [baseline_payload(candidate) for candidate in item.candidates],
                }
                for item in self.ambiguous[:100]
            ],
            "property_delta_records": [
                {
                    "raw": raw_payload(item.raw),
                    "baseline": baseline_payload(item.baseline),
                    "distance_nm": item.distance_nm,
                    "fields": list(item.property_delta),
                }
                for item in self.property_deltas[:100]
            ],
        }


def _open_readonly(path: Path) -> sqlite3.Connection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise BaselineError(f"官方设施基线不存在: {path}")
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except (OSError, sqlite3.DatabaseError) as error:
        raise BaselineError(f"无法打开官方设施基线: {path}: {error}") from error
    try:
        checks = [str(row[0]).lower() for row in connection.execute("PRAGMA integrity_check")]
    except sqlite3.DatabaseError as error:
        connection.close()
        raise BaselineError(f"官方设施基线完整性检查失败: {path}: {error}") from error
    if checks != ["ok"]:
        connection.close()
        detail = "; ".join(checks[:5]) or "unknown error"
        raise BaselineError(f"官方设施基线不是完整 SQLite 数据库: {path}: {detail}")
    return connection


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.DatabaseError as error:
        raise BaselineError(f"无法读取官方设施基线表结构 {table}: {error}") from error
    return {str(row[1]).lower() for row in rows}


def _number(value: object, *, field: str, table: str, row_id: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise BaselineError(f"官方设施基线 {table} 行 {row_id} 的 {field} 不是数字") from error
    if not math.isfinite(result):
        raise BaselineError(f"官方设施基线 {table} 行 {row_id} 的 {field} 不是有限数字")
    return result


def _optional_number(value: object, *, field: str, table: str, row_id: int) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _number(value, field=field, table=table, row_id=row_id)


def _read_table(connection: sqlite3.Connection, path: Path, kind: str, table: str) -> tuple[BaselineNavaid, ...]:
    columns = _table_columns(connection, table)
    missing = sorted(_REQUIRED_COLUMNS[table] - columns)
    if missing:
        raise BaselineError(
            f"官方设施基线 {path} 的 {table} 表缺少列: {', '.join(missing)}"
        )
    try:
        rows = connection.execute(
            f'SELECT rowid AS _baseline_rowid, ident, region, frequency, '
            f'mag_var, altitude, lonx, laty, name FROM "{table}"'
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise BaselineError(f"无法读取官方设施基线 {table} 表: {path}: {error}") from error
    if not rows:
        raise BaselineError(f"官方设施基线 {path} 的 {table} 表为空")
    result: list[BaselineNavaid] = []
    for row in rows:
        row_id = int(row["_baseline_rowid"])
        ident = str(row["ident"] or "").strip().upper()
        region = str(row["region"] or "").strip().upper()[:2]
        if not ident or not region:
            raise BaselineError(f"官方设施基线 {table} 行 {row_id} 缺少 ident 或 region")
        frequency = _number(row["frequency"], field="frequency", table=table, row_id=row_id)
        latitude = _number(row["laty"], field="laty", table=table, row_id=row_id)
        longitude = _number(row["lonx"], field="lonx", table=table, row_id=row_id)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise BaselineError(f"官方设施基线 {table} 行 {row_id} 坐标超出范围")
        if frequency <= 0:
            raise BaselineError(f"官方设施基线 {table} 行 {row_id} 频率必须为正数")
        magnetic_variation = _optional_number(
            row["mag_var"], field="mag_var", table=table, row_id=row_id,
        )
        elevation_value = _optional_number(
            row["altitude"], field="altitude", table=table, row_id=row_id,
        )
        elevation_ft = int(round(elevation_value)) if elevation_value is not None else None
        result.append(BaselineNavaid(
            kind=kind,
            ident=ident,
            region=region,
            frequency_khz=frequency,
            latitude=latitude,
            longitude=longitude,
            name=str(row["name"] or "").strip(),
            magnetic_variation=magnetic_variation,
            elevation_ft=elevation_ft,
            source=str(path),
            row_id=row_id,
        ))
    return tuple(sorted(result, key=lambda item: item.sort_key))


def load_baseline_sqlite(path: Path) -> BaselineIndex:
    """读取一个由 BGL 探针生成的官方导航台 SQLite 索引。"""
    path = path.expanduser().resolve()
    connection = _open_readonly(path)
    try:
        # 先完整检查两张表的存在性和列契约，再检查内容，避免错误信息
        # 被另一张空表遮蔽。
        table_errors: list[str] = []
        for _, table in _KIND_TABLES:
            columns = _table_columns(connection, table)
            if not columns:
                table_errors.append(f"缺少表 {table}")
                continue
            missing = sorted(_REQUIRED_COLUMNS[table] - columns)
            if missing:
                table_errors.append(
                    f"表 {table} 缺少列: {', '.join(missing)}"
                )
        if table_errors:
            raise BaselineError(
                f"官方设施基线 {path} 结构不完整: {'; '.join(table_errors)}"
            )
        records: list[BaselineNavaid] = []
        counts: list[tuple[str, int, int]] = []
        for kind, table in _KIND_TABLES:
            table_records = _read_table(connection, path, kind, table)
            records.extend(table_records)
            counts.append((table, len(table_records), 0))
    finally:
        connection.close()
    return BaselineIndex(
        records=tuple(sorted(records, key=lambda item: item.sort_key)),
        sources=(str(path),),
        database_counts=tuple(counts),
        verified=True,
    )


def merge_baseline_indexes(indexes: Sequence[BaselineIndex]) -> BaselineIndex:
    """合并官方来源并去除完全相同的跨包重复行。"""
    if not indexes:
        raise BaselineError("没有提供官方设施基线索引")
    if any(not index.verified for index in indexes):
        raise BaselineError("不能合并未通过验证的官方设施基线索引")
    records: dict[tuple[object, ...], BaselineNavaid] = {}
    for index in indexes:
        for record in index.records:
            records.setdefault(record.identity, record)
    sources = tuple(sorted({source for index in indexes for source in index.sources}))
    counts = tuple(
        item
        for index in indexes
        for item in index.database_counts
    )
    merged = BaselineIndex(
        records=tuple(sorted(records.values(), key=lambda item: item.sort_key)),
        sources=sources,
        database_counts=counts,
        verified=True,
    )
    if not merged.records:
        raise BaselineError("合并后的官方设施基线为空")
    return merged


def load_baseline_index(paths: Path | Iterable[Path]) -> BaselineIndex:
    """读取并合并一个或多个官方设施索引 SQLite 文件。"""
    if isinstance(paths, Path):
        path_list = (paths,)
    else:
        path_list = tuple(paths)
    if not path_list:
        raise BaselineError("没有提供官方设施基线索引路径")
    return merge_baseline_indexes(tuple(load_baseline_sqlite(path) for path in path_list))


def _distance_nm(first: Navaid, second: BaselineNavaid) -> float:
    first_lat = math.radians(first.latitude)
    second_lat = math.radians(second.latitude)
    delta_lat = second_lat - first_lat
    delta_lon = math.radians(second.longitude - first.longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_NM * math.asin(math.sqrt(min(1.0, value)))


def _source_frequency_khz(navaid: Navaid) -> float:
    if navaid.kind == "VOR":
        return float(navaid.frequency) * 1000
    if navaid.kind == "NDB":
        return float(navaid.frequency) * 100
    raise BaselineError(f"不支持的原始导航台类型: {navaid.kind}")


def _raw_identity(navaid: Navaid) -> tuple[object, ...]:
    return (
        navaid.kind.upper(),
        navaid.ident.strip().upper(),
        (navaid.country or "").strip().upper()[:2],
        round(_source_frequency_khz(navaid), 3),
        round(navaid.latitude, 5),
        round(navaid.longitude, 5),
    )


def _property_delta(raw: Navaid, baseline: BaselineNavaid, distance_nm: float) -> tuple[str, ...]:
    fields: list[str] = []
    if distance_nm > 0.01:
        fields.append("coordinates")
    if abs(_source_frequency_khz(raw) - baseline.frequency_khz) > 1:
        fields.append("frequency")
    if (
        baseline.magnetic_variation is not None
        and abs(raw.magnetic_variation - baseline.magnetic_variation) > 0.05
    ):
        fields.append("magnetic_variation")
    if (
        baseline.elevation_ft is not None
        and abs(raw.elevation_ft - baseline.elevation_ft) > 10
    ):
        fields.append("elevation")
    if raw.name.isascii() and raw.name.strip().upper() != baseline.name.strip().upper():
        fields.append("name")
    return tuple(fields)


def diff_navaids(
    navaids: Iterable[Navaid],
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float = 0.25,
) -> NavaidDiff:
    """选择官方基线中不存在的 424 导航台，并报告所有不确定匹配。"""
    if not baseline.verified or not baseline.records:
        raise BaselineError("官方设施基线未通过验证，不能执行导航台差分")
    if coordinate_tolerance_nm <= 0 or not math.isfinite(coordinate_tolerance_nm):
        raise ValueError("导航台坐标匹配阈值必须为正数")
    raw = tuple(sorted(tuple(navaids), key=lambda item: (
        item.kind.upper(), item.ident.upper(), item.country.upper(),
        item.frequency, item.latitude, item.longitude, item.key,
    )))
    selected: list[Navaid] = []
    matched: list[NavaidMatch] = []
    ambiguous: list[NavaidAmbiguity] = []
    suppressed: list[Navaid] = []
    seen: set[tuple[object, ...]] = set()
    for item in raw:
        identity = _raw_identity(item)
        if identity in seen:
            suppressed.append(item)
            continue
        seen.add(identity)
        candidates = []
        source_frequency = _source_frequency_khz(item)
        for candidate in baseline.candidates(item.kind, item.ident, item.country):
            if abs(candidate.frequency_khz - source_frequency) > 1:
                continue
            distance = _distance_nm(item, candidate)
            if distance <= coordinate_tolerance_nm:
                candidates.append((distance, candidate))
        candidates.sort(key=lambda pair: (pair[0], pair[1].sort_key))
        distinct = {candidate.identity for _, candidate in candidates}
        if len(distinct) > 1:
            ambiguous.append(NavaidAmbiguity(
                raw=item,
                candidates=tuple(candidate for _, candidate in candidates),
            ))
            continue
        if not candidates:
            selected.append(item)
            continue
        distance, candidate = candidates[0]
        match = NavaidMatch(
            raw=item,
            baseline=candidate,
            distance_nm=distance,
            property_delta=_property_delta(item, candidate, distance),
        )
        matched.append(match)
    property_deltas = tuple(item for item in matched if item.property_delta)
    return NavaidDiff(
        raw=raw,
        selected_navaids=tuple(sorted(selected, key=lambda item: (
            item.kind, item.ident.upper(), item.country.upper(),
            item.latitude, item.longitude, item.key,
        ))),
        matched_existing=tuple(matched),
        unmatched=tuple(selected),
        ambiguous=tuple(ambiguous),
        property_deltas=property_deltas,
        suppressed_duplicates=tuple(suppressed),
        baseline_count=baseline.count,
        baseline_counts_by_kind=baseline.counts_by_kind,
        coordinate_tolerance_nm=coordinate_tolerance_nm,
        verified=not ambiguous,
    )


def build_navaid_diff(
    navaids: Iterable[Navaid],
    baseline: BaselineIndex,
    *,
    coordinate_tolerance_nm: float = 0.25,
) -> NavaidDiff:
    """兼容性别名，供构建入口和外部脚本使用。"""
    return diff_navaids(
        navaids,
        baseline,
        coordinate_tolerance_nm=coordinate_tolerance_nm,
    )
