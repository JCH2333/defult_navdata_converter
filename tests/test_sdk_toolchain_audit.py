import json

from fenix_default_navdata.sdk_toolchain_audit import audit_sdk_toolchains


def _sdk(root, version, payload):
    (root / "Tools" / "bin").mkdir(parents=True)
    (root / "version.txt").write_text(version + "\n", encoding="utf-8")
    (root / "Tools" / "bin" / "fspackagetool.exe").write_bytes(payload)


def test_audit_keeps_toolchain_difference_separate_from_target_evidence(tmp_path):
    first = tmp_path / "sdk-1.5.3"
    second = tmp_path / "sdk-1.6.9"
    _sdk(first, "1.5.3", b"first")
    _sdk(second, "1.6.9", b"second")
    evidence = tmp_path / "historical.json"
    evidence.write_text(json.dumps({
        "diagnostic": "historical-sdk-probe-evidence-v1",
        "all_reader_complete": True,
        "cases": [{
            "identifier": "threshold",
            "disposition": "rejected",
            "reader_complete": True,
            "bgl_files": [{
                "size_changed": True,
                "section_types_changed": False,
                "section_counts_changed": False,
                "section_sizes_changed": False,
            }],
        }],
    }), encoding="utf-8")

    report = audit_sdk_toolchains([first, second], historical_evidence=evidence)

    assert report["read_only"] is True
    assert report["reference_payload_read"] is False
    assert report["navigation_records_read"] is False
    assert report["package_tool_hashes_distinct"] is True
    assert report["historical_probe_evidence"]["cases"][0]["layout_changed"] is True
    assert report["decision"]["adapter_change_authorized"] is False
