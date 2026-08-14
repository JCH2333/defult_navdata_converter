from __future__ import annotations

import json
from pathlib import Path

from .bgl import find_compiler
from .package import build_candidate
from .profile import Cycle, validate_cycle


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
    baseline_db: Path | None = None,
    baseline_tolerance_nm: float = 0.25,
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
        baseline_db=baseline_db.resolve() if baseline_db else None,
        baseline_tolerance_nm=baseline_tolerance_nm,
    )
    (output / "conversion-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8",
    )
    return result
