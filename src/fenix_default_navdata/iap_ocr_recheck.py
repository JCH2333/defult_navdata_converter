"""Compare two complete IAP OCR role-evidence cache audits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from .iap_ocr import IAP_OCR_ELIGIBLE_STATUSES
from .iap_ocr_audit import audit_iap_ocr_cache


class IapOcrRecheckError(ValueError):
    """Raised when independent IAP OCR evidence cannot be compared safely."""


_CandidateKey = tuple[str, str, str, str, str]
_RoleKey = tuple[_CandidateKey, int, str, str]
_RuntimeProfiles = dict[_CandidateKey, str | None]


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IapOcrRecheckError(f"IAP OCR 审计缺少 {field}")
    return value.strip()


def _report_evidence(
    report: Mapping[str, object],
) -> tuple[set[_CandidateKey], dict[_RoleKey, str], _RuntimeProfiles]:
    if report.get("diagnostic") != "iap-ocr-evidence-audit-v2":
        raise IapOcrRecheckError("IAP OCR 重跑比较只接受 v2 审计报告")
    if report.get("evidence_only") is not True or report.get("projection_allowed") is not False:
        raise IapOcrRecheckError("IAP OCR 审计不具备不可投影证据边界")
    groups = report.get("groups")
    if not isinstance(groups, list):
        raise IapOcrRecheckError("IAP OCR 审计缺少分组明细")

    candidates: set[_CandidateKey] = set()
    evidence: dict[_RoleKey, str] = {}
    runtime_profiles: _RuntimeProfiles = {}
    for group in groups:
        if not isinstance(group, Mapping):
            raise IapOcrRecheckError("IAP OCR 审计分组格式无效")
        airport = _text(group.get("airport"), "机场")
        label = _text(group.get("label"), "程序标签")
        runway = _text(group.get("runway"), "跑道")
        group_candidates = group.get("candidates")
        if not isinstance(group_candidates, list):
            raise IapOcrRecheckError("IAP OCR 审计分组缺少候选图页")
        for candidate in group_candidates:
            if not isinstance(candidate, Mapping):
                raise IapOcrRecheckError("IAP OCR 审计候选图页格式无效")
            if candidate.get("cache_state") != "complete":
                raise IapOcrRecheckError("IAP OCR 重跑比较要求两份缓存均完整")
            key = (
                airport,
                label,
                runway,
                _text(candidate.get("source_file"), "源图页"),
                _text(candidate.get("source_sha256"), "源图页 SHA-256").lower(),
            )
            candidates.add(key)
            profile_value = candidate.get("ocr_runtime_profile")
            runtime_profile = (
                profile_value.strip()
                if isinstance(profile_value, str) and profile_value.strip()
                else None
            )
            previous_profile = runtime_profiles.setdefault(key, runtime_profile)
            if previous_profile != runtime_profile:
                raise IapOcrRecheckError("同一 IAP OCR 候选图页混用了运行时标识")
            matches = candidate.get("ocr_role_matches")
            if not isinstance(matches, list):
                raise IapOcrRecheckError("IAP OCR 审计缺少角色证据")
            for match in matches:
                if not isinstance(match, Mapping):
                    raise IapOcrRecheckError("IAP OCR 角色证据格式无效")
                page = match.get("page")
                if not isinstance(page, int) or page < 1:
                    raise IapOcrRecheckError("IAP OCR 角色证据页码无效")
                role_key = (
                    key,
                    page,
                    _text(match.get("ident"), "航点").upper(),
                    _text(match.get("role"), "角色").upper(),
                )
                relation = _text(match.get("relation"), "相邻关系")
                if role_key in evidence:
                    raise IapOcrRecheckError("IAP OCR 审计包含重复角色证据")
                evidence[role_key] = relation
    return candidates, evidence, runtime_profiles


def _role_report_item(key: _RoleKey, relation: str) -> dict[str, object]:
    (airport, label, runway, source_file, source_sha256), page, ident, role = key
    return {
        "airport": airport,
        "label": label,
        "runway": runway,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "page": page,
        "ident": ident,
        "role": role,
        "relation": relation,
    }


def audit_iap_ocr_role_recheck(
    root: Path,
    canonical_cache: Path,
    rerun_cache: Path,
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> dict[str, object]:
    """Compare source-only IAP OCR role evidence without selecting any chart."""
    canonical = audit_iap_ocr_cache(
        root,
        canonical_cache,
        pdf_cache=pdf_cache,
        statuses=statuses,
    )
    rerun = audit_iap_ocr_cache(
        root,
        rerun_cache,
        pdf_cache=pdf_cache,
        statuses=statuses,
    )
    canonical_candidates, canonical_evidence, canonical_profiles = _report_evidence(canonical)
    rerun_candidates, rerun_evidence, rerun_profiles = _report_evidence(rerun)
    canonical_keys = set(canonical_evidence)
    rerun_keys = set(rerun_evidence)
    agreed = canonical_keys & rerun_keys
    relation_changed = {
        key
        for key in agreed
        if canonical_evidence[key] != rerun_evidence[key]
    }
    candidate_sets_match = canonical_candidates == rerun_candidates
    runtime_profiles_recorded = (
        all(profile is not None for profile in canonical_profiles.values())
        and all(profile is not None for profile in rerun_profiles.values())
    )
    runtime_profiles_match = (
        runtime_profiles_recorded
        and canonical_profiles == rerun_profiles
    )
    union = canonical_keys | rerun_keys
    consistent = (
        candidate_sets_match
        and runtime_profiles_match
        and not (canonical_keys - rerun_keys)
        and not (rerun_keys - canonical_keys)
        and not relation_changed
    )
    return {
        "diagnostic": "iap-ocr-role-recheck-v1",
        "evidence_only": True,
        "projection_allowed": False,
        "canonical": {
            "cache_root": canonical["cache_root"],
            "role_evidence": canonical["ocr_role_evidence"],
        },
        "rerun": {
            "cache_root": rerun["cache_root"],
            "role_evidence": rerun["ocr_role_evidence"],
        },
        "comparison": {
            "consistent": consistent,
            "candidate_sets_match": candidate_sets_match,
            "runtime_profiles_recorded": runtime_profiles_recorded,
            "runtime_profiles_match": runtime_profiles_match,
            "agreement_ratio": len(agreed) / len(union) if union else 1.0,
        },
        "runtime_profiles": {
            "canonical": sorted(
                {profile for profile in canonical_profiles.values() if profile is not None}
            ),
            "rerun": sorted(
                {profile for profile in rerun_profiles.values() if profile is not None}
            ),
            "canonical_unrecorded": sum(
                profile is None for profile in canonical_profiles.values()
            ),
            "rerun_unrecorded": sum(
                profile is None for profile in rerun_profiles.values()
            ),
        },
        "role_evidence": {
            "agreed": len(agreed),
            "canonical_only": len(canonical_keys - rerun_keys),
            "rerun_only": len(rerun_keys - canonical_keys),
            "relation_changed": len(relation_changed),
        },
        "differences": {
            "canonical_only": [
                _role_report_item(key, canonical_evidence[key])
                for key in sorted(canonical_keys - rerun_keys)
            ],
            "rerun_only": [
                _role_report_item(key, rerun_evidence[key])
                for key in sorted(rerun_keys - canonical_keys)
            ],
            "relation_changed": [
                {
                    **_role_report_item(key, canonical_evidence[key]),
                    "rerun_relation": rerun_evidence[key],
                }
                for key in sorted(relation_changed)
            ],
        },
    }


def write_iap_ocr_role_recheck(output: Path, report: dict[str, object]) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
