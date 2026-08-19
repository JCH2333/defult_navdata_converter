import json

from fenix_default_navdata.historical_sdk_probe_evidence import (
    audit_historical_sdk_probe_evidence,
)


def _report(path, size):
    path.write_text(json.dumps({
        "reader": {"ok": True},
        "bgl_layouts": [{"path": "a.bgl", "size": size, "layout": {
            "section_types": ["0x3"], "section_counts": [1], "section_sizes": [16],
        }}],
    }), encoding="utf-8")


def test_historical_evidence_normalizes_layout_pair(tmp_path):
    base, variant = tmp_path / "base.json", tmp_path / "variant.json"
    _report(base, 100)
    _report(variant, 120)
    report = audit_historical_sdk_probe_evidence([{
        "identifier": "threshold", "baseline": str(base), "variant": str(variant),
        "disposition": "rejected",
    }])
    assert report["all_reader_complete"] is True
    assert report["cases"][0]["bgl_files"][0]["size_changed"] is True
    assert report["cases"][0]["bgl_files"][0]["section_counts_changed"] is False
