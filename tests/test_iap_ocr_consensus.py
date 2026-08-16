from pathlib import Path

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.iap_ocr_consensus import (
    IapOcrConsensusError,
    audit_iap_ocr_role_consensus,
    load_iap_ocr_role_evidence,
)


def _report(
    cache_root: str,
    *,
    relation: str = "same_row",
    image_profile: str = "original",
) -> dict[str, object]:
    return {
        "diagnostic": "iap-ocr-evidence-audit-v2",
        "evidence_only": True,
        "projection_allowed": False,
        "cache_root": cache_root,
        "ocr_role_evidence": {"matches": 1},
        "groups": [{
            "airport": "ZAAA",
            "label": "R01",
            "runway": "01",
            "candidates": [{
                "source_file": "Terminal/ZAAA/first.pdf",
                "source_sha256": "a" * 64,
                "cache_state": "complete",
                "ocr_runtime_profile": "deterministic-profile",
                "ocr_recognition_settings": {
                    "command": "ocr-skill",
                    "backend": "llamacpp",
                    "mode": "ocr",
                    "image_profile": image_profile,
                    "render_scale": 3.0,
                    "runtime_profile": "deterministic-profile",
                },
                "ocr_role_matches": [{
                    "page": 1,
                    "ident": "FIX01",
                    "role": "FAF",
                    "relation": relation,
                }],
            }],
        }],
    }


def test_iap_ocr_consensus_requires_three_identical_complete_caches(monkeypatch) -> None:
    reports = [_report("a"), _report("b"), _report("c")]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_consensus.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_consensus(
        Path("raw"),
        [Path("a"), Path("b"), Path("c")],
    )

    assert report["evidence_only"] is True
    assert report["projection_allowed"] is False
    assert report["cache_count"] == 3
    assert report["comparison"] == {
        "consistent": True,
        "agreement_ratio": 1.0,
        "agreed_role_evidence": 1,
    }
    assert [item["consistent"] for item in report["comparisons"]] == [True, True]


def test_iap_ocr_consensus_reports_any_relation_change_without_projection(monkeypatch) -> None:
    reports = [_report("a"), _report("b"), _report("c", relation="vertical_stack")]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_consensus.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_consensus(
        Path("raw"),
        [Path("a"), Path("b"), Path("c")],
    )

    assert report["comparison"] == {
        "consistent": False,
        "agreement_ratio": 1.0,
        "agreed_role_evidence": 1,
    }
    assert report["comparisons"][1]["relation_changed"] == 1
    assert report["projection_allowed"] is False


def test_iap_ocr_consensus_rejects_changed_image_profile(monkeypatch) -> None:
    reports = [
        _report("a"),
        _report("b"),
        _report("c", image_profile="autocontrast-grayscale"),
    ]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_consensus.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_consensus(
        Path("raw"),
        [Path("a"), Path("b"), Path("c")],
    )

    assert report["comparison"]["consistent"] is False
    assert report["comparisons"][1]["runtime_profiles_match"] is True
    assert report["comparisons"][1]["recognition_settings_recorded"] is True
    assert report["comparisons"][1]["recognition_settings_match"] is False


def test_iap_ocr_consensus_rejects_too_few_or_duplicate_cache_roots() -> None:
    with pytest.raises(IapOcrConsensusError, match="至少需要三份"):
        audit_iap_ocr_role_consensus(Path("raw"), [Path("a"), Path("b")])
    with pytest.raises(IapOcrConsensusError, match="不能重复"):
        audit_iap_ocr_role_consensus(
            Path("raw"),
            [Path("a"), Path("a"), Path("c")],
        )


def test_iap_ocr_consensus_loads_only_unanimous_roles_for_matching_chart_pages(
    monkeypatch,
) -> None:
    reports = [_report("a"), _report("b"), _report("c")]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_consensus.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    evidence = load_iap_ocr_role_evidence(
        Path("raw"),
        [Path("a"), Path("b"), Path("c")],
    )

    assert evidence.roles_for((
        "ZAAA",
        "R01",
        "01",
        "Terminal/ZAAA/first.pdf",
        "a" * 64,
    )) == {"FIX01": {"FAF"}}
    assert evidence.report["accepted"] is True
    assert evidence.report["accepted_candidate_pages"] == 1
    assert evidence.report["accepted_role_evidence"] == 1


def test_iap_ocr_consensus_rejects_nonunanimous_roles_for_candidate_build(
    monkeypatch,
) -> None:
    reports = [_report("a"), _report("b"), _report("c", relation="vertical_stack")]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_consensus.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    with pytest.raises(IapOcrConsensusError, match="不一致"):
        load_iap_ocr_role_evidence(
            Path("raw"),
            [Path("a"), Path("b"), Path("c")],
        )


def test_cli_iap_ocr_consensus_passes_source_only_options(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_audit(root: Path, caches: list[Path], **kwargs) -> dict[str, object]:
        received.update(root=root, caches=caches, **kwargs)
        return {"comparison": {"consistent": True}}

    monkeypatch.setattr(
        "fenix_default_navdata.cli.audit_iap_ocr_role_consensus",
        fake_audit,
    )

    exit_code = main([
        "iap-ocr-consensus",
        "--source-root", "raw",
        "--pdf-cache", "parsed",
        "--cache-roots", "one", "two", "three",
        "--statuses", "ambiguous_chart",
        "--require-agreement",
    ])

    assert exit_code == 0
    assert received == {
        "root": Path("raw"),
        "caches": [Path("one"), Path("two"), Path("three")],
        "pdf_cache": Path("parsed"),
        "statuses": ["ambiguous_chart"],
    }
