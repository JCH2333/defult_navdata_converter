import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from fenix_default_navdata.bgl import (
    CompilerInfo,
    compile_package,
    find_compiler,
    write_bglcomp_xml,
    write_package_project,
)
from fenix_default_navdata.model import Airport, NavModel, Runway, SourceRef
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_bgl_xml_is_deterministic(tmp_path: Path):
    model = NavModel(Path("source"))
    model.airports["a"] = Airport("a", "ZBCF", "TEST", 35.0, 105.0, 1000, 18000, 180, SourceRef("AD_HP.csv", 2))
    model.runways.append(Runway("r", "a", "03L", 30.0, 10000, 150, "ASP", 1000, SourceRef("RWY_DIRECTION.csv", 2)))
    first = tmp_path / "one.xml"
    second = tmp_path / "two.xml"
    write_bglcomp_xml(model, DEFAULT_CYCLE, first)
    write_bglcomp_xml(model, DEFAULT_CYCLE, second)
    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    assert root.tag == "FSData"
    assert root.find("AiracCycle").attrib["cycleNumber"] == "08"
    assert root.find("Airport/Runway").attrib["number"] == "03"


def test_missing_compiler_is_reported():
    info = find_compiler(Path("does-not-exist.exe"))
    assert info.path is None


def test_package_tool_project_is_deterministic(tmp_path: Path):
    source = tmp_path / "source.xml"
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    root = tmp_path / "project"
    project = write_package_project(
        root,
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    parsed = ET.parse(project).getroot()
    assert parsed.tag == "Project"
    assert parsed.findtext("Packages/Package") == r"PackageDefinitions\test-navdata.xml"
    definition = ET.parse(root / "PackageDefinitions" / "test-navdata.xml").getroot()
    assert definition.findtext("PackageOrderHint") == "CUSTOM_NAVDATA_PATCH"
    assert definition.findtext("AssetGroups/AssetGroup/Type") == "BGL"
    assert definition.findtext("AssetGroups/AssetGroup/OutputDir") == r"scenery\test-navdata"
    assert (root / "PackageSources" / "NavData" / "source.xml").read_bytes() == source.read_bytes()


def test_package_tool_stages_project_in_ascii_path(tmp_path: Path, monkeypatch):
    unicode_root = tmp_path / "中文项目"
    source = unicode_root / "source.xml"
    source.parent.mkdir()
    source.write_text("<FSData version=\"9.0\"/>", encoding="utf-8")
    project = write_package_project(
        unicode_root / "project",
        package_name="test-navdata",
        title="Test NavData",
        output_dir=r"scenery\test-navdata",
        source_xmls=(source,),
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )

    def fake_run(command, **kwargs):
        staged_project = Path(command[1])
        assert str(staged_project).isascii()
        package = staged_project.parent / "Packages" / "test-navdata"
        package.mkdir(parents=True)
        for name in ("manifest.json", "layout.json", "bglIndex.bout"):
            (package / name).write_bytes(b"x")
        bgl = package / "scenery" / "test-navdata" / "source.bgl"
        bgl.parent.mkdir(parents=True)
        bgl.write_bytes(b"bgl")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("fenix_default_navdata.bgl.subprocess.run", fake_run)
    monkeypatch.setattr("fenix_default_navdata.bgl._simulator_pids", lambda: set())
    report = compile_package(
        project,
        CompilerInfo(Path("fspackagetool.exe"), "PackageTool", "test"),
        package_name="test-navdata",
    )
    package_root = Path(report["package_root"])
    assert package_root.is_dir()
    assert (package_root / "bglIndex.bout").read_bytes() == b"x"
    assert list(package_root.rglob("*.bgl"))
