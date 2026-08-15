import hashlib
from pathlib import Path
from types import SimpleNamespace

from fenix_default_navdata.cli import main
from fenix_default_navdata.iap_ocr import (
    build_iap_ocr_cache,
    collect_iap_ocr_jobs,
)
from fenix_default_navdata.model import SourceRef
from fenix_default_navdata.ocr_cache import OcrCacheBuild


def _model(root: Path):
    ambiguous_pdf = root / "Terminal" / "ZAAA" / "ZAAA-0C-01.pdf"
    missing_pdf = root / "Terminal" / "ZAAA" / "ZAAA-0C-02.pdf"
    ambiguous_pdf.parent.mkdir(parents=True)
    ambiguous_pdf.write_bytes(b"ambiguous")
    missing_pdf.write_bytes(b"missing")
    ambiguous_chart = SimpleNamespace(
        airport="ZAAA",
        chart_type="instrument-approach-index",
        runways=("01",),
        source=SourceRef(
            str(ambiguous_pdf),
            page=1,
            sha256=hashlib.sha256(ambiguous_pdf.read_bytes()).hexdigest(),
        ),
    )
    missing_chart = SimpleNamespace(
        airport="ZAAA",
        chart_type="instrument-approach-index",
        runways=("02",),
        source=SourceRef(
            str(missing_pdf),
            page=1,
            sha256=hashlib.sha256(missing_pdf.read_bytes()).hexdigest(),
        ),
    )
    ambiguous = SimpleNamespace(
        airport="ZAAA",
        label="R01",
        runway="01",
        kind="进近",
        transition="",
        legs=(object(),),
    )
    missing = SimpleNamespace(
        airport="ZAAA",
        label="R02",
        runway="02",
        kind="进近",
        transition="",
        legs=(object(),),
    )
    return SimpleNamespace(
        procedure_charts=[ambiguous_chart, missing_chart],
        procedure_segments=[ambiguous, missing],
        iap_coverage={
            "unresolved_groups": [
                {
                    "airport": "ZAAA",
                    "label": "R01",
                    "runway": "01",
                    "status": "ambiguous_chart",
                },
                {
                    "airport": "ZAAA",
                    "label": "R02",
                    "runway": "02",
                    "status": "no_matching_chart",
                },
            ],
        },
    ), ambiguous, ambiguous_chart


def test_collect_iap_ocr_jobs_uses_matching_or_same_runway_source_charts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "raw"
    model, ambiguous_segment, ambiguous_chart = _model(root)
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr.matching_iap_charts",
        lambda _model, segment: [ambiguous_chart]
        if segment is ambiguous_segment
        else [],
    )

    jobs = collect_iap_ocr_jobs(root, model)

    assert [job.source_file for job in jobs] == [
        "Terminal/ZAAA/ZAAA-0C-01.pdf",
        "Terminal/ZAAA/ZAAA-0C-02.pdf",
    ]
    assert jobs[0].statuses == ("ambiguous_chart",)
    assert jobs[0].groups == (("ZAAA", "R01", "01"),)
    assert jobs[1].statuses == ("no_matching_chart",)
    assert jobs[1].groups == (("ZAAA", "R02", "02"),)


def test_build_iap_ocr_cache_builds_deterministic_source_hashed_jobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "raw"
    cache_root = tmp_path / "ocr"
    model, ambiguous_segment, ambiguous_chart = _model(root)
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr.load_naip",
        lambda *args, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr.matching_iap_charts",
        lambda _model, segment: [ambiguous_chart]
        if segment is ambiguous_segment
        else [],
    )
    builds: list[tuple[Path, Path]] = []
    retries: list[int] = []

    def fake_build(source_pdf: Path, cache: Path, **kwargs) -> OcrCacheBuild:
        builds.append((source_pdf, cache))
        retries.append(kwargs["retries"])
        return OcrCacheBuild(
            cache=cache,
            source_file=source_pdf.relative_to(root).as_posix(),
            source_sha256=hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
            page_count=1,
            selected_pages=(1,),
            processed_pages=1,
            reused_pages=0,
            complete=True,
        )

    monkeypatch.setattr("fenix_default_navdata.iap_ocr.build_ocr_cache", fake_build)

    report = build_iap_ocr_cache(root, cache_root)

    assert report["planned_pdfs"] == 2
    assert report["processed_pages"] == 2
    assert report["complete_pdfs"] == 2
    assert all(cache_root in cache.parents for _, cache in builds)
    assert all(len(cache.name) == 16 for _, cache in builds)
    assert retries == [2, 2]


def test_cli_iap_ocr_cache_passes_evidence_only_options(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_build(root: Path, cache_root: Path, **kwargs) -> dict[str, object]:
        received.update(root=root, cache_root=cache_root, **kwargs)
        return {"planned_pdfs": 0, "evidence_only": True}

    monkeypatch.setattr(
        "fenix_default_navdata.cli.build_iap_ocr_cache",
        fake_build,
    )

    exit_code = main([
        "iap-ocr-cache",
        "--source-root", "raw",
        "--cache-root", "cache",
        "--pdf-cache", "parsed",
        "--statuses", "ambiguous_chart",
        "--limit", "3",
        "--dry-run",
    ])

    assert exit_code == 0
    assert received == {
        "root": Path("raw"),
        "cache_root": Path("cache"),
        "pdf_cache": Path("parsed"),
        "statuses": ["ambiguous_chart"],
        "command": "ocr-skill",
        "backend": "llamacpp",
        "mode": "markdown",
        "timeout_seconds": 240,
        "render_scale": 3.0,
        "image_profile": "original",
        "runtime_profile": "",
        "force": False,
        "limit": 3,
        "retries": 2,
        "dry_run": True,
    }
