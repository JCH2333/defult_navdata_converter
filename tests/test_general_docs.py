import hashlib
import json
from pathlib import Path

import pytest

from fenix_default_navdata.general_docs import (
    ENROUTE_KEY_POINT_DOCUMENT,
    GeneralDocumentCacheError,
    load_enroute_key_point_evidence,
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
