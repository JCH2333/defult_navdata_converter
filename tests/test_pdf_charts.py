from fenix_default_navdata.pdf_charts import extract_positioned_coordinate_page_points


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
