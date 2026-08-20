from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from .model import NavModel, is_china_icao


class AirportScopeSourceAuditError(RuntimeError):
    """输入不是可审计的机场范围或来源文件时抛出。"""


def _read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return list(csv.DictReader(raw.decode(encoding).splitlines()))
        except UnicodeDecodeError:
            continue
    raise AirportScopeSourceAuditError(f"不支持的 CSV 编码: {path}")


def _reference_airports(path: Path | None) -> set[str]:
    if path is None:
        return set()
    source = path.expanduser().resolve()
    if not source.is_file():
        raise AirportScopeSourceAuditError(f"参考 ContentHistory 不存在: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise AirportScopeSourceAuditError(f"参考 ContentHistory 无法读取: {source}") from error
    return {
        str(item.get("content", "")).strip().upper()
        for item in payload.get("items", [])
        if item.get("type") == "Airport"
        and is_china_icao(str(item.get("content", "")).strip().upper())
    }


def _candidate_airports(path: Path | None) -> set[str]:
    if path is None:
        return set()
    source = path.expanduser().resolve()
    if not source.is_file():
        raise AirportScopeSourceAuditError(f"候选 XML 不存在: {source}")
    try:
        root = ET.parse(source).getroot()
    except (OSError, ET.ParseError) as error:
        raise AirportScopeSourceAuditError(f"候选 XML 无法解析: {source}") from error
    return {
        str(element.get("ident", "")).strip().upper()
        for element in root.iter("Airport")
        if element.get("ident")
    }


def _source_evidence(
    root: Path,
    *,
    probe_idents: set[str] | None = None,
) -> dict[str, set[str]]:
    evidence = {
        "ad_hp": set(),
        "terminal_directory": set(),
        "csv_text": set(),
    }
    ad_hp = root / "AD_HP.csv"
    if ad_hp.is_file():
        for row in _read_csv(ad_hp):
            ident = (row.get("CODE_ID") or "").strip().upper()
            if is_china_icao(ident):
                evidence["ad_hp"].add(ident)

    terminal = root / "Terminal"
    if terminal.is_dir():
        evidence["terminal_directory"] = {
            path.name.upper()
            for path in terminal.iterdir()
            if path.is_dir() and is_china_icao(path.name.upper())
        }

    known = set().union(*evidence.values(), probe_idents or set())
    for path in root.glob("*.csv"):
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_bytes().decode("gbk", errors="replace")
        for ident in known:
            if re.search(rf"(?<![A-Z0-9]){re.escape(ident)}(?![A-Z0-9])", text):
                evidence["csv_text"].add(ident)
    return evidence


def _source_labels(ident: str, evidence: dict[str, set[str]]) -> list[str]:
    return [label for label, values in evidence.items() if ident in values]


def audit_airport_scope_sources(
    raw_root: Path,
    model: NavModel,
    *,
    candidate_xml: Path | None = None,
    reference_content_history: Path | None = None,
) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise AirportScopeSourceAuditError(f"424 原始目录不存在: {root}")

    model_airports = {
        airport.icao.strip().upper()
        for airport in model.airports.values()
        if airport.icao
    }
    candidate_airports = _candidate_airports(candidate_xml)
    reference_airports = _reference_airports(reference_content_history)
    evidence = _source_evidence(root, probe_idents=reference_airports)
    source_airports = set().union(*evidence.values())

    def rows(values: set[str]) -> list[dict[str, object]]:
        return [
            {"airport": ident, "source_evidence": _source_labels(ident, evidence)}
            for ident in sorted(values)
        ]

    reference_only = reference_airports - source_airports
    return {
        "diagnostic": "airport-scope-source-audit-v1",
        "read_only": True,
        "reference_records_read": False,
        "reference_metadata_read": reference_content_history is not None,
        "source": {
            "raw_root": str(root),
            "candidate_xml": (
                str(candidate_xml.expanduser().resolve())
                if candidate_xml is not None
                else None
            ),
            "reference_content_history": (
                str(reference_content_history.expanduser().resolve())
                if reference_content_history is not None
                else None
            ),
        },
        "sets": {
            "source_airports": sorted(source_airports),
            "model_airports": sorted(model_airports),
            "candidate_airports": sorted(candidate_airports),
            "reference_airports": sorted(reference_airports),
        },
        "summary": {
            "source_airport_total": len(source_airports),
            "model_airport_total": len(model_airports),
            "candidate_airport_total": len(candidate_airports),
            "reference_airport_total": len(reference_airports),
            "reference_only_total": len(reference_only),
            "candidate_only_total": len(candidate_airports - reference_airports),
            "model_without_direct_source_total": len(model_airports - source_airports),
            "reference_without_direct_source_total": len(reference_only),
        },
        "source_evidence_counts": {
            name: len(values) for name, values in evidence.items()
        },
        "source_evidence_overlap_counts": dict(sorted(Counter(
            ",".join(_source_labels(ident, evidence)) or "none"
            for ident in source_airports
        ).items())),
        "reference_only": rows(reference_only),
        "candidate_only": rows(candidate_airports - reference_airports),
        "model_without_direct_source": rows(model_airports - source_airports),
    }


def write_airport_scope_source_audit(
    path: Path,
    report: dict[str, object],
) -> None:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
