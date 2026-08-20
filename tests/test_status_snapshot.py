import json
from pathlib import Path

from fenix_default_navdata.status_snapshot import (
    audit_status_snapshot,
    write_status_snapshot,
)


def _write_scope(root: Path, payload: bytes) -> None:
    package = root / "package"
    package.mkdir(parents=True)
    (package / "layout.json").write_bytes(payload)


def test_status_snapshot_is_read_only_and_reports_gate_states(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    raw = tmp_path / "raw"
    candidate = tmp_path / "candidate"
    repeat = tmp_path / "repeat"
    reference = tmp_path / "reference"
    project.mkdir()
    raw.mkdir()
    (raw / "AIRPORT.csv").write_text("id\nZAAA\n", encoding="utf-8")
    model = tmp_path / "model.json.gz"
    model.write_bytes(b"model")
    _write_scope(candidate, b"candidate")
    _write_scope(repeat, b"candidate")
    _write_scope(reference, b"reference")
    gap_cards = tmp_path / "gap-cards.json"
    gap_cards.write_text(
        json.dumps({"summary": {"total_cards": 40, "blocked": 8}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fenix_default_navdata.status_snapshot._git_summary",
        lambda _: {"head": "abc", "branch": "main", "worktree_clean": True},
    )

    report = audit_status_snapshot(
        project_root=project,
        raw_root=raw,
        model=model,
        candidate=candidate,
        repeat_candidate=repeat,
        reference=reference,
        gap_cards=gap_cards,
    )

    assert report["diagnostic"] == "authority-status-snapshot-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["inputs"]["raw_csv_lock"]["top_level_csv_count"] == 1
    assert report["inputs"]["gap_cards"]["summary"]["total_cards"] == 40
    assert report["convergence"]["candidate_replay_equal"] is True
    assert report["convergence"]["reference_byte_equal"] is False
    assert report["gates"]["release"]["deployable"] is False

    output = tmp_path / "diagnostics" / "snapshot.json"
    write_status_snapshot(output, report)
    assert json.loads(output.read_text(encoding="utf-8")) == report
