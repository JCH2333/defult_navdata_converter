from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .iap_coverage import iap_section_kind, procedure_kind
from .model import NavModel, SourceRef
from .pdf_charts import approach_procedure_name_candidates


class IapPrimarySourceAuditError(RuntimeError):
    """IAP 主进近直接来源审计无法安全建立时抛出。"""


_SOURCE_SECTION_KINDS = {
    "approach",
    "approach_transition",
    "missed",
}
_SINGLE_LETTER_VARIANT_LABEL = re.compile(
    r"^(?P<base>[A-Z]\d{2}[LRC]?)-[WXYZ]$",
    re.IGNORECASE,
)


def _source_payload(source: SourceRef) -> dict[str, object]:
    return {
        "file": source.file,
        "row": source.row,
        "page": source.page,
        "sha256": source.sha256,
    }


def _load_cache(path: Path) -> tuple[list[Mapping[str, object]], dict[str, object]]:
    source = path.expanduser().resolve()
    try:
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IapPrimarySourceAuditError(f"无法读取 PDF 直接证据缓存: {source}") from error
    if not isinstance(payload, Mapping):
        raise IapPrimarySourceAuditError("PDF 直接证据缓存根节点必须是对象")
    charts = payload.get("charts")
    if not isinstance(charts, list):
        raise IapPrimarySourceAuditError("PDF 直接证据缓存缺少 charts 列表")
    valid_charts: list[Mapping[str, object]] = []
    for chart in charts:
        if not isinstance(chart, Mapping):
            raise IapPrimarySourceAuditError("PDF 直接证据缓存包含无效图页")
        valid_charts.append(chart)
    return valid_charts, {
        "path": str(source),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "chart_count": len(valid_charts),
    }


def _same_source(chart: Mapping[str, object], source: SourceRef) -> bool:
    chart_source = chart.get("source")
    if not isinstance(chart_source, Mapping):
        return False
    return (
        chart_source.get("file") == source.file
        and chart_source.get("page") == source.page
        and chart_source.get("sha256") == source.sha256
    )


def _cache_section_kind(leg: Mapping[str, object]) -> str:
    raw_kind = leg.get("procedure_kind")
    if not isinstance(raw_kind, str):
        return ""
    kind = procedure_kind(raw_kind)
    if kind == "approach" and leg.get("transition"):
        return "approach_transition"
    return kind


def _model_section_summary(
    model: NavModel,
    airport: str,
    label: str,
    runway: str,
) -> tuple[dict[str, int], dict[str, list[dict[str, object]]]]:
    sections: Counter[str] = Counter()
    legs: dict[str, list[dict[str, object]]] = {
        kind: [] for kind in sorted(_SOURCE_SECTION_KINDS)
    }
    for segment in model.procedure_segments:
        if (segment.airport, segment.label, segment.runway) != (airport, label, runway):
            continue
        kind = iap_section_kind(segment)
        if kind not in _SOURCE_SECTION_KINDS:
            continue
        sections[kind] += 1
        legs[kind].extend(
            {
                "type": leg.leg_type,
                "ident": leg.fix_ident,
            }
            for leg in segment.legs
        )
    return (
        {kind: sections[kind] for kind in sorted(_SOURCE_SECTION_KINDS)},
        legs,
    )


def _related_label_set(label: str) -> tuple[str, set[str]]:
    match = _SINGLE_LETTER_VARIANT_LABEL.fullmatch(label)
    base_label = match["base"].upper() if match else label.upper()
    return base_label, {
        base_label,
        *(f"{base_label}-{suffix}" for suffix in "WXYZ"),
    }


def _related_model_section_summary(
    model: NavModel,
    airport: str,
    label: str,
    runway: str,
) -> dict[str, int]:
    """Count all source-model sections in one strict base/variant family."""

    _, related_labels = _related_label_set(label)
    sections: Counter[str] = Counter()
    for segment in model.procedure_segments:
        kind = iap_section_kind(segment)
        if (
            segment.airport != airport
            or segment.runway != runway
            or segment.label.upper() not in related_labels
            or kind not in _SOURCE_SECTION_KINDS
        ):
            continue
        sections[kind] += 1
    return {kind: sections[kind] for kind in sorted(_SOURCE_SECTION_KINDS)}


def _same_page_related_section_summary(
    page_labels: Iterable[Mapping[str, object]],
    label: str,
    runway: str,
) -> dict[str, object] | None:
    """Summarize an unsuffixed IAP identity and its single-letter variants.

    This is intentionally stricter than the BGL inheritance rule: it only
    proves that a directly cached database page has no primary anywhere in a
    related base/variant family. It never assigns those sections to a target.
    """

    base_label, related_labels = _related_label_set(label)
    sections: Counter[str] = Counter()
    members: list[dict[str, object]] = []
    for item in page_labels:
        page_label = item.get("label")
        page_runway = item.get("runway")
        page_sections = item.get("sections")
        if (
            not isinstance(page_label, str)
            or not isinstance(page_runway, str)
            or not isinstance(page_sections, Mapping)
            or page_runway != runway
            or page_label.upper() not in related_labels
        ):
            continue
        member_sections: dict[str, int] = {}
        for kind in sorted(_SOURCE_SECTION_KINDS):
            value = page_sections.get(kind)
            if not isinstance(value, int):
                raise IapPrimarySourceAuditError("数据库编码图页分段计数无效")
            sections[kind] += value
            member_sections[kind] = value
        members.append({
            "label": page_label,
            "runway": page_runway,
            "sections": member_sections,
        })
    if len(members) < 2:
        return None
    return {
        "base_label": base_label,
        "members": sorted(members, key=lambda item: str(item["label"])),
        "sections": {
            kind: sections[kind] for kind in sorted(_SOURCE_SECTION_KINDS)
        },
    }


def _instrument_chart_title_candidates(
    model: NavModel,
    airport: str,
    label: str,
    runway: str,
) -> list[dict[str, object]]:
    """Report title-supported chart candidates without assigning a primary.

    A chart title may contain the same database label while the corresponding
    database coding page still has no primary section.  This is diagnostic
    evidence only: it must never turn a title or an IAF/IF overlap into legs.
    """

    result: list[dict[str, object]] = []
    for chart in model.procedure_charts:
        if (
            chart.airport != airport
            or chart.chart_type != "instrument-approach-index"
            or runway not in chart.runways
        ):
            continue
        title_candidates = approach_procedure_name_candidates(
            chart.chart_name,
            chart.runways,
            chart.airport,
        )
        result.append({
            "filename": chart.filename,
            "chart_name": chart.chart_name,
            "source": _source_payload(chart.source),
            "title_label_candidates": list(title_candidates),
            "direct_label_match": label in title_candidates,
        })
    return sorted(
        result,
        key=lambda item: (
            not bool(item["direct_label_match"]),
            str(item["filename"]),
        ),
    )


def _cache_section_summary(
    charts: Iterable[Mapping[str, object]],
    airport: str,
    label: str,
    runway: str,
    source: SourceRef,
) -> tuple[
    dict[str, int],
    dict[str, list[dict[str, object]]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    sections: Counter[str] = Counter()
    legs: dict[str, list[dict[str, object]]] = {
        kind: [] for kind in sorted(_SOURCE_SECTION_KINDS)
    }
    evidence_pages: list[dict[str, object]] = []
    same_page_labels: dict[tuple[str, str], Counter[str]] = {}
    for chart in charts:
        if (
            chart.get("airport") != airport
            or chart.get("chart_type") != "terminal-database-coding"
            or not _same_source(chart, source)
        ):
            continue
        terminal_legs = chart.get("terminal_legs")
        if not isinstance(terminal_legs, list):
            raise IapPrimarySourceAuditError("数据库编码图页缺少 terminal_legs 列表")
        selected_legs: list[Mapping[str, object]] = []
        for leg in terminal_legs:
            if not isinstance(leg, Mapping):
                raise IapPrimarySourceAuditError("数据库编码图页包含无效航段")
            kind = _cache_section_kind(leg)
            if kind not in _SOURCE_SECTION_KINDS:
                continue
            leg_label = leg.get("procedure_label")
            leg_runway = leg.get("runway")
            if not isinstance(leg_label, str) or not isinstance(leg_runway, str):
                raise IapPrimarySourceAuditError("数据库编码图页 IAP 航段缺少标签或跑道")
            same_page_labels.setdefault((leg_label, leg_runway), Counter())[kind] += 1
            if leg_label != label or leg_runway != runway:
                continue
            sections[kind] += 1
            selected_legs.append(leg)
            legs[kind].append({
                "type": leg.get("leg_type"),
                "ident": leg.get("fix_ident"),
            })
        evidence_pages.append({
            "chart_name": chart.get("chart_name"),
            "chart_type": chart.get("chart_type"),
            "filename": chart.get("filename"),
            "source": chart.get("source"),
            "matching_leg_count": len(selected_legs),
        })
    page_label_summaries = [
        {
            "label": page_label,
            "runway": page_runway,
            "sections": {
                kind: counts[kind] for kind in sorted(_SOURCE_SECTION_KINDS)
            },
        }
        for (page_label, page_runway), counts in sorted(same_page_labels.items())
    ]
    return (
        {kind: sections[kind] for kind in sorted(_SOURCE_SECTION_KINDS)},
        legs,
        evidence_pages,
        page_label_summaries,
    )


def audit_iap_primary_sources(
    model: NavModel,
    evidence_caches: Iterable[Path],
) -> dict[str, object]:
    """Audit unresolved IAP groups using only exact-source database-chart caches.

    This audit never changes the model or BGL projection.  A cache can only
    justify an explicit rejection when its terminal-database chart is tied to
    the exact PDF page and SHA-256 already referenced by the rejected group.
    """

    unresolved = model.iap_coverage.get("unresolved_groups")
    if not isinstance(unresolved, list):
        raise IapPrimarySourceAuditError("NavModel 缺少 IAP 未决分组审计")
    rejected = {
        (item.airport, item.chart): item
        for item in model.rejected_procedures
    }
    charts: list[Mapping[str, object]] = []
    cache_inputs: list[dict[str, object]] = []
    for cache in evidence_caches:
        loaded, manifest = _load_cache(Path(cache))
        charts.extend(loaded)
        cache_inputs.append(manifest)
    if not cache_inputs:
        raise IapPrimarySourceAuditError("至少需要一个 PDF 直接证据缓存")

    items: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    for group in sorted(
        unresolved,
        key=lambda item: (
            str(item.get("airport") or ""),
            str(item.get("label") or ""),
            str(item.get("runway") or ""),
        ),
    ):
        if not isinstance(group, Mapping):
            raise IapPrimarySourceAuditError("IAP 未决分组格式无效")
        airport = group.get("airport")
        label = group.get("label")
        runway = group.get("runway")
        if not all(isinstance(value, str) for value in (airport, label, runway)):
            raise IapPrimarySourceAuditError("IAP 未决分组缺少身份字段")
        rejected_item = rejected.get((airport, label))
        if rejected_item is None:
            raise IapPrimarySourceAuditError("IAP 未决分组未同步到 RejectedProcedure")
        model_sections, model_legs = _model_section_summary(
            model, airport, label, runway,
        )
        (
            cache_sections,
            cache_legs,
            evidence_pages,
            same_page_labels,
        ) = _cache_section_summary(charts, airport, label, runway, rejected_item.source)
        related_same_page_sections = _same_page_related_section_summary(
            same_page_labels,
            label,
            runway,
        )
        related_model_sections = _related_model_section_summary(
            model,
            airport,
            label,
            runway,
        )
        instrument_chart_candidates = _instrument_chart_title_candidates(
            model,
            airport,
            label,
            runway,
        )
        if not evidence_pages:
            disposition = "not_evaluated_no_matching_direct_database_chart"
        elif (
            model_sections["approach"] == 0
            and model_sections["approach_transition"] > 0
            and model_sections["missed"] > 0
            and cache_sections["approach"] == 0
            and cache_sections["approach_transition"] > 0
            and cache_sections["missed"] > 0
        ):
            disposition = "rejected_transition_and_missed_without_primary"
        elif (
            related_same_page_sections is not None
            and related_model_sections["approach"] == 0
            and related_same_page_sections["sections"]["approach"] == 0
            and related_same_page_sections["sections"]["approach_transition"] > 0
            and related_same_page_sections["sections"]["missed"] > 0
        ):
            disposition = "rejected_related_same_page_sections_without_primary"
        else:
            disposition = "unresolved_direct_database_evidence_inconclusive"
        status_counts[disposition] += 1
        items.append({
            "key": f"{airport}:{label}",
            "airport": airport,
            "label": label,
            "runway": runway,
            "source": _source_payload(rejected_item.source),
            "iap_coverage_status": group.get("status"),
            "disposition": disposition,
            "model_sections": model_sections,
            "model_legs": model_legs,
            "related_model_sections": related_model_sections,
            "direct_database_sections": cache_sections,
            "direct_database_legs": cache_legs,
            "evidence_pages": evidence_pages,
            "same_page_iap_labels": same_page_labels,
            "related_same_page_sections": related_same_page_sections,
            "instrument_chart_title_candidates": instrument_chart_candidates,
            "projection_allowed": False,
        })
    return {
        "diagnostic": "iap-primary-source-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "model_mutated": False,
        "projection_changed": False,
        "source": {
            "model_root": str(model.root),
            "pdf_evidence_caches": cache_inputs,
        },
        "summary": {
            "unresolved_group_total": len(items),
            "by_disposition": dict(sorted(status_counts.items())),
        },
        "items": items,
    }


def write_iap_primary_source_audit(
    path: Path,
    report: Mapping[str, object],
) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
