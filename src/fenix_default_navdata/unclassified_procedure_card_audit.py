from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymupdf

from .model import NavModel, ProcedureChart, ProcedureSegment, SourceRef
from .unclassified_procedure_audit import _label_family


_PROJECTED_KINDS = frozenset({"离场", "进场", "进近过渡", "进近", "复飞"})
_KIND_PATTERNS = (
    ("进近及复飞", ("进近", "复飞")),
    ("进近过渡", ("进近过渡",)),
    ("离场", ("离场",)),
    ("进场", ("进场",)),
    ("进近", ("进近",)),
    ("复飞", ("复飞",)),
)


class UnclassifiedProcedureCardAuditError(RuntimeError):
    """An exact unclassified-procedure card cannot be audited safely."""


def _source_payload(source: SourceRef) -> dict[str, object]:
    return {
        "file": source.file,
        "row": source.row,
        "page": source.page,
        "sha256": source.sha256,
    }


def _card_records(model: NavModel) -> list[tuple[str, ProcedureSegment]]:
    records = sorted(
        (
            segment
            for segment in model.procedure_segments
            if segment.kind not in _PROJECTED_KINDS
        ),
        key=lambda segment: (
            segment.airport,
            segment.label,
            segment.runway,
            segment.transition,
            segment.source.file,
            segment.source.page or 0,
        ),
    )
    return [
        (f"{segment.airport}:{segment.label}:{segment.runway}:{index}", segment)
        for index, segment in enumerate(records)
    ]


def _source_path(model: NavModel, source: SourceRef) -> Path:
    path = Path(source.file)
    return path if path.is_absolute() else model.root / path


def _read_source_page_text(path: Path, page: int) -> str:
    with pymupdf.open(path) as document:
        if page < 1 or page > document.page_count:
            raise UnclassifiedProcedureCardAuditError(
                f"来源页超出 PDF 范围: {path} page={page}"
            )
        return document[page - 1].get_text("text")


def _line_payload(line: str, start: int, end: int) -> dict[str, object]:
    return {"line": line, "start": start, "end": end}


def _label_matches(text: str, label: str) -> list[dict[str, object]]:
    normalized = (label or "").strip()
    if not normalized:
        return []
    pattern = re.compile(
        rf"(?<![A-Z0-9-]){re.escape(normalized)}(?![A-Z0-9-])",
        re.IGNORECASE,
    )
    matches: list[dict[str, object]] = []
    offset = 0
    for line in text.splitlines():
        for match in pattern.finditer(line):
            matches.append(_line_payload(line, offset + match.start(), offset + match.end()))
        offset += len(line) + 1
    return matches


def _heading_matches(text: str) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    offset = 0
    for line in text.splitlines():
        for phrase, kinds in _KIND_PATTERNS:
            if phrase in line:
                start = line.index(phrase)
                item = _line_payload(line, offset + start, offset + start + len(phrase))
                item["phrase"] = phrase
                item["kinds"] = list(kinds)
                matches.append(item)
                break
        offset += len(line) + 1
    return matches


def _direct_label_kind_links(
    label_matches: list[dict[str, object]],
    heading_matches: list[dict[str, object]],
) -> list[dict[str, object]]:
    headings_by_line: dict[str, list[str]] = {}
    for heading in heading_matches:
        line = heading["line"]
        kinds = heading["kinds"]
        if isinstance(line, str) and isinstance(kinds, list):
            headings_by_line.setdefault(line, []).extend(
                kind for kind in kinds if isinstance(kind, str)
            )
    links: list[dict[str, object]] = []
    for label_match in label_matches:
        line = label_match["line"]
        if not isinstance(line, str):
            continue
        kinds = sorted(set(headings_by_line.get(line, [])))
        if kinds:
            links.append({"line": line, "kinds": kinds})
    return links


def _matching_charts(model: NavModel, segment: ProcedureSegment) -> list[ProcedureChart]:
    return [
        chart
        for chart in model.procedure_charts
        if chart.airport.upper() == segment.airport.upper()
        and chart.chart_type == "terminal-database-coding"
        and chart.source.file == segment.source.file
        and chart.source.page == segment.source.page
    ]


def _chart_payload(chart: ProcedureChart) -> dict[str, object]:
    return {
        "filename": chart.filename,
        "page": chart.page,
        "chart_type": chart.chart_type,
        "chart_name": chart.chart_name,
        "procedure_labels": list(chart.procedure_labels),
        "runways": list(chart.runways),
        "source": _source_payload(chart.source),
    }


def audit_unclassified_procedure_card(
    model: NavModel,
    card_key: str,
) -> dict[str, object]:
    """Audit one exact card using direct source text without inferring order."""

    selected = {
        key: segment
        for key, segment in _card_records(model)
        if key == card_key
    }
    if len(selected) != 1:
        raise UnclassifiedProcedureCardAuditError(f"未找到精确未分类程序卡: {card_key}")
    segment = selected[card_key]
    source_path = _source_path(model, segment.source)
    if not source_path.is_file():
        raise UnclassifiedProcedureCardAuditError(f"来源 PDF 不存在: {source_path}")
    page = segment.source.page
    if page is None:
        raise UnclassifiedProcedureCardAuditError(f"来源程序卡缺少页码: {card_key}")

    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if segment.source.sha256 and source_sha256 != segment.source.sha256:
        raise UnclassifiedProcedureCardAuditError(
            f"来源 PDF SHA-256 不匹配: {source_path}"
        )
    text = _read_source_page_text(source_path, page)
    label_matches = _label_matches(text, segment.label)
    heading_matches = _heading_matches(text)
    direct_links = _direct_label_kind_links(label_matches, heading_matches)
    linked_kinds = sorted({
        kind
        for link in direct_links
        for kind in link["kinds"]
        if isinstance(kind, str)
    })
    source_proven_kind = (
        linked_kinds[0]
        if len(label_matches) == 1 and len(direct_links) == 1 and len(linked_kinds) == 1
        else None
    )
    if source_proven_kind is not None:
        disposition = "direct_label_kind_link_confirmed"
        reason = "标签与唯一程序类别标题在同一来源文本行直接关联"
    elif not label_matches:
        disposition = "rejected_missing_direct_label_anchor"
        reason = "标签未在同一来源 PDF 页面直接出现；邻近类别标题和顺序不能推断程序类别"
    else:
        disposition = "rejected_ambiguous_direct_label_kind_link"
        reason = "标签未与唯一程序类别标题形成同一文本行的直接关联"

    return {
        "diagnostic": "unclassified-procedure-card-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "model_changed": False,
        "projection_changed": False,
        "card_key": card_key,
        "segment": {
            "airport": segment.airport,
            "label": segment.label,
            "label_family": _label_family(segment.label),
            "runway": segment.runway,
            "transition": segment.transition,
            "approach_family": segment.approach_family,
            "source": _source_payload(segment.source),
            "legs": [
                {
                    "sequence": leg.sequence,
                    "leg_type": leg.leg_type,
                    "fix_ident": leg.fix_ident,
                    "procedure_kind": leg.procedure_kind,
                    "transition": leg.transition,
                    "approach_family": leg.approach_family,
                }
                for leg in segment.legs
            ],
        },
        "terminal_database_chart_evidence": [
            _chart_payload(chart) for chart in _matching_charts(model, segment)
        ],
        "source_page": {
            "path": str(source_path),
            "page": page,
            "sha256": source_sha256,
            "sha256_matches_model": source_sha256 == (segment.source.sha256 or source_sha256),
        },
        "direct_text": {
            "label_matches": label_matches,
            "label_match_count": len(label_matches),
            "category_heading_matches": heading_matches,
            "direct_label_kind_links": direct_links,
        },
        "source_proven_kind": source_proven_kind,
        "target_mapping_allowed": source_proven_kind is not None,
        "disposition": disposition,
        "reason": reason,
    }


def write_unclassified_procedure_card_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
