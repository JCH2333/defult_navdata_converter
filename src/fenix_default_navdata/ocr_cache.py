"""Build resumable, source-hashed OCR caches for raw 424 PDF evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pypdfium2
from PIL import ImageOps


_CACHE_SCHEMA_VERSION = 1
_IMAGE_PROFILES = ("original", "autocontrast-grayscale")
_DEFAULT_OCR_COMMAND = "ocr-skill"
_DEFAULT_OCR_BACKEND = "llamacpp"
_DEFAULT_OCR_MODE = "ocr"
_DEFAULT_IMAGE_PROFILE = "original"


class OcrCacheError(ValueError):
    """Raised when a reusable OCR cache cannot be built or verified."""


@dataclass(frozen=True)
class OcrCacheBuild:
    """Summary of one deterministic, resumable OCR cache build."""

    cache: Path
    source_file: str
    source_sha256: str
    page_count: int
    selected_pages: tuple[int, ...]
    processed_pages: int
    reused_pages: int
    complete: bool

    def to_report(self) -> dict[str, object]:
        return {
            "cache": str(self.cache),
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "page_count": self.page_count,
            "selected_pages": list(self.selected_pages),
            "processed_pages": self.processed_pages,
            "reused_pages": self.reused_pages,
            "complete": self.complete,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_file(source_pdf: Path, source_root: Path) -> str:
    try:
        return source_pdf.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError as error:
        raise OcrCacheError(
            "PDF 必须位于 --source-root 指定的原始数据目录内"
        ) from error


def _pdf_page_count(source_pdf: Path) -> int:
    document = pypdfium2.PdfDocument(str(source_pdf))
    try:
        return len(document)
    finally:
        document.close()


def _render_page(
    source_pdf: Path,
    page_number: int,
    destination: Path,
    render_scale: float,
    image_profile: str,
) -> None:
    document = pypdfium2.PdfDocument(str(source_pdf))
    try:
        page = document[page_number - 1]
        try:
            bitmap = page.render(scale=render_scale)
            try:
                image = bitmap.to_pil()
                if image_profile == "original":
                    prepared = image
                elif image_profile == "autocontrast-grayscale":
                    prepared = ImageOps.autocontrast(image.convert("L"))
                else:
                    raise OcrCacheError(f"不支持的 OCR 图像预处理: {image_profile}")
                prepared.save(destination, format="PNG")
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


def _read_payload(payload: dict[str, object]) -> dict[str, object] | None:
    try:
        document = payload["data"]["documents"][0]
        markdown = document["markdown"]
    except (IndexError, KeyError, TypeError):
        return None
    if payload.get("ok") is not True or not isinstance(markdown, str):
        return None
    return payload


def _read_page_payload(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _read_payload(payload)


def _run_ocr(
    image: Path,
    *,
    command: str,
    backend: str,
    mode: str,
    timeout_seconds: int,
    retries: int = 0,
) -> dict[str, object]:
    if retries < 0:
        raise OcrCacheError("OCR 重试次数不能为负数")
    arguments = [
        command,
        "extract",
        str(image),
        "--backend",
        backend,
        "--mode",
        mode,
        "--json",
    ]
    last_error = ""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                arguments,
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise OcrCacheError(f"找不到 OCR 命令: {command}") from error
        except subprocess.TimeoutExpired:
            last_error = f"OCR 单页超时（{timeout_seconds} 秒）: {image.name}"
        else:
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().replace("\r", " ")
                last_error = (
                    f"OCR 失败（退出代码 {result.returncode}）: "
                    f"{image.name}; {detail[:400]}"
                )
            else:
                try:
                    payload = json.loads(result.stdout)
                except json.JSONDecodeError:
                    last_error = f"OCR 未返回 JSON: {image.name}"
                else:
                    if isinstance(payload, dict) and _read_payload(payload) is not None:
                        return payload
                    last_error = f"OCR 页面无有效 Markdown: {image.name}"
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise OcrCacheError(f"{last_error}（已尝试 {retries + 1} 次）")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _selected_pages(
    page_count: int,
    first_page: int | None,
    last_page: int | None,
) -> tuple[int, ...]:
    start = first_page or 1
    end = last_page or page_count
    if start < 1 or end < start or end > page_count:
        raise OcrCacheError(
            f"无效页码范围: first={start}, last={end}, total={page_count}"
        )
    return tuple(range(start, end + 1))


def _prepare_manifest(
    cache: Path,
    *,
    source_file: str,
    source_sha256: str,
    page_count: int,
    render_scale: float,
    command: str,
    backend: str,
    mode: str,
    image_profile: str,
    runtime_profile: str,
) -> None:
    manifest_path = cache / "manifest.json"
    expected = {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "page_count": page_count,
    }
    recognition = {
        "command": command,
        "backend": backend,
        "mode": mode,
        "image_profile": image_profile,
    }
    if runtime_profile:
        recognition["runtime_profile"] = runtime_profile
    if manifest_path.is_file():
        try:
            current = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as error:
            raise OcrCacheError(
                f"OCR 缓存清单不是有效 JSON: {manifest_path}"
            ) from error
        if not isinstance(current, dict):
            raise OcrCacheError("OCR 缓存清单必须是对象")
        for key, value in expected.items():
            if current.get(key) != value:
                raise OcrCacheError(
                    f"OCR 缓存与当前原始 PDF 不匹配: {key}"
                )
        if (
            current.get("renderer") != "pypdfium2"
            or current.get("render_scale") != render_scale
        ):
            raise OcrCacheError(
                "OCR 缓存的页面渲染设置与本次识别不一致"
            )
        current_recognition = current.get("recognition")
        if current_recognition is None:
            legacy_recognition = {
                "command": _DEFAULT_OCR_COMMAND,
                "backend": _DEFAULT_OCR_BACKEND,
                "mode": _DEFAULT_OCR_MODE,
                "image_profile": _DEFAULT_IMAGE_PROFILE,
            }
            if recognition != legacy_recognition:
                raise OcrCacheError(
                    "旧版 OCR 缓存只能按原始默认识别设置复用"
                )
        elif current_recognition != recognition:
            raise OcrCacheError(
                "OCR 缓存识别设置与本次重跑不一致"
            )
        return
    _write_json(
        manifest_path,
        {
            **expected,
            "renderer": "pypdfium2",
            "render_scale": render_scale,
            "recognition": recognition,
        },
    )


def build_ocr_cache(
    source_pdf: Path,
    cache: Path,
    *,
    source_root: Path,
    command: str = _DEFAULT_OCR_COMMAND,
    backend: str = _DEFAULT_OCR_BACKEND,
    mode: str = _DEFAULT_OCR_MODE,
    timeout_seconds: int = 180,
    render_scale: float = 2.0,
    first_page: int | None = None,
    last_page: int | None = None,
    force: bool = False,
    image_profile: str = _DEFAULT_IMAGE_PROFILE,
    runtime_profile: str = "",
    retries: int = 0,
) -> OcrCacheBuild:
    """Render physical PDF pages, OCR each page, and retain resumable evidence."""
    source_pdf = source_pdf.expanduser().resolve()
    source_root = source_root.expanduser().resolve()
    cache = cache.expanduser().resolve()
    if not source_pdf.is_file():
        raise OcrCacheError(f"找不到原始 PDF: {source_pdf}")
    if not source_root.is_dir():
        raise OcrCacheError(f"找不到原始数据目录: {source_root}")
    if cache == source_root or source_root in cache.parents:
        raise OcrCacheError("OCR 缓存不得写入 424 原始数据目录")
    if timeout_seconds < 1:
        raise OcrCacheError("OCR 超时必须为正整数秒")
    if retries < 0:
        raise OcrCacheError("OCR 重试次数不能为负数")
    if render_scale <= 0:
        raise OcrCacheError("渲染比例必须大于零")
    if image_profile not in _IMAGE_PROFILES:
        raise OcrCacheError(f"不支持的 OCR 图像预处理: {image_profile}")
    if runtime_profile and not runtime_profile.strip():
        raise OcrCacheError("OCR 运行时标识不能只包含空白字符")

    source_file = _source_file(source_pdf, source_root)
    source_sha256 = _sha256(source_pdf)
    page_count = _pdf_page_count(source_pdf)
    if page_count < 1:
        raise OcrCacheError("PDF 没有可识别页面")
    selected = _selected_pages(page_count, first_page, last_page)

    cache.mkdir(parents=True, exist_ok=True)
    _prepare_manifest(
        cache,
        source_file=source_file,
        source_sha256=source_sha256,
        page_count=page_count,
        render_scale=render_scale,
        command=command,
        backend=backend,
        mode=mode,
        image_profile=image_profile,
        runtime_profile=runtime_profile,
    )
    image_cache = cache / ".images"
    image_cache.mkdir(exist_ok=True)

    processed = 0
    reused = 0
    for page_number in selected:
        page_path = cache / f"page-{page_number:04d}.json"
        if not force and _read_page_payload(page_path) is not None:
            reused += 1
            continue
        image_path = image_cache / f"page-{page_number:04d}.png"
        if not image_path.is_file():
            _render_page(
                source_pdf,
                page_number,
                image_path,
                render_scale,
                image_profile,
            )
        payload = _run_ocr(
            image_path,
            command=command,
            backend=backend,
            mode=mode,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        _write_json(page_path, payload)
        processed += 1

    complete = all(
        _read_page_payload(cache / f"page-{page_number:04d}.json") is not None
        for page_number in range(1, page_count + 1)
    )
    return OcrCacheBuild(
        cache=cache,
        source_file=source_file,
        source_sha256=source_sha256,
        page_count=page_count,
        selected_pages=selected,
        processed_pages=processed,
        reused_pages=reused,
        complete=complete,
    )
