from pathlib import Path

from fenix_default_navdata import cli


def test_ocr_audit_compares_available_rerun_pages_without_an_extra_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def audit(
        source_root: Path,
        canonical_cache: Path,
        rerun_cache: Path,
    ) -> dict[str, object]:
        captured.update(
            source_root=source_root,
            canonical_cache=canonical_cache,
            rerun_cache=rerun_cache,
        )
        return {"comparison": {"consistent": True}}

    monkeypatch.setattr(cli, "audit_enroute_navaid_ocr_rerun", audit)

    result = cli.main([
        "ocr-audit",
        "--source-root", "raw",
        "--canonical-cache", "canonical",
        "--rerun-cache", "rerun",
    ])

    assert result == 0
    assert captured == {
        "source_root": Path("raw"),
        "canonical_cache": Path("canonical"),
        "rerun_cache": Path("rerun"),
    }
