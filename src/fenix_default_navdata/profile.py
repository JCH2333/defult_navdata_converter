from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cycle:
    number: str
    revision: int
    begin: str
    end: str


DEFAULT_CYCLE = Cycle("2608", 1, "20260806", "20260903")


def load_cycle(path: Path | None = None) -> Cycle:
    """读取本地周期 JSON；没有 sidecar 时使用任务锁定的 2608R1。"""
    if path is None or not path.is_file():
        return DEFAULT_CYCLE
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    number = str(payload.get("Cycle") or payload.get("cycle") or payload.get("cycleNumber") or "").strip()
    revision = int(payload.get("Revision", payload.get("revision", 1)))
    begin = str(payload.get("StartDate", payload.get("cycleBegin", ""))).strip()
    end = str(payload.get("EndDate", payload.get("cycleEnd", ""))).strip()
    if not number or len(number) != 4:
        raise ValueError(f"周期 JSON 缺少四位周期号: {path}")
    return Cycle(number, revision, begin, end)


def validate_cycle(cycle: Cycle) -> None:
    if cycle.number != "2608" or cycle.revision != 1:
        raise ValueError(f"当前工具只允许 2608R1，收到 {cycle.number}R{cycle.revision}")
    if len(cycle.begin) != 8 or len(cycle.end) != 8:
        raise ValueError("周期起止日期必须为 YYYYMMDD")
