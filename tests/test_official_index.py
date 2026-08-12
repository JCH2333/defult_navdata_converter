from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from fenix_default_navdata.official_index import (
    BASE_PACKAGE,
    JEPP_PACKAGE,
    OfficialIndexError,
    build_official_navaid_index,
    load_verified_official_navaid_index,
    metadata_path_for,
)


def _write_package(root: Path, name: str, bgl_name: str) -> Path:
    package = root / name
    scenery_root = (
        package / "scenery" / "fs-base" / "scenery" / "0000"
        if name == BASE_PACKAGE
        else package / "scenery" / "fs-base-jep" / "scenery" / "0000"
    )
    scenery_root.mkdir(parents=True)
    (package / "manifest.json").write_text('{"name": "' + name + '"}\n', encoding="utf-8")
    (package / "layout.json").write_text('{"content": []}\n', encoding="utf-8")
    (package / "bglIndex.bout").write_bytes(b"index")
    (scenery_root / bgl_name).write_bytes(b"bgl-" + name.encode("ascii"))
    return package


def _write_reader_index(output: Path, base_bgl: Path, jepp_bgl: Path) -> None:
    connection = sqlite3.connect(output)
    connection.executescript(
        """
        CREATE TABLE bgl_file (
            bgl_file_id INTEGER PRIMARY KEY,
            filepath TEXT NOT NULL
        );
        CREATE TABLE vor (
            vor_id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            ident TEXT,
            region TEXT,
            frequency INTEGER,
            mag_var REAL,
            altitude INTEGER,
            lonx REAL,
            laty REAL,
            name TEXT
        );
        CREATE TABLE ndb (
            ndb_id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            ident TEXT,
            region TEXT,
            frequency INTEGER,
            mag_var REAL,
            altitude INTEGER,
            lonx REAL,
            laty REAL,
            name TEXT
        );
        CREATE TABLE waypoint (
            waypoint_id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            ident TEXT,
            region TEXT,
            lonx REAL,
            laty REAL
        );
        """
    )
    connection.executemany(
        "INSERT INTO bgl_file(bgl_file_id, filepath) VALUES (?, ?)",
        ((1, str(base_bgl)), (2, str(jepp_bgl)), (3, str(base_bgl))),
    )
    connection.execute(
        """
        INSERT INTO vor(file_id, ident, region, frequency, mag_var, altitude, lonx, laty, name)
        VALUES (1, 'BASE', 'ZB', 112300, 0.0, 100, 105.0, 35.0, 'BASE')
        """
    )
    connection.execute(
        """
        INSERT INTO ndb(file_id, ident, region, frequency, mag_var, altitude, lonx, laty, name)
        VALUES (2, 'JEPP', 'ZB', 44500, 0.0, 100, 106.0, 36.0, 'JEPP')
        """
    )
    connection.execute(
        """
        INSERT INTO waypoint(file_id, ident, region, lonx, laty)
        VALUES (3, 'POINT', 'ZB', 105.5, 35.5)
        """
    )
    connection.commit()
    connection.close()


def _reader_command_value(command: list[str], flag: str) -> Path:
    return Path(command[command.index(flag) + 1])


def _staged_bgl(root: Path, package_name: str, bgl_name: str) -> Path:
    mirror_name = (
        "official-core-reader-probe"
        if package_name == BASE_PACKAGE
        else "official-jepp-reader-probe"
    )
    return root / "Community" / mirror_name / "scenery" / mirror_name / "0000" / bgl_name


def test_builds_ascii_staged_verified_index_and_reuses_it(tmp_path: Path, monkeypatch):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"
    commands: list[list[str]] = []
    stage_roots: list[Path] = []

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        commands.append(command)
        assert command[1:3] == ["-f", "MSFS"]
        root = _reader_command_value(command, "-b")
        database = _reader_command_value(command, "-o")
        config = _reader_command_value(command, "-c")
        stage_roots.append(root)
        assert str(root).isascii()
        assert root.parent.name.startswith("official-index-stage-")
        assert config.is_file()
        assert "IncludeBglObjectFilter=VOR,NDB,WAYPOINT,AIRWAY" in config.read_text(
            encoding="utf-8"
        )
        assert not (root / "Community" / BASE_PACKAGE).exists()
        assert not (root / "Community" / JEPP_PACKAGE).exists()
        base_bgl = _staged_bgl(root, BASE_PACKAGE, "NVX00000.bgl")
        jepp_bgl = _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl")
        assert base_bgl.read_bytes() == b"bgl-" + BASE_PACKAGE.encode("ascii")
        assert jepp_bgl.read_bytes() == b"bgl-" + JEPP_PACKAGE.encode("ascii")
        _write_reader_index(
            database,
            base_bgl,
            jepp_bgl,
        )
        return subprocess.CompletedProcess(command, 1, "WARN fallback magdec", "")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)

    created = build_official_navaid_index(
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        reader=reader,
        cache_root=tmp_path / "cache",
    )

    assert created.reused is False
    assert created.baseline.counts_by_kind == {"VOR": 1, "NDB": 1}
    assert output.is_file()
    assert metadata_path_for(output).is_file()
    assert len(commands) == 1
    assert not stage_roots[0].parent.exists()
    metadata = json.loads(metadata_path_for(output).read_text(encoding="utf-8"))
    assert metadata["status"] == "verified"
    assert metadata["reader"]["returncode"] == 1
    assert metadata["database"]["waypoint_rows"] == 1
    assert metadata["record_provenance"]["record_counts"][BASE_PACKAGE]["VOR"] == 1
    assert metadata["record_provenance"]["record_counts"][BASE_PACKAGE]["WAYPOINT"] == 1
    assert metadata["record_provenance"]["record_counts"][JEPP_PACKAGE]["NDB"] == 1
    assert [(item.ident, item.region) for item in created.waypoints] == [("POINT", "ZB")]

    reused = build_official_navaid_index(
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        reader=reader,
        cache_root=tmp_path / "cache",
    )

    assert reused.reused is True
    assert len(commands) == 1


def test_verified_index_expires_when_official_package_tree_changes(tmp_path: Path, monkeypatch):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        root = _reader_command_value(command, "-b")
        _write_reader_index(
            _reader_command_value(command, "-o"),
            _staged_bgl(root, BASE_PACKAGE, "NVX00000.bgl"),
            _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl"),
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)
    build_official_navaid_index(
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        reader=reader,
        cache_root=tmp_path / "cache",
    )
    (jepp / "scenery" / "fs-base-jep" / "scenery" / "0000" / "NAX00000.bgl").write_bytes(
        b"new-cycle"
    )

    with pytest.raises(OfficialIndexError, match="文件树已变化"):
        load_verified_official_navaid_index(
            output,
            nav_base=base,
            nav_jepp=jepp,
        )


def test_reader_renamed_broken_sqlite_is_accepted_only_after_full_provenance_check(
    tmp_path: Path,
    monkeypatch,
):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        root = _reader_command_value(command, "-b")
        requested = _reader_command_value(command, "-o")
        renamed = requested.with_stem(f"{requested.stem}_BROKEN")
        _write_reader_index(
            renamed,
            _staged_bgl(root, BASE_PACKAGE, "NVX00000.bgl"),
            _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl"),
        )
        return subprocess.CompletedProcess(command, 1, "", "found errors")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)

    index = build_official_navaid_index(
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        reader=reader,
        cache_root=tmp_path / "cache",
    )

    assert index.baseline.counts_by_kind == {"VOR": 1, "NDB": 1}
    metadata = json.loads(metadata_path_for(output).read_text(encoding="utf-8"))
    assert metadata["reader"]["reader_marked_broken"] is True
    assert metadata["reader"]["produced_database_name"] == "official-navaids_BROKEN.sqlite"
    assert any("BROKEN" in warning for warning in metadata["warnings"])


def test_foreign_bgl_provenance_rejects_index_before_writing_output(tmp_path: Path, monkeypatch):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        root = _reader_command_value(command, "-b")
        _write_reader_index(
            _reader_command_value(command, "-o"),
            tmp_path / "foreign" / "nax.bgl",
            _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl"),
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)

    with pytest.raises(OfficialIndexError, match="不属于暂存官方双包"):
        build_official_navaid_index(
            nav_base=base,
            nav_jepp=jepp,
            output=output,
            reader=reader,
            cache_root=tmp_path / "cache",
        )

    assert not output.exists()
    assert not metadata_path_for(output).exists()


def test_foreign_waypoint_provenance_rejects_index_before_writing_output(tmp_path: Path, monkeypatch):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        root = _reader_command_value(command, "-b")
        database = _reader_command_value(command, "-o")
        _write_reader_index(
            database,
            _staged_bgl(root, BASE_PACKAGE, "NVX00000.bgl"),
            _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl"),
        )
        connection = sqlite3.connect(database)
        connection.execute(
            "UPDATE bgl_file SET filepath = ? WHERE bgl_file_id = 3",
            (str(tmp_path / "foreign" / "waypoint-source.bgl"),),
        )
        connection.commit()
        connection.close()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)

    with pytest.raises(OfficialIndexError, match="不属于暂存官方双包"):
        build_official_navaid_index(
            nav_base=base,
            nav_jepp=jepp,
            output=output,
            reader=reader,
            cache_root=tmp_path / "cache",
        )

    assert not output.exists()
    assert not metadata_path_for(output).exists()


def test_old_sidecar_version_is_explicitly_rejected(tmp_path: Path, monkeypatch):
    base = _write_package(tmp_path, BASE_PACKAGE, "NVX00000.bgl")
    jepp = _write_package(tmp_path, JEPP_PACKAGE, "NAX00000.bgl")
    reader = tmp_path / "navdatareader.exe"
    reader.write_bytes(b"reader-fixture")
    output = tmp_path / "official.sqlite"

    def fake_reader(command: list[str], *, cwd: Path, timeout_seconds: int):
        root = _reader_command_value(command, "-b")
        _write_reader_index(
            _reader_command_value(command, "-o"),
            _staged_bgl(root, BASE_PACKAGE, "NVX00000.bgl"),
            _staged_bgl(root, JEPP_PACKAGE, "NAX00000.bgl"),
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("fenix_default_navdata.official_index._run_reader", fake_reader)
    build_official_navaid_index(
        nav_base=base,
        nav_jepp=jepp,
        output=output,
        reader=reader,
        cache_root=tmp_path / "cache",
    )
    sidecar = metadata_path_for(output)
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["metadata_version"] = 2
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(OfficialIndexError, match="侧车版本不支持"):
        load_verified_official_navaid_index(
            output,
            nav_base=base,
            nav_jepp=jepp,
        )
