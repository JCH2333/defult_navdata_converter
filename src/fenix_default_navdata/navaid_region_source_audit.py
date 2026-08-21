"""Read-only audit of 424 navaid region evidence."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .source import (
    _FIR_COUNTRIES,
    _load_fir_polygons,
    _match_source_fir_region,
    _rows,
    parse_dms,
)


def _regions(fir: str) -> tuple[str, ...]:
    names = (part.strip() for part in (fir or "").replace(",", "，").split("，"))
    return tuple(sorted({_FIR_COUNTRIES[name] for name in names if name in _FIR_COUNTRIES}))


def audit_navaid_region_sources(root: Path) -> dict[str, object]:
    """Classify airport/FIR/polygon evidence without reading target data."""

    polygons, vertices = _load_fir_polygons(root)
    result: dict[str, object] = {
        "diagnostic": "navaid-region-source-audit-v1",
        "read_only": True,
        "source_files": ["VOR.csv", "NDB.csv", "AIRSPACE.csv", "AIRSPACE_BORDER_VERTEX.csv"],
        "fir_polygons": {"count": len(polygons), "vertices": vertices},
        "tables": {},
    }
    for filename in ("VOR.csv", "NDB.csv"):
        rows = list(_rows(root / filename))
        categories: Counter[str] = Counter()
        conflicts: list[dict[str, object]] = []
        for row_number, row in enumerate(rows, start=2):
            ident = (row.get("CODE_ID") or "").strip().upper()
            airport = (row.get("SERVICED_AIRPORT") or "").strip().upper()
            airport_region = airport[:2] if airport[:2] in _FIR_COUNTRIES.values() else ""
            fir_regions = _regions(row.get("CODE_FIR") or "")
            try:
                latitude = parse_dms(row.get("GEO_LAT_ACCURACY") or "")
                longitude = parse_dms(row.get("GEO_LONG_ACCURACY") or "")
                match = _match_source_fir_region(polygons, latitude, longitude)
            except ValueError:
                match = None

            if airport_region and fir_regions and airport_region not in fir_regions:
                category = "airport_vs_fir_conflict"
            elif airport_region and fir_regions:
                category = "airport_equals_fir"
            elif airport_region:
                category = "airport_only"
            elif fir_regions:
                category = "fir_only"
            else:
                category = "unresolved"
            categories[category] += 1

            if category == "airport_vs_fir_conflict":
                conflicts.append({
                    "row": row_number,
                    "ident": ident,
                    "serviced_airport": airport,
                    "airport_region": airport_region,
                    "fir_regions": list(fir_regions),
                    "polygon_status": match.status if match else "invalid_coordinate",
                    "polygon_region": match.country if match else "",
                })

        result["tables"][filename] = {
            "rows": len(rows),
            "categories": dict(sorted(categories.items())),
            "conflicts": conflicts,
        }
    return result
