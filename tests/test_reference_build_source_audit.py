import json
from pathlib import Path

from fenix_default_navdata.reference_build_source_audit import (
    audit_reference_build_sources,
)


def test_reference_build_source_audit_separates_reference_and_candidate_inputs(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference"
    (reference / "scenery").mkdir(parents=True)
    (reference / "scenery" / "00_enroute.bgl").write_bytes(b"payload")
    (reference / "manifest.json").write_text(
        json.dumps({"creator": "test", "package_version": "1.0.0"}),
        encoding="utf-8",
    )

    candidate = tmp_path / "candidate"
    (candidate / "_work" / "inputs").mkdir(parents=True)
    (candidate / "_work" / "inputs" / "00_enroute.xml").write_text(
        "<FSData />",
        encoding="utf-8",
    )

    sdk = tmp_path / "sdk"
    (sdk / "Tools" / "bin").mkdir(parents=True)
    (sdk / "Tools" / "bin" / "fspackagetool.exe").write_bytes(b"tool")
    (sdk / "Tools" / "bin" / "bglcomp.xsd").write_bytes(b"schema")

    report = audit_reference_build_sources(
        reference,
        candidate_root=candidate,
        sdk_roots=[sdk],
    )

    assert report["diagnostic"] == "reference-build-source-audit-v1"
    assert report["reference_payload_read"] is False
    assert report["summary"]["reference_source_xml_total"] == 0
    assert report["summary"]["candidate_source_xml_total"] == 1
    assert report["summary"]["sdk_package_tool_total"] == 1
    assert report["summary"]["sdk_bgl_generator_total"] == 0
    assert report["decision"]["adapter_change_authorized"] is False


def test_reference_build_source_audit_rejects_missing_reference(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    try:
        audit_reference_build_sources(missing)
    except RuntimeError as error:
        assert "参考包目录不存在" in str(error)
    else:
        raise AssertionError("missing reference must fail")
