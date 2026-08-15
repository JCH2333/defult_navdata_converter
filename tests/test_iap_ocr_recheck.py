from pathlib import Path

from fenix_default_navdata.cli import main
from fenix_default_navdata.iap_ocr_recheck import audit_iap_ocr_role_recheck


def _report(
    *,
    relation: str = "same_row",
    extra: bool = False,
    runtime_profile: str | None = "test-runtime-profile",
    image_profile: str | None = "original",
) -> dict[str, object]:
    matches = [{
        "page": 1,
        "ident": "FIX01",
        "role": "FAF",
        "relation": relation,
    }]
    if extra:
        matches.append({
            "page": 1,
            "ident": "FIX02",
            "role": "MAPT",
            "relation": "same_ocr_item",
        })
    return {
        "diagnostic": "iap-ocr-evidence-audit-v2",
        "evidence_only": True,
        "projection_allowed": False,
        "cache_root": "cache",
        "ocr_role_evidence": {"matches": len(matches)},
        "groups": [{
            "airport": "ZAAA",
            "label": "R01",
            "runway": "01",
            "candidates": [{
                "source_file": "Terminal/ZAAA/first.pdf",
                "source_sha256": "a" * 64,
                "cache_state": "complete",
                "ocr_runtime_profile": runtime_profile,
                "ocr_recognition_settings": (
                    {
                        "command": "ocr-skill",
                        "backend": "llamacpp",
                        "mode": "ocr",
                        "image_profile": image_profile,
                        "render_scale": 3.0,
                        "runtime_profile": runtime_profile,
                    }
                    if runtime_profile is not None and image_profile is not None
                    else None
                ),
                "ocr_role_matches": matches,
            }],
        }],
    }


def test_iap_ocr_recheck_requires_exact_role_evidence_agreement(monkeypatch) -> None:
    reports = [_report(), _report()]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_recheck.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_recheck(Path("raw"), Path("canonical"), Path("rerun"))

    assert report["evidence_only"] is True
    assert report["projection_allowed"] is False
    assert report["comparison"] == {
        "consistent": True,
        "candidate_sets_match": True,
        "runtime_profiles_recorded": True,
        "runtime_profiles_match": True,
        "recognition_settings_recorded": True,
        "recognition_settings_match": True,
        "agreement_ratio": 1.0,
    }
    assert report["role_evidence"] == {
        "agreed": 1,
        "canonical_only": 0,
        "rerun_only": 0,
        "relation_changed": 0,
    }


def test_iap_ocr_recheck_reports_unagreed_evidence_without_projection(monkeypatch) -> None:
    reports = [_report(), _report(extra=True)]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_recheck.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_recheck(Path("raw"), Path("canonical"), Path("rerun"))

    assert report["comparison"]["consistent"] is False
    assert report["role_evidence"] == {
        "agreed": 1,
        "canonical_only": 0,
        "rerun_only": 1,
        "relation_changed": 0,
    }
    assert report["differences"]["rerun_only"] == [{
        "airport": "ZAAA",
        "label": "R01",
        "runway": "01",
        "source_file": "Terminal/ZAAA/first.pdf",
        "source_sha256": "a" * 64,
        "page": 1,
        "ident": "FIX02",
        "role": "MAPT",
        "relation": "same_ocr_item",
    }]
    assert report["projection_allowed"] is False


def test_iap_ocr_recheck_rejects_unrecorded_or_changed_runtime_profile(monkeypatch) -> None:
    reports = [
        _report(runtime_profile="deterministic-a"),
        _report(runtime_profile="deterministic-b"),
    ]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_recheck.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_recheck(Path("raw"), Path("canonical"), Path("rerun"))

    assert report["comparison"]["consistent"] is False
    assert report["comparison"]["runtime_profiles_recorded"] is True
    assert report["comparison"]["runtime_profiles_match"] is False
    assert report["comparison"]["recognition_settings_match"] is False
    assert report["runtime_profiles"] == {
        "canonical": ["deterministic-a"],
        "rerun": ["deterministic-b"],
        "canonical_unrecorded": 0,
        "rerun_unrecorded": 0,
    }


def test_iap_ocr_recheck_rejects_changed_image_profile_with_same_runtime_profile(
    monkeypatch,
) -> None:
    reports = [
        _report(image_profile="original"),
        _report(image_profile="autocontrast-grayscale"),
    ]
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_recheck.audit_iap_ocr_cache",
        lambda *_args, **_kwargs: reports.pop(0),
    )

    report = audit_iap_ocr_role_recheck(Path("raw"), Path("canonical"), Path("rerun"))

    assert report["comparison"]["consistent"] is False
    assert report["comparison"]["runtime_profiles_match"] is True
    assert report["comparison"]["recognition_settings_recorded"] is True
    assert report["comparison"]["recognition_settings_match"] is False
    assert report["recognition_settings"]["canonical"][0]["image_profile"] == "original"
    assert (
        report["recognition_settings"]["rerun"][0]["image_profile"]
        == "autocontrast-grayscale"
    )


def test_cli_iap_ocr_recheck_passes_source_only_options(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_audit(root: Path, canonical: Path, rerun: Path, **kwargs) -> dict[str, object]:
        received.update(root=root, canonical=canonical, rerun=rerun, **kwargs)
        return {"comparison": {"consistent": True}}

    monkeypatch.setattr(
        "fenix_default_navdata.cli.audit_iap_ocr_role_recheck",
        fake_audit,
    )

    exit_code = main([
        "iap-ocr-recheck",
        "--source-root", "raw",
        "--canonical-cache", "canonical",
        "--rerun-cache", "rerun",
        "--pdf-cache", "parsed",
        "--statuses", "ambiguous_chart",
        "--require-agreement",
    ])

    assert exit_code == 0
    assert received == {
        "root": Path("raw"),
        "canonical": Path("canonical"),
        "rerun": Path("rerun"),
        "pdf_cache": Path("parsed"),
        "statuses": ["ambiguous_chart"],
    }
