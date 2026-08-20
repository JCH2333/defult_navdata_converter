from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.cli import main
from fenix_default_navdata.reference_template_source_audit import (
    audit_reference_template_sources,
    write_reference_template_source_audit,
)


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_audit_classifies_exact_changed_and_missing_template_files(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    _write(reference, "pkg/layout.json", b"same")
    _write(reference, "pkg/00_enroute.bgl", b"reference")
    _write(reference, "pkg/unique.bgl", b"unique")
    _write(base, "other/layout.json", b"same")
    _write(base, "pkg/00_enroute.bgl", b"template")
    _write(jepp, "other/unique.bgl", b"different")

    report = audit_reference_template_sources(
        reference,
        {"base": base, "jepp": jepp},
    )

    assert report["diagnostic"] == "reference-template-source-audit-v1"
    assert report["navigation_records_read"] is False
    assert report["decision"]["content_projection_authorized"] is False
    rows = {row["reference"]["path"]: row for row in report["files"]}
    assert rows["pkg/layout.json"]["status"] == "exact_template_file_match"
    assert rows["pkg/00_enroute.bgl"]["status"] == "same_relative_path_changed"
    assert rows["pkg/unique.bgl"]["status"] == "same_basename_changed"
    assert "reference" not in json.dumps(report["files"][0]["reference"])


def test_writer_and_cli_are_reusable(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    jepp.mkdir()
    _write(reference, "pkg/manifest.json", b"manifest")
    _write(base, "pkg/manifest.json", b"manifest")
    output = tmp_path / "audit.json"

    report = audit_reference_template_sources(reference, {"base": base, "jepp": jepp})
    write_reference_template_source_audit(output, report)
    assert json.loads(output.read_text(encoding="utf-8"))["summary"][
        "exact_template_file_matches"
    ] == 1

    cli_output = tmp_path / "cli.json"
    assert main([
        "reference-template-source-audit",
        "--reference", str(reference),
        "--template-base", str(base),
        "--template-jepp", str(jepp),
        "--output", str(cli_output),
    ]) == 0
    assert cli_output.exists()
