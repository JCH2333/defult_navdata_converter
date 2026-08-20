from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.sdk_toolchain_pair_audit import audit_sdk_toolchain_pair


def _write_probe(
    root: Path,
    *,
    compiler: Path,
    xml: Path,
    bgl: Path,
    rows: list[dict[str, object]],
) -> Path:
    compiler.parent.mkdir(parents=True, exist_ok=True)
    compiler.write_bytes(compiler.name.encode("ascii"))
    xml.write_text("<FSData><Waypoint waypointIdent='TEST'/></FSData>\n", encoding="utf-8")
    bgl.write_bytes(bgl.name.encode("ascii"))
    report = root / f"{bgl.stem}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "diagnostic": "sdk_airway_route_child_order",
                "probe": "sdk_airway_route_child_order",
                "status": "passed",
                "contract": {"single_variable": "route child order"},
                "scenarios": [
                    {"identifier": "same", "middle_child_order": ["Previous", "Next"]}
                ],
                "xml": str(xml),
                "compilation": {"compiler": str(compiler), "bgls": [str(bgl)]},
                "airway_rows": rows,
            }
        ),
        encoding="utf-8",
    )
    return report


def test_pair_audit_confirms_same_input_different_output(tmp_path: Path) -> None:
    first = _write_probe(
        tmp_path / "first",
        compiler=tmp_path / "sdk153" / "fspackagetool.exe",
        xml=tmp_path / "first.xml",
        bgl=tmp_path / "first.bgl",
        rows=[{"airway_name": "A", "fragment": 1}],
    )
    second = _write_probe(
        tmp_path / "second",
        compiler=tmp_path / "sdk169" / "fspackagetool.exe",
        xml=tmp_path / "second.xml",
        bgl=tmp_path / "second.bgl",
        rows=[{"airway_name": "A", "fragment": 2}],
    )
    Path(json.loads(second.read_text(encoding="utf-8"))["xml"]).write_text(
        Path(json.loads(first.read_text(encoding="utf-8"))["xml"]).read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    report = audit_sdk_toolchain_pair(first, second)

    assert report["inputs"]["same_probe_input"] is True
    assert report["outputs"]["reader_rows_equal"] is False
    assert report["decision"]["status"] == "toolchain_difference_changes_observed_output"
    assert report["decision"]["adapter_change_authorized"] is False


def test_pair_audit_rejects_different_xml_as_noncomparable(tmp_path: Path) -> None:
    first = _write_probe(
        tmp_path / "first",
        compiler=tmp_path / "sdk153" / "fspackagetool.exe",
        xml=tmp_path / "first.xml",
        bgl=tmp_path / "first.bgl",
        rows=[],
    )
    second = _write_probe(
        tmp_path / "second",
        compiler=tmp_path / "sdk169" / "fspackagetool.exe",
        xml=tmp_path / "second.xml",
        bgl=tmp_path / "second.bgl",
        rows=[],
    )
    Path(json.loads(first.read_text(encoding="utf-8"))["xml"]).write_text(
        "<FSData><Waypoint waypointIdent='FIRST'/></FSData>\n",
        encoding="utf-8",
    )

    report = audit_sdk_toolchain_pair(first, second)

    assert report["inputs"]["same_probe_input"] is False
    assert report["decision"]["status"] == "pair_not_comparable"


def test_pair_audit_does_not_treat_reader_only_difference_as_toolchain_output(
    tmp_path: Path,
) -> None:
    first = _write_probe(
        tmp_path / "first",
        compiler=tmp_path / "sdk153" / "fspackagetool.exe",
        xml=tmp_path / "same.xml",
        bgl=tmp_path / "same-first.bgl",
        rows=[{"fragment": 1}],
    )
    second = _write_probe(
        tmp_path / "second",
        compiler=tmp_path / "sdk169" / "fspackagetool.exe",
        xml=tmp_path / "same.xml",
        bgl=tmp_path / "same-second.bgl",
        rows=[{"fragment": 2}],
    )
    first_bgl = Path(json.loads(first.read_text(encoding="utf-8"))["compilation"]["bgls"][0])
    second_bgl = Path(json.loads(second.read_text(encoding="utf-8"))["compilation"]["bgls"][0])
    second_bgl.write_bytes(first_bgl.read_bytes())

    report = audit_sdk_toolchain_pair(first, second)

    assert report["outputs"]["compiled_bgl_bytes_equal"] is True
    assert report["outputs"]["reader_only_difference"] is True
    assert report["decision"]["status"] == "compiled_output_equal_reader_rows_differ"
    assert report["decision"]["targeted_toolchain_selection_experiment_authorized"] is False
