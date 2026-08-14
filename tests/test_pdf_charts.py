from fenix_default_navdata.pdf_charts import (
    extract_ad219_vors,
    extract_positioned_coordinate_page_points,
    extract_terminal_holding_evidence,
    extract_terminal_leg_evidence,
)
from fenix_default_navdata.model import SourceRef


def test_ad219_vor_evidence_keeps_direct_facts_without_a_magnetic_variation() -> None:
    evidence = extract_ad219_vors(
        """
        VOR/DME CZW 111.2 MHz CH49X
        N361635.6 E1130750.8
        距19跑道入口 013 MAG/2000m 942 m
        NDB SQ 398 kHz
        """,
        "ZBCZ",
        SourceRef("Terminal/ZBCZ/airport.pdf", 14, 14, "hash"),
    )

    assert len(evidence) == 1
    vor = evidence[0]
    assert (
        vor.airport,
        vor.ident,
        vor.frequency_mhz,
        round(vor.latitude, 6),
        round(vor.longitude, 6),
        vor.dme_elevation_meters,
        vor.source,
    ) == (
        "ZBCZ",
        "CZW",
        111.2,
        36.276556,
        113.130778,
        942.0,
        SourceRef("Terminal/ZBCZ/airport.pdf", 14, 14, "hash"),
    )


def test_ad219_vor_evidence_does_not_treat_position_distance_as_elevation() -> None:
    evidence = extract_ad219_vors(
        """
        VOR/DME HOK 116.0 MHz CH107X
        N311925.5 E1142545.0
        距 ARP 337 MAG/122982m
        NDB SQ 398 kHz
        """,
        "ZHEC",
        SourceRef("Terminal/ZHEC/airport.pdf", 19, 19, "hash"),
    )

    assert evidence[0].dme_elevation_meters is None


def test_positioned_coordinate_pages_allow_baseline_drift_without_cross_column_pairing():
    points = extract_positioned_coordinate_page_points([
        (27.4, 588.5, 52.5, 596.0, "BL723", 76, 1, 0),
        (61.1, 592.3, 169.4, 599.9, 'N44 53 29.6"E082 19 47.7"', 66, 0, 0),
        (153.4, 246.7, 172.9, 252.8, "HA364", 41, 0, 0),
        (178.7, 246.7, 266.9, 252.8, 'N28 24 14.1"E113 12 37.3"', 128, 0, 0),
        (299.7, 246.7, 363.8, 252.8, 'N28 13.2"E113 13.1"', 158, 0, 0),
    ])

    assert [
        (point.ident, round(point.latitude, 6), round(point.longitude, 6))
        for point in points
    ] == [
        ("HA364", 28.403917, 113.210361),
        ("BL723", 44.891556, 82.329917),
    ]


def test_database_holding_titles_keep_time_and_do_not_become_procedure_legs():
    text = """
    RWY01/18L/18R/19/36L/36R 离场等待（出航时间：1.5min）
    HM IGMOR Y 109 L 6000 RNAV1
    HM BOTPU Y 281 R 6000 RNAV1
    RWY01/36L/36R 进场等待（出航时间：1min）
    HM AA168 Y 099 R 4500 RNAV1
    RWY01 进近过渡 AA141
    IF AA141 1500 MAX210 RNAV1
    """

    holdings = extract_terminal_holding_evidence(text)

    assert [
        (
            holding.fix_ident,
            holding.runways,
            holding.inbound_course,
            holding.turn_direction,
            holding.time_minutes,
            holding.minimum_altitude_meters,
        )
        for holding in holdings
    ] == [
        ("IGMOR", ("01", "18L", "18R", "19", "36L", "36R"), 109, "L", 1.5, 6000),
        ("BOTPU", ("01", "18L", "18R", "19", "36L", "36R"), 281, "R", 1.5, 6000),
        ("AA168", ("01", "36L", "36R"), 99, "R", 1, 4500),
    ]
    assert [
        (leg.procedure_label, leg.procedure_kind, leg.leg_type, leg.fix_ident)
        for leg in extract_terminal_leg_evidence(text)
    ] == [("R01", "进近过渡", "IF", "AA141")]


def test_unnamed_runway_transition_does_not_become_numeric_procedure_label():
    text = """
    RWY33/34L/34R 跑道过渡
    IF SZ161 RNP1
    TF NLG 1500 MAX205 RNP1
    RWY15/16L/16R/33/34L/34R 进场 SAREX3
    IF SAREX RNP1
    TF SZ405 RNP1
    """

    legs = extract_terminal_leg_evidence(text)

    assert [(leg.procedure_label, leg.procedure_kind, leg.runway, leg.fix_ident) for leg in legs] == [
        ("SAREX-3", "进场", "15", "SAREX"),
        ("SAREX-3", "进场", "15", "SZ405"),
        ("SAREX-3", "进场", "16L", "SAREX"),
        ("SAREX-3", "进场", "16L", "SZ405"),
        ("SAREX-3", "进场", "16R", "SAREX"),
        ("SAREX-3", "进场", "16R", "SZ405"),
        ("SAREX-3", "进场", "33", "SAREX"),
        ("SAREX-3", "进场", "33", "SZ405"),
        ("SAREX-3", "进场", "34L", "SAREX"),
        ("SAREX-3", "进场", "34L", "SZ405"),
        ("SAREX-3", "进场", "34R", "SAREX"),
        ("SAREX-3", "进场", "34R", "SZ405"),
    ]
