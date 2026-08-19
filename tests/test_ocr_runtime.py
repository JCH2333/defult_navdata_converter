import json
import subprocess
from pathlib import Path

import pytest

from fenix_default_navdata.ocr_runtime import (
    OcrRuntimeProfileError,
    resolve_runtime_profile,
)
from fenix_default_navdata.ocr_runtime_probe import run_ocr_runtime_probe


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


def test_ocr_runtime_probe_compares_markdown_not_wrapped_content(
    tmp_path: Path,
    monkeypatch,
) -> None:
    descriptor = tmp_path / "runtime-profile.json"
    descriptor.write_text(json.dumps(_descriptor()), encoding="utf-8")
    pdf = tmp_path / "chart.pdf"
    pdf.write_bytes(b"%PDF-test")
    command = tmp_path / "ocr-skill.exe"
    command.write_bytes(b"test executable")
    monkeypatch.setattr(
        "fenix_default_navdata.ocr_runtime_probe._resolve_command",
        lambda _value: command,
    )
    calls = 0

    def runner(*_args, **_kwargs) -> subprocess.CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        payload = {
            "contract_version": "1.0.0",
            "ok": True,
            "data": {
                "documents": [{
                    "content": f"UNTRUSTED-OCR-CONTENT nonce-{calls}",
                    "markdown": "IAF TEST",
                    "page": 1,
                    "total_pages": 1,
                    "has_more": False,
                }],
            },
            "error": None,
            "meta": {
                "layer": "extract",
                "backend": "llamacpp",
                "elapsed_ms": calls,
            },
        }
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload).encode("utf-8"),
            stderr=b"",
        )

    report = run_ocr_runtime_probe(
        pdf,
        descriptor,
        ocr_command=str(command),
        runner=runner,
    )

    assert report["summary"] == {
        "all_runs_succeeded": True,
        "semantic_outputs_equal": True,
        "raw_stdout_equal": False,
        "repeatable": True,
    }
    assert report["ocr_text_written"] is False


def test_ocr_runtime_probe_accepts_local_console_json_encoding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    descriptor = tmp_path / "runtime-profile.json"
    descriptor.write_text(json.dumps(_descriptor()), encoding="utf-8")
    pdf = tmp_path / "chart.pdf"
    pdf.write_bytes(b"%PDF-test")
    command = tmp_path / "ocr-skill.exe"
    command.write_bytes(b"test executable")
    monkeypatch.setattr(
        "fenix_default_navdata.ocr_runtime_probe._resolve_command",
        lambda _value: command,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.ocr_runtime_probe.locale.getpreferredencoding",
        lambda _flag: "gbk",
    )
    payload = {
        "contract_version": "1.0.0",
        "ok": True,
        "data": {"documents": [{"markdown": "进近", "page": 1}]},
        "error": None,
        "meta": {"layer": "extract", "backend": "llamacpp"},
    }

    def runner(*_args, **_kwargs) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False).encode("gbk"),
            stderr=b"",
        )

    report = run_ocr_runtime_probe(
        pdf,
        descriptor,
        ocr_command=str(command),
        runner=runner,
    )

    assert report["summary"]["repeatable"] is True
    assert [item["json_encoding"] for item in report["runs"]] == ["gbk", "gbk"]
