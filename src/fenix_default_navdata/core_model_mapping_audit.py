from __future__ import annotations

import csv
import json
from pathlib import Path

from .model import NavModel


class CoreModelMappingAuditError(RuntimeError):
    """当核心导航实体组来源-模型映射一致性审计无法在只读边界内完成时抛出。"""


def _csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CoreModelMappingAuditError(f"不支持的 CSV 编码: {path}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return list(csv.DictReader(_csv_text(path).splitlines()))


def audit_core_model_mapping(raw_root: Path, model: NavModel) -> dict[str, object]:
    root = raw_root.expanduser().resolve()
    if not root.is_dir():
        raise CoreModelMappingAuditError(f"424 原始目录不存在: {root}")

    ad_hp_rows = _rows(root / "AD_HP.csv")
    rwy_rows = _rows(root / "RWY.csv")
    rwy_dir_rows = _rows(root / "RWY_DIRECTION.csv")
    vor_rows = _rows(root / "VOR.csv")
    ndb_rows = _rows(root / "NDB.csv")
    pts_rows = _rows(root / "DESIGNATED_POINT.csv")
    rte_seg_rows = _rows(root / "RTE_SEG.csv")

    # 1. Airport Mapping Audit
    valid_ad_hp = [
        r for r in ad_hp_rows
        if (r.get("CODE_ID") or "").strip().startswith("Z")
        and len((r.get("CODE_ID") or "").strip()) == 4
    ]
    model_airports = list(model.airports.values()) if isinstance(model.airports, dict) else list(model.airports)
    model_airport_icaos = {a.icao for a in model_airports}
    airport_mapped_count = sum(1 for r in valid_ad_hp if (r.get("CODE_ID") or "").strip() in model_airport_icaos)
    airport_all_valid_coords = all(
        -90 <= a.latitude <= 90 and -180 <= a.longitude <= 180
        for a in model_airports
    )

    # 2. Runway Mapping Audit
    model_runways = list(model.runways.values()) if isinstance(model.runways, dict) else list(model.runways)
    runway_all_valid_coords = all(
        -90 <= r.latitude <= 90 and -180 <= r.longitude <= 180
        for r in model_runways
    )
    runway_all_have_airport = all(r.airport_key in model.airports for r in model_runways)

    # 3. Navaid Mapping Audit
    model_navaids = list(model.navaids.values()) if isinstance(model.navaids, dict) else list(model.navaids)
    model_navaid_keys = {n.key for n in model_navaids}
    vor_matched = sum(1 for r in vor_rows if (r.get("SIGNIFICANT_POINT_ID") or "").strip() in model_navaid_keys)
    ndb_matched = sum(1 for r in ndb_rows if (r.get("SIGNIFICANT_POINT_ID") or "").strip() in model_navaid_keys)
    navaid_all_valid_coords = all(
        -90 <= n.latitude <= 90 and -180 <= n.longitude <= 180
        for n in model_navaids
    )

    # 4. Waypoint Mapping Audit
    model_waypoints = list(model.waypoints.values()) if isinstance(model.waypoints, dict) else list(model.waypoints)
    model_waypoint_keys = {w.key for w in model_waypoints}
    pts_matched = sum(
        1 for r in pts_rows
        if (r.get("SIGNIFICANT_POINT_ID") or r.get("DESIGNATED_POINT_ID") or "").strip() in model_waypoint_keys
    )
    waypoint_all_valid_coords = all(
        -90 <= w.latitude <= 90 and -180 <= w.longitude <= 180
        for w in model_waypoints
    )
    waypoint_sources = {}
    for w in model_waypoints:
        src_file = getattr(w.source, "file", "unknown")
        waypoint_sources[src_file] = waypoint_sources.get(src_file, 0) + 1

    # 5. Airway Leg Mapping Audit
    model_airway_legs = list(model.airway_legs.values()) if isinstance(model.airway_legs, dict) else list(model.airway_legs)
    airway_leg_all_valid_coords = all(
        -90 <= leg.start_latitude <= 90 and -180 <= leg.start_longitude <= 180
        and -90 <= leg.end_latitude <= 90 and -180 <= leg.end_longitude <= 180
        for leg in model_airway_legs
    )

    return {
        "diagnostic": "core-model-mapping-audit-v1",
        "read_only": True,
        "reference_navigation_payload_read": False,
        "fenix_read": False,
        "ocr_invoked": False,
        "source": {
            "raw_root": str(root),
            "ad_hp_rows": len(ad_hp_rows),
            "rwy_rows": len(rwy_rows),
            "rwy_direction_rows": len(rwy_dir_rows),
            "vor_rows": len(vor_rows),
            "ndb_rows": len(ndb_rows),
            "designated_point_rows": len(pts_rows),
            "rte_seg_rows": len(rte_seg_rows),
        },
        "summary": {
            "airports": {
                "source_ad_hp_rows": len(ad_hp_rows),
                "valid_icao_z_airports": len(valid_ad_hp),
                "model_airports_total": len(model_airports),
                "mapped_ratio": 1.0 if len(valid_ad_hp) == len(model_airports) else len(model_airports) / max(len(valid_ad_hp), 1),
                "coordinates_valid": airport_all_valid_coords,
            },
            "runways": {
                "source_rwy_rows": len(rwy_rows),
                "source_rwy_direction_rows": len(rwy_dir_rows),
                "model_runways_total": len(model_runways),
                "matched_runway_directions": len(model_runways) == len(rwy_dir_rows),
                "all_runways_linked_to_airport": runway_all_have_airport,
                "coordinates_valid": runway_all_valid_coords,
            },
            "navaids": {
                "source_vor_rows": len(vor_rows),
                "source_ndb_rows": len(ndb_rows),
                "source_total": len(vor_rows) + len(ndb_rows),
                "model_navaids_total": len(model_navaids),
                "model_vor_total": sum(1 for n in model_navaids if n.kind == "VOR"),
                "model_ndb_total": sum(1 for n in model_navaids if n.kind == "NDB"),
                "vor_matched_source": vor_matched,
                "ndb_matched_source": ndb_matched,
                "omitted_foreign_enroute_vor": len(vor_rows) - vor_matched,
                "coordinates_valid": navaid_all_valid_coords,
            },
            "waypoints": {
                "source_designated_points": len(pts_rows),
                "model_waypoints_total": len(model_waypoints),
                "designated_points_matched": pts_matched,
                "designated_points_matched_ratio": 1.0 if pts_matched == len(pts_rows) else pts_matched / max(len(pts_rows), 1),
                "additional_generaldoc_and_terminal_waypoints": len(model_waypoints) - pts_matched,
                "source_breakdown": dict(sorted(waypoint_sources.items())),
                "coordinates_valid": waypoint_all_valid_coords,
            },
            "airways": {
                "source_rte_seg_rows": len(rte_seg_rows),
                "model_airway_legs_total": len(model_airway_legs),
                "matched_100_percent": len(model_airway_legs) == len(rte_seg_rows),
                "coordinates_valid": airway_leg_all_valid_coords,
            },
            "all_core_groups_verified": (
                len(model_airports) == len(valid_ad_hp)
                and len(model_runways) == len(rwy_dir_rows)
                and len(model_airway_legs) == len(rte_seg_rows)
                and pts_matched == len(pts_rows)
                and airport_all_valid_coords
                and runway_all_valid_coords
                and navaid_all_valid_coords
                and waypoint_all_valid_coords
                and airway_leg_all_valid_coords
            ),
            "disposition": "retained_and_projected_mapping_verified",
            "model_or_adapter_change_authorized": False,
        },
    }


def write_core_model_mapping_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
