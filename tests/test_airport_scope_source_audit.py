import json
from pathlib import Path

from fenix_default_navdata.airport_scope_source_audit import (
    audit_airport_scope_sources,
)
from fenix_default_navdata.model import Airport, NavModel, SourceRef


def test_airport_scope_audit_separates_direct_source_and_reference_only(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    (raw / "Terminal" / "ZBAA").mkdir(parents=True)
    (raw / "AD_HP.csv").write_text(
        "AD_HP_ID,CODE_ID\nA1,ZBAA\nA2,ZBAR\n",
        encoding="utf-8",
    )
    (raw / "RTE_SEG.csv").write_text(
        "CODE_AIRPORT,IDENT\nZBAR,TEST\n",
        encoding="utf-8",
    )
    history = tmp_path / "ContentHistory.json"
    history.write_text(
        json.dumps({"items": [
            {"type": "Airport", "content": "ZBAA"},
            {"type": "Airport", "content": "ZGFS"},
        ]}),
        encoding="utf-8",
    )
    model = NavModel(raw)
    model.airports["A1"] = Airport(
        "A1", "ZBAA", "A", 1.0, 2.0, 0, 0, 0, SourceRef("AD_HP.csv", 2)
    )
    report = audit_airport_scope_sources(
        raw,
        model,
        reference_content_history=history,
    )

    assert report["diagnostic"] == "airport-scope-source-audit-v1"
    assert report["reference_records_read"] is False
    assert report["summary"]["source_airport_total"] == 2
    assert report["summary"]["reference_only_total"] == 1
    assert report["reference_only"] == [
        {"airport": "ZGFS", "source_evidence": []}
    ]
    assert report["source_evidence_overlap_counts"]["ad_hp,csv_text"] == 1
