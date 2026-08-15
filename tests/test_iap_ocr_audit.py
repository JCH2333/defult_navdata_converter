import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from fenix_default_navdata.cli import main
from fenix_default_navdata.iap_ocr_audit import audit_iap_ocr_cache
from fenix_default_navdata.model import ChartTerminalLeg, ProcedureSegment, SourceRef


def _payload(markdown: str) -> dict[str, object]:
    return {
        "ok": True,
        "data": {
            "documents": [{
                "source_kind": "image",
                "markdown": markdown,
            }],
        },
    }


def _write_cache(
    root: Path,
    cache_root: Path,
    source: Path,
    markdown: str,
) -> None:
    source_file = source.relative_to(root).as_posix()
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = cache_root / Path(source_file).with_suffix("") / source_sha256[:16]
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "page_count": 1,
    }), encoding="utf-8")
    (cache / "page-0001.json").write_text(
        json.dumps(_payload(markdown)),
        encoding="utf-8",
    )


def test_iap_ocr_audit_reports_unique_identifier_evidence_without_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "raw"
    cache_root = tmp_path / "ocr"
    first = root / "Terminal" / "ZAAA" / "first.pdf"
    second = root / "Terminal" / "ZAAA" / "second.pdf"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first_source = SourceRef(
        str(first),
        1,
        1,
        hashlib.sha256(first.read_bytes()).hexdigest(),
    )
    second_source = SourceRef(
        str(second),
        1,
        1,
        hashlib.sha256(second.read_bytes()).hexdigest(),
    )
    segment = ProcedureSegment(
        "ZAAA",
        "R01",
        "approach",
        "01",
        "",
        (
            ChartTerminalLeg("R01", "01", "IF", "FIX01", "fixture", sequence=1),
            ChartTerminalLeg("R01", "01", "TF", "FIX02", "fixture", sequence=2),
            ChartTerminalLeg("R01", "01", "TF", "FIX03", "fixture", sequence=3),
        ),
        first_source,
    )
    first_chart = SimpleNamespace(
        source=first_source,
        airport="ZAAA",
        chart_type="instrument-approach-index",
        runways=("01",),
    )
    second_chart = SimpleNamespace(
        source=second_source,
        airport="ZAAA",
        chart_type="instrument-approach-index",
        runways=("01",),
    )
    model = SimpleNamespace(
        procedure_segments=[segment],
        procedure_charts=[first_chart, second_chart],
        iap_coverage={
            "unresolved_groups": [{
                "airport": "ZAAA",
                "label": "R01",
                "runway": "01",
                "status": "ambiguous_chart",
            }],
        },
    )
    _write_cache(root, cache_root, first, "IAF[[10, 10, 30, 20]]\nFIX01[[12, 24, 38, 34]]")
    _write_cache(root, cache_root, second, "FIX01 FIX02 FIX03")
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_audit.load_naip",
        lambda *args, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.iap_ocr_audit.matching_iap_charts",
        lambda *_args: [first_chart, second_chart],
    )

    report = audit_iap_ocr_cache(root, cache_root)

    assert report["evidence_only"] is True
    assert report["projection_allowed"] is False
    assert report["summary"] == {
        "groups": 1,
        "evidence_status_counts": {"unique_identifier_only": 1},
        "cache_state_counts": {"complete": 2},
    }
    assert report["ocr_role_evidence"] == {
        "matches": 1,
        "groups_with_matches": 1,
        "candidates_with_matches": 1,
        "role_counts": {"IAF": 1},
    }
    assert report["groups"][0]["candidates"][1]["ocr_identifier_matches"] == [
        "FIX01",
        "FIX02",
        "FIX03",
    ]
    assert report["groups"][0]["candidates"][0]["ocr_role_matches"] == [{
        "page": 1,
        "ident": "FIX01",
        "role": "IAF",
        "relation": "vertical_stack",
    }]


def test_cli_iap_ocr_audit_passes_source_and_cache_options(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_audit(root: Path, cache_root: Path, **kwargs) -> dict[str, object]:
        received.update(root=root, cache_root=cache_root, **kwargs)
        return {"evidence_only": True, "projection_allowed": False}

    monkeypatch.setattr(
        "fenix_default_navdata.cli.audit_iap_ocr_cache",
        fake_audit,
    )

    exit_code = main([
        "iap-ocr-audit",
        "--source-root", "raw",
        "--cache-root", "cache",
        "--pdf-cache", "parsed",
        "--statuses", "ambiguous_chart",
    ])

    assert exit_code == 0
    assert received == {
        "root": Path("raw"),
        "cache_root": Path("cache"),
        "pdf_cache": Path("parsed"),
        "statuses": ["ambiguous_chart"],
    }
