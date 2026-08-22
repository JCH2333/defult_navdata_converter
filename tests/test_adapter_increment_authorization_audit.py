from pathlib import Path
from fenix_default_navdata.adapter_increment_authorization_audit import (
    audit_adapter_increment_authorization,
    write_adapter_increment_authorization_audit,
)

def test_audit_adapter_increment_authorization_basic(tmp_path: Path) -> None:
    report = audit_adapter_increment_authorization()
    assert report["diagnostic"] == "adapter-increment-authorization-audit-v1"
    assert report["read_only"] is True
    assert report["reference_records_exported"] is False
    assert report["summary"]["total_evaluated_targets"] == 6
    assert report["summary"]["authorized_increments_total"] == 0
    assert report["summary"]["all_increments_blocked_or_rejected"] is True
    assert report["summary"]["adapter_mutation_authorized"] is False

    out = tmp_path / "out.json"
    write_adapter_increment_authorization_audit(out, report)
    assert out.exists()