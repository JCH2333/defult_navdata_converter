from pathlib import Path

from fenix_default_navdata.model import NavModel
from fenix_default_navdata.source import _reject_unparsed_charts


def test_reject_unparsed_charts_excludes_source_evidence_pages(tmp_path: Path):
    terminal = tmp_path / "Terminal" / "ZBCF"
    terminal.mkdir(parents=True)
    (terminal / "Charts.csv").write_text(
        "PAGE_NUMBER,ChartTypeEx_CH,ChartName\n"
        "0W-1,标准仪表离场图,航路点坐标\n"
        "3P-01,标准仪表离场图,RNAV RWY03(FIX01)\n"
        "5L-01,仪表进近图_ILS,ILS/DME RWY03\n"
        "0C-01,仪表进近图,数据库编码\n",
        encoding="utf-8",
    )

    model = NavModel(tmp_path)
    _reject_unparsed_charts(model)

    assert [(item.airport, item.chart) for item in model.rejected_procedures] == [
        ("ZBCF", "ILS/DME RWY03"),
    ]
