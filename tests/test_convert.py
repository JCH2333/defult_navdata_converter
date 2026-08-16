from pathlib import Path

from fenix_default_navdata import convert as convert_module
from fenix_default_navdata.profile import DEFAULT_CYCLE


def test_convert_passes_requested_ocr_cache_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "raw"
    base = tmp_path / "base"
    jepp = tmp_path / "jepp"
    output = tmp_path / "output"
    for path in (raw, base, jepp):
        path.mkdir()
    received: dict[str, object] = {}

    def build_candidate(**kwargs) -> dict[str, object]:
        received.update(kwargs)
        Path(kwargs["output"]).mkdir(parents=True, exist_ok=True)
        return {"status": "test"}

    monkeypatch.setattr(convert_module, "find_compiler", lambda _path: "compiler")
    monkeypatch.setattr(convert_module, "build_candidate", build_candidate)

    report = convert_module.convert(
        raw,
        base,
        jepp,
        output,
        cycle=DEFAULT_CYCLE,
        general_doc_airway_cache_directories=(
            "enr-3.2.4-h-sample-original",
        ),
        iap_ocr_cache_roots=(
            tmp_path / "iap-a",
            tmp_path / "iap-b",
            tmp_path / "iap-c",
        ),
    )

    assert report == {"status": "test"}
    assert received["general_doc_airway_cache_directories"] == (
        "enr-3.2.4-h-sample-original",
    )
    assert received["iap_ocr_cache_roots"] == (
        (tmp_path / "iap-a").resolve(),
        (tmp_path / "iap-b").resolve(),
        (tmp_path / "iap-c").resolve(),
    )
