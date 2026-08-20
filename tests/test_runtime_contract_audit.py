from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.cli import main
from fenix_default_navdata.runtime_contract_audit import (
    classify_runtime_strings,
    write_runtime_contract_audit,
)


def test_classify_runtime_strings_extracts_contract_without_payload() -> None:
    report = classify_runtime_strings([
        "SELECT airport_identifier FROM tbl_airports WHERE airport_identifier=?",
        r"/work/NavigationData/e_dfd_PMDG.s3db",
        r"\ProcedureLegs\TermID_123.json",
        "ordinary user-interface text",
    ])

    assert report["summary"] == {
        "sql_string_count": 1,
        "table_name_count": 1,
        "path_string_count": 2,
    }
    assert report["table_names"] == ["tbl_airports"]
    assert "SELECT airport_identifier" in report["sql_strings"][0]
    assert "tbl_airports" in json.dumps(report)


def test_cli_writes_runtime_contract_report_with_fake_strings_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    binary = tmp_path / "module.dll"
    binary.write_bytes(b"binary")
    strings = tmp_path / "strings.exe"
    strings.write_bytes(b"tool")
    output = tmp_path / "runtime.json"

    def fake_run(*args, **kwargs):
        class Result:
            stdout = (
                "SELECT * FROM tbl_iaps WHERE airport_identifier=?\n"
                r"/work/NavigationData/db.s3db"
            )

        return Result()

    monkeypatch.setattr(
        "fenix_default_navdata.runtime_contract_audit.subprocess.run",
        fake_run,
    )
    assert main([
        "runtime-contract-audit",
        "--binary", "pmdg", str(binary),
        "--strings", str(strings),
        "--output", str(output),
    ]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostic"] == "runtime-contract-string-audit-v1"
    assert report["summary"]["distinct_table_names"] == ["tbl_iaps"]
    write_runtime_contract_audit(output, report)
