"""Load verified local OCR runtime descriptors for reusable cache builds."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Mapping


class OcrRuntimeProfileError(ValueError):
    """Raised when a local OCR runtime descriptor is incomplete or inconsistent."""


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MODEL_NAME = re.compile(r"[A-Za-z0-9._-]+\Z")
_LLAMA_BUILD = re.compile(r"b[0-9]+\Z")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OcrRuntimeProfileError(f"OCR 运行时描述缺少 {field}")
    return value.strip()


def _sha256(value: object, field: str) -> str:
    digest = _text(value, field).lower()
    if _SHA256.fullmatch(digest) is None:
        raise OcrRuntimeProfileError(f"OCR 运行时描述中的 {field} 不是 SHA-256")
    return digest


def _temperature(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise OcrRuntimeProfileError("OCR 运行时描述中的温度无效")
    temperature = float(value)
    if not math.isfinite(temperature):
        raise OcrRuntimeProfileError("OCR 运行时描述中的温度无效")
    return format(temperature, "g")


def _profile_from_descriptor(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != 1:
        raise OcrRuntimeProfileError("不支持的 OCR 运行时描述版本")
    model_name = _text(value.get("model_name"), "模型名称").lower()
    if _MODEL_NAME.fullmatch(model_name) is None:
        raise OcrRuntimeProfileError("OCR 运行时描述中的模型名称无效")
    llama_build = _text(value.get("llama_build"), "llama 构建号").lower()
    if _LLAMA_BUILD.fullmatch(llama_build) is None:
        raise OcrRuntimeProfileError("OCR 运行时描述中的 llama 构建号无效")
    seed = value.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise OcrRuntimeProfileError("OCR 运行时描述中的随机种子无效")
    expected = (
        f"{model_name}-llama-{llama_build}-seed{seed}-temp{_temperature(value.get('temperature'))}"
        f"-{_sha256(value.get('model_sha256'), '模型 SHA-256')}"
        f"-{_sha256(value.get('mmproj_sha256'), '视觉投影 SHA-256')}"
    )
    if _text(value.get("runtime_profile"), "运行时标识") != expected:
        raise OcrRuntimeProfileError("OCR 运行时描述与模型指纹不一致")
    return expected


def resolve_runtime_profile(
    runtime_profile: str,
    runtime_profile_file: Path | None,
) -> str:
    """Return a manual profile or one verified from the server launcher output."""
    profile = runtime_profile.strip()
    if runtime_profile_file is None:
        return profile
    if profile:
        raise OcrRuntimeProfileError(
            "--runtime-profile 与 --runtime-profile-file 不能同时使用"
        )
    path = runtime_profile_file.expanduser().resolve()
    if not path.is_file():
        raise OcrRuntimeProfileError(f"找不到 OCR 运行时描述文件: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise OcrRuntimeProfileError(
            f"OCR 运行时描述不是有效 JSON: {path}"
        ) from error
    if not isinstance(payload, Mapping):
        raise OcrRuntimeProfileError("OCR 运行时描述必须是对象")
    return _profile_from_descriptor(payload)
