from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from pypinyin import lazy_pinyin
import pymupdf

from .iap_coverage import analyze_iap_coverage, iap_section_kind
from .general_docs import (
    ENROUTE_KEY_POINT_CACHE_DIRECTORY,
    ENROUTE_KEY_POINT_DOCUMENT,
    ENROUTE_NAVAID_CACHE_DIRECTORY,
    ENROUTE_NAVAID_DOCUMENT,
    GeneralDocumentCacheError,
    load_enroute_airway_minimum_altitude_evidence,
    load_enroute_key_point_evidence,
    load_enroute_navaid_evidence,
    load_selected_enroute_key_point_evidence,
)
from .model import CN_PREFIXES, Airport, AirwayLeg, Holding, IapOcrRoleEvidence, NavModel, Navaid, ProcedureSegment, RejectedProcedure, RejectedRecord, Runway, SourceRef, TerminalWaypoint, Waypoint, is_china_icao
from .pdf_charts import (
    _is_instrument_approach_index_row,
    _is_standard_procedure_index_row,
    extract_airport_ad219_landing_aids,
    extract_airport_approach_charts,
    extract_airport_coordinate_pages,
    extract_airport_database_charts,
    extract_airport_standard_procedure_charts,
    approach_procedure_name_candidates,
)


_FIR_COUNTRIES = {
    "\u4e09\u4e9a\u60c5\u62a5\u533a": "ZJ",
    "\u4e0a\u6d77\u60c5\u62a5\u533a": "ZS",
    "\u4e4c\u9c81\u6728\u9f50\u60c5\u62a5\u533a": "ZW",
    "\u5170\u5dde\u60c5\u62a5\u533a": "ZL",
    "\u5317\u4eac\u60c5\u62a5\u533a": "ZB",
    "\u5e7f\u5dde\u60c5\u62a5\u533a": "ZG",
    "\u6606\u660e\u60c5\u62a5\u533a": "ZP",
    "\u6b66\u6c49\u60c5\u62a5\u533a": "ZH",
    "\u6c88\u9633\u60c5\u62a5\u533a": "ZY",
}

# These border fixes have no FIR in the 2608 source table. Their published
# identities map to an adjacent MSFS region key deterministically.
_EMPTY_FIR_COUNTRY_OVERRIDES = {"SARUL": "ZB", "MAGOG": "VH", "SULEM": "RC", "SADLI": "RK"}
_AIRPORT_PDF_NAME = re.compile(r"\b(?P<icao>Z[A-Z]{3})/[A-Z0-9]{3}\s*[-–]\s*(?P<name>.*)")
_AIRWAY_ENDPOINT_SOURCE_TYPES = {
    "DESIGNATED_POINT": "DESIGNATED_POINT",
    "地名点": "DESIGNATED_POINT",
    "VORDME": "VORDME",
    "NDB": "NDB",
}
_ACC_NAME = re.compile(r"([\u4e00-\u9fff]+)ACC")
_EARTH_RADIUS_NM = 3440.065
_FIR_BOUNDARY_MIN_DISTANCE_NM = 5.0
_ILS_APPROACH_LABEL = re.compile(r"^I\d{2}[LRC]?(?:-?[WXYZ])?$")


@dataclass(frozen=True)
class _FirPolygon:
    code: str
    country: str
    vertices: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class _FirRegionMatch:
    status: str
    country: str = ""


@dataclass(frozen=True)
class SourceFirRegionResolution:
    """Audit results for source-only blank designated-point FIR recovery."""

    polygons_loaded: int
    vertices_loaded: int
    blank_before: int
    recovered: int
    ambiguous: int
    near_boundary: int
    outside: int

    def to_report(self) -> dict[str, object]:
        return {
            "source": {
                "airspace": "AIRSPACE.csv",
                "vertices": "AIRSPACE_BORDER_VERTEX.csv",
            },
            "minimum_boundary_distance_nm": _FIR_BOUNDARY_MIN_DISTANCE_NM,
            "polygons_loaded": self.polygons_loaded,
            "vertices_loaded": self.vertices_loaded,
            "waypoints": {
                "blank_before": self.blank_before,
                "recovered": self.recovered,
                "ambiguous": self.ambiguous,
                "near_boundary": self.near_boundary,
                "outside": self.outside,
                "blank_after": self.blank_before - self.recovered,
            },
        }


def parse_dms(value: str) -> float:
    """Parse fixed-width NAIP DMS coordinates without guessing degree width."""
    raw = (value or "").strip().upper()
    if len(raw) < 5 or raw[0] not in "NSEW":
        raise ValueError(f"无效坐标: {value!r}")
    hemisphere, digits = raw[0], raw[1:]
    whole, dot, fraction = digits.partition(".")
    degree_digits = 2 if hemisphere in "NS" else 3
    if len(whole) < degree_digits + 4:
        raise ValueError(f"无效坐标: {value!r}")
    degrees = int(whole[:degree_digits])
    minutes = int(whole[degree_digits:degree_digits + 2])
    seconds = float(whole[degree_digits + 2:] + (dot + fraction if dot else ""))
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"无效坐标: {value!r}")
    result = degrees + minutes / 60 + seconds / 3600
    return -result if hemisphere in "SW" else result


def _rows(path: Path):
    raw = path.read_bytes()
    # The main NAIP tables are commonly GBK, while per-airport Charts.csv is UTF-8.
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - both supported encodings failed
        raise UnicodeDecodeError("naip", raw, 0, len(raw), "不支持的 CSV 编码")
    yield from csv.DictReader(text.splitlines())


def _optional_index(root: Path, filename: str, key: str) -> dict[str, dict[str, str]]:
    """Index an optional 424 table without making older fixtures invalid."""
    path = root / filename
    if not path.is_file():
        return {}
    index: dict[str, dict[str, str]] = {}
    for row in _rows(path):
        value = (row.get(key) or "").strip()
        if value:
            # The published 2608 tables use unique IDs.  Keep the first row
            # if a hand-built fixture violates that contract, preserving
            # deterministic behavior without silently replacing metadata.
            index.setdefault(value, row)
    return index


def summarize_airway_source_metadata(model: NavModel) -> dict[str, object]:
    """Summarize source semantics carried by normalized airway legs."""
    code_types = Counter(
        leg.source_code_type or "<blank>" for leg in model.airway_legs
    )
    segment_rnp = Counter(
        leg.source_segment_rnp_designator or "<blank>"
        for leg in model.airway_legs
    )
    location_types = Counter(
        leg.source_enroute_location_type or "<blank>"
        for leg in model.airway_legs
    )
    airspace_remarks = [
        leg.source_airspace_remark.strip()
        for leg in model.airway_legs
    ]
    target_hints = Counter(
        leg.route_type or "<unresolved>" for leg in model.airway_legs
    )
    return {
        "total": len(model.airway_legs),
        "source_code_type": dict(sorted(code_types.items())),
        "source_segment_rnp_designator": dict(sorted(segment_rnp.items())),
        "source_enroute_location_type": dict(sorted(location_types.items())),
        "source_airspace_remark": {
            "populated": sum(bool(value) for value in airspace_remarks),
            "blank": sum(not value for value in airspace_remarks),
            "distinct_nonblank": len({value for value in airspace_remarks if value}),
        },
        "target_route_type_hint": dict(sorted(target_hints.items())),
        "links": {
            "segment_found": sum(leg.source_segment_found for leg in model.airway_legs),
            "segment_missing": sum(not leg.source_segment_found for leg in model.airway_legs),
            "en_route_rte_found": sum(
                leg.source_en_route_rte_found for leg in model.airway_legs
            ),
            "en_route_rte_missing": sum(
                not leg.source_en_route_rte_found for leg in model.airway_legs
            ),
        },
    }


def _number(value: str, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except ValueError:
        return default


def _float(value: str, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except ValueError:
        return default


def _surface(value: str) -> str:
    """Project the first source-listed runway material into an SDK surface.

    A slash-separated 424 composition can describe a runway with multiple
    paving sections, while the MSFS Runway element accepts one material only.
    Retaining the first expressible source component is deterministic and
    avoids silently rewriting a concrete runway as asphalt.
    """
    components = [
        component.strip().upper()
        for component in re.split(r"[/、,;，；]+", value or "")
        if component.strip()
    ]
    for component in components:
        if any(token in component for token in ("水泥", "混凝土", "CONCRETE", "CON")):
            return "CON"
        if any(token in component for token in ("沥青", "ASPHALT", "ASP")):
            return "ASP"
        if any(token in component for token in ("草", "土", "GRASS", "GRE")):
            return "GRE"
        if any(token in component for token in ("水", "WATER", "WAT")):
            return "WAT"
    return "U"


def _feet(value: str) -> int:
    """NAIP vertical and runway dimensions are meters; Fenix stores feet."""
    return round(_float(value) * 3.28084)


def _navaid_elevation_feet(value: str, unit: str) -> int:
    """Convert a populated 424 navaid elevation to the model's feet unit.

    The 2608 VOR table declares metric vertical distance with ``M``.  Three
    populated rows omit that otherwise uniform unit, including CKA, whose
    source/target comparison confirms the same meter-to-feet conversion.
    Missing elevations remain zero; an unexpected explicit unit is rejected
    instead of silently changing its physical meaning.
    """
    if not (value or "").strip():
        return 0
    normalized_unit = (unit or "").strip().upper()
    if normalized_unit not in {"", "M"}:
        raise ValueError(f"unsupported navaid vertical unit: {unit!r}")
    return _feet(value)


def _airport_altitude_feet(value: str) -> int:
    """Project airport transition heights to Fenix's 100-foot resolution."""
    return int(round(_float(value) * 3.28084, -2))


def runway_threshold(
    latitude: float,
    longitude: float,
    true_heading: float,
    length_ft: int,
) -> tuple[float, float]:
    """Derive one published runway end from the airport reference point.

    `RWY_DIRECTION.csv` supplies a true direction but no end coordinates.
    The matched 424 airport reference point represents the runway midpoint
    for this projection, so each end sits half a runway length away on the
    reciprocal bearing.
    """
    earth_radius_m = 6_371_008.8
    angular_distance = length_ft * 0.3048 / 2 / earth_radius_m
    bearing = math.radians((true_heading + 180) % 360)
    start_latitude = math.radians(latitude)
    start_longitude = math.radians(longitude)
    end_latitude = math.asin(
        math.sin(start_latitude) * math.cos(angular_distance)
        + math.cos(start_latitude) * math.sin(angular_distance) * math.cos(bearing)
    )
    end_longitude = start_longitude + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(start_latitude),
        math.cos(angular_distance) - math.sin(start_latitude) * math.sin(end_latitude),
    )
    return math.degrees(end_latitude), ((math.degrees(end_longitude) + 540) % 360) - 180


def romanize_name(value: str) -> str:
    """Map a Chinese source name to the observed uppercase pinyin spelling."""
    return "".join(lazy_pinyin(value or "")).upper()


def _airport_pdf_english_name(text: str, icao: str) -> str | None:
    """Return an AD 2.1 English airport name printed after its Chinese name."""
    values: set[str] = set()
    for line in text.splitlines():
        match = _AIRPORT_PDF_NAME.search(line.upper())
        if match is None or match["icao"] != icao:
            continue
        original = line[match.start("name"):]
        tail = re.search(r"(?P<english>[A-Za-z][A-Za-z0-9 /'\-]*)\s*$", original)
        if tail is None:
            continue
        normalized = " ".join(re.findall(r"[A-Za-z0-9]+", tail["english"])).upper()
        words = normalized.split()
        # AD 2.1 headings can print the same bilingual airport name twice,
        # once in all caps and once in title case (for example ANQING/Anqing).
        # Collapse only an exact adjacent repetition; distinct slash-separated
        # place names such as ALXA LEFT BANNER/Bayanhot remain intact.
        if len(words) % 2 == 0 and words[:len(words) // 2] == words[len(words) // 2:]:
            normalized = " ".join(words[:len(words) // 2])
        if normalized:
            values.add(normalized)
    return next(iter(values)) if len(values) == 1 else None


def _load_airport_pdf_names(model: NavModel) -> None:
    """Use only uniquely printed AD 2.1 English airport names as name evidence."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    by_icao = {airport.icao: key for key, airport in model.airports.items()}
    for icao, key in by_icao.items():
        airport_directory = terminal / icao
        if not airport_directory.is_dir():
            continue
        evidence: list[tuple[str, Path, int]] = []
        for pdf in sorted(airport_directory.glob("*.pdf")):
            if pdf.name.upper().startswith(f"{icao}-"):
                continue
            with pymupdf.open(pdf) as document:
                for page_number in range(1, min(document.page_count, 2) + 1):
                    name = _airport_pdf_english_name(document[page_number - 1].get_text("text"), icao)
                    if name:
                        evidence.append((name, pdf, page_number))
        names = {name for name, _, _ in evidence}
        if len(names) != 1:
            continue
        name, pdf, page_number = evidence[0]
        source = SourceRef(
            str(pdf.relative_to(model.root).as_posix()), page_number, page_number,
            hashlib.sha256(pdf.read_bytes()).hexdigest(),
        )
        model.airports[key] = replace(model.airports[key], name=name, name_source=source)


def navaid_country(serviced_airport: str, fir: str) -> str:
    """Map a 424 navaid to a default-data region without guessing boundaries.

    A valid serviced airport is the only source-backed physical side for a
    navaid recorded against a FIR boundary, so it takes precedence.  A single
    published FIR is a fallback when no serviced airport exists.  Multiple
    country regions without that airport-side evidence remain unresolved.
    """

    airport_prefix = (serviced_airport or "").strip().upper()[:2]
    if airport_prefix in CN_PREFIXES:
        return airport_prefix
    fir_names = tuple(
        part.strip()
        for part in re.split(r"[，,]", fir or "")
        if part.strip()
    )
    if len(fir_names) == 1:
        try:
            return _FIR_COUNTRIES[fir_names[0]]
        except KeyError as error:
            raise ValueError(f"unmapped navaid FIR: {fir!r}") from error
    if fir_names:
        try:
            countries = {_FIR_COUNTRIES[name] for name in fir_names}
        except KeyError as error:
            raise ValueError(f"unmapped navaid FIR: {fir!r}") from error
        if len(countries) == 1:
            return next(iter(countries))
        raise ValueError(f"ambiguous navaid FIR without serviced airport: {fir!r}")
    raise ValueError("empty navaid FIR and serviced airport")


def waypoint_country(
    fir: str,
    latitude: float | None = None,
    longitude: float | None = None,
    ident: str = "",
    serviced_airport: str = "",
) -> str:
    """Map a structured designated point to an MSFS region key."""
    normalized_airport = (serviced_airport or "").strip().upper()
    if (
        re.fullmatch(r"Z[A-Z]{3}", normalized_airport)
        and is_china_icao(normalized_airport)
    ):
        # A source-declared servicing airport is more specific than its FIR.
        return normalized_airport[:2]
    if "\u9999\u6e2f" in (fir or ""):
        return "VH"
    if fir:
        # Without an airport-side marker, keep the first source-listed FIR.
        primary_fir = re.split(r"[，,]", fir, maxsplit=1)[0].strip()
        return navaid_country("", primary_fir)
    if ident in _EMPTY_FIR_COUNTRY_OVERRIDES:
        return _EMPTY_FIR_COUNTRY_OVERRIDES[ident]
    raise ValueError(f"empty waypoint FIR: {ident or '<unknown>'}")


def _airway_endpoint_key(
    endpoint_type: str,
    ident: str,
    latitude: float,
    longitude: float,
) -> tuple[str, str, float, float] | None:
    """Build the exact 424 identity used to recover a route endpoint FIR."""
    source_type = _AIRWAY_ENDPOINT_SOURCE_TYPES.get((endpoint_type or "").strip().upper())
    normalized_ident = (ident or "").strip().upper()
    if not source_type or not normalized_ident:
        return None
    return source_type, normalized_ident, round(latitude, 6), round(longitude, 6)


def _register_airway_endpoint_country(
    countries: dict[tuple[str, str, float, float], set[str]],
    endpoint_type: str,
    ident: str,
    latitude: float,
    longitude: float,
    country: str,
) -> None:
    key = _airway_endpoint_key(endpoint_type, ident, latitude, longitude)
    normalized_country = (country or "").strip().upper()[:2]
    if key is not None and normalized_country:
        countries.setdefault(key, set()).add(normalized_country)


def _recover_airway_endpoint_country(
    countries: dict[tuple[str, str, float, float], set[str]],
    endpoint_type: str,
    ident: str,
    latitude: float | None,
    longitude: float | None,
) -> str:
    """Return one source-proven FIR key, without geographic guesswork."""
    if latitude is None or longitude is None:
        return ""
    key = _airway_endpoint_key(endpoint_type, ident, latitude, longitude)
    matches = countries.get(key, set()) if key is not None else set()
    return next(iter(matches)) if len(matches) == 1 else ""


def _restore_airway_endpoint_countries(
    model: NavModel,
    countries: dict[tuple[str, str, float, float], set[str]],
) -> None:
    """Replace blank RTE_SEG FIRs only when another 424 table proves them."""
    model.airway_legs = [
        replace(
            leg,
            start_country=(
                _recover_airway_endpoint_country(
                    countries,
                    leg.start_type,
                    leg.start_ident,
                    leg.start_latitude,
                    leg.start_longitude,
                )
                or leg.start_country
            ),
            end_country=(
                _recover_airway_endpoint_country(
                    countries,
                    leg.end_type,
                    leg.end_ident,
                    leg.end_latitude,
                    leg.end_longitude,
                )
                or leg.end_country
            ),
        )
        for leg in model.airway_legs
    ]


def _load_fir_acc_countries(root: Path) -> dict[str, str]:
    """Map only explicitly named FIR control centers from AIRSPACE.csv."""
    path = root / "AIRSPACE.csv"
    if not path.is_file():
        return {}
    candidates: dict[str, set[str]] = {}
    for row in _rows(path):
        if (row.get("CODE_TYPE") or "").strip().upper() != "FIR":
            continue
        country = (row.get("CODE_ID") or "").strip().upper()[:2]
        name = (row.get("TXT_NAME") or "").strip()
        if country not in CN_PREFIXES or not name.endswith("飞行情报区"):
            continue
        acc_name = name.removesuffix("飞行情报区").strip()
        if acc_name:
            candidates.setdefault(acc_name, set()).add(country)
    return {
        name: next(iter(countries))
        for name, countries in sorted(candidates.items())
        if len(countries) == 1
    }


def _airway_acc_names(remark: str) -> set[str]:
    """Extract normalized source ACC names without assigning their regions."""
    return {
        match.group(1).removeprefix("以上").removeprefix("以下").strip()
        for match in _ACC_NAME.finditer(remark or "")
        if match.group(1).removeprefix("以上").removeprefix("以下").strip()
    }


def _explicit_endpoint_acc_evidence(
    remark: str,
    endpoints: tuple[tuple[str, str, float, float], ...],
    acc_countries: dict[str, str],
) -> dict[tuple[str, str, float, float], dict[str, set[str]]]:
    """Bind ACC evidence only to an explicitly labelled source route endpoint."""
    labels: list[tuple[int, int, tuple[str, str, float, float]]] = []
    for endpoint_type, ident, latitude, longitude in endpoints:
        key = _airway_endpoint_key(endpoint_type, ident, latitude, longitude)
        normalized_ident = (ident or "").strip()
        if key is None or key[0] != "DESIGNATED_POINT" or not normalized_ident:
            continue
        pattern = re.compile(
            rf"{re.escape(normalized_ident)}\s*[:\uFF1A]",
            re.IGNORECASE,
        )
        labels.extend(
            (match.start(), match.end(), key)
            for match in pattern.finditer(remark or "")
        )

    evidence: dict[tuple[str, str, float, float], dict[str, set[str]]] = {}
    ordered_labels = sorted(labels)
    for index, (_, end, key) in enumerate(ordered_labels):
        next_start = (
            ordered_labels[index + 1][0]
            if index + 1 < len(ordered_labels)
            else len(remark)
        )
        names = _airway_acc_names(remark[end:next_start])
        if not names:
            continue
        item = evidence.setdefault(key, {"regions": set(), "unknown": set()})
        item["regions"].update(
            acc_countries[name] for name in names if name in acc_countries
        )
        item["unknown"].update(names - acc_countries.keys())
    return evidence


def _restore_waypoint_countries_from_airway_acc(
    model: NavModel,
    countries: dict[tuple[str, str, float, float], set[str]],
    acc_countries: dict[str, str],
) -> dict[str, object]:
    """Recover blank designated-point regions from unambiguous source ACC evidence.

    A route remark is admissible only when every ACC it names is itself an
    AIRSPACE.csv FIR title and all mapped ACCs resolve to one target region.
    Blank remarks do not weaken otherwise unanimous evidence; unknown or
    cross-region ACCs keep the point unresolved.
    """
    evidence: dict[tuple[str, str, float, float], dict[str, set[str]]] = {}
    explicit_evidence: dict[
        tuple[str, str, float, float], dict[str, set[str]]
    ] = {}
    for leg in model.airway_legs:
        endpoints = (
            (leg.start_type, leg.start_ident, leg.start_latitude, leg.start_longitude),
            (leg.end_type, leg.end_ident, leg.end_latitude, leg.end_longitude),
        )
        for key, direct_item in _explicit_endpoint_acc_evidence(
            leg.source_airspace_remark,
            endpoints,
            acc_countries,
        ).items():
            item = explicit_evidence.setdefault(key, {"regions": set(), "unknown": set()})
            item["regions"].update(direct_item["regions"])
            item["unknown"].update(direct_item["unknown"])

        acc_names = _airway_acc_names(leg.source_airspace_remark)
        if not acc_names:
            continue
        regions = {acc_countries[name] for name in acc_names if name in acc_countries}
        unknown = acc_names - acc_countries.keys()
        for endpoint_type, ident, latitude, longitude in endpoints:
            key = _airway_endpoint_key(endpoint_type, ident, latitude, longitude)
            if key is None or key[0] != "DESIGNATED_POINT":
                continue
            item = evidence.setdefault(key, {"regions": set(), "unknown": set()})
            item["regions"].update(regions)
            item["unknown"].update(unknown)

    counts: Counter[str] = Counter()
    restored: list[Waypoint] = []
    for waypoint in model.waypoints:
        if waypoint.country:
            restored.append(waypoint)
            continue
        counts["blank_before"] += 1
        key = (
            "DESIGNATED_POINT",
            waypoint.ident.upper(),
            round(waypoint.latitude, 6),
            round(waypoint.longitude, 6),
        )
        explicit_item = explicit_evidence.get(key)
        item = explicit_item or evidence.get(key)
        if item is None:
            counts["not_airway_connected"] += 1
            restored.append(waypoint)
            continue
        counts["airway_connected"] += 1
        if explicit_item is not None:
            counts["explicit_endpoint_labeled"] += 1
        if item["unknown"]:
            counts["unknown_acc"] += 1
            restored.append(waypoint)
            continue
        if not item["regions"]:
            counts["no_mapped_acc"] += 1
            restored.append(waypoint)
            continue
        if len(item["regions"]) != 1:
            counts["multiple_acc_regions"] += 1
            restored.append(waypoint)
            continue
        country = next(iter(item["regions"]))
        restored_waypoint = replace(waypoint, country=country)
        restored.append(restored_waypoint)
        _register_airway_endpoint_country(
            countries,
            "DESIGNATED_POINT",
            restored_waypoint.ident,
            restored_waypoint.latitude,
            restored_waypoint.longitude,
            country,
        )
        counts["recovered"] += 1
        if explicit_item is not None:
            counts["recovered_from_explicit_endpoint_label"] += 1

    model.waypoints = restored
    counts["blank_after"] = counts["blank_before"] - counts["recovered"]
    return {
        "source": {
            "airspace": "AIRSPACE.csv",
            "airway_segments": "RTE_SEG.csv",
        },
        "fir_acc_names": len(acc_countries),
        "waypoints": {
            "blank_before": counts["blank_before"],
            "airway_connected": counts["airway_connected"],
            "not_airway_connected": counts["not_airway_connected"],
            "explicit_endpoint_labeled": counts["explicit_endpoint_labeled"],
            "recovered": counts["recovered"],
            "recovered_from_explicit_endpoint_label": (
                counts["recovered_from_explicit_endpoint_label"]
            ),
            "unknown_acc": counts["unknown_acc"],
            "no_mapped_acc": counts["no_mapped_acc"],
            "multiple_acc_regions": counts["multiple_acc_regions"],
            "blank_after": counts["blank_after"],
        },
    }


def _unwrap_longitude(longitude: float, origin_longitude: float) -> float:
    """Keep a polygon longitude close to the tested point's meridian."""
    return origin_longitude + ((longitude - origin_longitude + 180) % 360) - 180


def _angular_distance(
    latitude: float,
    longitude: float,
    other_latitude: float,
    other_longitude: float,
) -> float:
    first_latitude = math.radians(latitude)
    second_latitude = math.radians(other_latitude)
    delta_latitude = second_latitude - first_latitude
    delta_longitude = math.radians(other_longitude - longitude)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first_latitude)
        * math.cos(second_latitude)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * math.asin(math.sqrt(min(1.0, value)))


def _initial_bearing(
    latitude: float,
    longitude: float,
    other_latitude: float,
    other_longitude: float,
) -> float:
    first_latitude = math.radians(latitude)
    second_latitude = math.radians(other_latitude)
    delta_longitude = math.radians(other_longitude - longitude)
    return math.atan2(
        math.sin(delta_longitude) * math.cos(second_latitude),
        math.cos(first_latitude) * math.sin(second_latitude)
        - math.sin(first_latitude)
        * math.cos(second_latitude)
        * math.cos(delta_longitude),
    )


def _distance_to_fir_segment_nm(
    latitude: float,
    longitude: float,
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> float:
    """Return the nearest great-circle distance from a point to one FIR edge."""
    point_to_start = _angular_distance(
        start_latitude, start_longitude, latitude, longitude,
    )
    segment_length = _angular_distance(
        start_latitude, start_longitude, end_latitude, end_longitude,
    )
    if segment_length == 0:
        return point_to_start * _EARTH_RADIUS_NM
    start_to_point_bearing = _initial_bearing(
        start_latitude, start_longitude, latitude, longitude,
    )
    segment_bearing = _initial_bearing(
        start_latitude, start_longitude, end_latitude, end_longitude,
    )
    bearing_delta = start_to_point_bearing - segment_bearing
    cross_track = math.asin(
        max(-1.0, min(1.0, math.sin(point_to_start) * math.sin(bearing_delta)))
    )
    along_track = math.atan2(
        math.sin(point_to_start) * math.cos(bearing_delta),
        math.cos(point_to_start),
    )
    if 0 <= along_track <= segment_length:
        return abs(cross_track) * _EARTH_RADIUS_NM
    point_to_end = _angular_distance(
        end_latitude, end_longitude, latitude, longitude,
    )
    return min(point_to_start, point_to_end) * _EARTH_RADIUS_NM


def _point_is_inside_fir(
    latitude: float,
    longitude: float,
    polygon: _FirPolygon,
) -> bool:
    """Use a deterministic ray cast after locally unwrapping longitudes."""
    inside = False
    vertices = [
        (vertex_latitude, _unwrap_longitude(vertex_longitude, longitude))
        for vertex_latitude, vertex_longitude in polygon.vertices
    ]
    for index, (start_latitude, start_longitude) in enumerate(vertices):
        end_latitude, end_longitude = vertices[(index + 1) % len(vertices)]
        if (start_latitude > latitude) == (end_latitude > latitude):
            continue
        crossing_longitude = (
            (end_longitude - start_longitude)
            * (latitude - start_latitude)
            / (end_latitude - start_latitude)
            + start_longitude
        )
        if longitude < crossing_longitude:
            inside = not inside
    return inside


def _distance_to_fir_boundary_nm(
    latitude: float,
    longitude: float,
    polygon: _FirPolygon,
) -> float:
    distances = []
    for index, (start_latitude, start_longitude) in enumerate(polygon.vertices):
        end_latitude, end_longitude = polygon.vertices[
            (index + 1) % len(polygon.vertices)
        ]
        distances.append(_distance_to_fir_segment_nm(
            latitude,
            longitude,
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        ))
    return min(distances)


def _load_fir_polygons(root: Path) -> tuple[tuple[_FirPolygon, ...], int]:
    """Load only well-formed Chinese FIR boundaries from the 424 source."""
    airspace_path = root / "AIRSPACE.csv"
    vertices_path = root / "AIRSPACE_BORDER_VERTEX.csv"
    if not airspace_path.is_file() or not vertices_path.is_file():
        return (), 0
    firs: dict[str, tuple[str, str]] = {}
    for row in _rows(airspace_path):
        if (row.get("CODE_TYPE") or "").strip().upper() != "FIR":
            continue
        airspace_id = (row.get("AIRSPACE_ID") or "").strip()
        code = (row.get("CODE_ID") or "").strip().upper()
        country = code[:2]
        if airspace_id and country in CN_PREFIXES:
            firs.setdefault(airspace_id, (code, country))
    vertices: dict[str, list[tuple[int, float, float]]] = {
        airspace_id: [] for airspace_id in firs
    }
    invalid_firs: set[str] = set()
    for row in _rows(vertices_path):
        airspace_id = (row.get("AIRSPACE_ID") or "").strip()
        if airspace_id not in vertices:
            continue
        try:
            vertices[airspace_id].append((
                _number(row.get("NO_SEQ") or "0"),
                parse_dms(row.get("GEO_LAT") or ""),
                parse_dms(row.get("GEO_LONG") or ""),
            ))
        except ValueError:
            invalid_firs.add(airspace_id)
    polygons: list[_FirPolygon] = []
    vertices_loaded = 0
    for airspace_id, (code, country) in sorted(
        firs.items(), key=lambda item: item[1][0],
    ):
        polygon_vertices = vertices[airspace_id]
        if airspace_id in invalid_firs or len(polygon_vertices) < 3:
            continue
        polygon_vertices.sort(key=lambda item: item[0])
        polygons.append(_FirPolygon(
            code=code,
            country=country,
            vertices=tuple(
                (latitude, longitude)
                for _, latitude, longitude in polygon_vertices
            ),
        ))
        vertices_loaded += len(polygon_vertices)
    return tuple(polygons), vertices_loaded


def _match_source_fir_region(
    polygons: tuple[_FirPolygon, ...],
    latitude: float,
    longitude: float,
) -> _FirRegionMatch:
    """Recover a region only when source geometry leaves no boundary doubt."""
    containing = [
        polygon
        for polygon in polygons
        if _point_is_inside_fir(latitude, longitude, polygon)
    ]
    if len(containing) > 1:
        return _FirRegionMatch("ambiguous")
    if len(containing) == 1:
        if (
            _distance_to_fir_boundary_nm(latitude, longitude, containing[0])
            < _FIR_BOUNDARY_MIN_DISTANCE_NM
        ):
            return _FirRegionMatch("near_boundary")
        return _FirRegionMatch("recovered", containing[0].country)
    return _FirRegionMatch("outside")


def _validate_pdf_cache(root: Path, pdf_cache: Path | None) -> Path | None:
    if pdf_cache is None:
        return None
    resolved_cache = pdf_cache.resolve()
    if resolved_cache.is_relative_to(root):
        raise ValueError("PDF 证据缓存不得写入 NAIP 原始数据目录")
    return resolved_cache


def _load_general_document_waypoints(
    model: NavModel,
    cache_root: Path | None,
    fir_polygons: tuple[_FirPolygon, ...],
    airway_endpoint_countries: dict[tuple[str, str, float, float], set[str]],
    *,
    cache_directory: str = ENROUTE_KEY_POINT_CACHE_DIRECTORY,
) -> None:
    """Add only OCR points whose region and logical identity are unambiguous."""
    if cache_root is None:
        model.general_document_evidence = {
            **model.general_document_evidence,
            "available": False,
            "reason": "general document OCR cache was not provided",
            "waypoints": {
                "available": False,
                "reason": "general document OCR cache was not provided",
            },
        }
        return

    evidence, report = load_enroute_key_point_evidence(
        model.root,
        cache_root,
        cache_directory=cache_directory,
    )
    counts: Counter[str] = Counter()
    by_identity: dict[tuple[str, str], list[Waypoint]] = {}
    for point in model.waypoints:
        if point.country:
            by_identity.setdefault(
                (point.country.upper(), point.ident.upper()),
                [],
            ).append(point)

    for sequence, item in enumerate(evidence, start=1):
        region = _match_source_fir_region(
            fir_polygons,
            item.latitude,
            item.longitude,
        )
        if region.status != "recovered":
            counts[f"region_{region.status}"] += 1
            model.rejected_records.append(RejectedRecord(
                "general-document-waypoint",
                item.ident,
                f"general document region {region.status}",
                item.source,
            ))
            continue
        country = region.country
        identity = (country, item.ident.upper())
        existing = by_identity.get(identity, [])
        if existing:
            matches = [
                point
                for point in existing
                if _angular_distance(
                    point.latitude,
                    point.longitude,
                    item.latitude,
                    item.longitude,
                ) * _EARTH_RADIUS_NM <= 0.01
            ]
            if matches:
                counts["already_present"] += 1
                continue
            counts["identity_conflict"] += 1
            model.rejected_records.append(RejectedRecord(
                "general-document-waypoint",
                item.ident,
                "general document identity conflicts with source waypoint",
                item.source,
            ))
            continue

        point = Waypoint(
            f"general-doc:{item.source.sha256[:16]}:{item.source.page}:{sequence}:{item.ident}",
            item.ident,
            item.ident,
            item.latitude,
            item.longitude,
            item.source,
            country,
        )
        model.waypoints.append(point)
        by_identity.setdefault(identity, []).append(point)
        _register_airway_endpoint_country(
            airway_endpoint_countries,
            "DESIGNATED_POINT",
            point.ident,
            point.latitude,
            point.longitude,
            point.country,
        )
        counts["accepted"] += 1

    model.general_document_evidence = {
        **model.general_document_evidence,
        **report,
        "waypoints": {
            "accepted": counts["accepted"],
            "already_present": counts["already_present"],
            "identity_conflict": counts["identity_conflict"],
            "region_ambiguous": counts["region_ambiguous"],
            "region_near_boundary": counts["region_near_boundary"],
            "region_outside": counts["region_outside"],
        },
    }


def _load_general_document_navaids(
    model: NavModel,
    cache_root: Path | None,
    *,
    cache_directory: str = ENROUTE_NAVAID_CACHE_DIRECTORY,
) -> None:
    """Retain 4.1 facts and prove matching direct 424 identities conservatively."""
    if cache_root is None:
        model.general_document_evidence = {
            **model.general_document_evidence,
            "navaids": {
                "available": False,
                "reason": "general document OCR cache was not provided",
            },
        }
        return
    try:
        evidence, report = load_enroute_navaid_evidence(
            model.root,
            cache_root,
            cache_directory=cache_directory,
        )
    except GeneralDocumentCacheError as error:
        model.general_document_evidence = {
            **model.general_document_evidence,
            "navaids": {
                "available": False,
                "reason": str(error),
            },
        }
        return

    by_identity: dict[tuple[str, str], list[Navaid]] = {}
    for navaid in model.navaids:
        by_identity.setdefault((navaid.kind.upper(), navaid.ident.upper()), []).append(navaid)

    counts: Counter[str] = Counter()
    identifier_reconciliations: list[dict[str, object]] = []
    for item in evidence:
        model.enroute_navaid_evidence.append(item)
        matches = by_identity.get((item.kind.upper(), item.ident.upper()), [])
        if not matches:
            physical_matches = [
                navaid
                for navaid in model.navaids
                if navaid.kind.upper() == item.kind.upper()
                and abs(navaid.frequency - item.frequency) <= 0.001
                and _angular_distance(
                    navaid.latitude,
                    navaid.longitude,
                    item.latitude,
                    item.longitude,
                ) * _EARTH_RADIUS_NM <= 0.02
            ]
            if len(physical_matches) == 1:
                navaid = physical_matches[0]
                counts["ocr_identifier_reconciled"] += 1
                identifier_reconciliations.append({
                    "page": item.source.page,
                    "kind": item.kind,
                    "ocr_ident": item.ident,
                    "direct_424_ident": navaid.ident,
                    "source_file": navaid.source.file,
                    "source_row": navaid.source.row,
                })
                continue
            if len(physical_matches) > 1:
                counts["physical_identity_ambiguous"] += 1
                model.rejected_records.append(RejectedRecord(
                    "general-document-navaid",
                    item.ident,
                    "general document physical identity is ambiguous in direct 424 navaids",
                    item.source,
                ))
                continue
            counts["direct_identity_missing"] += 1
            continue
        if len(matches) != 1:
            counts["direct_identity_ambiguous"] += 1
            model.rejected_records.append(RejectedRecord(
                "general-document-navaid",
                item.ident,
                "general document identity is ambiguous in direct 424 navaids",
                item.source,
            ))
            continue
        navaid = matches[0]
        exact_frequency = abs(navaid.frequency - item.frequency) <= 0.001
        exact_position = _angular_distance(
            navaid.latitude,
            navaid.longitude,
            item.latitude,
            item.longitude,
        ) * _EARTH_RADIUS_NM <= 0.02
        if exact_frequency and exact_position:
            counts["matched_424"] += 1
            continue
        counts["identity_conflict"] += 1
        model.rejected_records.append(RejectedRecord(
            "general-document-navaid",
            item.ident,
            "general document fact conflicts with direct 424 navaid",
            item.source,
        ))

    model.general_document_evidence = {
        **model.general_document_evidence,
        "navaids": {
            **report,
            "matched_424": counts["matched_424"],
            "ocr_identifier_reconciled": counts["ocr_identifier_reconciled"],
            "ocr_identifier_reconciliations": identifier_reconciliations,
            "direct_identity_missing": counts["direct_identity_missing"],
            "direct_identity_ambiguous": counts["direct_identity_ambiguous"],
            "physical_identity_ambiguous": counts["physical_identity_ambiguous"],
            "identity_conflict": counts["identity_conflict"],
        },
    }


def _load_general_document_airway_minimum_altitudes(
    model: NavModel,
    cache_root: Path | None,
    *,
    cache_directories: tuple[str, ...],
) -> None:
    """Project only uniquely matched 3.2 table altitudes onto direct 424 legs."""
    if not cache_directories:
        model.general_document_evidence = {
            **model.general_document_evidence,
            "airway_minimum_altitudes": {
                "available": False,
                "reason": "no 3.2 airway OCR cache directories were requested",
            },
        }
        return
    if cache_root is None:
        raise ValueError("3.2 airway OCR caches require a general document cache root")

    by_identity: dict[tuple[str, str, str], list[int]] = {}
    for index, leg in enumerate(model.airway_legs):
        by_identity.setdefault((
            leg.airway.upper(),
            leg.start_ident.upper(),
            leg.end_ident.upper(),
        ), []).append(index)

    evidence_by_identity: dict[tuple[str, str, str], list[object]] = {}
    document_reports: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for cache_directory in cache_directories:
        try:
            evidence, report = load_enroute_airway_minimum_altitude_evidence(
                model.root,
                cache_root,
                cache_directory=cache_directory,
            )
        except GeneralDocumentCacheError as error:
            document_reports.append({
                "cache_directory": cache_directory,
                "available": False,
                "reason": str(error),
            })
            counts["unavailable_cache"] += 1
            continue
        document_reports.append({
            **report,
            "cache_directory": cache_directory,
        })
        for item in evidence:
            model.enroute_airway_minimum_altitude_evidence.append(item)
            evidence_by_identity.setdefault((
                item.airway.upper(),
                item.start_ident.upper(),
                item.end_ident.upper(),
            ), []).append(item)

    for identity, evidence in sorted(evidence_by_identity.items()):
        altitudes = {item.minimum_altitude_meters for item in evidence}
        if len(altitudes) != 1:
            counts["conflicting_evidence"] += 1
            for item in evidence:
                model.rejected_records.append(RejectedRecord(
                    "general-document-airway-minimum-altitude",
                    ":".join(identity),
                    "3.2 airway table gives conflicting minimum altitudes",
                    item.source,
                ))
            continue
        matches = by_identity.get(identity, [])
        if len(matches) == 0:
            counts["direct_424_leg_missing"] += 1
            continue
        if len(matches) != 1:
            counts["direct_424_leg_ambiguous"] += 1
            for item in evidence:
                model.rejected_records.append(RejectedRecord(
                    "general-document-airway-minimum-altitude",
                    ":".join(identity),
                    "3.2 airway table identity is ambiguous in direct 424 legs",
                    item.source,
                ))
            continue
        index = matches[0]
        altitude_ft = _feet(str(next(iter(altitudes))))
        leg = model.airway_legs[index]
        if leg.minimum_altitude_ft is not None and leg.minimum_altitude_ft != altitude_ft:
            counts["direct_424_conflict"] += 1
            for item in evidence:
                model.rejected_records.append(RejectedRecord(
                    "general-document-airway-minimum-altitude",
                    ":".join(identity),
                    "3.2 airway table conflicts with populated direct 424 altitude",
                    item.source,
                ))
            continue
        if leg.minimum_altitude_ft == altitude_ft:
            counts["already_projected"] += 1
            continue
        model.airway_legs[index] = replace(
            leg,
            minimum_altitude_ft=altitude_ft,
        )
        counts["projected"] += 1

    model.general_document_evidence = {
        **model.general_document_evidence,
        "airway_minimum_altitudes": {
            "available": bool(document_reports) and not counts["unavailable_cache"],
            "documents": document_reports,
            "parsed_records": len(model.enroute_airway_minimum_altitude_evidence),
            "projected": counts["projected"],
            "already_projected": counts["already_projected"],
            "direct_424_leg_missing": counts["direct_424_leg_missing"],
            "direct_424_leg_ambiguous": counts["direct_424_leg_ambiguous"],
            "direct_424_conflict": counts["direct_424_conflict"],
            "conflicting_evidence": counts["conflicting_evidence"],
            "unavailable_cache": counts["unavailable_cache"],
        },
    }


def audit_enroute_navaid_ocr_source(
    root: Path,
    cache: Path,
) -> dict[str, object]:
    """Audit one complete OCR cache against direct 424 navaid identities."""
    root = root.expanduser().resolve()
    cache = _validate_pdf_cache(root, cache)
    model = load_naip(root, include_terminal_documents=False)
    _load_general_document_navaids(
        model,
        cache.parent,
        cache_directory=cache.name,
    )
    navaids = model.general_document_evidence["navaids"]
    if navaids.get("available") is not True:
        raise GeneralDocumentCacheError(str(navaids.get("reason") or "OCR cache is unavailable"))
    unresolved = [
        {
            "ident": record.key,
            "page": record.source.page,
            "reason": record.reason,
        }
        for record in model.rejected_records
        if record.kind == "general-document-navaid"
    ]
    return {
        "diagnostic": "enroute-navaid-ocr-source-audit-v1",
        "evidence_only": True,
        "document": ENROUTE_NAVAID_DOCUMENT,
        "cache": str(cache),
        "source_sha256": navaids["source_sha256"],
        "navaids": navaids,
        "unresolved_evidence": unresolved,
    }


def _key_point_ocr_identity(item: object) -> tuple[object, ...]:
    return (
        getattr(item, "ident"),
        getattr(item, "latitude"),
        getattr(item, "longitude"),
        getattr(getattr(item, "source"), "page"),
    )


def _key_point_fir_counts(
    evidence: tuple[object, ...],
    polygons: tuple[_FirPolygon, ...],
) -> dict[str, int]:
    return dict(sorted(Counter(
        _match_source_fir_region(
            polygons,
            getattr(item, "latitude"),
            getattr(item, "longitude"),
        ).status
        for item in evidence
    ).items()))


def audit_enroute_key_point_ocr_rerun(
    root: Path,
    canonical_cache: Path,
    rerun_cache: Path,
    *,
    allow_partial_rerun: bool = False,
) -> dict[str, object]:
    """Compare full or explicitly partial 4.4 OCR rerun caches."""
    root = root.expanduser().resolve()
    canonical_cache = _validate_pdf_cache(root, canonical_cache)
    rerun_cache = _validate_pdf_cache(root, rerun_cache)
    canonical, canonical_report = load_enroute_key_point_evidence(
        root,
        canonical_cache.parent,
        cache_directory=canonical_cache.name,
    )
    if allow_partial_rerun:
        rerun, rerun_report = load_selected_enroute_key_point_evidence(
            root,
            rerun_cache,
            require_complete=False,
        )
    else:
        rerun, rerun_report = load_enroute_key_point_evidence(
            root,
            rerun_cache.parent,
            cache_directory=rerun_cache.name,
        )
    if canonical_report["source_sha256"] != rerun_report["source_sha256"]:
        raise GeneralDocumentCacheError("OCR rerun cache source PDF SHA-256 does not match")
    if canonical_report["pages"] != rerun_report["pages"]:
        raise GeneralDocumentCacheError("OCR rerun cache page count does not match")

    selected_pages = tuple(rerun_report.get(
        "selected_pages",
        range(1, int(canonical_report["pages"]) + 1),
    ))
    canonical = tuple(
        item for item in canonical if item.source.page in selected_pages
    )
    canonical_keys = {_key_point_ocr_identity(item) for item in canonical}
    rerun_keys = {_key_point_ocr_identity(item) for item in rerun}
    common = canonical_keys & rerun_keys
    canonical_only = tuple(
        item for item in canonical if _key_point_ocr_identity(item) not in rerun_keys
    )
    rerun_only = tuple(
        item for item in rerun if _key_point_ocr_identity(item) not in canonical_keys
    )
    differences = [
        {
            "page": page,
            "canonical_only": sum(
                1
                for item in canonical_only
                if item.source.page == page
            ),
            "rerun_only": sum(
                1
                for item in rerun_only
                if item.source.page == page
            ),
        }
        for page in range(1, int(canonical_report["pages"]) + 1)
        if any(
            item.source.page == page
            for item in canonical_only + rerun_only
        )
    ]
    polygons, vertices = _load_fir_polygons(root)
    union_count = len(canonical_keys | rerun_keys)
    return {
        "diagnostic": "enroute-key-point-ocr-rerun-audit-v1",
        "evidence_only": True,
        "document": ENROUTE_KEY_POINT_DOCUMENT,
        "source_sha256": canonical_report["source_sha256"],
        "canonical": {
            **canonical_report,
            "parsed_records": len(canonical),
        },
        "rerun": {
            **rerun_report,
            "parsed_records": len(rerun),
        },
        "comparison": {
            "consistent": not canonical_only and not rerun_only,
            "agreement_ratio": round(len(common) / union_count, 6) if union_count else 1.0,
            "projection_allowed": False,
            "reason": (
                "OCR rerun is diagnostic evidence only; it must not replace the "
                "canonical cache or enter a candidate build without a separate "
                "source-backed acceptance decision"
            ),
        },
        "scope": {
            "rerun_complete": len(selected_pages) == int(canonical_report["pages"]),
            "selected_pages": list(selected_pages),
        },
        "records": {
            "agreed": len(common),
            "canonical_only": len(canonical_only),
            "rerun_only": len(rerun_only),
            "differences_by_page": differences,
        },
        "source_fir_region_resolution": {
            "polygons_loaded": len(polygons),
            "vertices_loaded": vertices,
            "canonical": _key_point_fir_counts(canonical, polygons),
            "rerun": _key_point_fir_counts(rerun, polygons),
            "canonical_only": _key_point_fir_counts(canonical_only, polygons),
            "rerun_only": _key_point_fir_counts(rerun_only, polygons),
        },
    }


def load_naip(
    root: Path,
    pdf_cache: Path | None = None,
    *,
    general_doc_cache: Path | None = None,
    general_doc_key_point_cache_directory: str = ENROUTE_KEY_POINT_CACHE_DIRECTORY,
    general_doc_airway_cache_directories: tuple[str, ...] = (),
    iap_ocr_role_evidence: IapOcrRoleEvidence | None = None,
    include_terminal_documents: bool = True,
) -> NavModel:
    """Load only structured data; PDFs are inspected separately and never guessed."""
    root = root.resolve()
    pdf_cache = _validate_pdf_cache(root, pdf_cache)
    general_doc_cache = _validate_pdf_cache(root, general_doc_cache)
    model = NavModel(root=root, iap_ocr_role_evidence=iap_ocr_role_evidence)
    airway_endpoint_countries: dict[tuple[str, str, float, float], set[str]] = {}
    segment_rows = _optional_index(root, "SEGMENT.csv", "SEGMENT_ID")
    en_route_rows = _optional_index(root, "EN_ROUTE_RTE.csv", "EN_ROUTE_RTE_ID")
    fir_polygons, fir_vertices_loaded = _load_fir_polygons(root)
    fir_acc_countries = _load_fir_acc_countries(root)
    fir_region_counts: Counter[str] = Counter()
    for row_number, row in enumerate(_rows(root / "AD_HP.csv"), start=2):
        icao = (row.get("CODE_ID") or "").strip().upper()
        if not is_china_icao(icao):
            continue
        key = row["AD_HP_ID"]
        model.airports[key] = Airport(key, icao, row.get("TXT_NAME") or icao,
            round(parse_dms(row.get("GEO_LAT_ACCURACY") or ""), 6), round(parse_dms(row.get("GEO_LONG_ACCURACY") or ""), 6),
            _feet(row.get("VAL_ELEV") or "0"), _airport_altitude_feet(row.get("VAL_TRANSITION_ALT") or "0"),
            _airport_altitude_feet(row.get("VAL_TRANSITION_LEVEL") or "0"), SourceRef("AD_HP.csv", row_number))

    _load_airport_pdf_names(model)

    dimensions: dict[str, tuple[str, int, int, str, float, float]] = {}
    for row_number, row in enumerate(_rows(root / "RWY.csv"), start=2):
        airport_key = row.get("AD_HP_ID") or ""
        airport = model.airports.get(airport_key)
        if airport is not None:
            dimensions[row["RWY_ID"]] = (
                airport_key,
                _feet(row.get("VAL_LEN") or "0"),
                _feet(row.get("VAL_WID") or "0"),
                _surface(row.get("CODE_COMPOSITION") or ""),
                airport.latitude,
                airport.longitude,
            )
    for row_number, row in enumerate(_rows(root / "RWY_DIRECTION.csv"), start=2):
        runway = dimensions.get(row.get("RWY_ID") or "")
        if runway is not None:
            airport_key, length, width, surface, airport_latitude, airport_longitude = runway
            true_heading = _float(row.get("VAL_TRUE_BRG") or "0")
            latitude, longitude = runway_threshold(
                airport_latitude,
                airport_longitude,
                true_heading,
                length,
            )
            model.runways.append(Runway(row["RWY_DIRECTION_ID"], airport_key, row.get("TXT_DESIG") or "",
                true_heading, length, width, surface, _feet(row.get("VAL_ELEV") or "0"),
                SourceRef("RWY_DIRECTION.csv", row_number), latitude, longitude))

    for filename, kind, divisor in (("VOR.csv", "VOR", 1), ("NDB.csv", "NDB", 1)):
        for row_number, row in enumerate(_rows(root / filename), start=2):
            try:
                latitude = parse_dms(row.get("GEO_LAT_ACCURACY") or "")
                longitude = parse_dms(row.get("GEO_LONG_ACCURACY") or "")
                serviced_airport = (row.get("SERVICED_AIRPORT") or "").strip().upper()
                code_fir = (row.get("CODE_FIR") or "").strip()
                country = navaid_country(serviced_airport, code_fir)
                navaid = Navaid(row["SIGNIFICANT_POINT_ID"], row.get("CODE_ID") or "", kind,
                    row.get("TXT_NAME") or "", latitude,
                    longitude, _float(row.get("VAL_FREQ") or "0") / divisor,
                    _float(row.get("VAL_MAG_VAR") or "0"), _navaid_elevation_feet(
                        row.get("VAL_ELEV") or "0", row.get("UOM_DIST_VER") or "",
                    ),
                    country, SourceRef(filename, row_number),
                    code_in_airway=(row.get("CODE_IN_AIRWAY") or "").strip().upper(),
                    purpose=(row.get("PURPOSE") or "").strip().upper(),
                    is_rep_atc=(row.get("IS_REP_ATC") or "").strip().upper(),
                    route_restrict=(row.get("ROUTE_RESTRICT") or "").strip().upper(),
                    is_trans_point=(row.get("IS_TRANS_POINT") or "").strip().upper(),
                    is_border_point=(row.get("IS_BORDER_POINT") or "").strip().upper(),
                    serviced_airport=serviced_airport,
                    code_fir=code_fir,
                )
                model.navaids.append(navaid)
                _register_airway_endpoint_country(
                    airway_endpoint_countries,
                    "VORDME" if kind == "VOR" else "NDB",
                    navaid.ident,
                    navaid.latitude,
                    navaid.longitude,
                    navaid.country,
                )
            except ValueError:
                model.rejected_records.append(RejectedRecord(
                    kind=kind,
                    key=row.get("CODE_ID") or row.get("SIGNIFICANT_POINT_ID") or "",
                    reason="invalid coordinate or unmapped country",
                    source=SourceRef(filename, row_number),
                ))
    _load_general_document_navaids(model, general_doc_cache)
    for row_number, row in enumerate(_rows(root / "DESIGNATED_POINT.csv"), start=2):
        try:
            latitude = parse_dms(row.get("GEO_LAT_ACCURACY") or "")
            longitude = parse_dms(row.get("GEO_LONG_ACCURACY") or "")
            ident = row.get("CODE_ID") or ""
            serviced_airport = (row.get("SERVICED_AIRPORT") or "").strip()
            has_strict_serviced_airport = bool(
                re.fullmatch(r"Z[A-Z]{3}", serviced_airport.upper())
                and is_china_icao(serviced_airport)
            )
            country = (
                waypoint_country(
                    row.get("CODE_FIR") or "",
                    latitude,
                    longitude,
                    ident,
                    serviced_airport,
                )
                if (
                    (row.get("CODE_FIR") or "").strip()
                    or ident.upper() in _EMPTY_FIR_COUNTRY_OVERRIDES
                    or has_strict_serviced_airport
                )
                else ""
            )
            if not country:
                fir_region_counts["blank_before"] += 1
                fir_match = _match_source_fir_region(
                    fir_polygons,
                    latitude,
                    longitude,
                )
                fir_region_counts[fir_match.status] += 1
                if fir_match.status == "recovered":
                    country = fir_match.country
            model.waypoints.append(Waypoint(row["SIGNIFICANT_POINT_ID"], ident, row.get("TXT_NAME") or "",
                latitude, longitude, SourceRef("DESIGNATED_POINT.csv", row_number), country))
            if country:
                _register_airway_endpoint_country(
                    airway_endpoint_countries,
                    "DESIGNATED_POINT",
                    ident,
                    latitude,
                    longitude,
                    country,
                )
        except ValueError:
            model.rejected_records.append(RejectedRecord(
                kind="designated-point", key=row.get("CODE_ID") or row.get("SIGNIFICANT_POINT_ID") or "",
                reason="invalid coordinate or unmapped country", source=SourceRef("DESIGNATED_POINT.csv", row_number),
            ))
    _load_general_document_waypoints(
        model,
        general_doc_cache,
        fir_polygons,
        airway_endpoint_countries,
        cache_directory=general_doc_key_point_cache_directory,
    )
    model.source_fir_region_resolution = SourceFirRegionResolution(
        polygons_loaded=len(fir_polygons),
        vertices_loaded=fir_vertices_loaded,
        blank_before=fir_region_counts["blank_before"],
        recovered=fir_region_counts["recovered"],
        ambiguous=fir_region_counts["ambiguous"],
        near_boundary=fir_region_counts["near_boundary"],
        outside=fir_region_counts["outside"],
    ).to_report()
    for row_number, row in enumerate(_rows(root / "RTE_SEG.csv"), start=2):
        try:
            start_latitude = parse_dms(row.get("GEO_LAT_START_ACCURACY") or "")
            start_longitude = parse_dms(row.get("GEO_LONG_START_ACCURACY") or "")
            end_latitude = parse_dms(row.get("GEO_LAT_END_ACCURACY") or "")
            end_longitude = parse_dms(row.get("GEO_LONG_END_ACCURACY") or "")
            start_ident = row.get("CODE_POINT_START") or ""
            end_ident = row.get("CODE_POINT_END") or ""
            try:
                start_country = (
                    waypoint_country(row.get("CODE_FIR_START") or "", start_latitude, start_longitude, start_ident)
                    if (row.get("CODE_FIR_START") or "").strip()
                    else ""
                )
            except ValueError:
                start_country = ""
            try:
                end_country = (
                    waypoint_country(row.get("CODE_FIR_END") or "", end_latitude, end_longitude, end_ident)
                    if (row.get("CODE_FIR_END") or "").strip()
                    else ""
                )
            except ValueError:
                end_country = ""
            source_segment_id = (row.get("SEGMENT_ID") or "").strip()
            source_en_route_rte_id = (row.get("EN_ROUTE_RTE_ID") or "").strip()
            segment = segment_rows.get(source_segment_id)
            en_route = en_route_rows.get(source_en_route_rte_id)
            model.airway_legs.append(AirwayLeg(
                row.get("TXT_DESIG") or "", _number(row.get("VAL_SORT") or "0"),
                start_ident, end_ident, SourceRef("RTE_SEG.csv", row_number), row.get("CODE_DIR") or "",
                start_latitude, start_longitude, end_latitude, end_longitude, start_country, end_country,
                # RTE_SEG.CODE_TYPE is PBN/source semantics, not the SDK
                # VICTOR/JET/BOTH vocabulary.  Leave the target hint empty
                # until an adapter has a verified mapping rule.
                route_type="",
                start_type=row.get("CODE_TYPE_START") or "",
                end_type=row.get("CODE_TYPE_END") or "",
                source_code_type=(row.get("CODE_TYPE") or "").strip(),
                source_airspace_remark=(
                    row.get("Airspace_Remark") or ""
                ).strip(),
                source_segment_rnp_designator=(
                    (segment.get("TXT_DESIG_RNP") or "").strip()
                    if segment is not None else ""
                ),
                source_enroute_location_type=(
                    (en_route.get("TXT_LOC_TYPE") or "").strip()
                    if en_route is not None else ""
                ),
                source_segment_minimum_crossing_altitude=(
                    (segment.get("VAL_MTCA") or "").strip()
                    if segment is not None else ""
                ),
                source_route_minimum_crossing_altitude=(
                    (en_route.get("VAL_MTCA") or "").strip()
                    if en_route is not None else ""
                ),
                source_rte_seg_id=(row.get("RTE_SEG_ID") or "").strip(),
                source_segment_id=source_segment_id,
                source_en_route_rte_id=source_en_route_rte_id,
                source_segment_found=segment is not None,
                source_en_route_rte_found=en_route is not None,
            ))
        except ValueError:
            model.rejected_records.append(RejectedRecord(
                kind="airway-leg", key=row.get("TXT_DESIG") or "", reason="invalid airway endpoint coordinate",
                source=SourceRef("RTE_SEG.csv", row_number),
            ))
    model.source_acc_region_resolution = _restore_waypoint_countries_from_airway_acc(
        model,
        airway_endpoint_countries,
        fir_acc_countries,
    )
    _restore_airway_endpoint_countries(model, airway_endpoint_countries)
    _load_general_document_airway_minimum_altitudes(
        model,
        general_doc_cache,
        cache_directories=general_doc_airway_cache_directories,
    )
    if include_terminal_documents:
        _load_terminal_coordinate_pages(model, pdf_cache)
        _promote_shared_terminal_coordinate_waypoints(model)
        _load_terminal_landing_aids(model)
        _load_terminal_database_charts(model, pdf_cache)
        _load_terminal_standard_procedure_charts(model, pdf_cache)
        _build_database_procedure_segments(model)
        _build_database_holdings(model)
        _retain_database_referenced_terminal_waypoints(model)
        _load_terminal_approach_charts(model, pdf_cache)
        _project_same_page_rnp_primary_to_ils(model)
        _reject_unparsed_charts(model)
    return model


def _load_terminal_landing_aids(model: NavModel) -> None:
    """Retain AD 2.19 landing-aid evidence before target projection."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        ilses, vors = extract_airport_ad219_landing_aids(airport_directory)
        for ils in ilses:
            source_path = Path(ils.source.file)
            model.ilses.append(replace(
                ils,
                source=SourceRef(
                    source_path.relative_to(model.root).as_posix(), ils.source.row,
                    ils.source.page, ils.source.sha256,
                ),
            ))
        for vor in vors:
            source_path = Path(vor.source.file)
            model.ad219_vors.append(replace(
                vor,
                source=SourceRef(
                    source_path.relative_to(model.root).as_posix(), vor.source.row,
                    vor.source.page, vor.source.sha256,
                ),
            ))


def _load_terminal_coordinate_pages(model: NavModel, pdf_cache: Path | None = None) -> None:
    """Load coordinate-page evidence without treating it as structured NAIP data.

    Coordinate pages are indexed in each airport's Charts.csv.  A page is
    rejected explicitly when its printed identifier and coordinate columns
    cannot be paired one-for-one; an empty result is never silently skipped.
    """
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        charts = extract_airport_coordinate_pages(airport_directory) if pdf_cache is None else extract_airport_coordinate_pages(airport_directory, pdf_cache)
        if not charts:
            continue
        points = [point for chart in charts for point in chart.fix_coordinates if point.ident]
        if not points:
            model.rejected_records.append(RejectedRecord(
                "terminal-coordinate-page", airport_directory.name.upper(),
                "coordinate-page identifier and coordinate columns could not be paired",
                SourceRef(str(airport_directory.relative_to(model.root))),
            ))
            continue
        for chart in charts:
            for sequence, point in enumerate(chart.fix_coordinates, start=1):
                if not point.ident:
                    continue
                key = f"{chart.airport}:{chart.filename}:{chart.page}:{sequence}:{point.ident}"
                model.terminal_waypoints.append(TerminalWaypoint(
                    key, chart.airport, point.ident, point.latitude, point.longitude,
                    SourceRef((airport_directory / chart.filename).relative_to(model.root).as_posix(), chart.page, chart.page, chart.source.sha256), chart.airport[:2],
                ))


def _promote_shared_terminal_coordinate_waypoints(model: NavModel) -> None:
    """Promote only unambiguous cross-airport coordinate-page waypoints.

    A terminal coordinate catalogue is not normally an enroute source.  It can
    establish a global point only when the same untouched identifier and
    coordinate are independently published by at least two airports in the
    same region.  Existing global waypoint or navaid identities always take
    precedence.
    """
    grouped: dict[tuple[str, str], list[TerminalWaypoint]] = {}
    for point in model.terminal_waypoints:
        country = (point.country or point.airport[:2]).strip().upper()[:2]
        ident = point.ident.strip().upper()
        grouped.setdefault((country, ident), []).append(point)

    existing_identities = {
        ((point.country or "").strip().upper()[:2], point.ident.strip().upper())
        for point in model.waypoints
    }
    existing_identities.update(
        (navaid.country.strip().upper()[:2], navaid.ident.strip().upper())
        for navaid in model.navaids
    )
    rejections: Counter[str] = Counter()
    promoted: list[Waypoint] = []
    for (country, normalized_ident), candidates in sorted(grouped.items()):
        raw_idents = {point.ident.strip() for point in candidates}
        if not normalized_ident:
            rejections["empty_identifier"] += 1
            continue
        if len(raw_idents) != 1:
            rejections["identifier_variants"] += 1
            continue
        ident = next(iter(raw_idents))
        if len(ident) > 8:
            rejections["identifier_too_long"] += 1
            continue
        coordinates = {
            (round(point.latitude, 6), round(point.longitude, 6))
            for point in candidates
        }
        if len(coordinates) != 1:
            rejections["multiple_coordinates"] += 1
            continue
        if len({point.airport.upper() for point in candidates}) < 2:
            rejections["single_airport"] += 1
            continue
        if (country, normalized_ident) in existing_identities:
            rejections["existing_global_identity"] += 1
            continue
        representative = min(
            candidates,
            key=lambda point: (point.airport.upper(), point.key),
        )
        promoted.append(Waypoint(
            key=f"terminal-coordinate:{country}:{normalized_ident}",
            ident=ident,
            name=ident,
            latitude=representative.latitude,
            longitude=representative.longitude,
            source=representative.source,
            country=country,
        ))
        existing_identities.add((country, normalized_ident))

    model.waypoints.extend(promoted)
    model.terminal_coordinate_waypoint_promotion = {
        "source": "Terminal/*/Charts.csv coordinate pages",
        "coordinate_points": len(model.terminal_waypoints),
        "identity_groups": len(grouped),
        "promoted": len(promoted),
        "rejected": {
            "empty_identifier": rejections["empty_identifier"],
            "identifier_variants": rejections["identifier_variants"],
            "identifier_too_long": rejections["identifier_too_long"],
            "multiple_coordinates": rejections["multiple_coordinates"],
            "single_airport": rejections["single_airport"],
            "existing_global_identity": rejections["existing_global_identity"],
        },
    }


def _load_terminal_database_charts(model: NavModel, pdf_cache: Path | None = None) -> None:
    """Retain database-coding leg evidence for later Fenix procedure mapping."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        extractor = extract_airport_database_charts
        model.procedure_charts.extend(extractor(airport_directory) if pdf_cache is None else extractor(airport_directory, pdf_cache))


def _retain_database_referenced_terminal_waypoints(model: NavModel) -> None:
    """Keep coordinate-page points only when structured procedure evidence uses them.

    A coordinate page is an airport-wide catalogue, not a procedure sequence.
    Database-coded legs, holding fixes, and fully printed standard SID/STAR
    route-table entries establish an explicit source sequence.  Other chart
    labels, including IAP role and vector evidence, remain insufficient because
    they do not establish a complete procedure route.
    """
    used = {
        (chart.airport, identifier)
        for chart in model.procedure_charts
        for leg in chart.terminal_legs
        for identifier in (leg.fix_ident, leg.center_ident)
        if identifier
    }
    used.update((holding.fix_region, holding.fix_ident) for holding in model.holdings)
    used.update(
        (chart.airport, identifier)
        for chart in model.procedure_charts
        if chart.chart_type == "standard-terminal-procedure"
        for route in chart.standard_routes + chart.table_standard_routes
        for identifier in route.fixes
        if identifier
    )
    model.terminal_waypoints[:] = [
        point for point in model.terminal_waypoints
        if (point.airport, point.ident) in used
    ]


def _build_database_procedure_segments(model: NavModel) -> None:
    """Group consecutive database-coded rows without inventing route geometry."""
    model.procedure_segments.clear()
    for chart in model.procedure_charts:
        if chart.chart_type != "terminal-database-coding":
            continue
        active_key: tuple[str, str, str, str, str] | None = None
        active_legs = []

        def flush() -> None:
            if active_key is None or not active_legs:
                return
            label, kind, runway, transition, approach_family = active_key
            model.procedure_segments.append(ProcedureSegment(
                chart.airport,
                label,
                kind,
                runway,
                transition,
                tuple(active_legs),
                chart.source,
                approach_family=approach_family,
            ))

        for leg in chart.terminal_legs:
            key = (
                leg.procedure_label,
                leg.procedure_kind,
                leg.runway,
                leg.transition,
                leg.approach_family,
            )
            if active_key is not None and key != active_key:
                flush()
                active_legs.clear()
            active_key = key
            active_legs.append(leg)
        flush()

    _replace_standard_p_arrivals(model)


def _build_database_holdings(model: NavModel) -> None:
    """Build airport holdings only when their printed fix has a 424 coordinate."""
    model.holdings.clear()
    terminal_points: dict[tuple[str, str], list[TerminalWaypoint]] = {}
    global_points: dict[str, list[Waypoint]] = {}
    navaids: dict[str, list[Navaid]] = {}
    for point in model.terminal_waypoints:
        terminal_points.setdefault((point.airport, point.ident), []).append(point)
    for point in model.waypoints:
        global_points.setdefault(point.ident, []).append(point)
    for navaid in model.navaids:
        navaids.setdefault(navaid.ident, []).append(navaid)

    def source_point(points):
        by_coordinate = {
            (round(point.latitude, 6), round(point.longitude, 6)): point
            for point in points
        }
        return next(iter(by_coordinate.values())) if len(by_coordinate) == 1 else None

    terminal_keys = {
        (point.airport, point.ident, round(point.latitude, 6), round(point.longitude, 6))
        for point in model.terminal_waypoints
    }
    seen: set[tuple[object, ...]] = set()
    for chart in model.procedure_charts:
        if chart.chart_type != "terminal-database-coding":
            continue
        for evidence in chart.holding_evidence:
            airport = chart.airport.upper()
            point = source_point(terminal_points.get((airport, evidence.fix_ident), []))
            if point is None:
                point = source_point(global_points.get(evidence.fix_ident, []))
            if point is None:
                point = source_point(navaids.get(evidence.fix_ident, []))
            if point is None:
                model.rejected_records.append(RejectedRecord(
                    "holding",
                    f"{airport}:{evidence.fix_ident}",
                    "holding fix has no unambiguous 424 source coordinate",
                    chart.source,
                ))
                continue
            latitude, longitude = round(point.latitude, 6), round(point.longitude, 6)
            point_key = (airport, evidence.fix_ident, latitude, longitude)
            if point_key not in terminal_keys:
                terminal_point = TerminalWaypoint(
                    key=f"holding:{airport}:{evidence.fix_ident}:{latitude:.6f}:{longitude:.6f}",
                    airport=airport,
                    ident=evidence.fix_ident,
                    latitude=point.latitude,
                    longitude=point.longitude,
                    source=point.source,
                    country=getattr(point, "country", "") or airport[:2],
                )
                model.terminal_waypoints.append(terminal_point)
                terminal_points.setdefault((airport, evidence.fix_ident), []).append(terminal_point)
                terminal_keys.add(point_key)
            identity = (
                airport,
                evidence.fix_ident,
                latitude,
                longitude,
                evidence.inbound_course,
                evidence.turn_direction,
                evidence.time_minutes,
                evidence.minimum_altitude_meters,
                evidence.speed_limit_knots,
            )
            if identity in seen:
                continue
            seen.add(identity)
            model.holdings.append(Holding(
                name=evidence.fix_ident,
                fix_ident=evidence.fix_ident,
                fix_region=airport,
                latitude=point.latitude,
                longitude=point.longitude,
                inbound_course=evidence.inbound_course,
                turn_direction=evidence.turn_direction,
                length_nm=None,
                time_minutes=evidence.time_minutes,
                minimum_altitude_ft=(
                    _feet(str(evidence.minimum_altitude_meters))
                    if evidence.minimum_altitude_meters is not None
                    else None
                ),
                maximum_altitude_ft=None,
                speed_limit_knots=evidence.speed_limit_knots,
                source=chart.source,
            ))


def _source_route_templates(
    model: NavModel,
    airport: str,
    runway: str | None,
    fixes: tuple[str, ...],
    kind: str | None = None,
) -> list[tuple[ProcedureSegment, tuple]]:
    """Return complete, source-coded arrival subpaths matching one printed route."""
    templates = []
    for template in model.procedure_segments:
        if (
            template.airport != airport
            or (runway is not None and template.runway != runway)
            or (kind is not None and template.kind != kind)
        ):
            continue
        template_fixes = [leg.fix_ident for leg in template.legs if leg.fix_ident]
        for start in range(len(template_fixes) - len(fixes) + 1):
            if tuple(template_fixes[start:start + len(fixes)]) != fixes:
                continue
            selected = []
            seen = 0
            for leg in template.legs:
                if leg.fix_ident:
                    if start <= seen < start + len(fixes):
                        selected.append(leg)
                    seen += 1
            if len(selected) == len(fixes):
                templates.append((template, tuple(selected)))
    return templates


def _replace_standard_p_arrivals(model: NavModel) -> None:
    """Replace a uniquely identified P-route's merged coding-table tail.

    The standard arrival plate prints the Fenix navigation-data code and its
    complete route.  Its coding-table counterpart carries the ARINC leg types,
    but can concatenate two chart branches under one source label.  A rewrite
    is admitted only when the plate route, version conversion and a complete
    source leg-template all resolve uniquely within one airport.
    """
    replacement_route_entries = [
        (chart.airport, chart.runways, route)
        for chart in model.procedure_charts
        if chart.chart_type == "standard-terminal-procedure"
        for route in chart.standard_routes
    ]
    addition_route_entries = [
        (chart.airport, chart.runways, route)
        for chart in model.procedure_charts
        if chart.chart_type == "standard-terminal-procedure"
        for route in chart.standard_routes + chart.table_standard_routes
    ]
    replacements: dict[int, ProcedureSegment] = {}
    for index, segment in enumerate(model.procedure_segments):
        if segment.kind != "进场":
            continue
        fixed_legs = [leg for leg in segment.legs if leg.fix_ident]
        if not fixed_legs:
            continue
        version = re.search(r"-(?P<number>\d{1,2})(?P<letter>[A-Z]{1,2})$", segment.label)
        if version is None:
            continue
        first_fix = fixed_legs[0].fix_ident
        expected_version = f"{version['letter']}{version['number']}"
        candidates = [
            route for airport, runways, route in replacement_route_entries
            if airport == segment.airport
            and segment.runway in runways
            and route.procedure_label == f"{first_fix}-{expected_version}"
            and route.fixes[0] == first_fix
        ]
        if len(candidates) != 1:
            continue
        route = candidates[0]
        templates = _source_route_templates(model, segment.airport, None, route.fixes)
        distinct_templates = {
            tuple(
                (leg.leg_type, leg.fix_ident, leg.center_ident, leg.course_degrees, leg.altitude_meters, leg.turn_direction, leg.speed_limit_knots)
                for leg in selected
            )
            for _, selected in templates
        }
        if len(distinct_templates) != 1:
            continue
        _, selected = templates[0]
        legs = tuple(replace(
            leg, procedure_label=route.navigation_code, runway=segment.runway, procedure_kind=segment.kind,
        ) for leg in selected)
        replacements[index] = ProcedureSegment(
            segment.airport, route.navigation_code, segment.kind, segment.runway, segment.transition, legs, segment.source,
            route.navigation_code,
        )
    for index, replacement in replacements.items():
        model.procedure_segments[index] = replacement

    existing = {
        (segment.airport, segment.fenix_name or segment.label, segment.runway)
        for segment in model.procedure_segments
    }
    additions = []
    for airport, runways, route in addition_route_entries:
        if not route.procedure_label.startswith("P") or not route.navigation_code.startswith("P"):
            continue
        for runway in runways:
            identity = (airport, route.navigation_code, runway)
            if identity in existing:
                continue
            templates = _source_route_templates(model, airport, runway, route.fixes, kind="进场")
            distinct_templates = {
                tuple(
                    (leg.leg_type, leg.fix_ident, leg.center_ident, leg.course_degrees, leg.altitude_meters, leg.turn_direction, leg.speed_limit_knots)
                    for leg in selected
                )
                for _, selected in templates
            }
            if len(distinct_templates) != 1:
                continue
            template, selected = templates[0]
            legs = tuple(replace(
                leg, procedure_label=route.navigation_code, runway=runway, procedure_kind="进场",
            ) for leg in selected)
            additions.append(ProcedureSegment(
                airport, route.navigation_code, "进场", runway, template.transition, legs, template.source,
                route.navigation_code,
            ))
            existing.add(identity)
    model.procedure_segments.extend(additions)


def _load_terminal_approach_charts(model: NavModel, pdf_cache: Path | None = None) -> None:
    """Retain instrument-approach index pages before leg decoding exists."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        extractor = extract_airport_approach_charts
        model.procedure_charts.extend(extractor(airport_directory) if pdf_cache is None else extractor(airport_directory, pdf_cache))


def _source_page_key(source: SourceRef) -> tuple[str, int | None, str | None]:
    """Compare a database-code page without treating row positions as identity."""
    return source.file, source.page, source.sha256


def _project_same_page_rnp_primary_to_ils(model: NavModel) -> None:
    """Project a strictly shared RNP primary into an explicit ILS missed group.

    Some 2608 database coding pages print one RNP main approach followed by a
    distinct RNP ILS/DME missed section.  The ILS group has no main section,
    but its indexed ILS plate and the same database page establish that the
    RNP primary is shared.  This is deliberately narrower than generic shared
    IAP section assignment: it never carries a RNP missed section to ILS.
    """
    groups: dict[tuple[str, str, str], list[ProcedureSegment]] = {}
    for segment in model.procedure_segments:
        if iap_section_kind(segment) in {"approach_transition", "approach", "missed"}:
            groups.setdefault(
                (segment.airport, segment.label, segment.runway), [],
            ).append(segment)

    additions: list[ProcedureSegment] = []
    projections: list[dict[str, object]] = []
    for (airport, ils_label, runway), ils_sections in sorted(groups.items()):
        if not _ILS_APPROACH_LABEL.fullmatch(ils_label):
            continue
        if not ils_sections or any(
            iap_section_kind(segment) != "missed"
            or segment.approach_family.upper() != "ILS"
            for segment in ils_sections
        ):
            continue

        source_pages = {_source_page_key(segment.source) for segment in ils_sections}
        if len(source_pages) != 1:
            continue
        rnp_label = "R" + ils_label[1:]
        rnp_candidates = [
            segment
            for segment in groups.get((airport, rnp_label, runway), [])
            if (
                iap_section_kind(segment) == "approach"
                # The Rxx database label is the source identity for a plain
                # RNP primary. Some coding-table headings omit that repeated
                # family text, while RNP AR remains explicit and excluded.
                and segment.approach_family.upper() in {"", "RNP"}
                and _source_page_key(segment.source) in source_pages
            )
        ]
        if len(rnp_candidates) != 1:
            continue
        rnp_primary = rnp_candidates[0]

        matching_ils_charts = [
            chart
            for chart in model.procedure_charts
            if (
                chart.airport == airport
                and chart.chart_type == "instrument-approach-index"
                and runway in chart.runways
                and ils_label
                in approach_procedure_name_candidates(
                    chart.chart_name, chart.runways, chart.airport,
                )
            )
        ]
        shared_primary_charts = [
            chart
            for chart in matching_ils_charts
            if rnp_label in approach_procedure_name_candidates(
                chart.chart_name,
                chart.runways,
                chart.airport,
            )
        ]
        # A plain ILS variant plate can share the Ixx identity but cannot
        # establish that this Rxx primary is also the ILS primary. The combined
        # source title must explicitly resolve to both database identities.
        if len(shared_primary_charts) != 1:
            continue
        chart = shared_primary_charts[0]
        legs = tuple(
            replace(
                leg,
                procedure_label=ils_label,
                procedure_kind=rnp_primary.kind,
                runway=runway,
                approach_family="ILS",
            )
            for leg in rnp_primary.legs
        )
        if not legs:
            continue
        additions.append(ProcedureSegment(
            airport,
            ils_label,
            rnp_primary.kind,
            runway,
            rnp_primary.transition,
            legs,
            rnp_primary.source,
            rnp_primary.fenix_name,
            "ILS",
        ))
        projections.append({
            "airport": airport,
            "label": ils_label,
            "runway": runway,
            "selection": "same_database_page_unique_rnp_primary",
            "rnp_label": rnp_primary.label,
            "rnp_approach_family": (
                rnp_primary.approach_family or "implicit_rnp_label"
            ),
            "primary_legs": len(legs),
            "database_source": {
                "file": rnp_primary.source.file,
                "row": rnp_primary.source.row,
                "page": rnp_primary.source.page,
                "sha256": rnp_primary.source.sha256,
            },
            "ils_missed_source": {
                "file": ils_sections[0].source.file,
                "row": ils_sections[0].source.row,
                "page": ils_sections[0].source.page,
                "sha256": ils_sections[0].source.sha256,
            },
            "chart_name": chart.chart_name,
            "chart_source": {
                "file": chart.source.file,
                "row": chart.source.row,
                "page": chart.source.page,
                "sha256": chart.source.sha256,
            },
        })
    model.procedure_segments.extend(additions)
    model.shared_ils_primary_projections.extend(projections)


def _load_terminal_standard_procedure_charts(model: NavModel, pdf_cache: Path | None = None) -> None:
    """Retain SID/STAR chart text as source waypoint-label evidence."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        extractor = extract_airport_standard_procedure_charts
        model.procedure_charts.extend(extractor(airport_directory) if pdf_cache is None else extractor(airport_directory, pdf_cache))


def _reject_unparsed_charts(model: NavModel) -> None:
    model.iap_coverage = analyze_iap_coverage(model)
    unresolved = model.iap_coverage.get("unresolved_groups", [])
    if isinstance(unresolved, list) and unresolved:
        reasons = {
            "no_unique_primary": "没有唯一的主进近数据库编码段",
            "empty_primary": "主进近数据库编码段没有腿",
            "no_matching_chart": "没有匹配的仪表进近图页",
            "ambiguous_chart": "匹配多个仪表进近图页且无法由 MAP/MAPT 唯一消歧",
        }
        for item in unresolved:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            if not isinstance(source, dict):
                source = {}
            model.rejected_procedures.append(RejectedProcedure(
                str(item.get("airport") or ""),
                str(item.get("label") or ""),
                reasons.get(
                    str(item.get("status") or ""),
                    "IAP 来源证据尚未达到唯一投影条件",
                ),
                SourceRef(
                    str(source.get("file") or ""),
                    source.get("row") if isinstance(source.get("row"), int) else None,
                    source.get("page") if isinstance(source.get("page"), int) else None,
                    str(source.get("sha256")) if source.get("sha256") else None,
                ),
            ))
        return

    # Small fixtures may contain only Charts.csv and no database-coded
    # segments. Preserve their page-level rejection behavior for regression
    # coverage; full 2608 data uses the group-level audit above.
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for index in sorted(terminal.glob("*/Charts.csv")):
        airport = index.parent.name
        for row_number, row in enumerate(_rows(index), start=2):
            chart = row.get("ChartName") or f"第{row_number}行"
            # Database, standard-procedure, and coordinate pages each have an
            # explicit source-evidence path.  Only indexed instrument
            # approach pages remain outside the current leg decoder.
            if (
                "数据库编码" in chart
                or "航路点坐标" in chart
                or _is_standard_procedure_index_row(row)
            ):
                continue
            if not _is_instrument_approach_index_row(row):
                continue
            model.rejected_procedures.append(RejectedProcedure(
                airport,
                chart,
                "没有对应的数据库编码主进近段",
                SourceRef(str(index.relative_to(model.root)), row_number),
            ))
