import json
from pathlib import Path

import pytest

from fenix_default_navdata import cli
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.model import NavModel
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_ocr_audit_compares_available_rerun_pages_without_an_extra_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def audit(
        source_root: Path,
        canonical_cache: Path,
        rerun_cache: Path,
    ) -> dict[str, object]:
        captured.update(
            source_root=source_root,
            canonical_cache=canonical_cache,
            rerun_cache=rerun_cache,
        )
        return {"comparison": {"consistent": True}}

    monkeypatch.setattr(cli, "audit_enroute_navaid_ocr_rerun", audit)

    result = cli.main([
        "ocr-audit",
        "--source-root", "raw",
        "--canonical-cache", "canonical",
        "--rerun-cache", "rerun",
    ])

    assert result == 0
    assert captured == {
        "source_root": Path("raw"),
        "canonical_cache": Path("canonical"),
        "rerun_cache": Path("rerun"),
    }


def test_iap_ocr_cache_reads_verified_runtime_profile_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model_sha256 = "a" * 64
    mmproj_sha256 = "b" * 64
    profile = (
        "deepseek-ocr-2-q8_0-llama-b10331-seed2608-temp0-"
        f"{model_sha256}-{mmproj_sha256}"
    )
    descriptor = tmp_path / "runtime-profile.json"
    descriptor.write_text(json.dumps({
        "schema_version": 1,
        "runtime_profile": profile,
        "llama_build": "b10331",
        "model_name": "deepseek-ocr-2-q8_0",
        "model_sha256": model_sha256,
        "mmproj_sha256": mmproj_sha256,
        "seed": 2608,
        "temperature": 0,
    }), encoding="utf-8")
    received: dict[str, object] = {}

    def build(*_args, **kwargs) -> dict[str, object]:
        received.update(kwargs)
        return {"processed_pages": 0}

    monkeypatch.setattr(cli, "build_iap_ocr_cache", build)

    result = cli.main([
        "iap-ocr-cache",
        "--source-root", "raw",
        "--cache-root", "cache",
        "--runtime-profile-file", str(descriptor),
        "--dry-run",
    ])

    assert result == 0
    assert received["runtime_profile"] == profile


def test_route_fragment_probe_passes_sdk_and_reader_options(monkeypatch) -> None:
    received: dict[str, object] = {}
    compiler = CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test")

    def run(output: Path, **kwargs) -> dict[str, object]:
        received["output"] = output
        received.update(kwargs)
        return {"airway_rows": []}

    monkeypatch.setattr(cli, "find_compiler", lambda explicit: compiler)
    monkeypatch.setattr(cli, "run_route_fragment_probe", run)

    result = cli.main([
        "route-fragment-probe",
        "--output", "diagnostics/probe",
        "--bglcomp", "sdk.exe",
        "--reader", "reader.exe",
        "--cache-root", "cache",
        "--build-timeout", "600",
        "--reader-timeout", "90",
    ])

    assert result == 0
    assert received == {
        "output": Path("diagnostics/probe"),
        "compiler": compiler,
        "reader": Path("reader.exe"),
        "cache_root": Path("cache"),
        "build_timeout_seconds": 600,
        "reader_timeout_seconds": 90,
    }


def test_airway_connection_shape_probe_passes_sdk_and_reader_options(monkeypatch) -> None:
    received: dict[str, object] = {}
    compiler = CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test")

    def run(output: Path, **kwargs) -> dict[str, object]:
        received["output"] = output
        received.update(kwargs)
        return {"airway_rows": []}

    monkeypatch.setattr(cli, "find_compiler", lambda explicit: compiler)
    monkeypatch.setattr(cli, "run_airway_connection_shape_probe", run)

    result = cli.main([
        "airway-connection-shape-probe",
        "--output", "diagnostics/probe",
        "--bglcomp", "sdk.exe",
        "--reader", "reader.exe",
        "--cache-root", "cache",
        "--build-timeout", "600",
        "--reader-timeout", "90",
    ])

    assert result == 0
    assert received == {
        "output": Path("diagnostics/probe"),
        "compiler": compiler,
        "reader": Path("reader.exe"),
        "cache_root": Path("cache"),
        "build_timeout_seconds": 600,
        "reader_timeout_seconds": 90,
    }


def test_export_model_command_passes_source_and_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def export_intermediate_model(raw_root, output, **kwargs):
        captured["raw_root"] = raw_root
        captured["output"] = output
        captured.update(kwargs)
        return {"output": str(output)}

    monkeypatch.setattr(cli, "export_intermediate_model", export_intermediate_model)
    monkeypatch.setattr(cli, "detect_paths", lambda: type("P", (), {"raw_root": Path("raw")})())

    result = cli.main([
        "export-model",
        "--raw", "raw",
        "--output", "output/model.json.gz",
        "--pdf-cache", "pdf-cache",
    ])

    assert result == 0
    assert captured["raw_root"] == Path("raw")
    assert captured["output"] == Path("output/model.json.gz")
    assert captured["pdf_cache"] == Path("pdf-cache")


def test_build_command_loads_intermediate_model_and_skips_raw_requirement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model = NavModel(tmp_path / "raw")
    captured: dict[str, object] = {}

    def convert(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return {"status": "from-model"}

    monkeypatch.setattr(cli, "load_model", lambda path: model)
    monkeypatch.setattr(cli, "convert", convert)
    monkeypatch.setattr(
        cli,
        "detect_paths",
        lambda: type(
            "P",
            (),
            {
                "raw_root": None,
                "nav_base": Path("base"),
                "nav_jepp": Path("jepp"),
                "reference_root": None,
            },
        )(),
    )

    result = cli.main([
        "build",
        "--model", "model.json.gz",
        "--baseline-db", "official-navaids.sqlite",
        "--output", "output/candidate",
        "--nav-base", "base",
        "--nav-jepp", "jepp",
    ])

    assert result == 0
    assert captured["model"] is model
    assert captured["model_path"] == Path("model.json.gz")
    assert captured["baseline_db"] == Path("official-navaids.sqlite")
    assert captured["cycle"] == DEFAULT_CYCLE


def test_build_from_model_requires_an_official_navaid_index(monkeypatch):
    model = NavModel(Path("source"))

    monkeypatch.setattr(cli, "load_model", lambda path: model)
    monkeypatch.setattr(
        cli,
        "detect_paths",
        lambda: type(
            "P",
            (),
            {
                "raw_root": None,
                "nav_base": Path("base"),
                "nav_jepp": Path("jepp"),
                "reference_root": None,
            },
        )(),
    )

    with pytest.raises(
        SystemExit,
        match="使用 --model 构建必须传入已校验的 --baseline-db",
    ):
        cli.main([
            "build",
            "--model", "model.json.gz",
            "--output", "output/candidate",
            "--nav-base", "base",
            "--nav-jepp", "jepp",
        ])
