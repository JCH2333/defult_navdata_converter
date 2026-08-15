"""Read source-backed OCR evidence from 2608 enroute GeneralDoc PDFs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .model import EnrouteNavaidEvidence, SourceRef


ENROUTE_KEY_POINT_DOCUMENT = (
    "GeneralDoc/"
    "\u822a\u8def_4.4\u91cd\u8981\u70b9\u540d\u79f0\u4ee3\u7801.pdf"
)
ENROUTE_KEY_POINT_CACHE_DIRECTORY = "enr-4.4"
ENROUTE_NAVAID_DOCUMENT = (
    "GeneralDoc/"
    "\u822a\u8def_4.1\u65e0\u7ebf\u7535\u5bfc\u822a\u8bbe\u65bd\u2014\u2014\u822a\u8def.pdf"
)
ENROUTE_NAVAID_CACHE_DIRECTORY = "enr-4.1-navaids"
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
_CELL = re.compile(
    r"(?P<text>.*?)\[\["
    r"(?P<x0>\d+(?:\.\d+)?),\s*"
    r"(?P<y0>\d+(?:\.\d+)?),\s*"
    r"(?P<x1>\d+(?:\.\d+)?),\s*"
    r"(?P<y1>\d+(?:\.\d+)?)\]\]"
)
_NAVAID_LATITUDE = re.compile(
    r"^N(?P<degrees>\d{2})\D+(?P<minutes>\d{2})['\u2019](?P<seconds>\d{2})(?:[\"\u201d])?$"
)
_NAVAID_LONGITUDE = re.compile(
    r"^E(?P<degrees>\d{3})\D+(?P<minutes>\d{2})['\u2019](?P<seconds>\d{2})(?:[\"\u201d])?$"
)
_NAVAID_IDENT = re.compile(r"^[A-Z0-9]{2,5}$")
_NAVAID_FREQUENCY = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>MHz|kHz)$",
    re.IGNORECASE,
)
_NAVAID_ELEVATION = re.compile(r"^\d+(?:\.\d+)?$")


class GeneralDocumentCacheError(ValueError):
    """Raised when OCR cache files cannot be tied to the raw source PDF."""


@dataclass(frozen=True)
class EnrouteKeyPointEvidence:
    ident: str
    latitude: float
    longitude: float
    source: SourceRef


@dataclass(frozen=True)
class _OcrCell:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


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


def _ocr_cells(text: str) -> tuple[_OcrCell, ...]:
    return tuple(
        _OcrCell(
            match["text"].strip(),
            float(match["x0"]),
            float(match["y0"]),
            float(match["x1"]),
            float(match["y1"]),
        )
        for match in _CELL.finditer(text)
        if match["text"].strip()
    )


def _parse_navaid_coordinate(
    match: re.Match[str],
    *,
    maximum_degrees: int,
) -> float:
    return _coordinate(
        match["degrees"],
        match["minutes"],
        match["seconds"],
        maximum_degrees=maximum_degrees,
    )


def parse_enroute_navaids(
    text: str,
    source: SourceRef,
) -> tuple[EnrouteNavaidEvidence, ...]:
    """Parse complete 4.1 table rows without trusting damaged OCR name text.

    The local OCR model can preserve table geometry and Latin/numeric cells
    while replacing Chinese glyphs and degree signs.  This parser therefore
    requires type, identifier, frequency, and both DMS coordinate cells in
    their published table columns.  Missing or duplicated cells are rejected
    by omission instead of being paired across rows.
    """
    records: list[EnrouteNavaidEvidence] = []
    cells = _ocr_cells(text)
    for latitude_cell in cells:
        latitude_match = _NAVAID_LATITUDE.fullmatch(latitude_cell.text)
        if latitude_match is None or not 400 <= latitude_cell.x0 <= 520:
            continue
        nearby = tuple(
            cell
            for cell in cells
            if latitude_cell.y0 - 8 <= cell.y0 <= latitude_cell.y0 + 28
        )
        longitudes = tuple(
            cell
            for cell in nearby
            if 400 <= cell.x0 <= 540
            and _NAVAID_LONGITUDE.fullmatch(cell.text) is not None
        )
        kinds = tuple(
            cell
            for cell in nearby
            if cell.x0 < 180 and cell.text.upper() in {"VOR/DME", "NDB"}
        )
        idents = tuple(
            cell
            for cell in nearby
            if 180 <= cell.x0 <= 250
            and _NAVAID_IDENT.fullmatch(cell.text.upper()) is not None
            and cell.text.upper() not in {"VOR", "DME", "NDB"}
        )
        frequencies = tuple(
            cell
            for cell in nearby
            if 240 <= cell.x0 <= 350
            and _NAVAID_FREQUENCY.fullmatch(cell.text) is not None
        )
        if len(longitudes) != 1 or len(kinds) != 1 or len(idents) != 1 or len(frequencies) != 1:
            continue
        longitude_match = _NAVAID_LONGITUDE.fullmatch(longitudes[0].text)
        frequency_match = _NAVAID_FREQUENCY.fullmatch(frequencies[0].text)
        if longitude_match is None or frequency_match is None:
            continue
        elevations = tuple(
            cell
            for cell in nearby
            if 530 <= cell.x0 <= 610
            and _NAVAID_ELEVATION.fullmatch(cell.text) is not None
        )
        kind = "VOR" if kinds[0].text.upper() == "VOR/DME" else "NDB"
        records.append(
            EnrouteNavaidEvidence(
                kind=kind,
                ident=idents[0].text.upper(),
                frequency=float(frequency_match["value"]),
                latitude=_parse_navaid_coordinate(
                    latitude_match,
                    maximum_degrees=89,
                ),
                longitude=_parse_navaid_coordinate(
                    longitude_match,
                    maximum_degrees=179,
                ),
                elevation_meters=(
                    float(elevations[0].text) if len(elevations) == 1 else None
                ),
                source=source,
            )
        )
    return tuple(records)


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
    *,
    document: str,
    cache_directory: str,
) -> tuple[Path, Path, dict[str, object]]:
    document_cache = cache_root / cache_directory
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
    if manifest.get("source_file") != document:
        raise GeneralDocumentCacheError("OCR cache manifest names an unexpected source PDF")
    source_pdf = root / document
    if not source_pdf.is_file():
        raise GeneralDocumentCacheError(f"missing source PDF: {source_pdf}")
    source_hash = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    if manifest.get("source_sha256") != source_hash:
        raise GeneralDocumentCacheError("OCR cache source PDF SHA-256 does not match")
    return document_cache, source_pdf, manifest


def _load_complete_document(
    root: Path,
    cache_root: Path,
    *,
    document: str,
    cache_directory: str,
) -> tuple[tuple[tuple[int, str], ...], Path, str, dict[str, object]]:
    document_cache, source_pdf, manifest = _document_cache(
        root,
        cache_root,
        document=document,
        cache_directory=cache_directory,
    )
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
    pages: list[tuple[int, str]] = []
    for page_number in range(1, page_count + 1):
        page_path = document_cache / f"page-{page_number:04d}.json"
        try:
            payload = json.loads(page_path.read_text(encoding="utf-8-sig"))
            ocr_document = payload["data"]["documents"][0]
            markdown = ocr_document["markdown"]
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
        pages.append((page_number, markdown))
    return tuple(pages), source_pdf, source_hash, {
        "available": True,
        "cache": str(document_cache),
        "document": document,
        "source_sha256": source_hash,
        "pages": page_count,
    }


def _load_selected_document_pages(
    root: Path,
    cache: Path,
    *,
    document: str,
    require_complete: bool,
) -> tuple[tuple[tuple[int, str], ...], str, dict[str, object]]:
    """Load a verified OCR cache, allowing a deliberate subset for reruns."""
    cache = cache.expanduser().resolve()
    document_cache, source_pdf, manifest = _document_cache(
        root,
        cache.parent,
        document=document,
        cache_directory=cache.name,
    )
    page_count = manifest.get("page_count")
    if not isinstance(page_count, int) or page_count < 1:
        raise GeneralDocumentCacheError("OCR cache manifest has an invalid page count")

    numbered_pages: dict[int, Path] = {}
    for page_path in document_cache.glob("page-*.json"):
        match = re.fullmatch(r"page-(\d{4})\.json", page_path.name)
        if match is None:
            raise GeneralDocumentCacheError(
                f"invalid OCR cache page filename: {page_path.name}"
            )
        page_number = int(match.group(1))
        if page_number < 1 or page_number > page_count:
            raise GeneralDocumentCacheError(
                f"OCR cache page is outside document range: {page_path.name}"
            )
        numbered_pages[page_number] = page_path
    if not numbered_pages:
        raise GeneralDocumentCacheError("OCR cache has no valid page files")
    if require_complete and set(numbered_pages) != set(range(1, page_count + 1)):
        missing = page_count - len(numbered_pages)
        raise GeneralDocumentCacheError(
            f"OCR cache page set is incomplete (missing={missing}, unexpected=0)"
        )

    pages: list[tuple[int, str]] = []
    for page_number, page_path in sorted(numbered_pages.items()):
        try:
            payload = json.loads(page_path.read_text(encoding="utf-8-sig"))
            ocr_document = payload["data"]["documents"][0]
            markdown = ocr_document["markdown"]
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
        pages.append((page_number, markdown))

    source_hash = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    return tuple(pages), source_hash, {
        "cache": str(document_cache),
        "page_count": page_count,
        "selected_pages": list(numbered_pages),
    }


def _navaid_evidence_identity(
    item: EnrouteNavaidEvidence,
) -> tuple[object, ...]:
    return (
        item.kind,
        item.ident,
        item.frequency,
        item.latitude,
        item.longitude,
        item.elevation_meters,
    )


def _navaid_evidence_report_item(item: EnrouteNavaidEvidence) -> dict[str, object]:
    return {
        "kind": item.kind,
        "ident": item.ident,
        "frequency": item.frequency,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "elevation_meters": item.elevation_meters,
        "page": item.source.page,
    }


def audit_enroute_navaid_ocr_rerun(
    root: Path,
    canonical_cache: Path,
    rerun_cache: Path,
) -> dict[str, object]:
    """Compare a complete 4.1 cache with a same-PDF OCR rerun.

    The audit is intentionally evidence-only: it reports parser agreement and
    omissions by physical PDF page and never promotes OCR facts to a Navaid.
    """
    root = root.expanduser().resolve()
    canonical_pages, canonical_hash, canonical_report = _load_selected_document_pages(
        root,
        canonical_cache,
        document=ENROUTE_NAVAID_DOCUMENT,
        require_complete=True,
    )
    rerun_pages, rerun_hash, rerun_report = _load_selected_document_pages(
        root,
        rerun_cache,
        document=ENROUTE_NAVAID_DOCUMENT,
        require_complete=False,
    )
    if canonical_hash != rerun_hash:
        raise GeneralDocumentCacheError("OCR rerun cache source PDF SHA-256 does not match")
    if canonical_report["page_count"] != rerun_report["page_count"]:
        raise GeneralDocumentCacheError("OCR rerun cache page count does not match")

    canonical_by_page = {
        page: tuple(
            parse_enroute_navaids(
                markdown,
                SourceRef(
                    ENROUTE_NAVAID_DOCUMENT,
                    page=page,
                    sha256=canonical_hash,
                ),
            )
        )
        for page, markdown in canonical_pages
    }
    rerun_by_page = {
        page: tuple(
            parse_enroute_navaids(
                markdown,
                SourceRef(
                    ENROUTE_NAVAID_DOCUMENT,
                    page=page,
                    sha256=rerun_hash,
                ),
            )
        )
        for page, markdown in rerun_pages
    }
    agreed: list[EnrouteNavaidEvidence] = []
    canonical_only: list[EnrouteNavaidEvidence] = []
    rerun_only: list[EnrouteNavaidEvidence] = []
    for page, rerun_records in rerun_by_page.items():
        canonical_records = canonical_by_page[page]
        canonical_keys = {_navaid_evidence_identity(item) for item in canonical_records}
        rerun_keys = {_navaid_evidence_identity(item) for item in rerun_records}
        agreed.extend(
            item
            for item in canonical_records
            if _navaid_evidence_identity(item) in rerun_keys
        )
        canonical_only.extend(
            item
            for item in canonical_records
            if _navaid_evidence_identity(item) not in rerun_keys
        )
        rerun_only.extend(
            item
            for item in rerun_records
            if _navaid_evidence_identity(item) not in canonical_keys
        )
    union_count = len(agreed) + len(canonical_only) + len(rerun_only)
    consistent = not canonical_only and not rerun_only

    return {
        "diagnostic": "enroute-navaid-ocr-rerun-audit-v1",
        "evidence_only": True,
        "document": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": canonical_hash,
        "canonical": {
            **canonical_report,
            "parsed_records": sum(len(records) for records in canonical_by_page.values()),
            "selected_pages_parsed_records": sum(
                len(canonical_by_page[page]) for page in rerun_by_page
            ),
        },
        "rerun": {
            **rerun_report,
            "parsed_records": sum(len(records) for records in rerun_by_page.values()),
        },
        "comparison": {
            "consistent": consistent,
            "agreement_ratio": round(len(agreed) / union_count, 6) if union_count else 1.0,
            "selected_pages": list(rerun_by_page),
        },
        "records": {
            "agreed": len(agreed),
            "canonical_only": len(canonical_only),
            "rerun_only": len(rerun_only),
            "canonical_only_items": [
                _navaid_evidence_report_item(item)
                for item in canonical_only
            ],
            "rerun_only_items": [
                _navaid_evidence_report_item(item)
                for item in rerun_only
            ],
        },
    }


def write_enroute_navaid_ocr_rerun_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_enroute_key_point_evidence(
    root: Path,
    cache_root: Path,
) -> tuple[tuple[EnrouteKeyPointEvidence, ...], dict[str, object]]:
    """Load complete 4.4 OCR cache without trusting cache-provided source fields."""
    pages, _, source_hash, report = _load_complete_document(
        root,
        cache_root,
        document=ENROUTE_KEY_POINT_DOCUMENT,
        cache_directory=ENROUTE_KEY_POINT_CACHE_DIRECTORY,
    )
    records: list[EnrouteKeyPointEvidence] = []
    for page_number, markdown in pages:
        records.extend(
            parse_enroute_key_points(
                markdown,
                SourceRef(
                    ENROUTE_KEY_POINT_DOCUMENT,
                    page=page_number,
                    sha256=source_hash,
                ),
            )
        )

    return tuple(records), {
        "available": True,
        "document": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": source_hash,
        "pages": report["pages"],
        "parsed_records": len(records),
    }


def load_enroute_navaid_evidence(
    root: Path,
    cache_root: Path,
    *,
    cache_directory: str = ENROUTE_NAVAID_CACHE_DIRECTORY,
) -> tuple[tuple[EnrouteNavaidEvidence, ...], dict[str, object]]:
    """Load complete 4.1 OCR evidence without inventing missing target fields."""
    pages, _, source_hash, report = _load_complete_document(
        root,
        cache_root,
        document=ENROUTE_NAVAID_DOCUMENT,
        cache_directory=cache_directory,
    )
    records: list[EnrouteNavaidEvidence] = []
    for page_number, markdown in pages:
        records.extend(
            parse_enroute_navaids(
                markdown,
                SourceRef(
                    ENROUTE_NAVAID_DOCUMENT,
                    page=page_number,
                    sha256=source_hash,
                ),
            )
        )
    return tuple(records), {
        **report,
        "parsed_records": len(records),
    }
