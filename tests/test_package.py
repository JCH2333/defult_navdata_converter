import json
from pathlib import Path

import pytest

from fenix_default_navdata.baseline import BaselineIndex, BaselineNavaid
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.model import (
    AirwayLeg,
    IapOcrRoleEvidence,
    NavModel,
    Navaid,
    RejectedProcedure,
    RejectedRecord,
    SourceRef,
    Waypoint,
)
from fenix_default_navdata.official_index import OfficialNavaidIndex, OfficialWaypoint
from fenix_default_navdata.package import (
    AIRPORT_PACKAGE,
    NAV_PACKAGE,
    _normalize_package_tool_manifest,
    build_candidate,
)
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_package_tool_manifest_restores_2608r1_compatibility_contract(
    tmp_path: Path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "title": "China NavData AIRAC 2608",
        "minimum_game_version": "1.8.14",
        "minimum_compatibility_version": "8.11.0.236",
        "total_package_size": "123",
    }), encoding="utf-8")

    _normalize_package_tool_manifest(tmp_path)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload == {
        "title": "China NavData AIRAC 2608",
        "minimum_game_version": "1.7.35",
        "minimum_compatibility_version": "7.26.0.214",
        "total_package_size": "123",
    }


def test_missing_compiler_blocks_both_overlay_packages(tmp_path: Path, monkeypatch):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: NavModel(root),
    )
    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
    )
    assert report["packages"][NAV_PACKAGE]["status"] == "blocked"
    assert report["packages"][AIRPORT_PACKAGE]["status"] == "blocked"
    assert not (output / NAV_PACKAGE).exists()
    assert not (output / AIRPORT_PACKAGE).exists()


def test_build_candidate_uses_supplied_model_instead_of_loading_source(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    model_path = tmp_path / "model.json"
    for path in (raw, base, jepp):
        path.mkdir()
    model = NavModel(raw)
    model.waypoints.append(
        Waypoint("ZB.P01", "P01", "P01", 40.1, 116.1, SourceRef("DESIGNATED_POINT.csv", 2), country="ZB"),
    )
    model.iap_coverage = {"version": 1, "stale": True}

    def load_naip(*_args, **_kwargs):
        raise AssertionError("supplied NavModel must skip 424 parsing")

    monkeypatch.setattr("fenix_default_navdata.package.load_naip", load_naip)

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        model=model,
        model_path=model_path,
    )

    assert report["source"] == {
        "raw_424": str(raw),
        "intermediate_model": str(model_path),
    }
    assert report["model"]["waypoints"] == 1
    assert report["pdf_cache"] is None
    assert report["iap_coverage"]["version"] == 24
    assert "stale" not in report["iap_coverage"]


def test_missing_navaid_baseline_keeps_candidate_non_deployable(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: NavModel(root),
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
    )

    assert report["navaid_diff"]["navaid_diff_verified"] is False
    assert report["deployable"] is False
    assert report["model"]["selected_navaids"] == 0


def test_candidate_reports_terminal_coordinate_waypoint_promotion(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    for path in (raw, base, jepp):
        path.mkdir()
    model = NavModel(raw)
    model.terminal_coordinate_waypoint_promotion = {
        "coordinate_points": 2,
        "identity_groups": 1,
        "promoted": 1,
    }
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
    )

    assert report["model"]["terminal_coordinate_waypoint_promotion"] == {
        "coordinate_points": 2,
        "identity_groups": 1,
        "promoted": 1,
    }


def test_candidate_reports_source_rejection_audit_deterministically(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    for path in (raw, base, jepp):
        path.mkdir()
    model = NavModel(raw)
    model.rejected_records.extend((
        RejectedRecord(
            "terminal-waypoint",
            "B",
            "missing coordinate",
            SourceRef("Terminal/ZBBB/Charts.csv", 7),
        ),
        RejectedRecord(
            "terminal-waypoint",
            "A",
            "missing coordinate",
            SourceRef("Terminal/ZBAA/Charts.csv", 3),
        ),
        RejectedRecord(
            "airway-leg",
            "R1",
            "missing endpoint region",
            SourceRef("RTE_SEG.csv", 9),
        ),
    ))
    model.rejected_procedures.extend((
        RejectedProcedure(
            "ZBBB",
            "R01",
            "ambiguous chart",
            SourceRef("Terminal/ZBBB/Charts.csv", 4, 2),
        ),
        RejectedProcedure(
            "ZBAA",
            "R02",
            "no matching chart",
            SourceRef("Terminal/ZBAA/Charts.csv", 6, 3),
        ),
    ))
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
    )

    assert report["rejection_audit"] == {
        "records": {
            "total": 3,
            "by_kind": {"airway-leg": 1, "terminal-waypoint": 2},
            "by_kind_and_reason": [
                {
                    "kind": "airway-leg",
                    "reason": "missing endpoint region",
                    "count": 1,
                },
                {
                    "kind": "terminal-waypoint",
                    "reason": "missing coordinate",
                    "count": 2,
                },
            ],
        },
        "procedures": {
            "total": 2,
            "by_reason": {"ambiguous chart": 1, "no matching chart": 1},
            "items": [
                {
                    "airport": "ZBAA",
                    "chart": "R02",
                    "reason": "no matching chart",
                    "source": {
                        "file": "Terminal/ZBAA/Charts.csv",
                        "row": 6,
                        "page": 3,
                        "sha256": None,
                    },
                },
                {
                    "airport": "ZBBB",
                    "chart": "R01",
                    "reason": "ambiguous chart",
                    "source": {
                        "file": "Terminal/ZBBB/Charts.csv",
                        "row": 4,
                        "page": 2,
                        "sha256": None,
                    },
                },
            ],
        },
    }


def test_candidate_passes_accepted_iap_ocr_consensus_to_source_loader(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    for path in (raw, base, jepp):
        path.mkdir()
    evidence = IapOcrRoleEvidence({}, {"accepted": True})
    received: dict[str, object] = {}
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_iap_ocr_role_evidence",
        lambda *_args, **_kwargs: evidence,
    )

    def load(root, **kwargs):
        received.update(root=root, **kwargs)
        return NavModel(root)

    monkeypatch.setattr("fenix_default_navdata.package.load_naip", load)

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        iap_ocr_cache_roots=(tmp_path / "ocr-a", tmp_path / "ocr-b", tmp_path / "ocr-c"),
    )

    assert received["iap_ocr_role_evidence"] is evidence
    assert report["model"]["iap_ocr_evidence"] == {"accepted": True}


def test_candidate_does_not_create_output_when_iap_ocr_consensus_rejects(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    for path in (raw, base, jepp):
        path.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_iap_ocr_role_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("OCR 不一致")),
    )

    with pytest.raises(ValueError, match="OCR 不一致"):
        build_candidate(
            raw_root=raw,
            nav_base=base,
            nav_jepp=jepp,
            output=output,
            cycle=DEFAULT_CYCLE,
            compiler=CompilerInfo(None, "none", "missing"),
            iap_ocr_cache_roots=(
                tmp_path / "ocr-a",
                tmp_path / "ocr-b",
                tmp_path / "ocr-c",
            ),
        )

    assert not output.exists()


def test_overlay_packages_compile_independently(tmp_path: Path, monkeypatch):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: NavModel(root),
    )

    calls = []

    def compile_package(package_root, *args, **kwargs):
        calls.append(package_root.name)
        if package_root.name == NAV_PACKAGE:
            raise RuntimeError("main package failed")
        return {"status": "compiled"}

    monkeypatch.setattr(
        "fenix_default_navdata.package._compile_xml_package",
        compile_package,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(tmp_path / "fspackagetool.exe", "PackageTool", "test"),
    )

    assert calls == [NAV_PACKAGE, AIRPORT_PACKAGE]
    assert report["packages"][NAV_PACKAGE]["status"] == "failed"
    assert report["packages"][AIRPORT_PACKAGE]["status"] == "compiled"


def test_candidate_restores_verified_official_regions_before_enroute_projection(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    model = NavModel(root=raw)
    model.waypoints.append(Waypoint(
        "dp", "DP01", "", 35.0, 105.0,
        SourceRef("DESIGNATED_POINT.csv", 2),
    ))
    model.airway_legs.append(AirwayLeg(
        airway="R1",
        sequence=1,
        start_ident="DP01",
        end_ident="VOR01",
        source=SourceRef("RTE_SEG.csv", 2),
        start_latitude=35.0,
        start_longitude=105.0,
        end_latitude=36.0,
        end_longitude=106.0,
        start_type="DESIGNATED_POINT",
        end_type="VORDME",
    ))
    vor = BaselineNavaid(
        kind="VOR",
        ident="VOR01",
        region="ZG",
        frequency_khz=113000.0,
        latitude=36.0,
        longitude=106.0,
        name="VOR01",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=1,
    )
    ndb = BaselineNavaid(
        kind="NDB",
        ident="SPARE",
        region="ZB",
        frequency_khz=35000.0,
        latitude=1.0,
        longitude=1.0,
        name="SPARE",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=2,
    )
    official_index = OfficialNavaidIndex(
        database=tmp_path / "official.sqlite",
        metadata_path=tmp_path / "official.sqlite.metadata.json",
        baseline=BaselineIndex(
            records=(vor, ndb),
            sources=("fixture.sqlite",),
            database_counts=(),
            verified=True,
        ),
        waypoints=(OfficialWaypoint(
            ident="DP01",
            region="ZB",
            latitude=35.0,
            longitude=105.0,
            source="fixture.bgl",
            row_id=3,
        ),),
        metadata={"metadata_version": 3, "status": "verified"},
        reused=True,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_verified_official_navaid_index",
        lambda *args, **kwargs: official_index,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        baseline_db=official_index.database,
    )

    assert model.waypoints[0].country == "ZB"
    assert (model.airway_legs[0].start_country, model.airway_legs[0].end_country) == (
        "ZB",
        "ZG",
    )
    assert report["official_region_resolution"]["verified"] is True
    assert report["official_region_resolution"]["airway_legs"] == {
        "total": 1,
        "resolved_before": 0,
        "resolved_after": 1,
        "skipped_before": 1,
        "skipped_after": 0,
    }
    assert report["projection"]["airway_routes"] == 1
    assert report["projection"]["skipped_airway_legs"] == 0


def test_candidate_suppresses_cross_region_official_navaid_duplicate(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    model = NavModel(root=raw)
    model.navaids.append(Navaid(
        "vor", "CHF", "VOR", "CHF", 42.188889, 118.810833, 115.5,
        0.0, 0, "ZB", SourceRef("VOR.csv", 2), code_in_airway="Y",
    ))
    vor = BaselineNavaid(
        kind="VOR",
        ident="CHF",
        region="ZY",
        frequency_khz=115500.0,
        latitude=42.190000,
        longitude=118.811676,
        name="CHF",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=1,
    )
    ndb = BaselineNavaid(
        kind="NDB",
        ident="SPARE",
        region="ZB",
        frequency_khz=35000.0,
        latitude=1.0,
        longitude=1.0,
        name="SPARE",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=2,
    )
    official_index = OfficialNavaidIndex(
        database=tmp_path / "official.sqlite",
        metadata_path=tmp_path / "official.sqlite.metadata.json",
        baseline=BaselineIndex(
            records=(vor, ndb),
            sources=("fixture.sqlite",),
            database_counts=(),
            verified=True,
        ),
        waypoints=(OfficialWaypoint(
            ident="SPARE",
            region="ZB",
            latitude=1.0,
            longitude=1.0,
            source="fixture.bgl",
            row_id=3,
        ),),
        metadata={"metadata_version": 3, "status": "verified"},
        reused=True,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_verified_official_navaid_index",
        lambda *args, **kwargs: official_index,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        baseline_db=official_index.database,
    )

    assert report["navaid_diff"]["selected_missing"] == 1
    assert report["navaid_selection"]["navaid_selection_verified"] is True
    assert report["navaid_selection"]["suppressed_physical_duplicates"] == 1
    assert report["navaid_selection"]["official_baseline_preservations"] == 1
    assert report["model"]["selected_navaids"] == 1


def test_candidate_projects_source_backed_ndb_property_correction(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    model = NavModel(root=raw)
    model.navaids.append(Navaid(
        "ndb", "DM", "NDB", "DM", 29.256111, 91.764167, 435.0,
        -0.51, 0, "ZU", SourceRef("NDB.csv", 2), code_in_airway="Y",
    ))
    vor = BaselineNavaid(
        kind="VOR",
        ident="SPARE",
        region="ZB",
        frequency_khz=113000.0,
        latitude=1.0,
        longitude=1.0,
        name="SPARE",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=1,
    )
    ndb = BaselineNavaid(
        kind="NDB",
        ident="DM",
        region="ZU",
        frequency_khz=43500.0,
        latitude=29.255000,
        longitude=91.765000,
        name="DM",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=2,
    )
    official_index = OfficialNavaidIndex(
        database=tmp_path / "official.sqlite",
        metadata_path=tmp_path / "official.sqlite.metadata.json",
        baseline=BaselineIndex(
            records=(vor, ndb),
            sources=("fixture.sqlite",),
            database_counts=(),
            verified=True,
        ),
        waypoints=(OfficialWaypoint(
            ident="SPARE",
            region="ZB",
            latitude=1.0,
            longitude=1.0,
            source="fixture.bgl",
            row_id=3,
        ),),
        metadata={"metadata_version": 3, "status": "verified"},
        reused=True,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_verified_official_navaid_index",
        lambda *args, **kwargs: official_index,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        baseline_db=official_index.database,
    )

    assert report["navaid_selection"]["navaid_selection_verified"] is True
    assert report["navaid_selection"]["selected_property_corrections"] == 1
    assert report["model"]["selected_navaids"] == 1
    assert report["projection"]["navaids"] == 1


def test_candidate_projects_verified_official_baseline_ndb_preservation(
    tmp_path: Path,
    monkeypatch,
):
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "candidate"
    raw.mkdir()
    base.mkdir()
    jepp.mkdir()
    model = NavModel(root=raw)
    vor = BaselineNavaid(
        kind="VOR",
        ident="SPARE",
        region="ZB",
        frequency_khz=113000.0,
        latitude=1.0,
        longitude=1.0,
        name="SPARE",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=1,
    )
    ndb = BaselineNavaid(
        kind="NDB",
        ident="OLD",
        region="ZB",
        frequency_khz=34500.0,
        latitude=40.0,
        longitude=116.0,
        name="OLD",
        magnetic_variation=0.0,
        elevation_ft=0,
        source="fixture.bgl",
        row_id=2,
    )
    official_index = OfficialNavaidIndex(
        database=tmp_path / "official.sqlite",
        metadata_path=tmp_path / "official.sqlite.metadata.json",
        baseline=BaselineIndex(
            records=(vor, ndb),
            sources=("fixture.sqlite",),
            database_counts=(),
            verified=True,
        ),
        waypoints=(OfficialWaypoint(
            ident="SPARE",
            region="ZB",
            latitude=1.0,
            longitude=1.0,
            source="fixture.bgl",
            row_id=3,
        ),),
        metadata={"metadata_version": 3, "status": "verified"},
        reused=True,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_naip",
        lambda root, **kwargs: model,
    )
    monkeypatch.setattr(
        "fenix_default_navdata.package.load_verified_official_navaid_index",
        lambda *args, **kwargs: official_index,
    )

    report = build_candidate(
        raw_root=raw,
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        cycle=DEFAULT_CYCLE,
        compiler=CompilerInfo(None, "none", "missing"),
        baseline_db=official_index.database,
    )

    assert report["navaid_selection"]["navaid_selection_verified"] is True
    assert report["navaid_selection"]["projection_categories"] == {
        "raw_424_addition": 0,
        "raw_424_correction": 0,
        "official_baseline_preservation": 1,
        "rejected_ambiguous": 0,
        "official_baseline_precedence": 0,
        "verified_cross_region_raw_addition": 0,
        "rejected_sdk_identity_conflict": 0,
    }
    assert report["model"]["selected_navaids"] == 1
    assert report["projection"]["navaids"] == 1
