import json
from pathlib import Path

from fenix_default_navdata.package import BASE_PACKAGE, JEPP_PACKAGE
from fenix_default_navdata.validation import validate_candidate


def test_candidate_requires_both_official_baselines(tmp_path: Path):
    (tmp_path / BASE_PACKAGE).mkdir()
    (tmp_path / JEPP_PACKAGE).mkdir()
    (tmp_path / "conversion-report.json").write_text(json.dumps({"deployable": False}), encoding="utf-8")
    result = validate_candidate(tmp_path)
    assert result["official_baseline_present"] is True
    assert result["valid"] is False
    assert result["deployable"] is False
