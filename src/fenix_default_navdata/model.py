from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


CN_PREFIXES = ("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY")


def is_china_icao(icao: str) -> bool:
    return (icao or "").upper()[:2] in CN_PREFIXES


@dataclass(frozen=True)
class SourceRef:
    file: str
    row: int | None = None
    page: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class Airport:
    key: str
    icao: str
    name: str
    latitude: float
    longitude: float
    elevation_ft: int
    transition_altitude: int
    transition_level: int
    source: SourceRef
    name_source: SourceRef | None = None


@dataclass(frozen=True)
class Runway:
    key: str
    airport_key: str
    ident: str
    true_heading: float
    length_ft: int
    width_ft: int
    surface: str
    elevation_ft: int
    source: SourceRef
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class Navaid:
    key: str
    ident: str
    kind: str
    name: str
    latitude: float
    longitude: float
    frequency: float
    magnetic_variation: float
    elevation_ft: int
    country: str
    source: SourceRef
    terminal: bool = False
    # Keep the 424 selection flags on the neutral record.  Target adapters may
    # interpret them differently, but must not need to reopen raw CSV files.
    code_in_airway: str = ""
    purpose: str = ""
    is_rep_atc: str = ""
    route_restrict: str = ""
    is_trans_point: str = ""
    is_border_point: str = ""
    serviced_airport: str = ""
    code_fir: str = ""


@dataclass(frozen=True)
class Ils:
    """A source-backed localizer/GP/DME record from an AD 2.19 PDF page."""

    airport: str
    runway: str
    ident: str
    frequency_mhz: float
    category: str | None
    localizer_latitude: float
    localizer_longitude: float
    localizer_course_magnetic: float | None
    glide_slope_degrees: float | None
    crossing_height_meters: float | None
    glide_slope_latitude: float | None
    glide_slope_longitude: float | None
    dme_latitude: float | None
    dme_longitude: float | None
    dme_elevation_meters: float | None
    source: SourceRef


@dataclass(frozen=True)
class Ad219Vor:
    """A VOR/DME fact explicitly printed in an airport AD 2.19 table.

    This evidence intentionally has no magnetic variation.  It must remain
    separate from ``Navaid`` until the current 424 source proves that field.
    """

    airport: str
    ident: str
    frequency_mhz: float
    latitude: float
    longitude: float
    dme_elevation_meters: float | None
    source: SourceRef


@dataclass(frozen=True)
class Ad219NdbEvidence:
    """An NDB fact explicitly printed in an airport AD 2.19 table.

    The table does not establish the display name, magnetic variation,
    elevation, or target region required for a default BGL NDB.  It remains
    OCR audit evidence until direct 424 records prove those fields.
    """

    airport: str
    ident: str
    frequency_khz: float
    latitude: float
    longitude: float
    source: SourceRef


@dataclass(frozen=True)
class EnrouteNavaidEvidence:
    """A GeneralDoc 4.1 fact that lacks the complete target navaid contract.

    The enroute table prints type, ident, frequency, coordinates, and sometimes
    elevation, but does not publish magnetic variation or regional identity.
    It remains audit evidence until direct 424 records prove all target fields.
    """

    kind: str
    ident: str
    frequency: float
    latitude: float
    longitude: float
    elevation_meters: float | None
    source: SourceRef


@dataclass(frozen=True)
class Waypoint:
    key: str
    ident: str
    name: str
    latitude: float
    longitude: float
    source: SourceRef
    country: str = ""


@dataclass(frozen=True)
class TerminalWaypoint:
    """A terminal waypoint printed on an indexed coordinate-page PDF.

    This stays separate from structured designated points until the Fenix
    adapter has resolved physical identity and its deterministic ID phase.
    """

    key: str
    airport: str
    ident: str
    latitude: float
    longitude: float
    source: SourceRef
    country: str = ""


@dataclass(frozen=True)
class AirwayLeg:
    airway: str
    sequence: int
    start_ident: str
    end_ident: str
    source: SourceRef
    direction: str = ""
    start_latitude: float | None = None
    start_longitude: float | None = None
    end_latitude: float | None = None
    end_longitude: float | None = None
    start_country: str = ""
    end_country: str = ""
    route_type: str = ""
    level: str = ""
    start_type: str = ""
    end_type: str = ""
    minimum_altitude_ft: int | None = None
    # ``route_type`` is a target-adapter hint.  It must not be populated from
    # the source PBN value in RTE_SEG.CODE_TYPE because the two vocabularies
    # have different meanings.
    source_code_type: str = ""
    source_airspace_remark: str = ""
    source_segment_rnp_designator: str = ""
    source_enroute_location_type: str = ""
    source_segment_minimum_crossing_altitude: str = ""
    source_route_minimum_crossing_altitude: str = ""
    source_rte_seg_id: str = ""
    source_segment_id: str = ""
    source_en_route_rte_id: str = ""
    source_segment_found: bool = False
    source_en_route_rte_found: bool = False


@dataclass(frozen=True)
class EnrouteAirwayMinimumAltitudeEvidence:
    """One printed enroute-table minimum altitude tied to adjacent fixes."""

    airway: str
    start_ident: str
    end_ident: str
    minimum_altitude_meters: int
    source: SourceRef


@dataclass(frozen=True)
class RejectedProcedure:
    airport: str
    chart: str
    reason: str
    source: SourceRef


@dataclass(frozen=True)
class RejectedRecord:
    kind: str
    key: str
    reason: str
    source: SourceRef


@dataclass(frozen=True)
class ProcedureChart:
    airport: str
    filename: str
    page: int
    chart_type: str
    chart_name: str
    text_sha256: str
    procedure_labels: tuple[str, ...]
    runways: tuple[str, ...]
    waypoints: tuple[str, ...]
    terminal_legs: tuple["ChartTerminalLeg", ...]
    fix_coordinates: tuple["ChartFixCoordinate", ...]
    source: SourceRef
    route_fixes: tuple["ChartRouteFix", ...] = ()
    standard_routes: tuple["ChartStandardProcedureRoute", ...] = ()
    table_standard_routes: tuple["ChartStandardProcedureRoute", ...] = ()
    has_missed_approach: bool = False
    holding_evidence: tuple["ChartHoldingEvidence", ...] = ()


@dataclass(frozen=True)
class ChartFixCoordinate:
    """A coordinate observed in a chart text layer, not an inferred procedure leg."""

    ident: str | None
    latitude: float
    longitude: float
    raw: str


@dataclass(frozen=True)
class ChartTerminalLeg:
    procedure_label: str
    runway: str
    leg_type: str
    fix_ident: str | None
    raw: str
    procedure_kind: str = ""
    course_degrees: float | None = None
    altitude_meters: float | None = None
    turn_direction: str | None = None
    speed_limit_knots: int | None = None
    transition: str = ""
    center_ident: str | None = None
    sequence: int = 0
    fix_region: str = ""
    fix_type: str = ""
    fix_latitude: float | None = None
    fix_longitude: float | None = None
    fly_over: bool = False
    recommended_ident: str | None = None
    recommended_region: str = ""
    recommended_type: str = ""
    recommended_latitude: float | None = None
    recommended_longitude: float | None = None
    theta_degrees: float | None = None
    rho_nm: float | None = None
    distance_nm: float | None = None
    altitude_descriptor: str | None = None
    altitude1_ft: int | None = None
    altitude2_ft: int | None = None
    vertical_angle: float | None = None
    center_region: str = ""
    center_latitude: float | None = None
    center_longitude: float | None = None
    arc_radius_nm: float | None = None
    waypoint_description_code: str = ""
    speed_limit_descriptor: str | None = None
    # Direct database-table headings can identify RNP, RNP AR, or ILS.
    approach_family: str = ""


@dataclass(frozen=True)
class ChartHoldingEvidence:
    """One explicitly coded holding pattern from a terminal database page."""

    kind: str
    runways: tuple[str, ...]
    fix_ident: str
    inbound_course: float | None
    turn_direction: str
    time_minutes: float | None
    minimum_altitude_meters: float | None
    speed_limit_knots: int | None
    raw: str


@dataclass(frozen=True)
class Holding:
    name: str
    fix_ident: str
    fix_region: str
    latitude: float
    longitude: float
    inbound_course: float | None
    turn_direction: str
    length_nm: float | None
    time_minutes: float | None
    minimum_altitude_ft: int | None
    maximum_altitude_ft: int | None
    speed_limit_knots: int | None
    source: SourceRef


@dataclass(frozen=True)
class ChartRouteFix:
    """A fix explicitly paired with a printed approach-route role."""

    ident: str
    role: str


IapOcrCandidateKey = tuple[str, str, str, str, str]


@dataclass(frozen=True)
class IapOcrRoleEvidence:
    """Role pairs accepted only after independent source-PDF OCR consensus."""

    candidate_roles: dict[IapOcrCandidateKey, frozenset[tuple[str, str]]]
    report: dict[str, object]

    def roles_for(self, key: IapOcrCandidateKey) -> dict[str, set[str]]:
        roles: dict[str, set[str]] = {}
        for ident, role in self.candidate_roles.get(key, frozenset()):
            roles.setdefault(ident, set()).add(role)
        return roles


@dataclass(frozen=True)
class ChartStandardProcedureRoute:
    """One printed standard-procedure route-table entry."""

    procedure_label: str
    navigation_code: str
    fixes: tuple[str, ...]


@dataclass(frozen=True)
class ProcedureSegment:
    """One ordered, source-backed terminal procedure segment."""

    airport: str
    label: str
    kind: str
    runway: str
    transition: str
    legs: tuple[ChartTerminalLeg, ...]
    source: SourceRef
    # Only a standard-procedure route table may set this printed Fenix code.
    fenix_name: str | None = None
    # Preserved from the direct database-table heading, never inferred from Rxx.
    approach_family: str = ""


@dataclass
class NavModel:
    root: Path
    airports: dict[str, Airport] = field(default_factory=dict)
    runways: list[Runway] = field(default_factory=list)
    navaids: list[Navaid] = field(default_factory=list)
    ilses: list[Ils] = field(default_factory=list)
    ad219_vors: list[Ad219Vor] = field(default_factory=list)
    enroute_navaid_evidence: list[EnrouteNavaidEvidence] = field(default_factory=list)
    enroute_airway_minimum_altitude_evidence: list[EnrouteAirwayMinimumAltitudeEvidence] = field(default_factory=list)
    waypoints: list[Waypoint] = field(default_factory=list)
    terminal_waypoints: list[TerminalWaypoint] = field(default_factory=list)
    airway_legs: list[AirwayLeg] = field(default_factory=list)
    rejected_records: list[RejectedRecord] = field(default_factory=list)
    rejected_procedures: list[RejectedProcedure] = field(default_factory=list)
    procedure_charts: list[ProcedureChart] = field(default_factory=list)
    procedure_segments: list[ProcedureSegment] = field(default_factory=list)
    holdings: list[Holding] = field(default_factory=list)
    # Audit-only summary of source-backed IAP coverage.  Target adapters must
    # not treat role evidence as proof that every chart leg was decoded.
    iap_coverage: dict[str, object] = field(default_factory=dict)
    # Optional source-PDF OCR role evidence accepted through independent cache
    # consensus. It can only distinguish an existing matching IAP chart page.
    iap_ocr_role_evidence: IapOcrRoleEvidence | None = None
    # Audit-only result of recovering blank designated-point regions from
    # source FIR boundary geometry.  Empty means the optional FIR tables were
    # unavailable to the source loader.
    source_fir_region_resolution: dict[str, object] = field(default_factory=dict)
    # Audit-only result of recovering blank designated-point regions from
    # uniquely mapped source FIR/ACC remarks on connected airway segments.
    source_acc_region_resolution: dict[str, object] = field(default_factory=dict)
    # Audit-only record of terminal coordinate-page points promoted to global
    # waypoints through a source-only shared-identity rule.
    terminal_coordinate_waypoint_promotion: dict[str, object] = field(
        default_factory=dict,
    )
    # Audit-only status of GeneralDoc OCR evidence used for enroute additions.
    # The source loader records every rejection instead of silently guessing.
    general_document_evidence: dict[str, object] = field(default_factory=dict)
