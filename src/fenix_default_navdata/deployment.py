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


def deploy(candidate: Path, target: Path, *, backup_root: Path | None = None) -> Path:
    if simulator_running():
        raise RuntimeError("FlightSimulator2024.exe 正在运行，无法覆盖默认导航数据")
    candidate, target = candidate.resolve(), target.resolve()
    validation = validate_candidate(candidate)
    if not validation["valid"]:
        raise RuntimeError("候选缺少 BGL、bglIndex.bout 或包元数据，拒绝覆盖")
    if validation.get("test_build"):
        raise RuntimeError("候选仍标记为测试版；测试构建不得覆盖 Community")
    if not validation.get("byte_equal_reference"):
        raise RuntimeError("候选尚未与参考成品完成字节级一致验证，拒绝覆盖 Community")
    if not validation.get("flight_validation_verified"):
        raise RuntimeError("候选尚未登记 ZBCF、ZUNZ、ZUUU 与退出稳定性的实机验证，拒绝覆盖 Community")
    if not validation["deployable"]:
        raise RuntimeError("候选未通过完整发布门禁，拒绝覆盖 Community")
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
