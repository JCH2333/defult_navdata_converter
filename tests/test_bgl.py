from pathlib import Path
import xml.etree.ElementTree as ET

from fenix_default_navdata.bgl import find_compiler, write_bglcomp_xml
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
