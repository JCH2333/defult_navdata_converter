"""Run a fixed local OCR runtime repeatedly without retaining OCR text."""

from __future__ import annotations

import hashlib
import json
import locale
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .ocr_runtime import resolve_runtime_profile


class OcrRuntimeProbeError(ValueError):
    """Raised when a repeatability probe cannot inspect a real OCR result."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _resolve_command(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    resolved = shutil.which(value)
    if resolved is None:
        raise OcrRuntimeProbeError(f"找不到 OCR 命令: {value}")
    return Path(resolved).resolve()


def _decode_json_stdout(value: bytes) -> tuple[object, str]:
    encodings = ("utf-8-sig", locale.getpreferredencoding(False))
    errors: list[UnicodeDecodeError] = []
    for encoding in dict.fromkeys(encodings):
        try:
            return json.loads(value.decode(encoding)), encoding
        except UnicodeDecodeError as error:
            errors.append(error)
    if errors:
        raise errors[-1]
    raise OcrRuntimeProbeError("OCR 输出无法解码")


def _semantic_document(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise OcrRuntimeProbeError("OCR 输出中的文档项无效")
    markdown = value.get("markdown")
    if not isinstance(markdown, str):
        raise OcrRuntimeProbeError("OCR 输出中的文档项缺少 Markdown")
    result: dict[str, object] = {
        "markdown_sha256": _sha256(markdown.encode("utf-8")),
    }
    for field in ("page", "total_pages", "has_more"):
        if field in value:
            result[field] = value[field]
    return result


def _semantic_payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise OcrRuntimeProbeError("OCR 输出必须是 JSON 对象")
    data = value.get("data")
    if not isinstance(data, Mapping):
        raise OcrRuntimeProbeError("OCR 输出缺少数据对象")
    documents = data.get("documents")
    if not isinstance(documents, list):
        raise OcrRuntimeProbeError("OCR 输出缺少文档列表")
    meta = value.get("meta")
    if not isinstance(meta, Mapping):
        raise OcrRuntimeProbeError("OCR 输出缺少元数据")
    return {
        "contract_version": value.get("contract_version"),
        "ok": value.get("ok"),
        "error": value.get("error"),
        "meta": {
            "layer": meta.get("layer"),
            "backend": meta.get("backend"),
        },
        "documents": [_semantic_document(document) for document in documents],
    }


def _run(
    command: Sequence[str],
    *,
    timeout_seconds: int,
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
        env=dict(environment),
    )


def run_ocr_runtime_probe(
    pdf: Path,
    runtime_profile_file: Path,
    *,
    ocr_command: str = "ocr-skill",
    runs: int = 2,
    timeout_seconds: int = 300,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = _run,
) -> dict[str, object]:
    """Repeat ``ocr-skill extract`` and compare text-free semantic summaries."""
    if runs < 2:
        raise OcrRuntimeProbeError("OCR 重复性探针至少需要两次运行")
    if timeout_seconds <= 0:
        raise OcrRuntimeProbeError("OCR 超时时间必须为正数")
    pdf = pdf.expanduser().resolve()
    if not pdf.is_file():
        raise OcrRuntimeProbeError(f"找不到 OCR PDF: {pdf}")
    runtime_profile_file = runtime_profile_file.expanduser().resolve()
    runtime_profile = resolve_runtime_profile("", runtime_profile_file)
    command_path = _resolve_command(ocr_command)
    environment = dict(os.environ)
    environment["OCR_BACKEND"] = "llamacpp"
    items: list[dict[str, object]] = []
    semantic_hashes: list[str] = []
    for index in range(1, runs + 1):
        completed = runner(
            [str(command_path), "extract", str(pdf), "--json"],
            timeout_seconds=timeout_seconds,
            environment=environment,
        )
        raw_stdout = bytes(completed.stdout)
        raw_stderr = bytes(completed.stderr)
        item: dict[str, object] = {
            "run": index,
            "exit_code": completed.returncode,
            "raw_stdout_sha256": _sha256(raw_stdout),
            "raw_stderr_sha256": _sha256(raw_stderr),
        }
        try:
            payload, encoding = _decode_json_stdout(raw_stdout)
            semantic = _semantic_payload(payload)
            item["semantic_sha256"] = _canonical_sha256(semantic)
            item["document_count"] = len(semantic["documents"])
            item["backend"] = semantic["meta"]["backend"]
            item["ok"] = semantic["ok"]
            item["error_present"] = semantic["error"] is not None
            item["json_encoding"] = encoding
            semantic_hashes.append(item["semantic_sha256"])
        except (UnicodeDecodeError, json.JSONDecodeError, OcrRuntimeProbeError) as error:
            item["parse_error"] = str(error)
        items.append(item)
    all_succeeded = all(
        item.get("exit_code") == 0
        and item.get("ok") is True
        and item.get("backend") == "llamacpp"
        and not item.get("error_present")
        and "parse_error" not in item
        for item in items
    )
    semantic_equal = len(semantic_hashes) == runs and len(set(semantic_hashes)) == 1
    return {
        "diagnostic": "ocr-runtime-probe-v1",
        "read_only": True,
        "reference_records_read": False,
        "fenix_records_read": False,
        "model_mutated": False,
        "projection_changed": False,
        "ocr_text_written": False,
        "source": {
            "pdf": str(pdf),
            "pdf_sha256": _sha256(pdf.read_bytes()),
            "ocr_command": str(command_path),
            "ocr_command_sha256": _sha256(command_path.read_bytes()),
            "runtime_profile_file": str(runtime_profile_file),
            "runtime_profile_file_sha256": _sha256(runtime_profile_file.read_bytes()),
            "runtime_profile": runtime_profile,
            "backend": "llamacpp",
            "runs": runs,
            "timeout_seconds": timeout_seconds,
        },
        "runs": items,
        "summary": {
            "all_runs_succeeded": all_succeeded,
            "semantic_outputs_equal": semantic_equal,
            "raw_stdout_equal": len({item["raw_stdout_sha256"] for item in items}) == 1,
            "repeatable": all_succeeded and semantic_equal,
        },
    }


def write_ocr_runtime_probe(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
