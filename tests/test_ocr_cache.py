import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

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


def test_run_ocr_retries_transient_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image = tmp_path / "page-0001.png"
    image.write_bytes(b"png")
    responses = iter([
        SimpleNamespace(returncode=1, stdout="", stderr="connection refused"),
        SimpleNamespace(returncode=0, stdout=json.dumps(_payload("ok")), stderr=""),
    ])

    monkeypatch.setattr(ocr_cache.subprocess, "run", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(ocr_cache.time, "sleep", lambda _: None)

    payload = ocr_cache._run_ocr(
        image=image,
        command="ocr-skill",
        backend="llamacpp",
        mode="markdown",
        timeout_seconds=1,
        retries=1,
    )

    assert payload == _payload("ok")


def test_build_ocr_cache_is_resumable_and_uses_source_relative_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pdf = _source(tmp_path)
    rendered: list[int] = []
    ocred: list[str] = []

    monkeypatch.setattr(ocr_cache, "_pdf_page_count", lambda _: 3)

    def render(_: Path, page: int, destination: Path, __: float, ___: str) -> None:
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
        "recognition": {
            "command": "ocr-skill",
            "backend": "llamacpp",
            "mode": "ocr",
            "image_profile": "original",
        },
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
        lambda _, __, destination, ___, ____: destination.write_bytes(b"png"),
    )
    monkeypatch.setattr(ocr_cache, "_run_ocr", lambda *_args, **_kwargs: _payload("ok"))

    with pytest.raises(OcrCacheError, match="不得写入"):
        build_ocr_cache(pdf, root / "cache", source_root=root)

    cache = tmp_path / "cache" / "enr-4.1"
    build_ocr_cache(pdf, cache, source_root=root)
    pdf.write_bytes(b"changed")

    with pytest.raises(OcrCacheError, match="不匹配"):
        build_ocr_cache(pdf, cache, source_root=root)


def test_build_ocr_cache_rejects_recognition_setting_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pdf = _source(tmp_path)
    monkeypatch.setattr(ocr_cache, "_pdf_page_count", lambda _: 1)
    monkeypatch.setattr(
        ocr_cache,
        "_render_page",
        lambda _, __, destination, ___, ____: destination.write_bytes(b"png"),
    )
    monkeypatch.setattr(ocr_cache, "_run_ocr", lambda *_args, **_kwargs: _payload("ok"))

    cache = tmp_path / "cache" / "enr-4.1"
    build_ocr_cache(pdf, cache, source_root=root)

    with pytest.raises(OcrCacheError, match="识别设置"):
        build_ocr_cache(
            pdf,
            cache,
            source_root=root,
            image_profile="autocontrast-grayscale",
        )


def test_build_ocr_cache_accepts_legacy_default_recognition_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pdf = _source(tmp_path)
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    cache = tmp_path / "cache" / "enr-4.1"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": "GeneralDoc/航路_4.1无线电导航设施——航路.pdf",
        "source_sha256": source_hash,
        "page_count": 1,
        "renderer": "pypdfium2",
        "render_scale": 2.0,
    }), encoding="utf-8")
    monkeypatch.setattr(ocr_cache, "_pdf_page_count", lambda _: 1)
    monkeypatch.setattr(
        ocr_cache,
        "_render_page",
        lambda _, __, destination, ___, ____: destination.write_bytes(b"png"),
    )
    monkeypatch.setattr(ocr_cache, "_run_ocr", lambda *_args, **_kwargs: _payload("ok"))

    report = build_ocr_cache(pdf, cache, source_root=root)

    assert report.processed_pages == 1
