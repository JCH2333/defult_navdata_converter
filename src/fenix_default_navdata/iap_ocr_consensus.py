"""Verify consensus across at least three independent IAP OCR cache runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .iap_ocr import IAP_OCR_ELIGIBLE_STATUSES
from .iap_ocr_audit import audit_iap_ocr_cache
from .iap_ocr_recheck import _report_evidence, _role_report_item


class IapOcrConsensusError(ValueError):
    """Raised when a reusable multi-run OCR consensus cannot be verified."""


def _roots(cache_roots: Iterable[Path]) -> tuple[Path, ...]:
    roots = tuple(Path(root).expanduser().resolve() for root in cache_roots)
    if len(roots) < 3:
        raise IapOcrConsensusError("IAP OCR 共识审计至少需要三份独立缓存")
    if len(set(roots)) != len(roots):
        raise IapOcrConsensusError("IAP OCR 共识审计不能重复使用同一缓存目录")
    return roots


def audit_iap_ocr_role_consensus(
    root: Path,
    cache_roots: Iterable[Path],
    *,
    pdf_cache: Path | None = None,
    statuses: Iterable[str] = IAP_OCR_ELIGIBLE_STATUSES,
) -> dict[str, object]:
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

    return {
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
