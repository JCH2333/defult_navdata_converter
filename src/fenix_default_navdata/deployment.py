from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

from .package import AIRPORT_PACKAGE, BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, sha256
from .validation import validate_candidate


def simulator_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq FlightSimulator2024.exe", "/NH"],
        capture_output=True, text=True, encoding="cp936", errors="replace", check=False,
    )
    return "FlightSimulator2024.exe".lower() in result.stdout.lower()


def backup_community(target: Path, backup_root: Path | None = None) -> Path:
    target = target.resolve()
    root = (backup_root or target.parent / "backups").resolve()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / f"default_navdata_{stamp}"
    suffix = 2
    while backup.exists():
        backup = root / f"default_navdata_{stamp}_{suffix}"
        suffix += 1
    backup.mkdir(parents=True)
    files: dict[str, str] = {}
    for name in (BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, AIRPORT_PACKAGE):
        source = target / name
        if not source.exists():
            continue
        shutil.copytree(source, backup / name)
        for path in (backup / name).rglob("*"):
            if path.is_file():
                files[path.relative_to(backup).as_posix()] = sha256(path)
    (backup / "backup-manifest.json").write_text(
        json.dumps({"target": str(target), "created_at": dt.datetime.now().isoformat(), "files": files}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup


def deploy(candidate: Path, target: Path, *, allow_test_build: bool = False, backup_root: Path | None = None) -> Path:
    if simulator_running():
        raise RuntimeError("FlightSimulator2024.exe 正在运行，无法覆盖默认导航数据")
    candidate, target = candidate.resolve(), target.resolve()
    validation = validate_candidate(candidate)
    if not validation["valid"]:
        raise RuntimeError("候选缺少 BGL、bglIndex.bout 或包元数据，拒绝覆盖")
    if not validation["deployable"] and not allow_test_build:
        raise RuntimeError("候选不是可部署成品；必须显式使用 --allow-test-build")
    if not target.is_dir():
        raise FileNotFoundError(f"Community 目录不存在: {target}")
    backup = backup_community(target, backup_root)
    try:
        for name in (BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, AIRPORT_PACKAGE):
            source = candidate / name
            if not source.is_dir():
                continue
            temporary = target / f".{name}.deploy-new"
            shutil.copytree(source, temporary, dirs_exist_ok=True)
            old = target / name
            if old.exists():
                shutil.rmtree(old)
            temporary.replace(old)
    except Exception:
        restore(backup, target)
        raise
    return backup


def restore(backup: Path, target: Path) -> None:
    if simulator_running():
        raise RuntimeError("FlightSimulator2024.exe 正在运行，无法恢复默认导航数据")
    for name in (BASE_PACKAGE, JEPP_PACKAGE, NAV_PACKAGE, AIRPORT_PACKAGE):
        source = backup / name
        destination = target / name
        if destination.exists():
            shutil.rmtree(destination)
        if source.is_dir():
            shutil.copytree(source, destination)
