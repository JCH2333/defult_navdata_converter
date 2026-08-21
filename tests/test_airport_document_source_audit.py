from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.airport_document_source_audit import (
    audit_airport_document_sources,
    write_airport_document_source_audit,
)


def test_airport_document_audit_is_encoding_tolerant_and_nonprojectable(
    tmp_path: Path,
) -> None:
    ocr = tmp_path / "ocr.json"
    ocr.write_bytes(json.dumps({
        "ok": True,
        "data": {
            "documents": [{
                "source_path": "airport.pdf",
                "page": 1,
                "total_pages": 1,
                "markdown": "ZBSH/ABC and unrelated ZZZZ",
            }],
        },
    }, ensure_ascii=False).encode("cp936"))
    source = tmp_path / "airport.pdf"
    source.write_bytes(b"source-pdf")

    report = audit_airport_document_sources(
        [ocr],
        ["ZBSH", "ZGFS"],
        source_documents=[source],
    )

    assert report["diagnostic"] == "airport-document-source-audit-v1"
    assert report["summary"] == {
        "projection_authorized": False,
        "target_hit_total": 1,
        "target_miss_total": 1,
        "target_total": 2,
    }
    rows = {row["airport"]: row for row in report["targets"]}
    assert rows["ZBSH"]["hit"] is True
    assert rows["ZGFS"]["hit"] is False
    assert rows["ZBSH"]["projection_authorized"] is False
    output = tmp_path / "audit.json"
    write_airport_document_source_audit(output, report)
    assert json.loads(output.read_text(encoding="utf-8"))["ocr_text_exported"] is False
