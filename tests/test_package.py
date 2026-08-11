from pathlib import Path

from fenix_default_navdata.bgl import CompilerInfo
from fenix_default_navdata.model import NavModel
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
        "fenix_default_navdata.fenix_source.load_fenix_model",
        lambda fenix, root, cycle: NavModel(root),
    )
    report = build_candidate(
        fenix_db=tmp_path / "nd.db3",
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
