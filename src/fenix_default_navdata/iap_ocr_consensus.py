"""Verify consensus across at least three independent IAP OCR cache runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .iap_ocr import IAP_OCR_ELIGIBLE_STATUSES
from .iap_ocr_audit import audit_iap_ocr_cache
from .iap_ocr_recheck import _report_evidence, _role_report_item
from .model import IapOcrRoleEvidence


class IapOcrConsensusError(ValueError):
    """Raised when a reusable multi-run OCR consensus cannot be verified."""


_ALLOWED_ROLES = frozenset({"IAF", "IF", "FAF", "MAP", "MAPT"})


def _roots(cache_roots: Iterable[Path]) -> tuple[Path, ...]:
    roots = tuple(Path(root).expanduser().resolve() for root in cache_roots)
    if len(roots) < 3:
        raise IapOcrConsensusError("IAP OCR 共识审计至少需要三份独立缓存")
    if len(set(roots)) != len(roots):
        raise IapOcrConsensusError("IAP OCR 共识审计不能重复使用同一缓存目录")
    return roots


def _audit_iap_ocr_role_consensus(
    root: Path,
    cache_roots: Iterable[Path],
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> tuple[dict[str, object], dict[tuple[object, ...], str]]:
    """Compare three or more source-only OCR caches without enabling projection."""
    roots = _roots(cache_roots)
    reports = [
        audit_iap_ocr_cache(
            root,
            cache_root,
            pdf_cache=pdf_cache,
            statuses=statuses,
        )
        for cache_root in roots
    ]
    parsed = [_report_evidence(report) for report in reports]
    (
        canonical_candidates,
        canonical_evidence,
        canonical_profiles,
        canonical_settings,
    ) = parsed[0]
    canonical_keys = set(canonical_evidence)
    all_evidence_keys = [set(evidence) for _, evidence, _, _ in parsed]
    union = set().union(*all_evidence_keys)
    agreed = set.intersection(*all_evidence_keys)

    comparisons: list[dict[str, object]] = []
    all_consistent = True
    for report, (candidates, evidence, profiles, settings) in zip(
        reports[1:],
        parsed[1:],
        strict=True,
    ):
        evidence_keys = set(evidence)
        relation_changed = {
            key
            for key in canonical_keys & evidence_keys
            if canonical_evidence[key] != evidence[key]
        }
        candidate_sets_match = candidates == canonical_candidates
        runtime_profiles_recorded = (
            all(profile is not None for profile in canonical_profiles.values())
            and all(profile is not None for profile in profiles.values())
        )
        runtime_profiles_match = (
            runtime_profiles_recorded
            and profiles == canonical_profiles
        )
        recognition_settings_recorded = (
            all(item is not None for item in canonical_settings.values())
            and all(item is not None for item in settings.values())
        )
        recognition_settings_match = (
            recognition_settings_recorded
            and settings == canonical_settings
        )
        consistent = (
            candidate_sets_match
            and runtime_profiles_match
            and recognition_settings_match
            and not (canonical_keys - evidence_keys)
            and not (evidence_keys - canonical_keys)
            and not relation_changed
        )
        all_consistent = all_consistent and consistent
        comparisons.append({
            "cache_root": report["cache_root"],
            "consistent": consistent,
            "candidate_sets_match": candidate_sets_match,
            "runtime_profiles_recorded": runtime_profiles_recorded,
            "runtime_profiles_match": runtime_profiles_match,
            "recognition_settings_recorded": recognition_settings_recorded,
            "recognition_settings_match": recognition_settings_match,
            "canonical_only": len(canonical_keys - evidence_keys),
            "cache_only": len(evidence_keys - canonical_keys),
            "relation_changed": len(relation_changed),
            "differences": {
                "canonical_only": [
                    _role_report_item(key, canonical_evidence[key])
                    for key in sorted(canonical_keys - evidence_keys)
                ],
                "cache_only": [
                    _role_report_item(key, evidence[key])
                    for key in sorted(evidence_keys - canonical_keys)
                ],
                "relation_changed": [
                    {
                        **_role_report_item(key, canonical_evidence[key]),
                        "cache_relation": evidence[key],
                    }
                    for key in sorted(relation_changed)
                ],
            },
        })

    report = {
        "diagnostic": "iap-ocr-role-consensus-v1",
        "evidence_only": True,
        "projection_allowed": False,
        "cache_count": len(roots),
        "canonical": {
            "cache_root": reports[0]["cache_root"],
            "role_evidence": reports[0]["ocr_role_evidence"],
        },
        "comparison": {
            "consistent": all_consistent,
            "agreement_ratio": len(agreed) / len(union) if union else 1.0,
            "agreed_role_evidence": len(agreed),
        },
        "comparisons": comparisons,
    }
    return report, canonical_evidence


def audit_iap_ocr_role_consensus(
    root: Path,
    cache_roots: Iterable[Path],
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> dict[str, object]:
    """Compare three or more source-only OCR caches without enabling projection."""
    report, _ = _audit_iap_ocr_role_consensus(
        root,
        cache_roots,
        pdf_cache=pdf_cache,
        statuses=statuses,
    )
    return report


def load_iap_ocr_role_evidence(
    root: Path,
    cache_roots: Iterable[Path],
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = ("ambiguous_chart",),
) -> IapOcrRoleEvidence:
    """Accept only unanimous OCR roles for limited existing-chart selection.

    OCR may distinguish an already matched set of IAP chart pages. It never
    creates a primary approach, adds legs, or resolves a no-matching-chart
    group.
    """
    report, canonical_evidence = _audit_iap_ocr_role_consensus(
        root,
        cache_roots,
        pdf_cache=pdf_cache,
        statuses=statuses,
    )
    comparison = report["comparison"]
    if not isinstance(comparison, dict) or comparison.get("consistent") is not True:
        raise IapOcrConsensusError(
            "IAP OCR 多缓存角色证据不一致，不能用于候选构建"
        )

    candidate_roles: dict[tuple[str, str, str, str, str], set[tuple[str, str]]] = {}
    for role_key in canonical_evidence:
        candidate, _page, ident, role = role_key
        if not isinstance(candidate, tuple) or len(candidate) != 5:
            raise IapOcrConsensusError("IAP OCR 角色证据候选键无效")
        if role not in _ALLOWED_ROLES:
            raise IapOcrConsensusError(f"IAP OCR 包含不支持的图页角色: {role}")
        normalized_candidate = tuple(str(value) for value in candidate)
        candidate_roles.setdefault(normalized_candidate, set()).add((str(ident), role))

    return IapOcrRoleEvidence(
        candidate_roles={
            key: frozenset(sorted(roles))
            for key, roles in sorted(candidate_roles.items())
        },
        report={
            "accepted": True,
            "scope": (
                "仅用于已由 424 主进近标签匹配的多图 IAP 候选页消歧；"
                "不创建程序或航段"
            ),
            "cache_count": report["cache_count"],
            "accepted_candidate_pages": len(candidate_roles),
            "accepted_role_evidence": sum(
                len(roles) for roles in candidate_roles.values()
            ),
            "consensus": report,
        },
    )


def write_iap_ocr_role_consensus(output: Path, report: dict[str, object]) -> None:
    """Write an atomic, local-only consensus report."""
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
