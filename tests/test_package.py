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
