from pathlib import Path

from fenix_default_navdata.model import Airport, NavModel, Runway, SourceRef
from fenix_default_navdata.source_model_completeness_audit import (
    audit_source_model_completeness,
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _model(root: Path) -> NavModel:
    source = SourceRef("AD_HP.csv", row=2)
    model = NavModel(root)
    model.airports["A1"] = Airport(
        "A1", "ZBAA", "BEIJING", 40.0, 116.0, 100, 9000, 10000, source,
    )
    model.runways.append(
        Runway("D1", "A1", "18", 180.0, 10000, 150, "ASP", 100, source),
    )
    return model


def test_audit_keeps_source_boundaries_and_marks_historically_rejected_displacement(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    _write(
        root / "AD_HP.csv",
        "AD_HP_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,"
        "VAL_ELEV,VAL_TRANSITION_ALT,VAL_TRANSITION_LEVEL,VAL_MAG_VAR\n"
        "A1,ZBAA,BEIJING,N400000,E1160000,10,3000,9000,1\n",
    )
    _write(
        root / "RWY.csv",
        "RWY_ID,AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION\n"
        "R1,A1,3000,45,ASPHALT\n",
    )
    _write(
        root / "RWY_DIRECTION.csv",
        "RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV,VAL_THR_DISPLACE\n"
        "R1,18,180,10,300\n",
    )
    _write(root / "UNCLASSIFIED.csv", "CODE_ID\ncandidate-after-review\n")

    report = audit_source_model_completeness(root, _model(root))

    assert report["diagnostic"] == "source-model-completeness-audit-v1"
    assert report["read_only"] is True
    assert report["reference_navigation_payload_read"] is False
    assert report["fenix_read"] is False
    assert report["ocr_invoked"] is False
    assert report["groups"]["runways"]["source_complete"] is True
    assert report["groups"]["runways"]["model_record_counts"] == {"runways": 1}
    assert report["groups"]["runway_threshold_displacement"][
        "positive_displacement_record_total"
    ] == 1
    assert report["groups"]["runway_threshold_displacement"]["disposition"] == (
        "source_complete_current_target_rejected"
    )
    assert report["groups"]["runway_threshold_displacement"][
        "historical_probe_evidence"
    ] == {
        "probe": "r195-offset-threshold",
        "consolidated_audit": "r246-historical-sdk-probe-evidence-v1",
        "result": "no_section_cardinality_effect",
    }
    assert report["summary"]["source_complete_sdk_probe_candidates"] == []
    assert report["summary"]["source_complete_current_target_rejections"] == [
        "runway_threshold_displacement",
    ]
    assert report["summary"]["root_csv_file_total"] == 4
    assert report["summary"]["unclassified_csv_files"] == ["UNCLASSIFIED.csv"]
    assert report["summary"]["unclassified_csv_file_total"] == 1
    assert report["summary"]["model_or_adapter_change_authorized"] is False


def test_audit_rejects_sector_radios_and_marks_missing_declared_inputs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    _write(
        root / "AD_HP.csv",
        "AD_HP_ID,CODE_ID,TXT_NAME,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,"
        "VAL_ELEV,VAL_TRANSITION_ALT,VAL_TRANSITION_LEVEL,VAL_MAG_VAR\n",
    )
    _write(root / "RWY.csv", "RWY_ID,AD_HP_ID,VAL_LEN,VAL_WID,CODE_COMPOSITION\n")
    _write(
        root / "RWY_DIRECTION.csv",
        "RWY_ID,TXT_DESIG,VAL_TRUE_BRG,VAL_ELEV,VAL_THR_DISPLACE\n",
    )
    _write(
        root / "APPSECTOR_RUNWAYDIRECTION.csv",
        "AIRSPACE_ID,AD_HP_ID\nS1,A1\n",
    )
    for filename in (
        "AIRSPACE_RADIO.csv",
        "CONTROLLED_RADIO.csv",
        "RESTRICTED_RADIO.csv",
        "SPECIAL_AIRSPACE_RADIO.csv",
    ):
        _write(root / filename, "TXT_FREQ_TYPE,VAL_FREQ\nAPP,120.0\n")

    report = audit_source_model_completeness(root, _model(root))

    radios = report["groups"]["approach_sector_radios"]
    assert radios["disposition"] == "rejected_by_source_scope_and_cardinality"
    assert radios["source_complete"] is True
    assert radios["radio_file_row_total"] == 4
    assert report["groups"]["airways"]["source_complete"] is False
    assert report["groups"]["airways"]["missing_source_files"] == [
        "RTE_SEG.csv",
        "SEGMENT.csv",
        "EN_ROUTE_RTE.csv",
    ]
