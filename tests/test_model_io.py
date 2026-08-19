from pathlib import Path

import pytest

from fenix_default_navdata.model import (
    Airport,
    AirwayLeg,
    ChartRouteFix,
    IapOcrRoleEvidence,
    NavModel,
    ProcedureChart,
    SourceRef,
    Waypoint,
)
from fenix_default_navdata.model_io import (
    FORMAT_ID,
    SCHEMA_VERSION,
    dump_model,
    encode,
    load_model,
)


def _sample_model(root: Path) -> NavModel:
    source = SourceRef("AD_HP.csv", 2, sha256="ab" * 32)
    model = NavModel(root)
    model.airports["A1"] = Airport(
        "A1",
        "ZBAA",
        "BEIJING",
        40.08,
        116.58,
        115,
        9800,
        10800,
        source,
        magnetic_variation=-7.5,
    )
    model.waypoints.append(
        Waypoint("ZB.P01", "P01", "P01", 40.1, 116.1, source, country="ZB"),
    )
    model.airway_legs.append(
        AirwayLeg(
            "A1",
            10,
            "P01",
            "P02",
            source,
            start_country="ZB",
            end_country="ZB",
        ),
    )
    model.procedure_charts.append(
        ProcedureChart(
            "ZBAA",
            "ZBAA-9A.pdf",
            1,
            "instrument-approach-index",
            "RNP RWY 36L",
            "cd" * 32,
            ("R36L",),
            ("36L",),
            ("FF36L", "RW36L"),
            (),
            (),
            SourceRef("Terminal/ZBAA/ZBAA-9A.pdf", page=1, sha256="ef" * 32),
            route_fixes=(
                ChartRouteFix("FF36L", "FAF"),
                ChartRouteFix("RW36L", "MAPT"),
            ),
        ),
    )
    model.iap_ocr_role_evidence = IapOcrRoleEvidence(
        candidate_roles={
            ("ZBAA", "R36L", "36L", "ZBAA-9A.pdf", "ef" * 32): frozenset(
                {("FF36L", "FAF"), ("RW36L", "MAPT")},
            ),
        },
        report={"accepted": True, "accepted_candidate_pages": 1},
    )
    model.iap_coverage = {
        "procedure_groups": {"unresolved": 10},
        "roles": {"FF36L": {"FAF"}},
    }
    return model


def test_dump_and_load_roundtrip_json_and_gzip(tmp_path: Path) -> None:
    model = _sample_model(tmp_path / "raw")
    json_path = tmp_path / "model.json"
    gzip_path = tmp_path / "model.json.gz"

    json_report = dump_model(model, json_path)
    gzip_report = dump_model(model, gzip_path)

    assert json_report["format"] == FORMAT_ID
    assert json_report["schema_version"] == SCHEMA_VERSION
    assert json_report["gzip"] is False
    assert gzip_report["gzip"] is True
    assert json_report["counts"]["airports"] == 1

    loaded_json = load_model(json_path)
    loaded_gzip = load_model(gzip_path)

    assert encode(loaded_json) == encode(model)
    assert encode(loaded_gzip) == encode(model)
    assert loaded_json.airports["A1"].icao == "ZBAA"
    assert loaded_json.airports["A1"].magnetic_variation == -7.5
    assert loaded_json.iap_ocr_role_evidence is not None
    key = ("ZBAA", "R36L", "36L", "ZBAA-9A.pdf", "ef" * 32)
    assert loaded_json.iap_ocr_role_evidence.candidate_roles[key] == frozenset(
        {("FF36L", "FAF"), ("RW36L", "MAPT")},
    )
    assert loaded_json.iap_coverage["roles"]["FF36L"] == {"FAF"}
    assert loaded_json.procedure_charts[0].route_fixes[0].role == "FAF"


def test_load_model_rejects_unknown_format(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"format": "other", "schema_version": 1, "model": {}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="中间模型格式不是"):
        load_model(path)
