import json
from pathlib import Path

import pytest

from fenix_default_navdata.deployment import deploy
from fenix_default_navdata.package import (
    AIRPORT_PACKAGE,
    BASE_PACKAGE,
    JEPP_PACKAGE,
    NAV_PACKAGE,
)


def test_deploy_refuses_incomplete_test_candidate(tmp_path: Path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    (candidate / BASE_PACKAGE).mkdir()
    (candidate / JEPP_PACKAGE).mkdir()
    (candidate / "conversion-report.json").write_text(
        json.dumps({"deployable": False}), encoding="utf-8",
    )
    monkeypatch.setattr("fenix_default_navdata.deployment.simulator_running", lambda: False)
    with pytest.raises(RuntimeError, match="缺少 BGL"):
        deploy(candidate, target, allow_test_build=True)


def test_deploy_requires_explicit_permission_for_test_build(
    tmp_path: Path,
    monkeypatch,
):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    for name in (BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, AIRPORT_PACKAGE):
        (candidate / name).mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.simulator_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.validate_candidate",
        lambda candidate: {
            "valid": True,
            "deployable": True,
            "test_build": True,
        },
    )
    with pytest.raises(RuntimeError, match="--allow-test-build"):
        deploy(candidate, target)
