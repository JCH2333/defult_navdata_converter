import json
from pathlib import Path

import pytest

from fenix_default_navdata import cli
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.model import NavModel
from fenix_default_navdata.model_io import dump_model
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


def test_ocr_runtime_probe_writes_read_only_report(tmp_path: Path, monkeypatch) -> None:
    received: dict[str, object] = {}

    def probe(pdf: Path, runtime_profile_file: Path, **kwargs) -> dict[str, object]:
        received.update(
            pdf=pdf,
            runtime_profile_file=runtime_profile_file,
            **kwargs,
        )
        return {"summary": {"repeatable": True}}

    def write(path: Path, report: dict[str, object]) -> None:
        received["output"] = path
        received["report"] = report

    monkeypatch.setattr(cli, "run_ocr_runtime_probe", probe)
    monkeypatch.setattr(cli, "write_ocr_runtime_probe", write)

    result = cli.main([
        "ocr-runtime-probe",
        "--pdf", "chart.pdf",
        "--runtime-profile-file", "runtime-profile.json",
        "--ocr-command", "ocr-skill.exe",
        "--runs", "3",
        "--timeout-seconds", "120",
        "--output", str(tmp_path / "probe.json"),
    ])

    assert result == 0
    assert received == {
        "pdf": Path("chart.pdf"),
        "runtime_profile_file": Path("runtime-profile.json"),
        "ocr_command": "ocr-skill.exe",
        "runs": 3,
        "timeout_seconds": 120,
        "output": (tmp_path / "probe.json").resolve(),
        "report": {
            "summary": {"repeatable": True},
            "output": str((tmp_path / "probe.json").resolve()),
        },
    }


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


def test_airway_route_child_order_probe_passes_sdk_and_reader_options(
    monkeypatch,
) -> None:
    received: dict[str, object] = {}
    compiler = CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test")

    def run(output: Path, **kwargs) -> dict[str, object]:
        received["output"] = output
        received.update(kwargs)
        return {"status": "passed", "airway_rows": []}

    monkeypatch.setattr(cli, "find_compiler", lambda explicit: compiler)
    monkeypatch.setattr(cli, "run_airway_route_child_order_probe", run)

    result = cli.main([
        "airway-route-child-order-probe",
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


def test_airway_endpoint_audit_writes_requested_report(monkeypatch) -> None:
    received: dict[str, object] = {}

    monkeypatch.setattr(cli, "detect_paths", lambda: type("P", (), {
        "raw_root": Path("auto-raw"),
    })())
    monkeypatch.setattr(cli, "load_naip", lambda raw, **kwargs: received.update(
        raw=raw,
        **kwargs,
    ) or NavModel(raw))
    monkeypatch.setattr(
        cli,
        "audit_unresolved_airway_endpoints",
        lambda model: {"diagnostic": "airway-endpoint-source-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_unresolved_airway_endpoint_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "airway-endpoint-audit",
        "--output", "diagnostics/endpoints.json",
    ])

    assert result == 0
    assert received["raw"] == Path("auto-raw")
    assert received["include_terminal_documents"] is False
    assert received["output"] == Path("diagnostics/endpoints.json").resolve()


def test_airway_endpoint_card_audit_writes_requested_report(monkeypatch) -> None:
    received: dict[str, object] = {}

    monkeypatch.setattr(cli, "load_model", lambda path: received.update(
        model_path=path
    ) or NavModel(Path("model-root")))
    monkeypatch.setattr(
        cli,
        "audit_airway_endpoint_card",
        lambda raw, model, **kwargs: received.update(
            raw=raw,
            model=model,
            **kwargs,
        ) or {"diagnostic": "airway-endpoint-card-source-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_airway_endpoint_card_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "airway-endpoint-card-audit",
        "--raw", "raw",
        "--model", "output/model.json.gz",
        "--ident", "p225",
        "--output", "diagnostics/p225.json",
    ])

    assert result == 0
    assert received["raw"] == Path("raw")
    assert received["model_path"] == Path("output/model.json.gz")
    assert received["ident"] == "p225"
    assert received["output"] == Path("diagnostics/p225.json").resolve()


def test_non_designated_airway_endpoint_card_audit_writes_requested_report(
    monkeypatch,
) -> None:
    received: dict[str, object] = {}

    monkeypatch.setattr(cli, "load_model", lambda path: received.update(
        model_path=path
    ) or NavModel(Path("model-root")))
    monkeypatch.setattr(
        cli,
        "audit_non_designated_airway_endpoint_card",
        lambda raw, model, **kwargs: received.update(
            raw=raw,
            model=model,
            **kwargs,
        ) or {"diagnostic": "non-designated-airway-endpoint-card-source-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_airway_endpoint_card_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "non-designated-airway-endpoint-card-audit",
        "--raw", "raw",
        "--model", "output/model.json.gz",
        "--ident", "****",
        "--endpoint-type", "地名点",
        "--output", "diagnostics/m771.json",
    ])

    assert result == 0
    assert received["raw"] == Path("raw")
    assert received["model_path"] == Path("output/model.json.gz")
    assert received["ident"] == "****"
    assert received["endpoint_type"] == "地名点"
    assert received["output"] == Path("diagnostics/m771.json").resolve()


def test_file_convergence_audit_writes_requested_report(monkeypatch) -> None:
    received: dict[str, object] = {}

    monkeypatch.setattr(cli, "detect_paths", lambda: type("P", (), {
        "reference_root": Path("auto-reference"),
    })())
    monkeypatch.setattr(
        cli,
        "audit_file_convergence",
        lambda candidate, reference, **kwargs: received.update(
            candidate=candidate,
            reference=reference,
            **kwargs,
        ) or {"diagnostic": "file-convergence-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_file_convergence_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "file-convergence-audit",
        "--candidate", "output/r181",
        "--repeat-candidate", "output/r182",
        "--output", "diagnostics/convergence.json",
    ])

    assert result == 0
    assert received["candidate"] == Path("output/r181")
    assert received["reference"] == Path("auto-reference")
    assert received["repeat_candidate_root"] == Path("output/r182")
    assert received["output"] == Path("diagnostics/convergence.json").resolve()
    assert received["report"]["output"] == str(received["output"])


def test_model_replay_audit_fails_on_unexpected_difference(tmp_path: Path) -> None:
    baseline = NavModel(tmp_path / "raw")
    replay = NavModel(tmp_path / "raw")
    baseline.iap_coverage = {"version": 23}
    replay.iap_coverage = {"version": 24}
    baseline_path = tmp_path / "baseline.json.gz"
    replay_path = tmp_path / "replay.json.gz"
    output = tmp_path / "audit.json"
    dump_model(baseline, baseline_path)
    dump_model(replay, replay_path)

    result = cli.main([
        "model-replay-audit",
        "--baseline", str(baseline_path),
        "--replay", str(replay_path),
        "--output", str(output),
        "--fail-on-unexpected",
    ])

    assert result == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["unexpected_difference_count"] == 1


def test_airport_source_inventory_reads_model_and_writes_report(monkeypatch) -> None:
    received: dict[str, object] = {}
    model = NavModel(Path("raw"))

    monkeypatch.setattr(cli, "load_model", lambda path: received.update(
        model_path=path
    ) or model)
    monkeypatch.setattr(
        cli,
        "build_airport_source_inventory",
        lambda received_model, **kwargs: received.update(
            model=received_model,
            **kwargs,
        ) or {"diagnostic": "airport-source-inventory-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_airport_source_inventory",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "airport-source-inventory",
        "--model", "output/model.json.gz",
        "--candidate-xml", "output/china-navdata.xml",
        "--output", "diagnostics/airport-inventory.json",
    ])

    assert result == 0
    assert received["model_path"] == Path("output/model.json.gz")
    assert received["model"] is model
    assert received["candidate_xml"] == Path("output/china-navdata.xml")
    assert received["output"] == Path(
        "diagnostics/airport-inventory.json"
    ).resolve()
    assert received["report"]["output"] == str(received["output"])


def test_unclassified_procedure_audit_reads_model_and_writes_report(monkeypatch) -> None:
    received: dict[str, object] = {}
    model = NavModel(Path("raw"))

    monkeypatch.setattr(cli, "load_model", lambda path: received.update(
        model_path=path
    ) or model)
    monkeypatch.setattr(
        cli,
        "audit_unclassified_procedures",
        lambda received_model: received.update(model=received_model)
        or {"diagnostic": "unclassified-procedure-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_unclassified_procedure_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "unclassified-procedure-audit",
        "--model", "output/model.json.gz",
        "--output", "diagnostics/unclassified-procedures.json",
    ])

    assert result == 0
    assert received["model_path"] == Path("output/model.json.gz")
    assert received["model"] is model
    assert received["output"] == Path(
        "diagnostics/unclassified-procedures.json"
    ).resolve()
    assert received["report"]["output"] == str(received["output"])


def test_unclassified_procedure_card_audit_reads_exact_card_and_writes_report(
    monkeypatch,
) -> None:
    received: dict[str, object] = {}
    model = NavModel(Path("raw"))

    monkeypatch.setattr(cli, "load_model", lambda path: received.update(
        model_path=path
    ) or model)
    monkeypatch.setattr(
        cli,
        "audit_unclassified_procedure_card",
        lambda received_model, card: received.update(model=received_model, card=card)
        or {"diagnostic": "unclassified-procedure-card-audit-v1"},
    )
    monkeypatch.setattr(
        cli,
        "write_unclassified_procedure_card_audit",
        lambda path, report: received.update(output=path, report=report),
    )

    result = cli.main([
        "unclassified-procedure-card-audit",
        "--model", "output/model.json.gz",
        "--card", "ZGBS:RNP-0:12:0",
        "--output", "diagnostics/unclassified-procedure-card.json",
    ])

    assert result == 0
    assert received["model_path"] == Path("output/model.json.gz")
    assert received["model"] is model
    assert received["card"] == "ZGBS:RNP-0:12:0"
    assert received["output"] == Path(
        "diagnostics/unclassified-procedure-card.json"
    ).resolve()
    assert received["report"]["output"] == str(received["output"])


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
