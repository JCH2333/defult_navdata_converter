from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fenix_default_navdata.cli import main
from fenix_default_navdata.general_docs import EnrouteKeyPointEvidence
from fenix_default_navdata.model import (
    AirwayLeg,
    NavModel,
    SourceRef,
    TerminalWaypoint,
    Waypoint,
)
from fenix_default_navdata.source_gap import (
    SourceGapAuditError,
    audit_general_document_key_point_reference_coverage,
    audit_source_gaps,
    audit_terminal_coordinate_reference_coverage,
)


def _semantic_report(
    *,
    waypoint_samples: list[dict[str, object]],
    airway_samples: list[dict[str, object]],
    waypoint_omitted: int = 0,
) -> dict[str, object]:
    return {
        "diagnostic": "navdatareader-semantic-diff-v1",
        "read_only": True,
        "reference_values_redacted": True,
        "reader_output": {
            "candidate": {"bgl_file_rows": 1, "expected_bgl_count": 1},
            "reference": {"bgl_file_rows": 1, "expected_bgl_count": 1},
        },
        "tables": {
            "waypoint": {
                "reference_only_logical_keys": len(waypoint_samples),
                "reference_only_samples": waypoint_samples,
                "reference_only_samples_omitted": waypoint_omitted,
            },
            "airway": {
                "reference_only_logical_keys": len(airway_samples),
                "reference_only_samples": airway_samples,
                "reference_only_samples_omitted": 0,
            },
        },
    }


def _model(tmp_path: Path) -> NavModel:
    source = SourceRef("424.csv", 2)
    return NavModel(
        tmp_path,
        waypoints=[
            Waypoint("direct", "DIRECT", "", 35.0, 105.0, source, "ZG"),
            Waypoint("unresolved", "UNRESOLVED", "", 36.0, 106.0, source, ""),
        ],
        airway_legs=[
            AirwayLeg("A1", 1, "ENDPOINT", "TAIL", source, start_country="ZU"),
            AirwayLeg("A1", 2, "TAIL", "DIRECT", source, start_country="", end_country="ZG"),
        ],
    )


def test_source_gap_audit_classifies_only_against_424_model(tmp_path: Path) -> None:
    report = _semantic_report(
        waypoint_samples=[
            {"logical_key": {"ident": "DIRECT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "UNRESOLVED", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "ENDPOINT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "ABSENT", "region": "ZB", "airport_ident": None}},
        ],
        airway_samples=[
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 1,
            }},
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 9,
            }},
            {"logical_key": {
                "airway_name": "A2", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 1, "sequence_no": 1,
            }},
        ],
    )

    result = audit_source_gaps(_model(tmp_path), report)

    assert result["waypoint_source_categories"] == {
        "absent_from_structured_designated_and_route_endpoints": 1,
        "direct_designated_different_region": 1,
        "direct_designated_region_unresolved": 1,
        "route_endpoint_different_region": 1,
    }
    assert result["airway_source_categories"] == {
        "absent_from_rte_seg": 1,
        "same_source_airway_and_sequence": 1,
        "source_airway_name_with_different_sequence": 1,
    }
    assert result["candidate_airway_projection"] == {"available": False}
    serialized = json.dumps(result)
    assert "DIRECT" not in serialized
    assert "A1" not in serialized


def test_source_gap_audit_rejects_partial_reader_scan(tmp_path: Path) -> None:
    report = _semantic_report(waypoint_samples=[], airway_samples=[])
    report["reader_output"]["candidate"]["bgl_file_rows"] = 0

    with pytest.raises(SourceGapAuditError, match="candidate.*0/1"):
        audit_source_gaps(_model(tmp_path), report)


def test_source_gap_audit_distinguishes_projected_source_pairs(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    model.airway_legs[0] = AirwayLeg(
        "A1",
        1,
        "ENDPOINT",
        "TAIL",
        model.airway_legs[0].source,
        start_country="ZU",
        end_country="ZB",
    )
    model.airway_legs[1] = AirwayLeg(
        "A1",
        2,
        "TAIL",
        "UNRESOLVED",
        model.airway_legs[1].source,
        start_country="ZB",
        end_country="",
    )
    candidate_xml = tmp_path / "candidate.xml"
    candidate_xml.write_text(
        "\n".join((
            "<FSData>",
            '  <Waypoint waypointRegion="ZU" waypointIdent="ENDPOINT">',
            '    <Route name="A1"><Next waypointRegion="ZB" waypointIdent="TAIL" /></Route>',
            "  </Waypoint>",
            "</FSData>",
        )),
        encoding="utf-8",
    )
    report = _semantic_report(
        waypoint_samples=[],
        airway_samples=[
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 1,
            }},
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 2,
            }},
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 9,
            }},
            {"logical_key": {
                "airway_name": "A2", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 1, "sequence_no": 1,
            }},
        ],
    )

    result = audit_source_gaps(model, report, candidate_xml=candidate_xml)

    assert result["airway_source_categories"] == {
        "absent_from_rte_seg": 1,
        "same_source_airway_and_sequence_candidate_pair_projected": 1,
        "same_source_airway_and_sequence_unprojected_missing_endpoint_region": 1,
        "source_airway_name_with_different_sequence": 1,
    }
    assert result["candidate_airway_projection"] == {
        "available": True,
        "candidate_xml": str(candidate_xml.resolve()),
        "route_links": 1,
        "unique_route_pairs": 1,
        "skipped": {},
    }


def test_source_gap_audit_rejects_truncated_reference_gap_samples(tmp_path: Path) -> None:
    report = _semantic_report(
        waypoint_samples=[],
        airway_samples=[],
        waypoint_omitted=1,
    )

    with pytest.raises(SourceGapAuditError, match="截断"):
        audit_source_gaps(_model(tmp_path), report)


def test_terminal_coordinate_audit_keeps_source_categories_redacted(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    source = SourceRef("Terminal/ZBAA/coordinate-page.pdf", page=1)
    model.terminal_waypoints.extend((
        TerminalWaypoint("single", "ZBAA", "LOCAL", 40.1, 116.1, source, "ZB"),
        TerminalWaypoint("ambig-one", "ZBAA", "AMBIG", 40.2, 116.2, source, "ZB"),
        TerminalWaypoint("ambig-two", "ZBAD", "AMBIG", 40.3, 116.2, source, "ZB"),
        TerminalWaypoint("global-one", "ZBAA", "GLOBAL", 40.4, 116.4, source, "ZB"),
        TerminalWaypoint("global-two", "ZBAD", "GLOBAL", 40.4, 116.4, source, "ZB"),
        TerminalWaypoint("new-one", "ZBAA", "NEW", 40.5, 116.5, source, "ZB"),
        TerminalWaypoint("new-two", "ZBAD", "NEW", 40.5, 116.5, source, "ZB"),
    ))
    model.waypoints.append(Waypoint(
        "global", "GLOBAL", "", 35.0, 105.0, source, "ZB",
    ))
    report = _semantic_report(
        waypoint_samples=[
            {"logical_key": {"ident": "LOCAL", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "AMBIG", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "GLOBAL", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "NEW", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "NONE", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "AIRPORT", "region": "ZB", "airport_ident": "ZBAA"}},
            {"logical_key": {"ident": "LOCAL", "region": "ZB", "airport_ident": "ZBAA"}},
        ],
        airway_samples=[],
    )

    result = audit_terminal_coordinate_reference_coverage(model, report)

    assert result["categories"] == {
        "airport_terminal_coordinate_source_present": 1,
        "airport_terminal_not_present_in_coordinate_pages": 1,
        "not_present_in_terminal_coordinate_pages": 1,
        "terminal_existing_global_identity": 1,
        "terminal_multiple_coordinates": 1,
        "terminal_single_airport": 1,
        "terminal_source_promotable": 1,
    }
    serialized = json.dumps(result)
    for value in ("LOCAL", "AMBIG", "GLOBAL", "NEW", "NONE", "AIRPORT"):
        assert value not in serialized


def test_terminal_coordinate_audit_reports_unretained_airport_coordinate(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path)
    source = SourceRef("Terminal/ZBAA/coordinate-page.pdf", page=1)
    model.terminal_waypoints.append(
        TerminalWaypoint("local", "ZBAA", "LOCAL", 40.1, 116.1, source, "ZB"),
    )
    report = _semantic_report(
        waypoint_samples=[
            {"logical_key": {"ident": "LOCAL", "region": "ZB", "airport_ident": "ZBAA"}},
        ],
        airway_samples=[],
    )

    result = audit_terminal_coordinate_reference_coverage(
        model,
        report,
        retained_terminal_waypoints=(),
    )

    assert result["diagnostic"] == "terminal-coordinate-reference-coverage-v2"
    assert result["source"]["retention_checked"] is True
    assert result["categories"] == {
        "airport_terminal_coordinate_not_retained": 1,
    }
    assert "LOCAL" not in json.dumps(result)


def test_general_doc_keypoint_audit_keeps_source_categories_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model(tmp_path)
    source = SourceRef("GeneralDoc/enr-4.4.pdf", page=1, sha256="source")
    model.waypoints.extend((
        Waypoint("same", "SAME", "", 31.0, 105.0, source, "ZB"),
        Waypoint("conflict", "CONFLICT", "", 0.0, 0.0, source, "ZB"),
    ))
    evidence = (
        EnrouteKeyPointEvidence("SAFE", 30.0, 105.0, source),
        EnrouteKeyPointEvidence("SAME", 31.0, 105.0, source),
        EnrouteKeyPointEvidence("CONFLICT", 32.0, 105.0, source),
        EnrouteKeyPointEvidence("MULTI", 33.0, 105.0, source),
        EnrouteKeyPointEvidence("MULTI", 34.0, 105.0, source),
        EnrouteKeyPointEvidence("MISMATCH", 35.0, 105.0, source),
        EnrouteKeyPointEvidence("BOUNDARY", 36.0, 105.0, source),
    )
    statuses = {
        30.0: SimpleNamespace(status="recovered", country="ZB"),
        31.0: SimpleNamespace(status="recovered", country="ZB"),
        32.0: SimpleNamespace(status="recovered", country="ZB"),
        33.0: SimpleNamespace(status="recovered", country="ZB"),
        34.0: SimpleNamespace(status="recovered", country="ZB"),
        35.0: SimpleNamespace(status="recovered", country="ZG"),
        36.0: SimpleNamespace(status="near_boundary", country=""),
    }
    monkeypatch.setattr(
        "fenix_default_navdata.source_gap._load_fir_polygons",
        lambda root: (("polygon",), 3),
    )
    monkeypatch.setattr(
        "fenix_default_navdata.source_gap._match_source_fir_region",
        lambda polygons, latitude, longitude: statuses[latitude],
    )
    monkeypatch.setattr(
        "fenix_default_navdata.source_gap.load_enroute_key_point_evidence",
        lambda root, cache, cache_directory: (evidence, {
            "document": "GeneralDoc/enr-4.4.pdf",
            "source_sha256": "source",
            "pages": 1,
        }),
    )
    report = _semantic_report(
        waypoint_samples=[
            {"logical_key": {"ident": "SAFE", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "SAME", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "CONFLICT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "MULTI", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "MISMATCH", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "BOUNDARY", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "ABSENT", "region": "ZB", "airport_ident": None}},
            {"logical_key": {"ident": "AIRPORT", "region": "ZB", "airport_ident": "ZBAA"}},
        ],
        airway_samples=[],
    )
    result = audit_general_document_key_point_reference_coverage(
        model,
        report,
        source_root=tmp_path,
        cache_root=tmp_path / "ocr-cache",
    )

    assert result["categories"] == {
        "airport_scoped_reference_only": 1,
        "general_doc_already_present": 1,
        "general_doc_ident_absent": 1,
        "general_doc_identity_conflict": 1,
        "general_doc_multiple_coordinates": 1,
        "general_doc_region_mismatch": 1,
        "general_doc_region_near_boundary": 1,
        "general_doc_source_promotable": 1,
    }
    serialized = json.dumps(result)
    for value in (
        "SAFE",
        "SAME",
        "CONFLICT",
        "MULTI",
        "MISMATCH",
        "BOUNDARY",
        "ABSENT",
        "AIRPORT",
    ):
        assert value not in serialized


def test_source_gap_audit_records_airline_points_as_existing_rte_references(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    model = _model(raw)
    (raw / "RTE_SEG.csv").write_text(
        "\n".join((
            "TXT_DESIG,POINT_START_ID,POINT_END_ID",
            "A1,direct,unresolved",
        )),
        encoding="utf-8",
    )
    (raw / "FLIGHT_AIRLINE_POINT.csv").write_text(
        "\n".join((
            "AirwayName,StartPointID,EndPointID",
            "A1,direct,unresolved",
            "A1,unresolved,direct",
        )),
        encoding="utf-8",
    )
    report = _semantic_report(
        waypoint_samples=[],
        airway_samples=[
            {"logical_key": {
                "airway_name": "A1", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 2, "sequence_no": 1,
            }},
            {"logical_key": {
                "airway_name": "A2", "airway_type": "B", "route_type": None,
                "airway_fragment_no": 1, "sequence_no": 1,
            }},
        ],
    )

    result = audit_source_gaps(model, report)

    assert result["flight_airline_point_evidence"] == {
        "available": True,
        "rows": 2,
        "endpoint_pairs_resolved_to_direct_424_points": 2,
        "forward_rte_seg_matches": 1,
        "reverse_rte_seg_matches": 1,
        "unmatched_rte_seg_references": 0,
        "rte_absent_reference_airway_names": 1,
        "rows_for_rte_absent_reference_airways": 0,
    }


def test_source_gap_audit_marks_route_holdings_without_unique_named_identity(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    model = _model(raw)
    (raw / "ROUTE_HOLDING.csv").write_text(
        "\n".join((
            "POINT_ID,LOCATION_POINT,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY",
            "direct,DIRECT,N350000,E1050000",
            "holding-1,SHARED,N360000,E1060000",
            "holding-2,SHARED,N370000,E1070000",
        )),
        encoding="utf-8",
    )

    result = audit_source_gaps(model, _semantic_report(
        waypoint_samples=[],
        airway_samples=[],
    ))

    assert result["route_holding_evidence"] == {
        "available": True,
        "rows": 3,
        "direct_point_id_resolved": 1,
        "point_id_unresolved": 2,
        "unresolved_rows_with_coordinate": 2,
        "unresolved_location_point_values": 1,
        "unresolved_location_point_reused": 1,
        "unresolved_unique_location_coordinate_pairs": 2,
        "can_add_independent_enroute_waypoints": False,
    }


def test_cli_writes_source_gap_audit_without_loading_terminal_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    semantic = tmp_path / "semantic.json"
    semantic.write_text(json.dumps(_semantic_report(
        waypoint_samples=[],
        airway_samples=[],
    )), encoding="utf-8")
    output = tmp_path / "audit.json"
    observed: dict[str, object] = {}

    def fake_load(root: Path, *, include_terminal_documents: bool) -> NavModel:
        observed["root"] = root
        observed["include_terminal_documents"] = include_terminal_documents
        return _model(tmp_path)

    monkeypatch.setattr("fenix_default_navdata.cli.load_naip", fake_load)

    exit_code = main([
        "source-gap-audit",
        "--raw", str(tmp_path / "raw"),
        "--semantic-diff", str(semantic),
        "--output", str(output),
    ])

    assert exit_code == 0
    assert observed["include_terminal_documents"] is False
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostic"] == "source-gap-audit-v4"
    assert json.loads(capsys.readouterr().out)["read_only"] is True
