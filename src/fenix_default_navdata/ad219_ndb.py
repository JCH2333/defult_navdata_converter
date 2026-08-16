"""Build and audit source-hashed OCR evidence for airport AD 2.19 NDB rows.

The workflow is intentionally evidence-only.  OCR may identify an NDB printed
in an airport table, but it cannot supply the magnetic variation, elevation,
region, or display name required by the default BGL target contract.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .model import Ad219NdbEvidence, Navaid, SourceRef
from .llamacpp_ocr import DEFAULT_MAX_TOKENS, DIRECT_BACKEND
from .ocr_cache import _read_page_payload, build_ocr_cache
from .pdf_charts import extract_ad219_ndbs
from .source import load_naip


_CACHE_SCHEMA_VERSION = 1
_AD219_START = re.compile(r"AD\s*2\s*[.]?\s*19\b", re.IGNORECASE)
_AD219_END = re.compile(r"AD\s*2\s*[.]?\s*20\b", re.IGNORECASE)
_EVIDENCE_TARGET_GAPS = (
    "name",
    "magnetic_variation",
    "elevation_ft",
    "country",
)


class Ad219NdbOcrError(ValueError):
    """Raised when an AD 2.19 NDB OCR job cannot be verified."""


@dataclass(frozen=True)
class Ad219NdbOcrJob:
    """One non-chart airport PDF that may contain an AD 2.19 NDB table."""

    airport: str
    source_pdf: Path
    source_file: str
    source_sha256: str

    def to_report(self) -> dict[str, object]:
        return {
            "airport": self.airport,
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    """Read published 424 CSV files with the same UTF-8/GBK contract as NAIP."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - both supported encodings failed
        raise Ad219NdbOcrError(f"不支持的 CSV 编码: {path}")
    try:
        return tuple(csv.DictReader(text.splitlines()))
    except csv.Error as error:
        raise Ad219NdbOcrError(f"无法读取 CSV: {path}") from error


def _indexed_chart_filenames(airport: str, index: Path) -> set[str]:
    if not index.is_file():
        return set()
    return {
        f"{airport}-{(row.get('PAGE_NUMBER') or '').strip()}.pdf".casefold()
        for row in _csv_rows(index)
        if (row.get("PAGE_NUMBER") or "").strip()
    }


def collect_ad219_ndb_ocr_jobs(
    root: Path,
    *,
    airports: Iterable[str] = (),
) -> tuple[Ad219NdbOcrJob, ...]:
    """Select unindexed airport PDFs without reading their text layers."""
    root = root.expanduser().resolve()
    terminal = root / "Terminal"
    if not root.is_dir():
        raise Ad219NdbOcrError(f"找不到 424 原始数据目录: {root}")
    if not terminal.is_dir():
        raise Ad219NdbOcrError(f"找不到机场 PDF 目录: {terminal}")

    requested = tuple(
        dict.fromkeys(value.strip().upper() for value in airports if value.strip())
    )
    requested_set = set(requested)
    jobs: list[Ad219NdbOcrJob] = []
    available_airports: set[str] = set()
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        airport = airport_directory.name.upper()
        available_airports.add(airport)
        if requested_set and airport not in requested_set:
            continue
        indexed = _indexed_chart_filenames(airport, airport_directory / "Charts.csv")
        for pdf in sorted(airport_directory.glob("*.pdf")):
            if pdf.name.casefold() in indexed:
                continue
            source_file = pdf.relative_to(root).as_posix()
            jobs.append(Ad219NdbOcrJob(
                airport=airport,
                source_pdf=pdf.resolve(),
                source_file=source_file,
                source_sha256=_sha256(pdf),
            ))
    unknown = sorted(requested_set - available_airports)
    if unknown:
        raise Ad219NdbOcrError(
            "不存在的机场目录: " + ", ".join(unknown)
        )
    return tuple(sorted(
        jobs,
        key=lambda item: (item.airport, item.source_file, item.source_sha256),
    ))


def _cache_path(cache_root: Path, job: Ad219NdbOcrJob) -> Path:
    return cache_root / Path(job.source_file).with_suffix("") / job.source_sha256[:16]


def build_ad219_ndb_ocr_cache(
    root: Path,
    cache_root: Path,
    *,
    airports: Iterable[str] = (),
    command: str = "ocr-skill",
    backend: str = DIRECT_BACKEND,
    mode: str = "ocr",
    timeout_seconds: int = 240,
    render_scale: float = 3.0,
    image_profile: str = "original",
    runtime_profile: str = "",
    engine_timeout_seconds: int | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    force: bool = False,
    limit: int | None = None,
    retries: int = 2,
    dry_run: bool = False,
) -> dict[str, object]:
    """Build resumable local OCR caches for source airport PDFs.

    The command deliberately caches complete documents.  Page selection is
    deferred to the audit stage so that an OCR reading of the AD 2.19 heading
    itself is retained in the source evidence.
    """
    root = root.expanduser().resolve()
    cache_root = cache_root.expanduser().resolve()
    if cache_root == root or root in cache_root.parents:
        raise Ad219NdbOcrError("AD 2.19 NDB OCR 缓存不得写入 424 原始数据目录")
    if limit is not None and limit < 1:
        raise Ad219NdbOcrError("AD 2.19 NDB OCR 任务数量上限必须为正整数")

    jobs = collect_ad219_ndb_ocr_jobs(root, airports=airports)
    if limit is not None:
        jobs = jobs[:limit]
    report: dict[str, object] = {
        "diagnostic": "ad219-ndb-ocr-cache-v1",
        "evidence_only": True,
        "projection_allowed": False,
        "source_root": str(root),
        "cache_root": str(cache_root),
        "planned_pdfs": len(jobs),
        "jobs": [job.to_report() for job in jobs],
        "execution_settings": {
            "outer_timeout_seconds": timeout_seconds,
            "engine_timeout_seconds": engine_timeout_seconds,
            "max_tokens": max_tokens,
            "retries": retries,
        },
        "reason": (
            "OCR 仅缓存机场 AD 2.19 的原始证据；不会新增、修改或投影 NDB"
        ),
    }
    if dry_run:
        return report

    builds: list[dict[str, object]] = []
    for job in jobs:
        build = build_ocr_cache(
            job.source_pdf,
            _cache_path(cache_root, job),
            source_root=root,
            command=command,
            backend=backend,
            mode=mode,
            timeout_seconds=timeout_seconds,
            render_scale=render_scale,
            force=force,
            image_profile=image_profile,
            runtime_profile=runtime_profile,
            engine_timeout_seconds=engine_timeout_seconds,
            max_tokens=max_tokens,
            retries=retries,
        )
        builds.append({
            "airport": job.airport,
            **build.to_report(),
        })
    report["builds"] = builds
    report["complete_caches"] = sum(
        bool(item["complete"])
        for item in builds
    )
    return report


def _read_complete_cache(
    cache_root: Path,
    job: Ad219NdbOcrJob,
) -> tuple[tuple[tuple[int, str], ...] | None, str, dict[str, object]]:
    cache = _cache_path(cache_root, job)
    manifest_path = cache / "manifest.json"
    if not manifest_path.is_file():
        return None, "missing_cache", {"cache": str(cache)}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None, "invalid_manifest", {"cache": str(cache)}
    if not isinstance(manifest, Mapping):
        return None, "invalid_manifest", {"cache": str(cache)}
    if manifest.get("schema_version") != _CACHE_SCHEMA_VERSION:
        return None, "invalid_manifest", {"cache": str(cache)}
    if (
        manifest.get("source_file") != job.source_file
        or manifest.get("source_sha256") != job.source_sha256
    ):
        return None, "source_mismatch", {"cache": str(cache)}
    page_count = manifest.get("page_count")
    if not isinstance(page_count, int) or page_count < 1:
        return None, "invalid_manifest", {"cache": str(cache)}
    expected = {f"page-{page:04d}.json" for page in range(1, page_count + 1)}
    actual = {
        path.name
        for path in cache.glob("page-*.json")
        if path.is_file()
    }
    if actual != expected:
        return None, "incomplete_cache", {
            "cache": str(cache),
            "missing_pages": len(expected - actual),
            "unexpected_pages": len(actual - expected),
        }
    pages: list[tuple[int, str]] = []
    for page_number in range(1, page_count + 1):
        payload = _read_page_payload(cache / f"page-{page_number:04d}.json")
        if payload is None:
            return None, "invalid_page", {
                "cache": str(cache),
                "page": page_number,
            }
        markdown = payload["data"]["documents"][0]["markdown"]
        if not isinstance(markdown, str):
            return None, "invalid_page", {
                "cache": str(cache),
                "page": page_number,
            }
        pages.append((page_number, markdown))
    recognition = manifest.get("recognition")
    return tuple(pages), "complete", {
        "cache": str(cache),
        "page_count": page_count,
        "recognition": dict(recognition) if isinstance(recognition, Mapping) else None,
    }


def _ad219_page_text(
    pages: Iterable[tuple[int, str]],
) -> tuple[tuple[int, str], ...]:
    """Return only OCR text delimited by AD 2.19 and AD 2.20 headings."""
    active = False
    result: list[tuple[int, str]] = []
    for page_number, markdown in pages:
        start = _AD219_START.search(markdown)
        if not active and start is None:
            continue
        if start is not None:
            active = True
            text = markdown[start.end():]
        else:
            text = markdown
        if not active:
            continue
        end = _AD219_END.search(text)
        if end is not None:
            # OCR commonly prefixes the next heading with the airport ICAO
            # (for example ``ZBCZAD2.20``).  Remove the whole heading line,
            # not only the ``AD2.20`` suffix.
            text = text[:text.rfind("\n", 0, end.start()) + 1]
            active = False
        if text.strip():
            result.append((page_number, text))
    return tuple(result)


def _distance_nm(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    latitude_delta = math.radians(latitude_b - latitude_a)
    longitude_delta = math.radians(longitude_b - longitude_a)
    latitude_a_radians = math.radians(latitude_a)
    latitude_b_radians = math.radians(latitude_b)
    sin_latitude = math.sin(latitude_delta / 2)
    sin_longitude = math.sin(longitude_delta / 2)
    value = (
        sin_latitude * sin_latitude
        + math.cos(latitude_a_radians)
        * math.cos(latitude_b_radians)
        * sin_longitude
        * sin_longitude
    )
    return 3440.065 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _direct_ndb_missing_fields(root: Path) -> dict[int, tuple[str, ...]]:
    """Return only raw CSV completeness facts, never values from a reference."""
    path = root / "NDB.csv"
    if not path.is_file():
        raise Ad219NdbOcrError(f"找不到直接 424 NDB 表: {path}")
    result: dict[int, tuple[str, ...]] = {}
    for row_number, row in enumerate(_csv_rows(path), start=2):
        missing: list[str] = []
        if not (row.get("TXT_NAME") or "").strip():
            missing.append("name")
        if not (row.get("VAL_MAG_VAR") or "").strip():
            missing.append("magnetic_variation")
        if not (row.get("VAL_ELEV") or "").strip():
            missing.append("elevation_ft")
        if not (
            (row.get("SERVICED_AIRPORT") or "").strip()
            or (row.get("CODE_FIR") or "").strip()
        ):
            missing.append("country")
        result[row_number] = tuple(missing)
    return result


def _record_identity(item: Ad219NdbEvidence) -> tuple[object, ...]:
    return (
        item.airport,
        item.ident,
        item.frequency_khz,
        item.latitude,
        item.longitude,
        item.source.file,
        item.source.page,
    )


def _evidence_report_item(
    item: Ad219NdbEvidence,
    *,
    status: str,
    direct_record: Navaid | None,
    remaining_target_gaps: tuple[str, ...],
) -> dict[str, object]:
    return {
        "airport": item.airport,
        "ident": item.ident,
        "source_file": item.source.file,
        "source_sha256": item.source.sha256,
        "page": item.source.page,
        "reconciliation": status,
        "direct_424_source": (
            {
                "file": direct_record.source.file,
                "row": direct_record.source.row,
            }
            if direct_record is not None
            else None
        ),
        "printed_evidence_missing_target_fields": list(_EVIDENCE_TARGET_GAPS),
        "remaining_target_gaps": list(remaining_target_gaps),
    }


def audit_ad219_ndb_ocr(
    root: Path,
    cache_root: Path,
    *,
    airports: Iterable[str] = (),
    coordinate_tolerance_nm: float = 0.02,
) -> dict[str, object]:
    """Audit cached AD 2.19 NDB facts against direct current-cycle NDB.csv."""
    root = root.expanduser().resolve()
    cache_root = cache_root.expanduser().resolve()
    if coordinate_tolerance_nm <= 0:
        raise Ad219NdbOcrError("AD 2.19 NDB 坐标匹配阈值必须为正数")
    if cache_root == root or root in cache_root.parents:
        raise Ad219NdbOcrError("AD 2.19 NDB OCR 缓存不得位于 424 原始数据目录内")

    jobs = collect_ad219_ndb_ocr_jobs(root, airports=airports)
    model = load_naip(root, include_terminal_documents=False)
    direct_ndbs = tuple(
        item for item in model.navaids if item.kind.upper() == "NDB"
    )
    missing_fields_by_row = _direct_ndb_missing_fields(root)

    cache_states: Counter[str] = Counter()
    detected_sections = 0
    records: list[dict[str, object]] = []
    reconciliations: Counter[str] = Counter()
    seen: set[tuple[object, ...]] = set()
    for job in jobs:
        pages, cache_state, _cache_detail = _read_complete_cache(cache_root, job)
        cache_states[cache_state] += 1
        if pages is None:
            continue
        ad219_pages = _ad219_page_text(pages)
        if ad219_pages:
            detected_sections += 1
        for page_number, text in ad219_pages:
            source = SourceRef(
                job.source_file,
                page=page_number,
                sha256=job.source_sha256,
            )
            for evidence in extract_ad219_ndbs(text, job.airport, source):
                identity = _record_identity(evidence)
                if identity in seen:
                    continue
                seen.add(identity)
                same_identity = [
                    item
                    for item in direct_ndbs
                    if item.ident.upper() == evidence.ident.upper()
                    and abs(item.frequency - evidence.frequency_khz) <= 0.001
                    and _distance_nm(
                        item.latitude,
                        item.longitude,
                        evidence.latitude,
                        evidence.longitude,
                    ) <= coordinate_tolerance_nm
                ]
                same_physical = [
                    item
                    for item in direct_ndbs
                    if abs(item.frequency - evidence.frequency_khz) <= 0.001
                    and _distance_nm(
                        item.latitude,
                        item.longitude,
                        evidence.latitude,
                        evidence.longitude,
                    ) <= coordinate_tolerance_nm
                ]
                same_ident = [
                    item
                    for item in direct_ndbs
                    if item.ident.upper() == evidence.ident.upper()
                ]
                direct_record: Navaid | None = None
                if len(same_identity) == 1:
                    direct_record = same_identity[0]
                    remaining = missing_fields_by_row.get(
                        direct_record.source.row or -1,
                        _EVIDENCE_TARGET_GAPS,
                    )
                    status = (
                        "matched_complete_direct_424"
                        if not remaining
                        else "matched_direct_424_with_target_gaps"
                    )
                elif len(same_identity) > 1 or len(same_physical) > 1:
                    status = "direct_424_ambiguous"
                    remaining = _EVIDENCE_TARGET_GAPS
                elif len(same_physical) == 1:
                    direct_record = same_physical[0]
                    remaining = missing_fields_by_row.get(
                        direct_record.source.row or -1,
                        _EVIDENCE_TARGET_GAPS,
                    )
                    status = "physical_match_identifier_difference"
                elif same_ident:
                    status = "direct_424_identity_conflict"
                    remaining = _EVIDENCE_TARGET_GAPS
                else:
                    status = "direct_424_missing"
                    remaining = _EVIDENCE_TARGET_GAPS
                reconciliations[status] += 1
                records.append(_evidence_report_item(
                    evidence,
                    status=status,
                    direct_record=direct_record,
                    remaining_target_gaps=remaining,
                ))

    records.sort(key=lambda item: (
        str(item["airport"]),
        str(item["source_file"]),
        int(item["page"] or 0),
        str(item["ident"]),
        str(item["reconciliation"]),
    ))
    incomplete_target_contract = sum(
        bool(item["remaining_target_gaps"])
        for item in records
    )
    return {
        "diagnostic": "ad219-ndb-ocr-audit-v1",
        "evidence_only": True,
        "projection_allowed": False,
        "source_root": str(root),
        "cache_root": str(cache_root),
        "coordinate_tolerance_nm": coordinate_tolerance_nm,
        "reason": (
            "AD 2.19 OCR 仅用于来源审计；没有直接 424 完整目标字段的记录不得投影"
        ),
        "summary": {
            "candidate_pdfs": len(jobs),
            "cache_state_counts": dict(sorted(cache_states.items())),
            "documents_with_ad219_section": detected_sections,
            "parsed_ndb_records": len(records),
            "reconciliation_counts": dict(sorted(reconciliations.items())),
            "records_with_remaining_target_gaps": incomplete_target_contract,
        },
        "records": records,
    }


def write_ad219_ndb_ocr_audit(output: Path, report: Mapping[str, object]) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
