"""Read source-backed OCR evidence from 2608 enroute GeneralDoc PDFs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .model import SourceRef


ENROUTE_KEY_POINT_DOCUMENT = (
    "GeneralDoc/"
    "\u822a\u8def_4.4\u91cd\u8981\u70b9\u540d\u79f0\u4ee3\u7801.pdf"
)
ENROUTE_KEY_POINT_CACHE_DIRECTORY = "enr-4.4"
_CACHE_SCHEMA_VERSION = 1
_POINT = re.compile(
    r"(?P<ident>[A-Z0-9]{2,5})\s*"
    r"N\s*(?P<latitude_degrees>\d{2})\s*[\N{DEGREE SIGN}\N{MASCULINE ORDINAL INDICATOR}]\s*"
    r"(?P<latitude_minutes>\d{2})\s*[\N{PRIME}\N{APOSTROPHE}]\s*"
    r"(?P<latitude_seconds>\d{2})\s*[\N{DOUBLE PRIME}\N{QUOTATION MARK}]\s*"
    r"E\s*(?P<longitude_degrees>\d{3})\s*[\N{DEGREE SIGN}\N{MASCULINE ORDINAL INDICATOR}]\s*"
    r"(?P<longitude_minutes>\d{2})\s*[\N{PRIME}\N{APOSTROPHE}]\s*"
    r"(?P<longitude_seconds>\d{2})\s*[\N{DOUBLE PRIME}\N{QUOTATION MARK}]"
)


class GeneralDocumentCacheError(ValueError):
    """Raised when OCR cache files cannot be tied to the raw source PDF."""


@dataclass(frozen=True)
class EnrouteKeyPointEvidence:
    ident: str
    latitude: float
    longitude: float
    source: SourceRef


def _coordinate(
    degrees: str,
    minutes: str,
    seconds: str,
    *,
    maximum_degrees: int,
) -> float:
    degree_value = int(degrees)
    minute_value = int(minutes)
    second_value = int(seconds)
    if degree_value > maximum_degrees or minute_value >= 60 or second_value >= 60:
        raise GeneralDocumentCacheError("invalid OCR DMS coordinate")
    return degree_value + minute_value / 60 + second_value / 3600


def parse_enroute_key_points(
    text: str,
    source: SourceRef,
) -> tuple[EnrouteKeyPointEvidence, ...]:
    """Parse explicitly printed 4.4 name-code coordinate table records."""
    records = []
    for match in _POINT.finditer(text.upper()):
        records.append(
            EnrouteKeyPointEvidence(
                ident=match["ident"],
                latitude=_coordinate(
                    match["latitude_degrees"],
                    match["latitude_minutes"],
                    match["latitude_seconds"],
                    maximum_degrees=89,
                ),
                longitude=_coordinate(
                    match["longitude_degrees"],
                    match["longitude_minutes"],
                    match["longitude_seconds"],
                    maximum_degrees=179,
                ),
                source=source,
            )
        )
    return tuple(records)


def _document_cache(
    root: Path,
    cache_root: Path,
) -> tuple[Path, Path, dict[str, object]]:
    document_cache = cache_root / ENROUTE_KEY_POINT_CACHE_DIRECTORY
    manifest_path = document_cache / "manifest.json"
    if not manifest_path.is_file():
        raise GeneralDocumentCacheError(
            f"missing OCR cache manifest: {manifest_path}"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise GeneralDocumentCacheError(
            f"invalid OCR cache manifest: {manifest_path}"
        ) from error
    if not isinstance(manifest, dict):
        raise GeneralDocumentCacheError("OCR cache manifest must be an object")
    if manifest.get("schema_version") != _CACHE_SCHEMA_VERSION:
        raise GeneralDocumentCacheError("unsupported OCR cache manifest schema")
    if manifest.get("source_file") != ENROUTE_KEY_POINT_DOCUMENT:
        raise GeneralDocumentCacheError("OCR cache manifest names an unexpected source PDF")
    source_pdf = root / ENROUTE_KEY_POINT_DOCUMENT
    if not source_pdf.is_file():
        raise GeneralDocumentCacheError(f"missing source PDF: {source_pdf}")
    source_hash = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    if manifest.get("source_sha256") != source_hash:
        raise GeneralDocumentCacheError("OCR cache source PDF SHA-256 does not match")
    return document_cache, source_pdf, manifest


def load_enroute_key_point_evidence(
    root: Path,
    cache_root: Path,
) -> tuple[tuple[EnrouteKeyPointEvidence, ...], dict[str, object]]:
    """Load complete 4.4 OCR cache without trusting cache-provided source fields."""
    document_cache, source_pdf, manifest = _document_cache(root, cache_root)
    page_count = manifest.get("page_count")
    if not isinstance(page_count, int) or page_count < 1:
        raise GeneralDocumentCacheError("OCR cache manifest has an invalid page count")

    expected = {f"page-{page:04d}.json" for page in range(1, page_count + 1)}
    actual = {
        path.name
        for path in document_cache.glob("page-*.json")
        if path.is_file()
    }
    if actual != expected:
        missing = len(expected - actual)
        unexpected = len(actual - expected)
        raise GeneralDocumentCacheError(
            f"OCR cache page set is incomplete (missing={missing}, unexpected={unexpected})"
        )

    source_hash = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    records: list[EnrouteKeyPointEvidence] = []
    for page_number in range(1, page_count + 1):
        page_path = document_cache / f"page-{page_number:04d}.json"
        try:
            payload = json.loads(page_path.read_text(encoding="utf-8-sig"))
            document = payload["data"]["documents"][0]
            markdown = document["markdown"]
        except (
            IndexError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise GeneralDocumentCacheError(
                f"invalid OCR cache page: {page_path}"
            ) from error
        if payload.get("ok") is not True or not isinstance(markdown, str):
            raise GeneralDocumentCacheError(
                f"failed OCR cache page: {page_path}"
            )
        source = SourceRef(
            ENROUTE_KEY_POINT_DOCUMENT,
            page=page_number,
            sha256=source_hash,
        )
        records.extend(parse_enroute_key_points(markdown, source))

    return tuple(records), {
        "available": True,
        "cache": str(document_cache),
        "document": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": source_hash,
        "pages": page_count,
        "parsed_records": len(records),
    }
