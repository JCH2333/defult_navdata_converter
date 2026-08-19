from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model import NavModel
from .model_io import encode, model_counts


class ModelReplayAuditError(RuntimeError):
    """模型重放审计输入或白名单不满足确定性契约。"""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _field_path(path: str, key: str) -> str:
    if key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=True)}]"


def _category(path: str) -> str:
    match = re.match(r"^\$\.([A-Za-z_][A-Za-z0-9_]*)", path)
    return match.group(1) if match else "root"


def _difference(
    path: str,
    baseline: object,
    replay: object,
    reason: str,
) -> dict[str, str]:
    return {
        "path": path,
        "category": _category(path),
        "reason": reason,
        "baseline_sha256": _digest(baseline),
        "replay_sha256": _digest(replay),
    }


def _tagged(value: object) -> tuple[str, object] | None:
    if (
        isinstance(value, dict)
        and set(value) == {"__n__", "v"}
        and isinstance(value["__n__"], str)
    ):
        return value["__n__"], value["v"]
    return None


def _compare(
    baseline: object,
    replay: object,
    *,
    path: str = "$",
) -> list[dict[str, str]]:
    if type(baseline) is not type(replay):
        return [_difference(path, baseline, replay, "type_changed")]
    baseline_tagged = _tagged(baseline)
    replay_tagged = _tagged(replay)
    if baseline_tagged is not None or replay_tagged is not None:
        if baseline_tagged is None or replay_tagged is None:
            return [_difference(path, baseline, replay, "type_changed")]
        if baseline_tagged[0] != replay_tagged[0]:
            return [_difference(path, baseline, replay, "type_changed")]
        return _compare(baseline_tagged[1], replay_tagged[1], path=path)
    if isinstance(baseline, dict):
        differences: list[dict[str, str]] = []
        baseline_keys = set(baseline)
        replay_keys = set(replay)
        for key in sorted(baseline_keys - replay_keys):
            differences.append(
                _difference(_field_path(path, str(key)), baseline[key], None, "removed")
            )
        for key in sorted(replay_keys - baseline_keys):
            differences.append(
                _difference(_field_path(path, str(key)), None, replay[key], "added")
            )
        for key in sorted(baseline_keys & replay_keys):
            differences.extend(
                _compare(
                    baseline[key],
                    replay[key],
                    path=_field_path(path, str(key)),
                )
            )
        return differences
    if isinstance(baseline, list):
        differences = []
        common = min(len(baseline), len(replay))
        for index in range(common):
            differences.extend(
                _compare(
                    baseline[index],
                    replay[index],
                    path=f"{path}[{index}]",
                )
            )
        for index in range(common, len(baseline)):
            differences.append(
                _difference(f"{path}[{index}]", baseline[index], None, "removed")
            )
        for index in range(common, len(replay)):
            differences.append(
                _difference(f"{path}[{index}]", None, replay[index], "added")
            )
        return differences
    if baseline != replay:
        return [_difference(path, baseline, replay, "value_changed")]
    return []


def _allow_key(item: Mapping[str, object]) -> tuple[str, str, str]:
    path = item.get("path")
    baseline_sha256 = item.get("baseline_sha256")
    replay_sha256 = item.get("replay_sha256")
    if not all(isinstance(value, str) for value in (
        path,
        baseline_sha256,
        replay_sha256,
    )):
        raise ModelReplayAuditError(
            "白名单项目必须包含 path、baseline_sha256 和 replay_sha256"
        )
    assert isinstance(path, str)
    assert isinstance(baseline_sha256, str)
    assert isinstance(replay_sha256, str)
    if not path.startswith("$"):
        raise ModelReplayAuditError("白名单 path 必须以 $ 开头")
    if not _SHA256.fullmatch(baseline_sha256) or not _SHA256.fullmatch(replay_sha256):
        raise ModelReplayAuditError("白名单 SHA-256 必须是 64 位小写十六进制")
    return path, baseline_sha256, replay_sha256


def load_difference_allowlist(path: Path) -> tuple[dict[str, str], ...]:
    """加载只含精确路径及两侧哈希的模型差异白名单。"""

    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelReplayAuditError(f"无法读取模型差异白名单: {path}") from error
    items = payload.get("allowed_differences") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ModelReplayAuditError("模型差异白名单必须是数组或含 allowed_differences 的对象")
    result: list[dict[str, str]] = []
    keys: set[tuple[str, str, str]] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ModelReplayAuditError("模型差异白名单项目必须是对象")
        key = _allow_key(item)
        if key in keys:
            raise ModelReplayAuditError("模型差异白名单含重复项目")
        keys.add(key)
        result.append({
            "path": key[0],
            "baseline_sha256": key[1],
            "replay_sha256": key[2],
        })
    return tuple(result)


def audit_model_replay(
    baseline: NavModel,
    replay: NavModel,
    *,
    allowed_differences: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """比较两个 NavModel 快照并以精确路径和哈希执行白名单门禁。

    此函数只消费已加载的中间模型。输出不包含任一字段的原始值，避免把
    导航内容或 OCR 文本变成新的诊断输入。
    """

    allow_keys = {_allow_key(item) for item in allowed_differences}
    baseline_encoded = encode(baseline)
    replay_encoded = encode(replay)
    all_differences = _compare(baseline_encoded, replay_encoded)
    allowed: list[dict[str, str]] = []
    unexpected: list[dict[str, str]] = []
    for item in all_differences:
        key = (
            item["path"],
            item["baseline_sha256"],
            item["replay_sha256"],
        )
        (allowed if key in allow_keys else unexpected).append(item)
    category_counts = Counter(item["category"] for item in all_differences)
    return {
        "diagnostic": "model-replay-audit-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "baseline": {
            "model_sha256": _digest(baseline_encoded),
            "counts": model_counts(baseline),
        },
        "replay": {
            "model_sha256": _digest(replay_encoded),
            "counts": model_counts(replay),
        },
        "difference_count": len(all_differences),
        "difference_categories": dict(sorted(category_counts.items())),
        "allowed_difference_count": len(allowed),
        "unexpected_difference_count": len(unexpected),
        "consistent": not unexpected,
        "allowed_differences": allowed,
        "unexpected_differences": unexpected,
    }


def write_model_replay_audit(path: Path, report: Mapping[str, object]) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
