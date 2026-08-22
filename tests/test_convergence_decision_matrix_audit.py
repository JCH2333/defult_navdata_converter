from pathlib import Path
from fenix_default_navdata.convergence_decision_matrix_audit import (
    audit_convergence_decision_matrix,
    write_convergence_decision_matrix,
)

def test_audit_convergence_decision_matrix_basic(tmp_path: Path) -> None:
    cand = tmp_path / "cand" / "zzz-pkg"
    ref = tmp_path / "ref" / "zzz-pkg"
    cand.mkdir(parents=True)
    ref.mkdir(parents=True)
    
    (cand / "manifest.json").write_text('{"title":"test"}', encoding="utf-8")
    (ref / "manifest.json").write_text('{"title":"test"}', encoding="utf-8")
    
    report = audit_convergence_decision_matrix(tmp_path / "cand", tmp_path / "ref")
    assert report["diagnostic"] == "convergence-decision-matrix-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["summary"]["total_files"] == 1
    assert report["summary"]["files_equal_reference"] == 1
    assert report["summary"]["adapter_change_authorized_total"] == 0

    out = tmp_path / "out.json"
    write_convergence_decision_matrix(out, report)
    assert out.exists()