from pathlib import Path
from fenix_default_navdata.sdk_target_contract_audit import (
    build_sdk_target_contract_audit,
    write_sdk_target_contract_audit,
)

def test_build_sdk_target_contract_audit_basic(tmp_path: Path) -> None:
    report = build_sdk_target_contract_audit()
    assert report["diagnostic"] == "sdk-target-contract-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["summary"]["total_contracts"] == 4
    assert report["summary"]["adapter_mutation_authorized"] is False
    assert report["summary"]["reversal_authorized_total"] == 0

    out = tmp_path / "out.json"
    write_sdk_target_contract_audit(out, report)
    assert out.exists()