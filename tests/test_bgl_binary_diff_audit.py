from __future__ import annotations

import struct
from pathlib import Path

from fenix_default_navdata.bgl_binary_diff_audit import (
    audit_bgl_binary_differences,
    write_bgl_binary_diff_audit,
)
from fenix_default_navdata.cli import main


def _bgl(
    sections: tuple[tuple[int, int, int, bytes], ...],
    *,
    qmid: tuple[int, ...] = (0x20,),
) -> bytes:
    header_size = 0x38
    table_size = len(sections) * 20
    offset = header_size + table_size
    table: list[bytes] = []
    payload = bytearray()
    for section_type, field_a, count, body in sections:
        table.append(struct.pack(
            "<IIIII",
            section_type,
            field_a,
            count,
            offset,
            len(body),
        ))
        payload.extend(body)
        offset += len(body)
    padded_qmid = qmid + (0,) * (8 - len(qmid))
    return (
        struct.pack(
            "<IIIIII",
            0x19920201,
            header_size,
            0,
            0,
            0x08051803,
            len(sections),
        )
        + struct.pack("<" + "I" * 8, *padded_qmid[:8])
        + b"".join(table)
        + bytes(payload)
    )


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_binary_diff_pairs_sections_by_type_and_hides_payload(tmp_path: Path) -> None:
    relative = "pkg/scenery/changed.bgl"
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    _write(candidate, relative, _bgl((
        (0x03, 1, 1, b"AAAA"),
        (0x22, 1, 2, b"BBBB"),
    )))
    _write(reference, relative, _bgl((
        (0x03, 1, 1, b"AAAA"),
        (0x17, 1, 2, b"CCCC"),
        (0x22, 1, 3, b"BBBB!"),
    )))

    report = audit_bgl_binary_differences(candidate, reference)

    assert report["diagnostic"] == "bgl-binary-diff-audit-v1"
    assert report["reference_records_exported"] is False
    assert report["reference_payload_exported"] is False
    row = report["files"][0]
    assert row["status"] == "changed"
    assert row["header_metadata_equal"] is False
    sections = {
        (item["section_type"], item["occurrence"]): item
        for item in row["section_diffs"]
    }
    assert sections[(0x17, 0)]["status"] == "missing_candidate"
    assert sections[(0x22, 0)]["payload_size_delta"] == -1
    assert "AAAA" not in str(report)
    assert "CCCC" not in str(report)


def test_binary_diff_supports_selected_paths_and_json_writer(tmp_path: Path) -> None:
    selected = "pkg/scenery/selected.bgl"
    ignored = "pkg/scenery/ignored.bgl"
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    payload = _bgl(((0x03, 1, 1, b"DATA"),))
    _write(candidate, selected, payload)
    _write(reference, selected, payload)
    _write(candidate, ignored, payload)
    _write(reference, ignored, _bgl(((0x03, 1, 1, b"DIFF"),)))

    report = audit_bgl_binary_differences(
        candidate,
        reference,
        relative_paths=[selected.upper().replace("/", "\\")],
    )

    assert report["summary"]["selected_files"] == 1
    assert report["summary"]["equal_files"] == 1
    assert [row["path"] for row in report["files"]] == [selected]
    output = tmp_path / "diagnostics" / "diff.json"
    write_bgl_binary_diff_audit(output, report)
    assert output.exists()
    assert "reference_payload_exported" in output.read_text(encoding="utf-8")


def test_cli_runs_binary_diff_audit(tmp_path: Path) -> None:
    relative = "pkg/scenery/changed.bgl"
    candidate = tmp_path / "candidate"
    reference = tmp_path / "reference"
    _write(candidate, relative, _bgl(((0x03, 1, 1, b"AAAA"),)))
    _write(reference, relative, _bgl(((0x03, 1, 1, b"BBBB"),)))
    output = tmp_path / "audit.json"

    assert main([
        "bgl-binary-diff-audit",
        "--candidate", str(candidate),
        "--reference", str(reference),
        "--output", str(output),
    ]) == 0
    assert output.exists()
