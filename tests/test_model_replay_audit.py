import json
from pathlib import Path

import pytest

from fenix_default_navdata.model import NavModel, SourceRef, Waypoint
from fenix_default_navdata.model_replay_audit import (
    ModelReplayAuditError,
    audit_model_replay,
    load_difference_allowlist,
    write_model_replay_audit,
)


def _model(root: Path, country: str = "ZB") -> NavModel:
    model = NavModel(root)
    model.waypoints.append(
        Waypoint(
            "ZB.DOVIV",
            "DOVIV",
            "DOVIV",
            39.0,
            116.0,
            SourceRef("DESIGNATED_POINT.csv", 2, sha256="a" * 64),
            country=country,
        )
    )
    return model


def test_model_replay_audit_accepts_identical_models(tmp_path: Path) -> None:
    report = audit_model_replay(_model(tmp_path), _model(tmp_path))

    assert report["consistent"] is True
    assert report["difference_count"] == 0
    assert report["unexpected_differences"] == []


def test_model_replay_audit_requires_exact_allowlist_entry(tmp_path: Path) -> None:
    baseline = _model(tmp_path, "")
    replay = _model(tmp_path, "ZB")
    initial = audit_model_replay(baseline, replay)
    difference = initial["unexpected_differences"][0]

    report = audit_model_replay(
        baseline,
        replay,
        allowed_differences=[{
            "path": difference["path"],
            "baseline_sha256": difference["baseline_sha256"],
            "replay_sha256": difference["replay_sha256"],
        }],
    )

    assert report["consistent"] is True
    assert report["allowed_difference_count"] == 1
    assert "DOVIV" not in json.dumps(report)


def test_model_replay_audit_rejects_difference_outside_allowlist(tmp_path: Path) -> None:
    report = audit_model_replay(_model(tmp_path, ""), _model(tmp_path, "ZB"))

    assert report["consistent"] is False
    assert report["unexpected_difference_count"] == 1
    assert report["unexpected_differences"][0]["reason"] == "value_changed"


def test_model_replay_report_and_allowlist_use_standard_json(tmp_path: Path) -> None:
    baseline = _model(tmp_path, "")
    replay = _model(tmp_path, "ZB")
    report = audit_model_replay(baseline, replay)
    output = tmp_path / "audit.json"
    write_model_replay_audit(output, report)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["diagnostic"] == "model-replay-audit-v1"

    allowlist = tmp_path / "allowlist.json"
    difference = report["unexpected_differences"][0]
    allowlist.write_text(json.dumps({"allowed_differences": [{
        "path": difference["path"],
        "baseline_sha256": difference["baseline_sha256"],
        "replay_sha256": difference["replay_sha256"],
    }]}), encoding="utf-8")

    assert load_difference_allowlist(allowlist)[0]["path"] == difference["path"]

    allowlist.write_text('{"allowed_differences": [{"path": "$"}]}', encoding="utf-8")
    with pytest.raises(ModelReplayAuditError, match="必须包含"):
        load_difference_allowlist(allowlist)
