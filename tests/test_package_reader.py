from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from fenix_default_navdata.package_reader import PackageReaderError, read_package


def _write_package(root: Path) -> Path:
    package = root / "zzz-reader-fixture"
    scenery = package / "scenery" / "reader-fixture"
    scenery.mkdir(parents=True)
    (package / "manifest.json").write_text('{"content_type":"SCENERY"}\n', encoding="utf-8")
    (package / "layout.json").write_text('{"content":[]}\n', encoding="utf-8")
    (package / "bglIndex.bout").write_bytes(b"index")
    (scenery / "00_enroute.bgl").write_bytes(b"enroute")
    (scenery / "ZB_airports.bgl").write_bytes(b"airports")
    return package


def _write_reader_database(path: Path, *, bgl_rows: int, vor_rows: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE bgl_file (bgl_file_id INTEGER PRIMARY KEY, filepath TEXT NOT NULL)"
        )
        connection.execute("CREATE TABLE vor (vor_id INTEGER PRIMARY KEY, ident TEXT)")
        connection.executemany(
            "INSERT INTO bgl_file(bgl_file_id, filepath) VALUES (?, ?)",
            ((index, f"source-{index}.bgl") for index in range(1, bgl_rows + 1)),
        )
        connection.executemany(
            "INSERT INTO vor(vor_id, ident) VALUES (?, ?)",
            ((index, f"V{index}") for index in range(1, vor_rows + 1)),
        )
        connection.commit()
    finally:
        connection.close()


def test_reads_complete_package_from_ascii_stage_and_preserves_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path)
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "candidate.sqlite"
    commands: list[list[str]] = []
    stage_roots: list[Path] = []

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        commands.append(command)
        root = Path(command[command.index("-b") + 1])
        stage_roots.append(root)
        config = Path(command[command.index("-c") + 1])
        staged = root / "Community" / package.name
        assert str(root).isascii()
        assert staged.joinpath("manifest.json").read_bytes() == package.joinpath("manifest.json").read_bytes()
        assert staged.joinpath("layout.json").read_bytes() == package.joinpath("layout.json").read_bytes()
        assert staged.joinpath("bglIndex.bout").read_bytes() == package.joinpath("bglIndex.bout").read_bytes()
        assert staged.joinpath("scenery", "reader-fixture", "00_enroute.bgl").read_bytes() == b"enroute"
        assert staged.joinpath("scenery", "reader-fixture", "ZB_airports.bgl").read_bytes() == b"airports"
        assert "IncludeFilenames=00_enroute.bgl" in config.read_text(encoding="utf-8")
        _write_reader_database(
            Path(command[command.index("-o") + 1]).with_stem("package-reader_BROKEN"),
            bgl_rows=1,
            vor_rows=1,
        )
        return subprocess.CompletedProcess(command, 1, "", "base scenery unavailable")

    monkeypatch.setattr("fenix_default_navdata.package_reader._run_reader", fake_reader)

    result = read_package(
        package,
        output,
        reader=reader,
        cache_root=tmp_path / "cache",
        filename_patterns=("00_enroute.bgl",),
    )

    assert output.is_file()
    assert result.database == output.resolve()
    assert result.package["matched_bgl_count"] == 1
    assert result.scan["bgl_file_rows"] == 1
    assert result.scan["target_rows"]["vor"] == 1
    assert result.reader["returncode"] == 1
    assert result.reader["reader_marked_broken"] is True
    assert len(commands) == 1
    assert not stage_roots[0].parent.exists()


def test_rejects_reader_output_without_registered_bgl_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path)
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "candidate.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        _write_reader_database(
            Path(command[command.index("-o") + 1]),
            bgl_rows=0,
            vor_rows=1,
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("fenix_default_navdata.package_reader._run_reader", fake_reader)

    with pytest.raises(PackageReaderError, match="没有登记任何 BGL 来源"):
        read_package(
            package,
            output,
            reader=reader,
            cache_root=tmp_path / "cache",
        )

    assert not output.exists()
