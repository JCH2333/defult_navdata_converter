import hashlib
import json
from pathlib import Path

import pytest

from fenix_default_navdata.ad219_ndb import (
    Ad219NdbOcrError,
    _ad219_page_text,
    _read_complete_cache,
    audit_ad219_ndb_ocr,
    collect_ad219_ndb_ocr_jobs,
)
from fenix_default_navdata.model import Navaid, NavModel, SourceRef
from fenix_default_navdata.pdf_charts import extract_ad219_ndbs


def _payload(markdown: str) -> dict[str, object]:
    return {
        "ok": True,
        "data": {
            "documents": [{
                "source_kind": "image",
                "markdown": markdown,
            }],
        },
    }


def _job_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "raw"
    airport = root / "Terminal" / "ZBCZ"
    airport.mkdir(parents=True)
    (airport / "Charts.csv").write_bytes(
        "PAGE_NUMBER\n0C-1\n".encode("gbk")
    )
    (airport / "ZBCZ-0C-1.pdf").write_bytes(b"indexed")
    source = airport / "长治王村.pdf"
    source.write_bytes(b"airport-document")
    return root, source


def test_extract_ad219_ndb_keeps_only_printed_identity_frequency_and_position() -> None:
    evidence = extract_ad219_ndbs(
        """
        NDB SQ 398 kHz
        N361418.8 E1130704.2
        LM 01
        """,
        "ZBCZ",
        SourceRef("Terminal/ZBCZ/长治王村.pdf", page=14, sha256="hash"),
    )

    assert len(evidence) == 1
    item = evidence[0]
    assert (
        item.airport,
        item.ident,
        item.frequency_khz,
        round(item.latitude, 6),
        round(item.longitude, 6),
        item.source,
    ) == (
        "ZBCZ",
        "SQ",
        398.0,
        36.238556,
        113.117833,
        SourceRef("Terminal/ZBCZ/长治王村.pdf", page=14, sha256="hash"),
    )


def test_extract_ad219_ndb_rejects_row_without_printed_coordinate() -> None:
    assert extract_ad219_ndbs(
        "NDB SQ 398 kHz\nLM 01",
        "ZBCZ",
        SourceRef("Terminal/ZBCZ/长治王村.pdf", page=14, sha256="hash"),
    ) == ()


def test_extract_ad219_ndb_accepts_collapsed_markdown_table_cells() -> None:
    evidence = extract_ad219_ndbs(
        """
        ZBCZ AD 2.19 Radio navigation and landing aids
        <table>长治NDBSQ398 kHzH24N361418.8E1130704.2距ARP 219°MAG/1376m</table>
        """,
        "ZBCZ",
        SourceRef("Terminal/ZBCZ/长治王村.pdf", page=14, sha256="hash"),
    )

    assert [(item.ident, item.frequency_khz, round(item.latitude, 6)) for item in evidence] == [
        ("SQ", 398.0, 36.238556),
    ]


def test_collect_ad219_ndb_jobs_excludes_indexed_chart_pages(tmp_path: Path) -> None:
    root, source = _job_root(tmp_path)

    jobs = collect_ad219_ndb_ocr_jobs(root, airports=["ZBCZ"])

    assert [(item.airport, item.source_file) for item in jobs] == [
        ("ZBCZ", "Terminal/ZBCZ/长治王村.pdf"),
    ]
    assert jobs[0].source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_collect_ad219_ndb_jobs_rejects_unknown_requested_airport(tmp_path: Path) -> None:
    root, _ = _job_root(tmp_path)

    with pytest.raises(Ad219NdbOcrError, match="不存在"):
        collect_ad219_ndb_ocr_jobs(root, airports=["ZBAD"])


def test_ad219_page_text_keeps_only_the_delimited_section() -> None:
    pages = _ad219_page_text((
        (13, "AD 2.18\nother"),
        (14, "AD 2.19\nNDB SQ 398 kHz\nN361418.8 E1130704.2"),
        (15, "NDB XX 300 kHz\nN350000 E1050000\nAD 2.20\nignored"),
    ))

    assert pages == (
        (14, "\nNDB SQ 398 kHz\nN361418.8 E1130704.2"),
        (15, "NDB XX 300 kHz\nN350000 E1050000\n"),
    )


def test_ad219_page_text_accepts_compact_page_heading() -> None:
    pages = _ad219_page_text((
        (14, "ZBCZAD2.19\nNDB SQ 398 kHz\nN361418.8 E1130704.2"),
        (15, "NDB XX 300 kHz\nN350000 E1050000\nZBCZAD2.20"),
    ))

    assert pages == (
        (14, "\nNDB SQ 398 kHz\nN361418.8 E1130704.2"),
        (15, "NDB XX 300 kHz\nN350000 E1050000\n"),
    )


def test_read_complete_cache_requires_every_source_hashed_page(tmp_path: Path) -> None:
    root, _ = _job_root(tmp_path)
    job = collect_ad219_ndb_ocr_jobs(root)[0]
    cache_root = tmp_path / "cache"
    cache = cache_root / "Terminal" / "ZBCZ" / "长治王村" / job.source_sha256[:16]
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": job.source_file,
        "source_sha256": job.source_sha256,
        "page_count": 2,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(
        json.dumps(_payload("AD 2.19")),
        encoding="utf-8",
    )

    pages, state, detail = _read_complete_cache(cache_root, job)

    assert pages is None
    assert state == "incomplete_cache"
    assert detail["missing_pages"] == 1


def test_ad219_ndb_audit_keeps_csv_match_with_missing_target_field_nonprojectable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _ = _job_root(tmp_path)
    (root / "NDB.csv").write_bytes((
        "SIGNIFICANT_POINT_ID,CODE_ID,TXT_NAME,VAL_MAG_VAR,VAL_ELEV,"
        "SERVICED_AIRPORT,CODE_FIR\n"
        "sq,SQ,长治,-5.0,,ZBCZ,\n"
    ).encode("gbk"))
    job = collect_ad219_ndb_ocr_jobs(root)[0]
    cache_root = tmp_path / "cache"
    cache = cache_root / "Terminal" / "ZBCZ" / "长治王村" / job.source_sha256[:16]
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": job.source_file,
        "source_sha256": job.source_sha256,
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps(_payload(
        "ZBCZAD2.19\n"
        "<table>长治NDBSQ398 kHzH24N361418.8E1130704.2</table>\n"
        "ZBCZAD2.20"
    )), encoding="utf-8")
    model = NavModel(root)
    model.navaids.append(Navaid(
        key="sq",
        ident="SQ",
        kind="NDB",
        name="长治",
        latitude=36.238556,
        longitude=113.117833,
        frequency=398.0,
        magnetic_variation=-5.0,
        elevation_ft=0,
        country="ZB",
        source=SourceRef("NDB.csv", 2),
    ))
    monkeypatch.setattr(
        "fenix_default_navdata.ad219_ndb.load_naip",
        lambda *_args, **_kwargs: model,
    )

    report = audit_ad219_ndb_ocr(root, cache_root, airports=["ZBCZ"])

    assert report["projection_allowed"] is False
    assert report["summary"]["reconciliation_counts"] == {
        "matched_direct_424_with_target_gaps": 1,
    }
    assert report["records"] == [{
        "airport": "ZBCZ",
        "ident": "SQ",
        "source_file": "Terminal/ZBCZ/长治王村.pdf",
        "source_sha256": job.source_sha256,
        "page": 1,
        "reconciliation": "matched_direct_424_with_target_gaps",
        "direct_424_source": {"file": "NDB.csv", "row": 2},
        "printed_evidence_missing_target_fields": [
            "name",
            "magnetic_variation",
            "elevation_ft",
            "country",
        ],
        "remaining_target_gaps": ["elevation_ft"],
    }]
