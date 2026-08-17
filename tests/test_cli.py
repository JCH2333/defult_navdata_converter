import json
from pathlib import Path

from fenix_default_navdata import cli
from fenix_default_navdata.bgl import CompilerInfo


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
