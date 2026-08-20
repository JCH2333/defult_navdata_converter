from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .model import NavModel


class GeneralDocSourceAuditError(RuntimeError):
    """当 GENERAL_DOC.csv 关系审计无法在只读边界内完成时抛出。"""


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise GeneralDocSourceAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return list(csv.DictReader(_csv_text(path).splitlines()))


def audit_general_doc_source(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise GeneralDocSourceAuditError(f"424 原始目录不存在: {root}")

    doc_path = root / "GENERAL_DOC.csv"
    doc_rows = _rows(doc_path)
    pdf_dir = root / "GeneralDoc"

    existing_files = {p.name for p in pdf_dir.iterdir()} if pdf_dir.is_dir() else set()

    total_rows = len(doc_rows)
    nonempty_pdfname = 0
    matched_pdf_files = 0
    sections_without_pdf = 0

    for row in doc_rows:
        pdf_name = (row.get("PdfName") or "").strip()
        if pdf_name:
            nonempty_pdfname += 1
            if (pdf_name + ".pdf") in existing_files:
                matched_pdf_files += 1
        else:
            sections_without_pdf += 1

    return {
        "diagnostic": "general-doc-source-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "general_doc_csv_rows": total_rows,
            "general_doc_pdf_directory_exists": pdf_dir.is_dir(),
            "actual_pdf_file_count": len(existing_files),
        },
        "summary": {
            "total_catalog_rows": total_rows,
            "pdf_referenced_rows": nonempty_pdfname,
            "matched_pdf_files": matched_pdf_files,
            "catalog_section_headers_without_pdf": sections_without_pdf,
            "disposition": "source_evidence_only",
            "projection_allowed": False,
            "reason": (
                "GENERAL_DOC.csv 是 424 GeneralDoc 航行通告/章节 PDF 的元数据目录索引；"
                "内容已由 GeneralDoc PDF 与经校验的 OCR 缓存管线按需审计消费，"
                "CSV 本身不直接提供新的独立结构化导航实体。"
            ),
        },
    }


def write_general_doc_source_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
