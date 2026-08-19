from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf


class IapUncachedPdfAuditError(ValueError):
    """Raised when an evidence-cache coverage inventory is not safe to audit."""


_DATABASE_CODING_MARKERS = ("数据库编码", "DATABASE CODING")
_INSTRUMENT_APPROACH_MARKERS = (
    "仪表进近图",
    "仪表进场图",
    "INSTRUMENT APPROACH",
)


def _load_inventory(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise IapUncachedPdfAuditError(
            f"cannot read evidence-cache inventory: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise IapUncachedPdfAuditError("inventory root must be an object")
    if payload.get("diagnostic") != "iap-evidence-cache-coverage-inventory-v1":
        raise IapUncachedPdfAuditError("unexpected inventory diagnostic")
    for flag in (
        "read_only",
        "reference_records_read",
        "fenix_records_read",
        "model_mutated",
        "projection_changed",
    ):
        expected = flag == "read_only"
        if payload.get(flag) is not expected:
            raise IapUncachedPdfAuditError(
                f"inventory safety flag {flag!r} is not {expected!r}"
            )
    if not isinstance(payload.get("airports"), list):
        raise IapUncachedPdfAuditError("inventory airports must be a list")
    return payload


def _label_pattern(label: str) -> re.Pattern[str]:
    compact = (label or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", compact):
        raise IapUncachedPdfAuditError(f"unsupported IAP label: {label!r}")
    separator = r"[\s\-_]*"
    pieces = [separator.join(map(re.escape, part)) for part in compact.split("-")]
    return re.compile(r"(?<![A-Z0-9])" + separator.join(pieces) + r"(?![A-Z0-9])")


def _page_categories(text: str) -> list[str]:
    upper = (text or "").upper()
    categories: list[str] = []
    if any(marker in upper for marker in _DATABASE_CODING_MARKERS):
        categories.append("terminal-database-coding")
    if any(marker in upper for marker in _INSTRUMENT_APPROACH_MARKERS):
        categories.append("instrument-approach-index")
    return categories


def _safe_pdf_path(raw_root: Path, relative_path: str) -> Path:
    raw_root = raw_root.expanduser().resolve()
    candidate = (raw_root / relative_path).resolve()
    if raw_root not in candidate.parents:
        raise IapUncachedPdfAuditError(
            f"inventory PDF is outside raw root: {relative_path!r}"
        )
    return candidate


def _audit_file(
    raw_root: Path,
    airport: str,
    labels: list[str],
    record: dict[str, Any],
) -> dict[str, Any]:
    relative_path = record.get("relative_path")
    expected_hash = record.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
        raise IapUncachedPdfAuditError("uncached inventory record lacks path or hash")
    path = _safe_pdf_path(raw_root, relative_path)
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash.casefold() != expected_hash.casefold():
        raise IapUncachedPdfAuditError(
            f"inventory PDF hash changed: {relative_path}"
        )

    patterns = {label: _label_pattern(label) for label in labels}
    pages: list[dict[str, object]] = []
    categories: set[str] = set()
    label_pages: dict[str, list[int]] = {label: [] for label in labels}
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")
            page_categories = _page_categories(text)
            categories.update(page_categories)
            matched_labels = [
                label for label, pattern in patterns.items()
                if pattern.search(text.upper())
            ]
            for label in matched_labels:
                label_pages[label].append(page_number)
            pages.append({
                "page": page_number,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "direct_categories": page_categories,
                "direct_label_matches": matched_labels,
            })

    matched_labels = {
        label: page_numbers
        for label, page_numbers in label_pages.items()
        if page_numbers
    }
    relevant_categories = sorted(categories.intersection({
        "terminal-database-coding",
        "instrument-approach-index",
    }))
    eligible = bool(relevant_categories and matched_labels)
    return {
        "relative_path": relative_path,
        "sha256": actual_hash,
        "airport": airport,
        "cached": False,
        "page_count": len(pages),
        "pages": pages,
        "direct_categories": relevant_categories,
        "direct_label_matches": matched_labels,
        "eligible_minimal_evidence_cache": eligible,
        "disposition": (
            "eligible_minimal_evidence_cache"
            if eligible
            else "not_directly_relevant_to_unresolved_iap"
        ),
    }


def audit_uncached_iap_pdfs(
    inventory_path: Path,
    raw_root: Path,
) -> dict[str, object]:
    """Classify uncached IAP-adjacent PDFs using only their direct text.

    The inventory controls the exact 424 PDF scope and SHA-256 values.  This
    audit intentionally does not inspect candidate output, reference payloads,
    Fenix data, OCR, or any normalized model.  A file is only eligible for a
    minimal evidence cache when direct text proves both a relevant document
    class and one of that airport's unresolved IAP labels.
    """
    inventory = _load_inventory(inventory_path)
    airports: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for airport_entry in inventory["airports"]:
        if not isinstance(airport_entry, dict):
            raise IapUncachedPdfAuditError("inventory airport entry must be an object")
        airport = airport_entry.get("airport")
        labels = airport_entry.get("unresolved_labels")
        records = airport_entry.get("files")
        if (
            not isinstance(airport, str)
            or not isinstance(labels, list)
            or not all(isinstance(label, str) for label in labels)
            or not isinstance(records, list)
        ):
            raise IapUncachedPdfAuditError("inventory airport entry is malformed")
        airport_files = [
            _audit_file(raw_root, airport, labels, record)
            for record in records
            if isinstance(record, dict) and record.get("cached") is False
        ]
        files.extend(airport_files)
        airports.append({
            "airport": airport,
            "unresolved_labels": labels,
            "uncached_pdf_count": len(airport_files),
            "eligible_minimal_evidence_cache_count": sum(
                item["eligible_minimal_evidence_cache"] for item in airport_files
            ),
            "files": airport_files,
        })

    disposition_counts = Counter(
        str(item["disposition"]) for item in files
    )
    eligible_files = [
        item["relative_path"]
        for item in files
        if item["eligible_minimal_evidence_cache"]
    ]
    return {
        "diagnostic": "uncached-iap-pdf-direct-text-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "ocr_used": False,
        "model_mutated": False,
        "projection_changed": False,
        "source": {
            "inventory": str(inventory_path),
            "raw_root": str(raw_root),
            "target_cards": inventory.get("source", {}).get("target_cards", []),
        },
        "summary": {
            "airport_count": len(airports),
            "uncached_pdf_count": len(files),
            "eligible_minimal_evidence_cache_count": len(eligible_files),
            "dispositions": dict(sorted(disposition_counts.items())),
            "no_unread_direct_424_evidence": not eligible_files,
        },
        "eligible_files": eligible_files,
        "airports": airports,
    }


def write_uncached_iap_pdf_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
