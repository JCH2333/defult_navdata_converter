import json
from pathlib import Path

import pytest

from fenix_default_navdata.deployment import deploy, stage_functional_test
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
        deploy(candidate, target)


def test_deploy_refuses_structurally_valid_test_candidate(
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
            "deployable": False,
            "test_build": True,
            "byte_equal_reference": True,
            "flight_validation_verified": True,
        },
    )
    with pytest.raises(RuntimeError, match="测试版"):
        deploy(candidate, target)


def test_deploy_requires_reference_byte_equality(
    tmp_path: Path,
    monkeypatch,
):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.simulator_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.validate_candidate",
        lambda candidate: {
            "valid": True,
            "deployable": False,
            "test_build": False,
            "byte_equal_reference": False,
            "flight_validation_verified": True,
        },
    )
    with pytest.raises(RuntimeError, match="字节级一致"):
        deploy(candidate, target)


def test_deploy_requires_flight_validation(
    tmp_path: Path,
    monkeypatch,
):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.simulator_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.validate_candidate",
        lambda candidate: {
            "valid": True,
            "deployable": False,
            "test_build": False,
            "byte_equal_reference": True,
            "flight_validation_verified": False,
        },
    )
    with pytest.raises(RuntimeError, match="实机验证"):
        deploy(candidate, target)


def test_stage_functional_test_requires_test_build(
    tmp_path: Path,
    monkeypatch,
):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.simulator_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.validate_candidate",
        lambda candidate: {
            "valid": True,
            "local_contract_verified": True,
            "test_build": False,
            "report_status": "release",
        },
    )
    with pytest.raises(RuntimeError, match="test_build"):
        stage_functional_test(candidate, target)


def test_stage_functional_test_backups_and_records_hashes(
    tmp_path: Path,
    monkeypatch,
):
    candidate = tmp_path / "candidate"
    target = tmp_path / "Community"
    candidate.mkdir()
    target.mkdir()
    package_names = (BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, AIRPORT_PACKAGE)
    for name in package_names:
        candidate_package = candidate / name
        candidate_package.mkdir()
        (candidate_package / "manifest.json").write_text("{}", encoding="utf-8")
        (candidate_package / "layout.json").write_text("{}", encoding="utf-8")
        (candidate_package / "bglIndex.bout").write_bytes(b"index")
        (candidate_package / "scenery" / "x.bgl").parent.mkdir()
        (candidate_package / "scenery" / "x.bgl").write_bytes(b"candidate")
        target_package = target / name
        target_package.mkdir()
        (target_package / "old.txt").write_text("original", encoding="utf-8")
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.simulator_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.deployment.validate_candidate",
        lambda candidate: {
            "valid": True,
            "local_contract_verified": True,
            "test_build": True,
            "report_status": "candidate",
        },
    )

    backup = stage_functional_test(candidate, target, backup_root=tmp_path / "backups")

    assert (target / NAV_PACKAGE / "scenery" / "x.bgl").read_bytes() == b"candidate"
    assert (backup / NAV_PACKAGE / "old.txt").read_text(encoding="utf-8") == "original"
    stage_manifest = json.loads((backup / "functional-test-stage.json").read_text(encoding="utf-8"))
    assert stage_manifest["kind"] == "functional-test-stage"
    assert stage_manifest["packages"][NAV_PACKAGE]["files"]["scenery/x.bgl"]
