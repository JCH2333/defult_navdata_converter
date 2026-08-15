"""Build local OCR evidence caches for IAP groups blocked on chart matching."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .iap_coverage import iap_section_kind, matching_iap_charts
from .model import NavModel
from .ocr_cache import OcrCacheError, build_ocr_cache
from .source import load_naip


IAP_OCR_ELIGIBLE_STATUSES = ("ambiguous_chart", "no_matching_chart")


class IapOcrError(ValueError):
    """Raised when a source-backed IAP OCR cache cannot be planned."""


@dataclass(frozen=True)
class IapOcrJob:
    """One source chart PDF needed to investigate unresolved IAP matching."""

    source_pdf: Path
    source_file: str
    source_sha256: str
    statuses: tuple[str, ...]
    groups: tuple[tuple[str, str, str], ...]

    def to_report(self) -> dict[str, object]:
        return {
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "statuses": list(self.statuses),
            "groups": [
                {"airport": airport, "label": label, "runway": runway}
                for airport, label, runway in self.groups
            ],
        }


def _source_pdf(root: Path, value: str) -> tuple[Path, str]:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.expanduser().resolve()
    try:
        return path, path.relative_to(root).as_posix()
    except ValueError as error:
        raise IapOcrError("IAP 图页来源不位于 424 原始数据目录内") from error


def _source_sha256(path: Path, declared: object) -> str:
    if isinstance(declared, str) and declared:
        return declared.lower()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _primary_iap_segments(model: NavModel) -> dict[tuple[str, str, str], object]:
    groups: dict[tuple[str, str, str], list[object]] = defaultdict(list)
    for segment in model.procedure_segments:
        if iap_section_kind(segment) == "approach":
            groups[(segment.airport, segment.label, segment.runway)].append(segment)
    return {
        key: segments[0]
        for key, segments in groups.items()
        if len(segments) == 1 and bool(segments[0].legs)
    }


def collect_iap_ocr_jobs(
    root: Path,
    model: NavModel,
    *,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> tuple[IapOcrJob, ...]:
    """Select only source PDFs that may resolve chart-selection evidence."""
    requested = tuple(dict.fromkeys(statuses))
    unsupported = sorted(set(requested) - set(IAP_OCR_ELIGIBLE_STATUSES))
    if not requested or unsupported:
        detail = ", ".join(unsupported) if unsupported else "空集合"
        raise IapOcrError(f"不支持的 IAP OCR 状态筛选: {detail}")

    coverage = model.iap_coverage
    unresolved = coverage.get("unresolved_groups") if isinstance(coverage, Mapping) else None
    if not isinstance(unresolved, list):
        raise IapOcrError("IAP 覆盖报告缺少未决分组")

    primary_by_group = _primary_iap_segments(model)
    charts_by_airport_runway: dict[tuple[str, str], list[object]] = defaultdict(list)
    for chart in model.procedure_charts:
        if chart.chart_type != "instrument-approach-index":
            continue
        for runway in chart.runways:
            charts_by_airport_runway[(chart.airport, runway)].append(chart)

    selected: dict[tuple[str, str], dict[str, object]] = {}
    for item in unresolved:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "")
        if status not in requested:
            continue
        group = (
            str(item.get("airport") or ""),
            str(item.get("label") or ""),
            str(item.get("runway") or ""),
        )
        segment = primary_by_group.get(group)
        if segment is None:
            continue
        charts = (
            matching_iap_charts(model, segment)
            if status == "ambiguous_chart"
            else charts_by_airport_runway[(group[0], group[2])]
        )
        for chart in charts:
            source_pdf, source_file = _source_pdf(root, chart.source.file)
            if not source_pdf.is_file():
                raise IapOcrError(f"找不到 IAP 图页来源: {source_file}")
            source_sha256 = _source_sha256(source_pdf, chart.source.sha256)
            key = (source_file, source_sha256)
            entry = selected.setdefault(
                key,
                {
                    "source_pdf": source_pdf,
                    "statuses": set(),
                    "groups": set(),
                },
            )
            entry["statuses"].add(status)
            entry["groups"].add(group)

    return tuple(
        IapOcrJob(
            source_pdf=entry["source_pdf"],
            source_file=source_file,
            source_sha256=source_sha256,
            statuses=tuple(sorted(entry["statuses"])),
            groups=tuple(sorted(entry["groups"])),
        )
        for (source_file, source_sha256), entry in sorted(selected.items())
    )


def _cache_path(cache_root: Path, job: IapOcrJob) -> Path:
    relative = Path(job.source_file).with_suffix("")
    return cache_root / relative / job.source_sha256[:16]


def build_iap_ocr_cache(
    root: Path,
    cache_root: Path,
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
    command: str = "ocr-skill",
    backend: str = "llamacpp",
    mode: str = "markdown",
    timeout_seconds: int = 240,
    render_scale: float = 3.0,
    image_profile: str = "original",
    force: bool = False,
    limit: int | None = None,
    retries: int = 2,
    dry_run: bool = False,
) -> dict[str, object]:
    """Build source-hashed OCR caches for the IAP chart-evidence gap only."""
    root = root.expanduser().resolve()
    cache_root = cache_root.expanduser().resolve()
    if not root.is_dir():
        raise IapOcrError(f"找不到原始数据目录: {root}")
    if cache_root == root or root in cache_root.parents:
        raise IapOcrError("IAP OCR 缓存不得写入 424 原始数据目录")
    if limit is not None and limit < 1:
        raise IapOcrError("IAP OCR 任务数量上限必须为正整数")

    requested_statuses = tuple(dict.fromkeys(statuses))
    model = load_naip(root, pdf_cache=pdf_cache, include_terminal_documents=True)
    jobs = collect_iap_ocr_jobs(root, model, statuses=requested_statuses)
    if limit is not None:
        jobs = jobs[:limit]
    report: dict[str, object] = {
        "diagnostic": "iap-ocr-cache-v1",
        "evidence_only": True,
        "source_root": str(root),
        "cache_root": str(cache_root),
        "statuses": list(requested_statuses),
        "jobs": [job.to_report() for job in jobs],
        "planned_pdfs": len(jobs),
        "reason": (
            "OCR only collects raw chart evidence for later parser work; it does "
            "not resolve IAP groups or modify candidate projection"
        ),
    }
    if dry_run:
        report["dry_run"] = True
        return report

    results: list[dict[str, object]] = []
    for job in jobs:
        try:
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
                retries=retries,
            )
        except OcrCacheError as error:
            raise IapOcrError(f"IAP OCR 失败: {job.source_file}: {error}") from error
        results.append({**job.to_report(), **build.to_report()})
    report["dry_run"] = False
    report["results"] = results
    report["processed_pages"] = sum(
        int(item["processed_pages"]) for item in results
    )
    report["reused_pages"] = sum(int(item["reused_pages"]) for item in results)
    report["complete_pdfs"] = sum(bool(item["complete"]) for item in results)
    return report
