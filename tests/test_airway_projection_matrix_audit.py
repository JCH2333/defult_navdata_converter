from __future__ import annotations

import json
from pathlib import Path

from fenix_default_navdata.airway_projection_matrix_audit import (
    audit_airway_projection_matrix,
)
from fenix_default_navdata.cli import main
from fenix_default_navdata.model import AirwayLeg, NavModel, SourceRef


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("RTE_SEG.csv", 2)
    return NavModel(
        tmp_path,
        airway_legs=[
            AirwayLeg(
                "A1", 1, "START", "END", source,
                start_country="ZU", end_country="ZB",
                start_latitude=30.0, start_longitude=100.0,
                end_latitude=31.0, end_longitude=101.0,
                minimum_altitude_ft=12000,
            ),
            AirwayLeg(
                "A2", 2, "BAD", "END", source,
                start_country="", end_country="ZB",
                start_latitude=30.0, start_longitude=100.0,
                end_latitude=31.0, end_longitude=101.0,
            ),
        ],
    )


def _candidate_xml(path: Path, *, altitude: str = "12000F") -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<FSData>
  <Waypoint waypointRegion="ZU" waypointIdent="START">
    <Route name="A1" routeType="BOTH">
      <Next waypointRegion="ZB" waypointIdent="END" altitudeMinimum="{altitude}" />
    </Route>
  </Waypoint>
  <Waypoint waypointRegion="ZB" waypointIdent="END">
    <Route name="A1" routeType="BOTH">
      <Previous waypointRegion="ZU" waypointIdent="START" altitudeMinimum="{altitude}" />
    </Route>
  </Waypoint>
</FSData>
""",
        encoding="utf-8",
    )


def test_projection_matrix_classifies_projected_and_rejected_source(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.xml"
    _candidate_xml(candidate)

    report = audit_airway_projection_matrix(_model(tmp_path), candidate)

    assert report["classification_counts"] == {
        "projected": 1,
        "rejected_by_source": 1,
    }
    assert report["entries"][0]["connections"][0]["xml_locations"] == [{
        "waypoint_index": 1,
        "route_index": 1,
        "child_index": 1,
    }]
    assert report["entries"][1]["reasons"] == ["missing_start_region"]
    assert report["candidate_connections_without_source_owner"] == 0


def test_projection_matrix_accepts_unique_target_identity_resolution(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    candidate = tmp_path / "candidate.xml"
    _candidate_xml(candidate)
    model.airway_legs[1] = AirwayLeg(
        "A2", 2, "BAD", "END", model.airway_legs[1].source,
        end_country="ZB",
        start_latitude=30.0, start_longitude=100.0,
        end_latitude=31.0, end_longitude=101.0,
    )
    candidate.write_text(
        candidate.read_text(encoding="utf-8").replace(
            "</FSData>",
            """  <Waypoint waypointRegion="ZU" waypointIdent="BAD">
    <Route name="A2" routeType="BOTH">
      <Next waypointRegion="ZB" waypointIdent="END" altitudeMinimum="0F" />
    </Route>
  </Waypoint>
  <Waypoint waypointRegion="ZB" waypointIdent="END">
    <Route name="A2" routeType="BOTH">
      <Previous waypointRegion="ZU" waypointIdent="BAD" altitudeMinimum="0F" />
    </Route>
  </Waypoint>
</FSData>""",
        ),
        encoding="utf-8",
    )

    report = audit_airway_projection_matrix(model, candidate)

    assert report["classification_counts"] == {
        "projected": 1,
        "projected_after_target_identity_resolution": 1,
    }


def test_projection_matrix_detects_xml_attribute_mismatch(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.xml"
    _candidate_xml(candidate, altitude="0F")

    report = audit_airway_projection_matrix(_model(tmp_path), candidate)

    assert report["classification_counts"] == {
        "ambiguous_output_match": 1,
        "rejected_by_source": 1,
    }


def test_cli_writes_projection_matrix(tmp_path: Path, monkeypatch, capsys) -> None:
    candidate = tmp_path / "candidate.xml"
    _candidate_xml(candidate)
    output = tmp_path / "matrix.json"
    model_path = tmp_path / "model.json.gz"
    monkeypatch.setattr(
        "fenix_default_navdata.cli.load_model",
        lambda path: _model(tmp_path),
    )

    assert main([
        "airway-projection-matrix-audit",
        "--model", str(model_path),
        "--candidate-xml", str(candidate),
        "--output", str(output),
    ]) == 0

    assert json.loads(output.read_text(encoding="utf-8"))["classification_counts"] == {
        "projected": 1,
        "rejected_by_source": 1,
    }
    assert json.loads(capsys.readouterr().out)["read_only"] is True
