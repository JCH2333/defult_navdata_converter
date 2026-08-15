import hashlib
import json
from pathlib import Path

import pytest

from fenix_default_navdata.general_docs import (
    ENROUTE_NAVAID_DOCUMENT,
    ENROUTE_KEY_POINT_DOCUMENT,
    GeneralDocumentCacheError,
    audit_enroute_navaid_ocr_rerun,
    load_enroute_navaid_evidence,
    load_enroute_key_point_evidence,
    parse_enroute_navaids,
    parse_enroute_key_points,
)
from fenix_default_navdata.model import SourceRef
from fenix_default_navdata.source import audit_enroute_key_point_ocr_rerun


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


def _cache(
    root: Path,
    pages: dict[int, str],
    *,
    directory: str = "enr-4.4",
    page_count: int | None = None,
) -> Path:
    source = root / ENROUTE_KEY_POINT_DOCUMENT
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-pdf")
    cache = root.parent / "ocr-cache" / directory
    cache.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "page_count": page_count or len(pages),
    }
    (cache / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    for page, markdown in pages.items():
        (cache / f"page-{page:04d}.json").write_text(
            json.dumps(_payload(markdown)),
            encoding="utf-8",
        )
    return cache.parent


def _navaid_cache(
    root: Path,
    name: str,
    pages: dict[int, str],
    *,
    page_count: int,
) -> Path:
    source = root / ENROUTE_NAVAID_DOCUMENT
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-pdf")
    cache = root.parent / "ocr-cache" / name
    cache.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "source_file": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "page_count": page_count,
    }
    (cache / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for page, markdown in pages.items():
        (cache / f"page-{page:04d}.json").write_text(
            json.dumps(_payload(markdown)),
            encoding="utf-8",
        )
    return cache


def _navaid_markdown(ident: str) -> str:
    return "\n".join((
        f"{ident}[[192, 304, 232, 319]]",
        "112.1MHz[[256, 299, 336, 313]]",
        "N41\ufffd\ufffd15'38\"[[433, 299, 512, 313]]",
        "1188[[551, 305, 591, 320]]",
        "VOR/DME[[92, 317, 167, 331]]",
        "E080\ufffd\ufffd19'34\"[[433, 317, 514, 331]]",
    ))


def test_parse_enroute_key_points_accepts_adjacent_two_column_ocr_cells() -> None:
    source = SourceRef(ENROUTE_KEY_POINT_DOCUMENT, page=1, sha256="source")

    records = parse_enroute_key_points(
        "W568ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033H166"
        "ABVILN29\u00b038\u203230\u2033E119\u00b018\u203254\u2033",
        source,
    )

    assert [
        (record.ident, record.latitude, record.longitude, record.source)
        for record in records
    ] == [
        ("ABTUD", pytest.approx(27.964722), pytest.approx(112.136944), source),
        ("ABVIL", pytest.approx(29.641667), pytest.approx(119.315000), source),
    ]


def test_parse_enroute_key_points_accepts_local_ocr_dms_separator_damage() -> None:
    source = SourceRef(ENROUTE_KEY_POINT_DOCUMENT, page=1, sha256="source")

    records = parse_enroute_key_points(
        "ABTUBN36锟斤拷00'02\"E117锟斤拷22'04\"A593W568",
        source,
    )

    assert [
        (record.ident, record.latitude, record.longitude, record.source)
        for record in records
    ] == [
        ("ABTUB", pytest.approx(36.000556), pytest.approx(117.367778), source),
    ]


def test_parse_enroute_key_points_uses_geometry_for_local_ocr_cells() -> None:
    source = SourceRef(ENROUTE_KEY_POINT_DOCUMENT, page=1, sha256="source")

    records = parse_enroute_key_points(
        "\n".join((
            "ABTUB[[102, 150, 162, 168]]",
            "N36\ufffd\ufffd00'02\"[[216, 140, 298, 158]]",
            "E117\ufffd\ufffd22'04\"[[216, 159, 298, 174]]",
            "A593W568[[362, 150, 449, 168]]",
        )),
        source,
    )

    assert [
        (record.ident, record.latitude, record.longitude, record.source)
        for record in records
    ] == [
        ("ABTUB", pytest.approx(36.000556), pytest.approx(117.367778), source),
    ]


def test_parse_enroute_navaids_uses_table_cells_when_local_ocr_loses_degree_signs() -> None:
    source = SourceRef(ENROUTE_NAVAID_DOCUMENT, page=1, sha256="source")

    records = parse_enroute_navaids(
        "\n".join((
            "KQS[[192, 304, 232, 319]]",
            "112.1MHz[[256, 299, 336, 313]]",
            "N41\ufffd\ufffd15'38\"[[433, 299, 512, 313]]",
            "1188[[551, 305, 591, 320]]",
            "VOR/DME[[92, 317, 167, 331]]",
            "CH58X[[267, 317, 325, 331]]",
            "E080\ufffd\ufffd19'34\"[[433, 317, 514, 331]]",
        )),
        source,
    )

    assert len(records) == 1
    assert (
        records[0].kind,
        records[0].ident,
        records[0].frequency,
        records[0].latitude,
        records[0].longitude,
        records[0].elevation_meters,
        records[0].source,
    ) == (
        "VOR",
        "KQS",
        112.1,
        pytest.approx(41.260556),
        pytest.approx(80.326111),
        1188.0,
        source,
    )


def test_load_enroute_key_point_evidence_requires_complete_hashed_cache(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache = _cache(
        root,
        {
            1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033",
            2: "ABVILN29\u00b038\u203230\u2033E119\u00b018\u203254\u2033",
        },
    )

    records, report = load_enroute_key_point_evidence(root, cache)

    assert [(record.ident, record.source.page) for record in records] == [
        ("ABTUD", 1),
        ("ABVIL", 2),
    ]
    assert report["pages"] == 2
    assert report["parsed_records"] == 2

    (cache / "enr-4.4" / "page-0002.json").unlink()

    with pytest.raises(GeneralDocumentCacheError, match="incomplete"):
        load_enroute_key_point_evidence(root, cache)


def test_load_enroute_key_point_evidence_rejects_stale_source_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache = _cache(
        root,
        {1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033"},
    )
    source = root / ENROUTE_KEY_POINT_DOCUMENT
    source.write_bytes(b"changed-source-pdf")

    with pytest.raises(GeneralDocumentCacheError, match="SHA-256"):
        load_enroute_key_point_evidence(root, cache)


def test_load_enroute_key_point_evidence_accepts_explicit_cache_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache = _cache(
        root,
        {1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033"},
        directory="enr-4.4-rerun",
    )

    records, report = load_enroute_key_point_evidence(
        root,
        cache,
        cache_directory="enr-4.4-rerun",
    )

    assert [(record.ident, record.source.page) for record in records] == [
        ("ABTUD", 1),
    ]
    assert report["parsed_records"] == 1


def test_audit_enroute_key_point_ocr_rerun_reports_cache_agreement(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache_root = _cache(
        root,
        {1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033"},
    )
    _cache(
        root,
        {1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033"},
        directory="enr-4.4-rerun",
    )

    report = audit_enroute_key_point_ocr_rerun(
        root,
        cache_root / "enr-4.4",
        cache_root / "enr-4.4-rerun",
    )

    assert report["diagnostic"] == "enroute-key-point-ocr-rerun-audit-v1"
    assert report["evidence_only"] is True
    assert report["comparison"] == {
        "consistent": True,
        "agreement_ratio": 1.0,
        "projection_allowed": False,
        "reason": (
            "OCR rerun is diagnostic evidence only; it must not replace the "
            "canonical cache or enter a candidate build without a separate "
            "source-backed acceptance decision"
        ),
    }
    assert report["records"] == {
        "agreed": 1,
        "canonical_only": 0,
        "rerun_only": 0,
        "differences_by_page": [],
    }
    assert report["source_fir_region_resolution"]["polygons_loaded"] == 0
    assert report["source_fir_region_resolution"]["rerun"] == {"outside": 1}


def test_audit_enroute_key_point_ocr_rerun_allows_explicit_page_subset(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache_root = _cache(
        root,
        {
            1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033",
            2: "ABVILN29\u00b038\u203230\u2033E119\u00b018\u203254\u2033",
        },
        page_count=2,
    )
    _cache(
        root,
        {1: "ABTUDN27\u00b057\u203253\u2033E112\u00b008\u203213\u2033"},
        directory="enr-4.4-rerun",
        page_count=2,
    )

    report = audit_enroute_key_point_ocr_rerun(
        root,
        cache_root / "enr-4.4",
        cache_root / "enr-4.4-rerun",
        allow_partial_rerun=True,
    )

    assert report["comparison"]["consistent"] is True
    assert report["scope"] == {
        "rerun_complete": False,
        "selected_pages": [1],
    }
    assert report["records"] == {
        "agreed": 1,
        "canonical_only": 0,
        "rerun_only": 0,
        "differences_by_page": [],
    }


def test_load_enroute_navaid_evidence_requires_complete_hashed_cache(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    source = root / ENROUTE_NAVAID_DOCUMENT
    source.parent.mkdir(parents=True)
    source.write_bytes(b"source-pdf")
    cache = root.parent / "ocr-cache" / "enr-4.1-navaids"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": ENROUTE_NAVAID_DOCUMENT,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(json.dumps(_payload("\n".join((
        "KQS[[192, 304, 232, 319]]",
        "112.1MHz[[256, 299, 336, 313]]",
        "N41\ufffd\ufffd15'38\"[[433, 299, 512, 313]]",
        "1188[[551, 305, 591, 320]]",
        "VOR/DME[[92, 317, 167, 331]]",
        "E080\ufffd\ufffd19'34\"[[433, 317, 514, 331]]",
    )))), encoding="utf-8")

    records, report = load_enroute_navaid_evidence(root, cache.parent)

    assert [(item.ident, item.source.page) for item in records] == [("KQS", 1)]
    assert report["parsed_records"] == 1


def test_load_enroute_navaid_evidence_accepts_an_explicit_cache_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    cache = _navaid_cache(
        root,
        "enr-4.1-navaids-rerun",
        {1: _navaid_markdown("KQS")},
        page_count=1,
    )

    records, report = load_enroute_navaid_evidence(
        root,
        cache.parent,
        cache_directory=cache.name,
    )

    assert [(item.ident, item.source.page) for item in records] == [("KQS", 1)]
    assert report["parsed_records"] == 1


def test_audit_enroute_navaid_ocr_rerun_compares_partial_same_source_cache(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    canonical = _navaid_cache(
        root,
        "enr-4.1-navaids",
        {1: _navaid_markdown("KQS"), 2: _navaid_markdown("DNY")},
        page_count=2,
    )
    rerun = _navaid_cache(
        root,
        "enr-4.1-navaids-rerun",
        {2: _navaid_markdown("DNY")},
        page_count=2,
    )

    report = audit_enroute_navaid_ocr_rerun(root, canonical, rerun)

    assert report["diagnostic"] == "enroute-navaid-ocr-rerun-audit-v1"
    assert report["evidence_only"] is True
    assert report["canonical"]["parsed_records"] == 2
    assert report["canonical"]["selected_pages_parsed_records"] == 1
    assert report["rerun"]["selected_pages"] == [2]
    assert report["rerun"]["parsed_records"] == 1
    assert report["comparison"] == {
        "consistent": True,
        "agreement_ratio": 1.0,
        "selected_pages": [2],
    }
    assert report["records"]["agreed"] == 1
    assert report["records"]["canonical_only"] == 0
    assert report["records"]["rerun_only"] == 0


def test_audit_enroute_navaid_ocr_rerun_rejects_incomplete_canonical_cache(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    canonical = _navaid_cache(
        root,
        "enr-4.1-navaids",
        {1: _navaid_markdown("KQS")},
        page_count=2,
    )
    rerun = _navaid_cache(
        root,
        "enr-4.1-navaids-rerun",
        {1: _navaid_markdown("KQS")},
        page_count=2,
    )

    with pytest.raises(GeneralDocumentCacheError, match="incomplete"):
        audit_enroute_navaid_ocr_rerun(root, canonical, rerun)
