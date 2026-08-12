from pathlib import Path

from fenix_default_navdata.baseline import BaselineIndex, BaselineNavaid
from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef, Waypoint
from fenix_default_navdata.official_index import OfficialNavaidIndex, OfficialWaypoint
from fenix_default_navdata.package import AIRPORT_PACKAGE, NAV_PACKAGE, build_candidate
from fenix_default_navdata.profile import DEFAULT_CYCLE


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
