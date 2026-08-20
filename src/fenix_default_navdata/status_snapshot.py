from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Mapping

from .bgl_format import audit_file_convergence


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_summary(project_root: Path) -> dict[str, object]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout.strip()

    try:
        return {
            "head": run("rev-parse", "HEAD"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "worktree_clean": not bool(run("status", "--porcelain")),
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return {"available": False, "error": str(error)}


def _raw_csv_lock(raw_root: Path | None) -> dict[str, object] | None:
    if raw_root is None:
        return None
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"424 原始目录不存在: {root}")
    files = []
    for path in sorted(root.glob("*.csv")):
        files.append({
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return {
        "root": str(root),
        "top_level_csv_count": len(files),
        "files": files,
    }


def _report_digest(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"审计报告不存在: {resolved}")
    return {
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _gap_card_summary(path: Path | None) -> dict[str, object] | None:
    digest = _report_digest(path)
    if digest is None:
        return None
    try:
        payload = json.loads(Path(digest["path"]).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"来源缺口卡报告不是有效 JSON: {digest['path']}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("来源缺口卡报告根节点必须是对象")
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("来源缺口卡报告缺少 summary")
    return {**digest, "summary": dict(summary)}


def audit_status_snapshot(
    *,
    project_root: Path,
    model: Path,
    candidate: Path,
    reference: Path,
    repeat_candidate: Path | None = None,
    raw_root: Path | None = None,
    gap_cards: Path | None = None,
) -> dict[str, object]:
    """Build a deterministic read-only gate summary without reading BGL payloads."""

    model_path = model.expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"冻结 NavModel 不存在: {model_path}")
    convergence = audit_file_convergence(
        candidate,
        reference,
        repeat_candidate_root=repeat_candidate,
    )
    summary = convergence["summary"]
    reference_equal = summary["reference_equal_files"] == summary["reference_scope_files"]
    replay_equal = (
        repeat_candidate is not None
        and summary["repeat_equal_files"] == summary["repeat_scope_files"]
    )
    return {
        "diagnostic": "authority-status-snapshot-v1",
        "read_only": True,
        "reference_records_exported": False,
        "project": _git_summary(project_root.expanduser().resolve()),
        "inputs": {
            "raw_csv_lock": _raw_csv_lock(raw_root),
            "nav_model": {
                "path": str(model_path),
                "size": model_path.stat().st_size,
                "sha256": _sha256(model_path),
            },
            "gap_cards": _gap_card_summary(gap_cards),
        },
        "convergence": {
            "summary": summary,
            "reference_byte_equal": reference_equal,
            "candidate_replay_equal": replay_equal,
        },
        "gates": {
            "automated_validation": {
                "candidate_replay_equal": replay_equal,
                "reference_byte_equal": reference_equal,
            },
            "structural_deployment": {
                "backup_restore_exercised": False,
                "community_overwritten": False,
            },
            "flight_validation": {"verified": False},
            "release": {
                "deployable": False,
                "formal_release_allowed": False,
            },
        },
    }


def write_status_snapshot(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
