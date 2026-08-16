"""Audit source-hashed IAP OCR evidence without changing chart selection."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from .iap_coverage import matching_iap_charts
from .iap_ocr import (
    IAP_OCR_ELIGIBLE_STATUSES,
    _primary_iap_segments,
    _source_pdf,
    _source_sha256,
)
from .iap_ocr_roles import extract_iap_ocr_role_evidence
from .ocr_cache import _read_page_payload
from .source import load_naip


class IapOcrAuditError(ValueError):
    """Raised when an IAP OCR evidence audit cannot be verified."""


def _cache_path(cache_root: Path, source_file: str, source_sha256: str) -> Path:
    return cache_root / Path(source_file).with_suffix("") / source_sha256[:16]


def _recognition_settings(
    manifest: Mapping[str, object],
) -> dict[str, object] | None:
    recognition = manifest.get("recognition")
    if not isinstance(recognition, Mapping):
        return None
    values: dict[str, str] = {}
    for field in (
        "command",
        "backend",
        "mode",
        "image_profile",
        "runtime_profile",
        "adapter",
    ):
        value = recognition.get(field)
        if not isinstance(value, str) or not value.strip():
            return None
        values[field] = value.strip()
    max_tokens = recognition.get("max_tokens")
    if (
        not isinstance(max_tokens, int)
        or isinstance(max_tokens, bool)
        or max_tokens < 1
    ):
        return None
    render_scale = manifest.get("render_scale")
    if (
        not isinstance(render_scale, (int, float))
        or isinstance(render_scale, bool)
        or render_scale <= 0
    ):
        return None
    return {
        **values,
        "max_tokens": max_tokens,
        "render_scale": float(render_scale),
    }


def _read_cached_pages(
    cache: Path,
    *,
    source_file: str,
    source_sha256: str,
) -> tuple[
    tuple[tuple[int, str], ...] | None,
    str,
    str | None,
    dict[str, object] | None,
]:
    manifest_path = cache / "manifest.json"
    if not manifest_path.is_file():
        return None, "missing_cache", None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None, "invalid_manifest", None, None
    if not isinstance(manifest, dict):
        return None, "invalid_manifest", None, None
    if (
        manifest.get("source_file") != source_file
        or manifest.get("source_sha256") != source_sha256
    ):
        return None, "source_mismatch", None, None
    page_count = manifest.get("page_count")
    if not isinstance(page_count, int) or page_count < 1:
        return None, "invalid_manifest", None, None
    recognition = manifest.get("recognition")
    runtime_profile = (
        recognition.get("runtime_profile").strip()
        if isinstance(recognition, Mapping)
        and isinstance(recognition.get("runtime_profile"), str)
        and recognition["runtime_profile"].strip()
        else None
    )
    settings = _recognition_settings(manifest)

    pages: list[tuple[int, str]] = []
    for page_number in range(1, page_count + 1):
        payload = _read_page_payload(cache / f"page-{page_number:04d}.json")
        if payload is None:
            return None, "incomplete_cache", runtime_profile, settings
        markdown = payload["data"]["documents"][0]["markdown"]
        if not isinstance(markdown, str):
            return None, "invalid_page", runtime_profile, settings
        pages.append((page_number, markdown))
    return tuple(pages), "complete", runtime_profile, settings


def _matching_identifiers(markdown: str, idents: set[str]) -> tuple[str, ...]:
    upper = markdown.upper()
    return tuple(
        sorted(
            ident
            for ident in idents
            if re.search(rf"(?<![A-Z0-9]){re.escape(ident)}(?![A-Z0-9])", upper)
        )
    )


def audit_iap_ocr_cache(
    root: Path,
    cache_root: Path,
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> dict[str, object]:
    """Report OCR identifier evidence while permanently keeping it non-projectable."""
    root = root.expanduser().resolve()
    cache_root = cache_root.expanduser().resolve()
    if not root.is_dir():
        raise IapOcrAuditError(f"找不到原始数据目录: {root}")
    if not cache_root.is_dir():
        raise IapOcrAuditError(f"找不到 IAP OCR 缓存目录: {cache_root}")
    if cache_root == root or root in cache_root.parents:
        raise IapOcrAuditError("IAP OCR 缓存不得位于 424 原始数据目录内")

    requested_statuses = tuple(dict.fromkeys(statuses))
    unsupported = sorted(set(requested_statuses) - set(IAP_OCR_ELIGIBLE_STATUSES))
    if not requested_statuses or unsupported:
        detail = ", ".join(unsupported) if unsupported else "空集合"
        raise IapOcrAuditError(f"不支持的 IAP OCR 状态筛选: {detail}")

    model = load_naip(root, pdf_cache=pdf_cache, include_terminal_documents=True)
    coverage = model.iap_coverage
    unresolved = coverage.get("unresolved_groups") if isinstance(coverage, Mapping) else None
    if not isinstance(unresolved, list):
        raise IapOcrAuditError("IAP 覆盖报告缺少未决分组")

    primary_by_group = _primary_iap_segments(model)
    charts_by_airport_runway: dict[tuple[str, str], list[object]] = defaultdict(list)
    for chart in model.procedure_charts:
        if chart.chart_type == "instrument-approach-index":
            for runway in chart.runways:
                charts_by_airport_runway[(chart.airport, runway)].append(chart)

    groups: list[dict[str, object]] = []
    cache_states: Counter[str] = Counter()
    ocr_role_counts: Counter[str] = Counter()
    role_evidence_groups = 0
    role_evidence_candidates = 0
    for unresolved_group in unresolved:
        if not isinstance(unresolved_group, Mapping):
            continue
        status = unresolved_group.get("status")
        if status not in requested_statuses:
            continue
        airport = unresolved_group.get("airport")
        label = unresolved_group.get("label")
        runway = unresolved_group.get("runway")
        if not all(isinstance(value, str) and value for value in (airport, label, runway)):
            raise IapOcrAuditError("IAP 未决分组缺少机场、标签或跑道")
        segment = primary_by_group.get((airport, label, runway))
        if segment is None:
            raise IapOcrAuditError(f"IAP 未决分组没有可审计主进近段: {airport}/{label}")
        chart_candidates = (
            matching_iap_charts(model, segment)
            if status == "ambiguous_chart"
            else charts_by_airport_runway[(airport, runway)]
        )
        leg_idents = {
            leg.fix_ident.strip().upper()
            for leg in segment.legs
            if leg.fix_ident and leg.fix_ident.strip()
        }
        candidates: list[dict[str, object]] = []
        for chart in chart_candidates:
            source_pdf, source_file = _source_pdf(root, chart.source.file)
            source_sha256 = _source_sha256(source_pdf, chart.source.sha256)
            cache = _cache_path(cache_root, source_file, source_sha256)
            pages, cache_state, runtime_profile, recognition_settings = _read_cached_pages(
                cache,
                source_file=source_file,
                source_sha256=source_sha256,
            )
            cache_states[cache_state] += 1
            markdown = "\n".join(markdown for _, markdown in pages) if pages is not None else None
            candidates.append({
                "source_file": source_file,
                "source_sha256": source_sha256,
                "cache": str(cache),
                "cache_state": cache_state,
                "ocr_runtime_profile": runtime_profile,
                "ocr_recognition_settings": recognition_settings,
                "ocr_identifier_matches": list(
                    _matching_identifiers(markdown, leg_idents)
                    if markdown is not None
                    else ()
                ),
                "ocr_role_matches": [
                    evidence.to_report()
                    for evidence in extract_iap_ocr_role_evidence(pages, leg_idents)
                ] if pages is not None else [],
            })

        counts = [
            len(item["ocr_identifier_matches"])
            for item in candidates
            if item["cache_state"] == "complete"
        ]
        maximum = max(counts, default=0)
        winners = [
            item
            for item in candidates
            if item["cache_state"] == "complete"
            and len(item["ocr_identifier_matches"]) == maximum
        ]
        if any(item["cache_state"] != "complete" for item in candidates):
            evidence_status = "incomplete_ocr_cache"
        elif maximum >= 2 and len(winners) == 1:
            evidence_status = "unique_identifier_only"
        else:
            evidence_status = "not_discriminating"
        role_matches = [
            match
            for candidate in candidates
            for match in candidate["ocr_role_matches"]
        ]
        if role_matches:
            role_evidence_groups += 1
            role_evidence_candidates += sum(
                bool(candidate["ocr_role_matches"])
                for candidate in candidates
            )
            ocr_role_counts.update(str(match["role"]) for match in role_matches)
        groups.append({
            "airport": airport,
            "label": label,
            "runway": runway,
            "source_status": status,
            "primary_leg_idents": sorted(leg_idents),
            "evidence_status": evidence_status,
            "candidates": candidates,
        })

    evidence_statuses = Counter(
        str(group["evidence_status"])
        for group in groups
    )
    return {
        "diagnostic": "iap-ocr-evidence-audit-v2",
        "evidence_only": True,
        "projection_allowed": False,
        "source_root": str(root),
        "cache_root": str(cache_root),
        "statuses": list(requested_statuses),
        "summary": {
            "groups": len(groups),
            "evidence_status_counts": dict(sorted(evidence_statuses.items())),
            "cache_state_counts": dict(sorted(cache_states.items())),
        },
        "ocr_role_evidence": {
            "matches": sum(ocr_role_counts.values()),
            "groups_with_matches": role_evidence_groups,
            "candidates_with_matches": role_evidence_candidates,
            "role_counts": dict(sorted(ocr_role_counts.items())),
        },
        "groups": groups,
    }


def write_iap_ocr_audit(output: Path, report: dict[str, object]) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
