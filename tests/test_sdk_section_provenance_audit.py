from __future__ import annotations

import json
import struct
from pathlib import Path

from fenix_default_navdata.sdk_section_provenance_audit import (
    audit_sdk_section_provenance,
    write_sdk_section_provenance_audit,
)


def _bgl(section_type: int, count: int, size: int) -> bytes:
    body = bytes([section_type]) * size
    return (
        struct.pack("<IIIIII", 0x19920201, 0x38, 0, 0, 0x08051803, 1)
        + struct.pack("<IIIIIIII", 0x20, 0, 0, 0, 0, 0, 0, 0)
        + struct.pack("<IIIII", section_type, 1, count, 0x4C, size)
        + body
    )


def test_section_provenance_reports_xml_and_section_deltas_without_payload(
    tmp_path: Path,
) -> None:
    baseline_xml = tmp_path / "baseline.xml"
    variant_xml = tmp_path / "variant.xml"
    baseline_bgl = tmp_path / "baseline.bgl"
    variant_bgl = tmp_path / "variant.bgl"
    baseline_xml.write_text("<FSData />\n", encoding="utf-8")
    variant_xml.write_text("<FSData><Ndb /></FSData>\n", encoding="utf-8")
    baseline_bgl.write_bytes(_bgl(0x03, 1, 4))
    variant_bgl.write_bytes(_bgl(0x17, 2, 8))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "diagnostic": "sdk-section-provenance-manifest-v1",
        "cases": [{
            "name": "ndb-child",
            "baseline": {"xml": str(baseline_xml), "bgl": str(baseline_bgl)},
            "variants": [{
                "name": "with-ndb",
                "xml": str(variant_xml),
                "bgl": str(variant_bgl),
            }],
        }],
    }), encoding="utf-8")

    report = audit_sdk_section_provenance(manifest)

    assert report["diagnostic"] == "sdk-section-provenance-audit-v1"
    assert report["navigation_records_read"] is False
    assert report["decision"]["section_type_semantics_inferred"] is False
    assert report["summary"]["case_count"] == 1
    assert report["summary"]["variant_count"] == 1
    assert "0x17" in report["summary"]["section_effects"]
    variant = report["cases"][0]["variants"][0]
    assert variant["same_xml_as_baseline"] is False
    delta = variant["section_delta"]
    assert delta["section_table_equal"] is False
    assert {row["type"] for row in delta["by_type"]} == {0x03, 0x17}
    assert "with-ndb" in json.dumps(report, ensure_ascii=False)

    output = tmp_path / "audit.json"
    write_sdk_section_provenance_audit(output, report)
    assert output.is_file()


def test_section_provenance_rejects_wrong_manifest_version(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"diagnostic": "wrong", "cases": []}), encoding="utf-8")

    try:
        audit_sdk_section_provenance(manifest)
    except RuntimeError as error:
        assert "manifest diagnostic" in str(error)
    else:
        raise AssertionError("expected malformed manifest to be rejected")


def test_section_provenance_accepts_utf8_bom_manifest(tmp_path: Path) -> None:
    xml = tmp_path / "probe.xml"
    bgl = tmp_path / "probe.bgl"
    xml.write_text("<FSData />", encoding="utf-8")
    bgl.write_bytes(_bgl(0x03, 1, 1))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "diagnostic": "sdk-section-provenance-manifest-v1",
        "cases": [{
            "name": "bom",
            "baseline": {"xml": str(xml), "bgl": str(bgl)},
            "variants": [{"name": "same", "xml": str(xml), "bgl": str(bgl)}],
        }],
    }), encoding="utf-8-sig")

    report = audit_sdk_section_provenance(manifest)

    assert report["cases"][0]["variants"][0]["same_xml_as_baseline"] is True
    assert report["summary"]["same_input_replay_count"] == 1
