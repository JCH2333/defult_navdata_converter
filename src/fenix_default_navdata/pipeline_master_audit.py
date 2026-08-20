from __future__ import annotations

import json
from pathlib import Path

from .bgl_projection_master_audit import audit_bgl_projection_master
from .model import NavModel
from .source_model_master_audit import audit_source_model_master

class PipelineMasterAuditError(RuntimeError):
    """当端到端数据转换流水线主审败无法在只跻边界内完成时恛出。"""

def audit_pipeline_master(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise PipelineMasterAuditError(f"424 原始目录不存在: {root}")

    source_model_audit = audit_source_model_master(root, model)
    bgl_projection_audit = audit_bgl_projection_master(model)

    source_verified = source_model_audit.get("summary", {}).get("master_pipeline_verified") is True
    projection_verified = bgl_projection_audit.get("summary", {}).get("projection_schema_verified") is True
    compiler_available = bgl_projection_audit.get("compiler", {}).get("available") is True

    pipeline_verified = source_verified and projection_verified

    return {
        "diagnostic": "pipeline-master-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "pipeline": {
            "raw_root": str(root),
            "source_model_verified": source_verified,
            "bgl_projection_verified": projection_verified,
            "compiler_available": compiler_available,
        },
        "summary": {
            "pipeline_master_verified": pipeline_verified,
            "source_model_master": source_model_audit.get("summary", {}),
            "bgl_projection_master": bgl_projection_audit.get("summary", {}),
            "disposition": "pipeline_master_verified" if pipeline_verified else "pipeline_master_rejected",
            "model_or_adapter_change_authorized": False,
        },
        "sub_audits": {
            "source_model_master": source_model_audit,
            "bgl_projection_master": bgl_projection_audit,
        },
    }


def write_pipeline_master_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
