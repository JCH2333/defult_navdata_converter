from pathlib import Path

from fenix_default_navdata.navaid_region_source_audit import audit_navaid_region_sources


def test_navaid_region_source_audit_classifies_conflicts(tmp_path: Path) -> None:
    (tmp_path / "AIRSPACE.csv").write_text(
        "AIRSPACE_ID,CODE_TYPE,CODE_ID\n", encoding="utf-8"
    )
    (tmp_path / "AIRSPACE_BORDER_VERTEX.csv").write_text(
        "VERTEX_ID,AIRSPACE_ID,NO_SEQ,GEO_LAT,GEO_LONG\n", encoding="utf-8"
    )
    header = (
        "SIGNIFICANT_POINT_ID,CODE_ID,GEO_LAT_ACCURACY,GEO_LONG_ACCURACY,"
        "SERVICED_AIRPORT,CODE_FIR\n"
    )
    (tmp_path / "VOR.csv").write_text(
        header
        + "vor-1,TEST,N400000,E1160000,ZBES,沈阳情报区\n"
        + "vor-2,OK,N400000,E1160000,ZBES,北京情报区\n",
        encoding="utf-8",
    )
    (tmp_path / "NDB.csv").write_text(header + "ndb-1,ND,N400000,E1160000,,北京情报区\n", encoding="utf-8")

    report = audit_navaid_region_sources(tmp_path)

    assert report["diagnostic"] == "navaid-region-source-audit-v1"
    assert report["read_only"] is True
    assert report["tables"]["VOR.csv"]["categories"]["airport_vs_fir_conflict"] == 1
    assert report["tables"]["VOR.csv"]["conflicts"][0]["fir_regions"] == ["ZY"]
