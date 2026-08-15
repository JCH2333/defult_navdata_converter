import json
from pathlib import Path

import pytest

from fenix_default_navdata.ocr_runtime import (
    OcrRuntimeProfileError,
    resolve_runtime_profile,
)


def _descriptor() -> dict[str, object]:
    model_sha256 = "a" * 64
    mmproj_sha256 = "b" * 64
    profile = (
        "deepseek-ocr-2-q8_0-llama-b10331-seed2608-temp0-"
        f"{model_sha256}-{mmproj_sha256}"
    )
    return {
        "schema_version": 1,
        "runtime_profile": profile,
        "llama_build": "b10331",
        "model_name": "deepseek-ocr-2-q8_0",
        "model_sha256": model_sha256,
        "mmproj_sha256": mmproj_sha256,
        "seed": 2608,
        "temperature": 0.0,
    }


def test_resolve_runtime_profile_reads_verified_descriptor(tmp_path: Path) -> None:
    descriptor = _descriptor()
    path = tmp_path / "runtime-profile.json"
    path.write_text(json.dumps(descriptor), encoding="utf-8")

    assert resolve_runtime_profile("", path) == descriptor["runtime_profile"]


def test_resolve_runtime_profile_rejects_mismatched_descriptor(tmp_path: Path) -> None:
    descriptor = _descriptor()
    descriptor["runtime_profile"] = "short-profile"
    path = tmp_path / "runtime-profile.json"
    path.write_text(json.dumps(descriptor), encoding="utf-8")

    with pytest.raises(OcrRuntimeProfileError, match="模型指纹"):
        resolve_runtime_profile("", path)


def test_resolve_runtime_profile_rejects_manual_and_descriptor_together(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime-profile.json"
    path.write_text(json.dumps(_descriptor()), encoding="utf-8")

    with pytest.raises(OcrRuntimeProfileError, match="不能同时使用"):
        resolve_runtime_profile("manual", path)
