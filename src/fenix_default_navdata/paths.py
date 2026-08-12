from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_NAME = "导航数据"


@dataclass(frozen=True)
class DetectedPaths:
    raw_root: Path | None
    nav_base: Path | None
    nav_jepp: Path | None
    reference_root: Path | None
    community_root: Path | None


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _first_existing(paths: list[Path], *, directory: bool = True) -> Path | None:
    for path in paths:
        if (path.is_dir() if directory else path.is_file()):
            return path.resolve()
    return None


def detect_paths() -> DetectedPaths:
    root = _workspace_root()
    community = Path(r"F:\games\community\Community")
    raw = _first_existing([
        root / "424源数据" / "2608" / "2608",
    ])
    nav_base = _first_existing([
        community / "navigraph-nav-base",
        Path(r"F:\games\community\Community\navigraph-nav-base"),
    ])
    nav_jepp = _first_existing([
        community / "navigraph-nav-jepp",
        Path(r"F:\games\community\Community\navigraph-nav-jepp"),
    ])
    reference = _first_existing([
        root / "424源数据" / "2608" / "Default navdata 2608R1",
    ])
    return DetectedPaths(
        raw,
        nav_base,
        nav_jepp,
        reference,
        community if community.is_dir() else None,
    )
