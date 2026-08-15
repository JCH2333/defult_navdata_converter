import hashlib
import json
from pathlib import Path

import pytest

from fenix_default_navdata.general_docs import (
    ENROUTE_NAVAID_DOCUMENT,
    ENROUTE_KEY_POINT_DOCUMENT,
    GeneralDocumentCacheError,
    load_enroute_navaid_evidence,
    load_enroute_key_point_evidence,
    parse_enroute_navaids,
    parse_enroute_key_points,
)
from fenix_default_navdata.model import SourceRef


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


def _cache(root: Path, pages: dict[int, str]) -> Path:
    source = root / ENROUTE_KEY_POINT_DOCUMENT
    source.parent.mkdir(parents=True)
    source.write_bytes(b"source-pdf")
    cache = root.parent / "ocr-cache" / "enr-4.4"
    cache.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "source_file": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "page_count": len(pages),
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
