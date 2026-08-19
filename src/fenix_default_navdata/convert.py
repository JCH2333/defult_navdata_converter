from __future__ import annotations

import json
import os
from pathlib import Path

from .bgl import find_compiler
from .iap_ocr_consensus import load_iap_ocr_role_evidence
from .model import NavModel
from .model_io import dump_model
from .package import build_candidate
from .profile import DEFAULT_CYCLE, Cycle, validate_cycle
from .source import load_naip


def convert(
    raw_root: Path,
    nav_base: Path,
    nav_jepp: Path,
    output: Path,
    *,
    cycle: Cycle,
    reference: Path | None = None,
    compiler: Path | None = None,
    pdf_cache: Path | None = None,
    general_doc_cache: Path | None = None,
    general_doc_key_point_cache_directory: str = "enr-4.4",
    general_doc_airway_cache_directories: tuple[str, ...] = (),
    iap_ocr_cache_roots: tuple[Path, ...] = (),
    baseline_db: Path | None = None,
    baseline_tolerance_nm: float = 0.25,
    model: NavModel | None = None,
    model_path: Path | None = None,
    normalize_package_tool_times: bool = True,
) -> dict[str, object]:
    validate_cycle(cycle)
    result = build_candidate(
        raw_root=raw_root.resolve(),
        nav_base=nav_base.resolve(),
        nav_jepp=nav_jepp.resolve(),
        output=output.resolve(),
        cycle=cycle,
        compiler=find_compiler(compiler),
        reference=reference.resolve() if reference else None,
        pdf_cache=pdf_cache,
        general_doc_cache=general_doc_cache,
        general_doc_key_point_cache_directory=general_doc_key_point_cache_directory,
        general_doc_airway_cache_directories=general_doc_airway_cache_directories,
        iap_ocr_cache_roots=tuple(
            cache.expanduser().resolve() for cache in iap_ocr_cache_roots
        ),
        baseline_db=baseline_db.resolve() if baseline_db else None,
        baseline_tolerance_nm=baseline_tolerance_nm,
        model=model,
        model_path=model_path.resolve() if model_path else None,
        normalize_package_tool_times=normalize_package_tool_times,
    )
    (output / "conversion-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8",
    )
    return result


def export_intermediate_model(
    raw_root: Path,
    output: Path,
    *,
    pdf_cache: Path | None = None,
    general_doc_cache: Path | None = None,
    general_doc_key_point_cache_directory: str = "enr-4.4",
    general_doc_airway_cache_directories: tuple[str, ...] = (),
    iap_ocr_cache_roots: tuple[Path, ...] = (),
) -> dict[str, object]:
    """Parse 424 into NavModel and dump a reusable adapter snapshot."""

    raw_root = raw_root.expanduser().resolve()
    if pdf_cache is None:
        cache_root = Path(os.environ.get("LOCALAPPDATA", str(output.parent)))
        pdf_cache = (
            cache_root
            / "default_navdata_converter"
            / f"pdf-evidence-cache-{DEFAULT_CYCLE.number}r{DEFAULT_CYCLE.revision}"
        )
    pdf_cache = pdf_cache.expanduser().resolve()
    resolved_ocr_roots = tuple(
        cache.expanduser().resolve() for cache in iap_ocr_cache_roots
    )
    iap_ocr_role_evidence = (
        load_iap_ocr_role_evidence(
            raw_root,
            resolved_ocr_roots,
            pdf_cache=pdf_cache,
        )
        if resolved_ocr_roots
        else None
    )
    model = load_naip(
        raw_root,
        pdf_cache=pdf_cache,
        general_doc_cache=general_doc_cache,
        general_doc_key_point_cache_directory=general_doc_key_point_cache_directory,
        general_doc_airway_cache_directories=general_doc_airway_cache_directories,
        iap_ocr_role_evidence=iap_ocr_role_evidence,
        include_terminal_documents=True,
    )
    report = dump_model(model, output)
    report["source"] = {"raw_424": str(raw_root)}
    report["pdf_cache"] = str(pdf_cache)
    report["general_doc_cache"] = str(general_doc_cache) if general_doc_cache else None
    report["iap_ocr_cache_roots"] = [str(path) for path in resolved_ocr_roots]
    return report
