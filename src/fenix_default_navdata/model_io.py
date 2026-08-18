from __future__ import annotations

import gzip
import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from . import model as model_module
from .model import NavModel


FORMAT_ID = "default-navdata-intermediate-model"
SCHEMA_VERSION = 1
_TAG = "__n__"
_VALUE = "v"
_DATACLASS_TYPES = {
    cls.__name__: cls
    for cls in vars(model_module).values()
    if isinstance(cls, type) and is_dataclass(cls)
}


def dump_model(model: NavModel, path: Path) -> dict[str, object]:
    """Serialize a source NavModel as a reusable adapter snapshot."""

    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "model": encode(model),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    compressed = _gzip_path(output)
    if compressed:
        with gzip.GzipFile(filename=str(output), mode="wb", mtime=0) as handle:
            handle.write(text.encode("utf-8"))
    else:
        output.write_text(text, encoding="utf-8")
    return {
        "output": str(output),
        "format": FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "gzip": compressed,
        "source_root": str(model.root),
        "counts": model_counts(model),
    }


def load_model(path: Path) -> NavModel:
    """Load a previously dumped NavModel snapshot."""

    source = path.expanduser().resolve()
    if _gzip_path(source):
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("中间模型文件根对象必须是 JSON 对象")
    if payload.get("format") != FORMAT_ID:
        raise ValueError(f"中间模型格式不是 {FORMAT_ID}: {payload.get('format')!r}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"中间模型 schema 版本不受支持: {payload.get('schema_version')!r}"
        )
    model = decode(payload.get("model"))
    if not isinstance(model, NavModel):
        raise ValueError("中间模型根对象不是 NavModel")
    return model


def model_counts(model: NavModel) -> dict[str, int]:
    return {
        "airports": len(model.airports),
        "runways": len(model.runways),
        "navaids": len(model.navaids),
        "ilses": len(model.ilses),
        "waypoints": len(model.waypoints),
        "terminal_waypoints": len(model.terminal_waypoints),
        "airway_legs": len(model.airway_legs),
        "procedure_charts": len(model.procedure_charts),
        "procedure_segments": len(model.procedure_segments),
        "holdings": len(model.holdings),
        "rejected_records": len(model.rejected_records),
        "rejected_procedures": len(model.rejected_procedures),
    }


def encode(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return {_TAG: "path", _VALUE: str(value)}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            _TAG: type(value).__name__,
            _VALUE: {
                item.name: encode(getattr(value, item.name))
                for item in fields(value)
            },
        }
    if isinstance(value, tuple):
        return {_TAG: "tuple", _VALUE: [encode(item) for item in value]}
    if isinstance(value, frozenset):
        return {
            _TAG: "frozenset",
            _VALUE: _sorted_encoded([encode(item) for item in value]),
        }
    if isinstance(value, set):
        return {
            _TAG: "set",
            _VALUE: _sorted_encoded([encode(item) for item in value]),
        }
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        if all(isinstance(key, str) for key in value):
            return {str(key): encode(item) for key, item in value.items()}
        return {
            _TAG: "dict",
            _VALUE: _sorted_encoded_items(
                [
                    {"k": encode(key), "v": encode(item)}
                    for key, item in value.items()
                ]
            ),
        }
    raise TypeError(f"无法编码中间模型值: {type(value)!r}")


def decode(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [decode(item) for item in value]
    if isinstance(value, dict):
        if _is_tag(value):
            return _decode_tagged(value[_TAG], value[_VALUE])
        return {str(key): decode(item) for key, item in value.items()}
    raise TypeError(f"无法解码中间模型值: {type(value)!r}")


def _gzip_path(path: Path) -> bool:
    return path.name.endswith(".gz")


def _is_tag(value: dict[str, Any]) -> bool:
    return set(value) == {_TAG, _VALUE} and isinstance(value.get(_TAG), str)


def _decode_tagged(name: str, payload: Any) -> Any:
    if name == "path":
        if not isinstance(payload, str):
            raise ValueError("path 标签的值必须是字符串")
        return Path(payload)
    if name == "tuple":
        if not isinstance(payload, list):
            raise ValueError("tuple 标签的值必须是数组")
        return tuple(decode(item) for item in payload)
    if name == "frozenset":
        if not isinstance(payload, list):
            raise ValueError("frozenset 标签的值必须是数组")
        return frozenset(decode(item) for item in payload)
    if name == "set":
        if not isinstance(payload, list):
            raise ValueError("set 标签的值必须是数组")
        return set(decode(item) for item in payload)
    if name == "dict":
        if not isinstance(payload, list):
            raise ValueError("dict 标签的值必须是数组")
        decoded: dict[Any, Any] = {}
        for item in payload:
            if not isinstance(item, dict) or set(item) != {"k", "v"}:
                raise ValueError("dict 标签的每一项必须含 k/v")
            decoded[decode(item["k"])] = decode(item["v"])
        return decoded
    cls = _DATACLASS_TYPES.get(name)
    if cls is None:
        raise ValueError(f"未知的中间模型类型: {name}")
    if not isinstance(payload, dict):
        raise ValueError(f"{name} 标签的值必须是对象")
    return cls(**{key: decode(item) for key, item in payload.items()})


def _encoded_sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sorted_encoded(values: list[Any]) -> list[Any]:
    return sorted(values, key=_encoded_sort_key)


def _sorted_encoded_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: _encoded_sort_key(item["k"]))
