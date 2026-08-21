from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping, Sequence


class AirportDocumentSourceAuditError(RuntimeError):
    """Raised when an OCR document source audit input is invalid."""


_ICAO_RE = re.compile(r"\b[A-Z][A-Z0-9]{3}\b")


def _read_json(path: Path) -> dict[str, object]:
    raw = path.expanduser().read_bytes()
    errors: list[Exception] = []
    for encoding in ("utf-8-sig", "cp936", "gb18030"):
        try:
            value = json.loads(raw.decode(encoding))
            break
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(error)
    else:
        raise AirportDocumentSourceAuditError(
            f"cannot decode OCR JSON: {path}"
        ) from errors[-1]
    if not isinstance(value, dict) or value.get("ok") is not True:
        raise AirportDocumentSourceAuditError(f"OCR JSON is not successful: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _documents(report: Mapping[str, object]) -> list[Mapping[str, object]]:
    data = report.get("data")
    if not isinstance(data, Mapping):
        raise AirportDocumentSourceAuditError("OCR JSON lacks data")
    raw_documents = data.get("documents")
    if isinstance(raw_documents, list):
        documents = raw_documents
    elif isinstance(data.get("markdown"), str) or isinstance(data.get("content"), str):
        documents = [data]
    else:
        raise AirportDocumentSourceAuditError("OCR JSON lacks document content")
    result = [item for item in documents if isinstance(item, Mapping)]
    if not result:
        raise AirportDocumentSourceAuditError("OCR JSON contains no documents")
    return result


def audit_airport_document_sources(
    ocr_reports: Sequence[Path],
    target_airports: Sequence[str],
    *,
    source_documents: Sequence[Path] = (),
) -> dict[str, object]:
    """Audit whether airport reference-only identities appear in 424 PDFs.

    OCR is evidence only. A hit does not authorize projection; the report
    records that the documents need structured field and target-scope proof.
    """

    targets = tuple(sorted({item.strip().upper() for item in target_airports if item.strip()}))
    if not targets:
        raise AirportDocumentSourceAuditError("target_airports must not be empty")
    if any(not _ICAO_RE.fullmatch(item) for item in targets):
        raise AirportDocumentSourceAuditError("target airport identifiers are invalid")
    if not ocr_reports:
        raise AirportDocumentSourceAuditError("ocr_reports must not be empty")

    report_rows: list[dict[str, object]] = []
    found: dict[str, list[dict[str, object]]] = {item: [] for item in targets}
    for report_path in ocr_reports:
        report = _read_json(report_path)
        for document in _documents(report):
            text = document.get("markdown") or document.get("content") or ""
            if not isinstance(text, str):
                raise AirportDocumentSourceAuditError(
                    f"OCR document content is not text: {report_path}"
                )
            source_path = document.get("source_path") or document.get("path")
            row = {
                "ocr_report": str(report_path.expanduser().resolve()),
                "source_path": str(source_path) if isinstance(source_path, str) else None,
                "page": document.get("page"),
                "total_pages": document.get("total_pages"),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_length": len(text),
                "target_hits": {},
            }
            for target in targets:
                positions = [match.start() for match in re.finditer(
                    re.escape(target), text, flags=re.IGNORECASE
                )]
                if positions:
                    snippets = [
                        text[max(0, position - 100):position + len(target) + 160]
                        .replace("\r", " ")
                        .replace("\n", " ")
                        for position in positions[:3]
                    ]
                    hit = {
                        "count": len(positions),
                        "snippet_sha256": hashlib.sha256(
                            "\n".join(snippets).encode("utf-8")
                        ).hexdigest(),
                    }
                    row["target_hits"][target] = hit
                    found[target].append({
                        "ocr_report": str(report_path.expanduser().resolve()),
                        "source_path": row["source_path"],
                        "page": row["page"],
                        "count": len(positions),
                    })
            report_rows.append(row)

    document_rows: list[dict[str, object]] = []
    for path in source_documents:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise AirportDocumentSourceAuditError(f"source document missing: {resolved}")
        document_rows.append({
            "path": str(resolved),
            "sha256": _sha256(resolved),
            "size": resolved.stat().st_size,
        })

    target_rows = [
        {
            "airport": target,
            "hit": bool(found[target]),
            "matches": found[target],
            "projection_authorized": False,
            "reason": (
                "OCR airport-document presence is not sufficient to populate "
                "AD_HP, runway, terminal and target loading fields."
            ),
        }
        for target in targets
    ]
    return {
        "diagnostic": "airport-document-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "ocr_text_exported": False,
        "source_documents": document_rows,
        "ocr_reports": [
            {
                "path": str(path.expanduser().resolve()),
                "sha256": _sha256(path),
                "size": path.expanduser().stat().st_size,
            }
            for path in ocr_reports
        ],
        "targets": target_rows,
        "summary": {
            "target_total": len(targets),
            "target_hit_total": sum(bool(found[target]) for target in targets),
            "target_miss_total": sum(not found[target] for target in targets),
            "projection_authorized": False,
        },
    }


def write_airport_document_source_audit(
    path: Path, report: Mapping[str, object]
) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
