"""Bounded local llama.cpp OCR requests for auditable evidence caches."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DIRECT_BACKEND = "llamacpp-direct"
DIRECT_ADAPTER = "builtin-llamacpp-openai-v1"
DIRECT_COMMAND = "builtin:llama.cpp-openai-v1"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MODEL = "ocr"
DEFAULT_URL = "http://127.0.0.1:8090"
_PROMPTS = {
    "markdown": "<|grounding|>Convert the document to markdown.",
    "ocr": "<|grounding|>OCR this image.",
    "free": "Free OCR.",
    "figure": "Parse the figure.",
}


class LlamaCppOcrError(ValueError):
    """Raised when the bounded local llama.cpp OCR request fails."""


def _server_url() -> str:
    return (os.environ.get("OCR_LLAMA_URL") or DEFAULT_URL).rstrip("/")


def _model_name() -> str:
    return os.environ.get("OCR_LLAMA_MODEL") or DEFAULT_MODEL


def _message_content(payload: object) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LlamaCppOcrError(
            f"llama.cpp 响应缺少 choices[0].message.content: {str(payload)[:300]}"
        ) from error
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or "")
            if isinstance(item, dict)
            else str(item)
            for item in content
        )
    return str(content)


def run_llamacpp_ocr(
    image: Path,
    *,
    mode: str,
    timeout_seconds: int,
    max_tokens: int,
) -> dict[str, object]:
    """Run one bounded, deterministic OCR request through the local server."""
    if mode not in _PROMPTS:
        raise LlamaCppOcrError(f"不支持的 llama.cpp OCR 模式: {mode}")
    if timeout_seconds < 1:
        raise LlamaCppOcrError("llama.cpp OCR 超时必须为正整数秒")
    if max_tokens < 1:
        raise LlamaCppOcrError("llama.cpp OCR max_tokens 必须为正整数")
    if not image.is_file():
        raise LlamaCppOcrError(f"找不到 OCR 图像: {image}")

    mime, _ = mimetypes.guess_type(str(image))
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    data_url = f"data:{mime or 'image/png'};base64,{encoded}"
    request_payload: dict[str, Any] = {
        "model": _model_name(),
        "temperature": 0.0,
        "seed": 2608,
        "top_k": 1,
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": _PROMPTS[mode]},
            ],
        }],
    }
    try:
        request = Request(
            f"{_server_url()}/v1/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace") if error.fp else str(error)
        raise LlamaCppOcrError(
            f"llama.cpp HTTP {error.code}: {detail[:500]}"
        ) from error
    except URLError as error:
        raise LlamaCppOcrError(
            f"无法连接本地 llama.cpp OCR 服务 {_server_url()}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise LlamaCppOcrError("llama.cpp 返回的不是有效 JSON") from error
    except OSError as error:
        raise LlamaCppOcrError(f"llama.cpp OCR 请求失败: {error}") from error

    return {
        "ok": True,
        "data": {
            "documents": [{
                "source_kind": "image",
                "markdown": _message_content(response_payload),
            }],
        },
        "meta": {
            "backend": DIRECT_BACKEND,
            "adapter": DIRECT_ADAPTER,
            "max_tokens": max_tokens,
        },
    }
