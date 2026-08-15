import hashlib
import json
from pathlib import Path

import pytest

from fenix_default_navdata import ocr_cache
from fenix_default_navdata.ocr_cache import OcrCacheError, build_ocr_cache


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


def _source(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "raw"
    pdf = root / "GeneralDoc" / "航路_4.1无线电导航设施——航路.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf-source")
    return root, pdf


def test_build_ocr_cache_is_resumable_and_uses_source_relative_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pdf = _source(tmp_path)
    rendered: list[int] = []
    ocred: list[str] = []

    monkeypatch.setattr(ocr_cache, "_pdf_page_count", lambda _: 3)

    def render(_: Path, page: int, destination: Path, __: float) -> None:
        rendered.append(page)
        destination.write_bytes(f"png-{page}".encode("ascii"))

    def run(image: Path, **_: object) -> dict[str, object]:
        ocred.append(image.name)
        return _payload(f"PAGE {image.stem}")

    monkeypatch.setattr(ocr_cache, "_render_page", render)
    monkeypatch.setattr(ocr_cache, "_run_ocr", run)

    cache = tmp_path / "cache" / "enr-4.1"
    first = build_ocr_cache(
        pdf,
        cache,
        source_root=root,
        first_page=1,
        last_page=1,
    )

    assert first.source_file == "GeneralDoc/航路_4.1无线电导航设施——航路.pdf"
    assert first.source_sha256 == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert first.processed_pages == 1
    assert first.reused_pages == 0
    assert first.complete is False

    second = build_ocr_cache(pdf, cache, source_root=root)

    assert second.processed_pages == 2
    assert second.reused_pages == 1
    assert second.complete is True
    assert rendered == [1, 2, 3]
    assert ocred == ["page-0001.png", "page-0002.png", "page-0003.png"]
    assert json.loads((cache / "manifest.json").read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "source_file": "GeneralDoc/航路_4.1无线电导航设施——航路.pdf",
        "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "page_count": 3,
        "renderer": "pypdfium2",
        "render_scale": 2.0,
    }


def test_build_ocr_cache_rejects_stale_or_raw_directory_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pdf = _source(tmp_path)
    monkeypatch.setattr(ocr_cache, "_pdf_page_count", lambda _: 1)
    monkeypatch.setattr(
        ocr_cache,
        "_render_page",
        lambda _, __, destination, ___: destination.write_bytes(b"png"),
    )
    monkeypatch.setattr(ocr_cache, "_run_ocr", lambda *_args, **_kwargs: _payload("ok"))

    with pytest.raises(OcrCacheError, match="不得写入"):
        build_ocr_cache(pdf, root / "cache", source_root=root)

    cache = tmp_path / "cache" / "enr-4.1"
    build_ocr_cache(pdf, cache, source_root=root)
    pdf.write_bytes(b"changed")

    with pytest.raises(OcrCacheError, match="不匹配"):
        build_ocr_cache(pdf, cache, source_root=root)
