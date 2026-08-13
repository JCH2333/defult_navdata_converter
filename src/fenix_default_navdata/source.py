from __future__ import annotations

import csv
import hashlib
import math
import re
from dataclasses import replace
from pathlib import Path

from pypinyin import lazy_pinyin
import pymupdf

from .iap_coverage import analyze_iap_coverage
from .model import CN_PREFIXES, Airport, AirwayLeg, Holding, NavModel, Navaid, ProcedureSegment, RejectedProcedure, RejectedRecord, Runway, SourceRef, TerminalWaypoint, Waypoint, is_china_icao
from .pdf_charts import (
    _is_instrument_approach_index_row,
    _is_standard_procedure_index_row,
    extract_airport_ad219_ils,
    extract_airport_approach_charts,
    extract_airport_coordinate_pages,
    extract_airport_database_charts,
    extract_airport_standard_procedure_charts,
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
    airport_prefix = (serviced_airport or "").strip().upper()[:2]
    if airport_prefix in CN_PREFIXES:
        return airport_prefix
    fir_name = (fir or "").split("\uff0c", maxsplit=1)[0].strip()
    try:
        return _FIR_COUNTRIES[fir_name]
    except KeyError as error:
        raise ValueError(f"unmapped navaid FIR: {fir!r}") from error


def waypoint_country(fir: str, latitude: float | None = None, longitude: float | None = None, ident: str = "") -> str:
    """Map a structured designated-point FIR to an MSFS region key."""
    if "\u9999\u6e2f" in (fir or ""):
        return "VH"
    if fir:
        return navaid_country("", fir)
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


def _validate_pdf_cache(root: Path, pdf_cache: Path | None) -> Path | None:
    if pdf_cache is None:
        return None
    resolved_cache = pdf_cache.resolve()
    if resolved_cache.is_relative_to(root):
        raise ValueError("PDF 证据缓存不得写入 NAIP 原始数据目录")
    return resolved_cache


def load_naip(
    root: Path,
    pdf_cache: Path | None = None,
    *,
    include_terminal_documents: bool = True,
) -> NavModel:
    """Load only structured data; PDFs are inspected separately and never guessed."""
    root = root.resolve()
    pdf_cache = _validate_pdf_cache(root, pdf_cache)
    model = NavModel(root=root)
    airway_endpoint_countries: dict[tuple[str, str, float, float], set[str]] = {}
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
    for row_number, row in enumerate(_rows(root / "DESIGNATED_POINT.csv"), start=2):
        try:
            latitude = parse_dms(row.get("GEO_LAT_ACCURACY") or "")
            longitude = parse_dms(row.get("GEO_LONG_ACCURACY") or "")
            ident = row.get("CODE_ID") or ""
            country = (
                waypoint_country(row.get("CODE_FIR") or "", latitude, longitude, ident)
                if (row.get("CODE_FIR") or "").strip() or ident.upper() in _EMPTY_FIR_COUNTRY_OVERRIDES
                else ""
            )
            model.waypoints.append(Waypoint(row["SIGNIFICANT_POINT_ID"], ident, row.get("TXT_NAME") or "",
                latitude, longitude, SourceRef("DESIGNATED_POINT.csv", row_number), country))
            if (row.get("CODE_FIR") or "").strip() or ident.upper() in _EMPTY_FIR_COUNTRY_OVERRIDES:
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
            model.airway_legs.append(AirwayLeg(
                row.get("TXT_DESIG") or "", _number(row.get("VAL_SORT") or "0"),
                start_ident, end_ident, SourceRef("RTE_SEG.csv", row_number), row.get("CODE_DIR") or "",
                start_latitude, start_longitude, end_latitude, end_longitude, start_country, end_country,
                route_type=row.get("CODE_TYPE") or "",
                start_type=row.get("CODE_TYPE_START") or "",
                end_type=row.get("CODE_TYPE_END") or "",
            ))
        except ValueError:
            model.rejected_records.append(RejectedRecord(
                kind="airway-leg", key=row.get("TXT_DESIG") or "", reason="invalid airway endpoint coordinate",
                source=SourceRef("RTE_SEG.csv", row_number),
            ))
    _restore_airway_endpoint_countries(model, airway_endpoint_countries)
    if include_terminal_documents:
        _load_terminal_coordinate_pages(model, pdf_cache)
        _load_terminal_landing_aids(model)
        _load_terminal_database_charts(model, pdf_cache)
        _load_terminal_standard_procedure_charts(model, pdf_cache)
        _build_database_procedure_segments(model)
        _build_database_holdings(model)
        _retain_database_referenced_terminal_waypoints(model)
        _load_terminal_approach_charts(model, pdf_cache)
        _reject_unparsed_charts(model)
    return model


def _load_terminal_landing_aids(model: NavModel) -> None:
    """Retain AD 2.19 landing-aid evidence before any Fenix field projection."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        for ils in extract_airport_ad219_ils(airport_directory):
            source_path = Path(ils.source.file)
            model.ilses.append(replace(
                ils,
                source=SourceRef(
                    source_path.relative_to(model.root).as_posix(), ils.source.row,
                    ils.source.page, ils.source.sha256,
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


def _load_terminal_database_charts(model: NavModel, pdf_cache: Path | None = None) -> None:
    """Retain database-coding leg evidence for later Fenix procedure mapping."""
    terminal = model.root / "Terminal"
    if not terminal.is_dir():
        return
    for airport_directory in sorted(path for path in terminal.iterdir() if path.is_dir()):
        extractor = extract_airport_database_charts
        model.procedure_charts.extend(extractor(airport_directory) if pdf_cache is None else extractor(airport_directory, pdf_cache))


def _retain_database_referenced_terminal_waypoints(model: NavModel) -> None:
    """Keep coordinate-page points only when a database-coded segment uses them.

    A coordinate page is an airport-wide catalogue, not a procedure sequence.
    Restricting it to explicitly printed legs prevents decorative, runway and
    unused catalogue labels from consuming Fenix waypoint IDs.
    """
    used = {
        (chart.airport, identifier)
        for chart in model.procedure_charts
        for leg in chart.terminal_legs
        for identifier in (leg.fix_ident, leg.center_ident)
        if identifier
    }
    used.update((holding.fix_region, holding.fix_ident) for holding in model.holdings)
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
        active_key: tuple[str, str, str, str] | None = None
        active_legs = []

        def flush() -> None:
            if active_key is None or not active_legs:
                return
            label, kind, runway, transition = active_key
            model.procedure_segments.append(ProcedureSegment(
                chart.airport, label, kind, runway, transition, tuple(active_legs), chart.source,
            ))

        for leg in chart.terminal_legs:
            key = (leg.procedure_label, leg.procedure_kind, leg.runway, leg.transition)
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
