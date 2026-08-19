import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from fenix_default_navdata.iap_uncached_pdf_audit import (
    IapUncachedPdfAuditError,
    audit_uncached_iap_pdfs,
)


def _pdf(path: Path, text: str) -> str:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(path: Path, relative_path: str, sha256: str) -> Path:
    path.write_text(json.dumps({
        "diagnostic": "iap-evidence-cache-coverage-inventory-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "model_mutated": False,
        "projection_changed": False,
        "source": {"target_cards": ["ZTEST:I08-X"]},
        "airports": [{
            "airport": "ZTEST",
            "unresolved_labels": ["I08-X"],
            "files": [{
                "relative_path": relative_path,
                "sha256": sha256,
                "cached": False,
            }],
        }],
    }), encoding="utf-8")
    return path


def test_audit_accepts_only_direct_class_and_label_evidence(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    pdf = raw_root / "Terminal" / "ZTEST" / "ZTEST-5A.pdf"
    pdf.parent.mkdir(parents=True)
    sha256 = _pdf(pdf, "INSTRUMENT APPROACH I08-X")
    inventory = _inventory(
        tmp_path / "inventory.json",
        "Terminal/ZTEST/ZTEST-5A.pdf",
        sha256,
    )

    report = audit_uncached_iap_pdfs(inventory, raw_root)

    assert report["summary"] == {
        "airport_count": 1,
        "uncached_pdf_count": 1,
        "eligible_minimal_evidence_cache_count": 1,
        "dispositions": {"eligible_minimal_evidence_cache": 1},
        "no_unread_direct_424_evidence": False,
    }
    file = report["airports"][0]["files"][0]
    assert file["direct_categories"] == ["instrument-approach-index"]
    assert file["direct_label_matches"] == {"I08-X": [1]}


def test_audit_rejects_label_only_or_unindexed_pdf_without_a_direct_class(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    pdf = raw_root / "Terminal" / "ZTEST" / "ZTEST-2A.pdf"
    pdf.parent.mkdir(parents=True)
    sha256 = _pdf(pdf, "I08-X")
    inventory = _inventory(
        tmp_path / "inventory.json",
        "Terminal/ZTEST/ZTEST-2A.pdf",
        sha256,
    )

    report = audit_uncached_iap_pdfs(inventory, raw_root)

    assert report["summary"]["no_unread_direct_424_evidence"] is True
    assert report["airports"][0]["files"][0]["disposition"] == (
        "not_directly_relevant_to_unresolved_iap"
    )


def test_audit_rejects_changed_source_pdf_hash(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    pdf = raw_root / "Terminal" / "ZTEST" / "ZTEST-5A.pdf"
    pdf.parent.mkdir(parents=True)
    _pdf(pdf, "INSTRUMENT APPROACH I08-X")
    inventory = _inventory(
        tmp_path / "inventory.json",
        "Terminal/ZTEST/ZTEST-5A.pdf",
        "0" * 64,
    )

    with pytest.raises(IapUncachedPdfAuditError, match="hash changed"):
        audit_uncached_iap_pdfs(inventory, raw_root)
