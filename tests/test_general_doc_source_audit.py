from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.general_doc_source_audit import (
    audit_general_doc_source,
    write_general_doc_source_audit,
)
from fenix_default_navdata.model import NavModel


def test_general_doc_source_audit(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()

    (raw / "GENERAL_DOC.csv").write_text(
        "Id,ParentId,Name,PdfName,IS_MODIFIED\n"
        "1,,GEN 0,GEN0,N\n"
        "2,1,GEN 0.1,GEN0_1,N\n"
        "3,2,GEN 0.1.1,,N\n",
        encoding="utf-8",
    )
    doc_dir = raw / "GeneralDoc"
    doc_dir.mkdir()
    (doc_dir / "GEN0.pdf").write_bytes(b"%PDF-1.4 mock")

    model = NavModel(raw)

    report = audit_general_doc_source(raw, model)

    assert report["diagnostic"] == "general-doc-source-audit-v1"
    assert report["read_only"] is True
    assert report["summary"]["total_catalog_rows"] == 3
    assert report["summary"]["pdf_referenced_rows"] == 2
    assert report["summary"]["matched_pdf_files"] == 1
    assert report["summary"]["catalog_section_headers_without_pdf"] == 1
    assert report["summary"]["projection_allowed"] is False
    assert report["summary"]["disposition"] == "source_evidence_only"

    out_file = tmp_path / "out.json"
    write_general_doc_source_audit(out_file, report)
    assert json.loads(out_file.read_text(encoding="utf-8")) == report
