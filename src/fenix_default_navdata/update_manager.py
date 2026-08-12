from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from .version import __version__


REPOSITORY = "JCH2333/defult_navdata_converter"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases"


@dataclass(frozen=True)
class Release:
    version: str
    asset_name: str
    url: str
    sha256: str
    size: int


def _version(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.lstrip("v").split("."))


def check_prerelease() -> Release | None:
    request = Request(API_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": "default_navdata_converter"})
    try:
        with urlopen(request, timeout=8) as response:
            releases = json.loads(response.read(2 * 1024 * 1024))
    except Exception:
        return None
    for release in releases:
        if not release.get("prerelease") or release.get("draft"):
            continue
        version = str(release.get("tag_name", "")).lstrip("v")
        try:
            if _version(version) <= _version(__version__):
                continue
        except (ValueError, TypeError):
            continue
        asset_name = f"default-navdata-converter-v{version}.zip"
        asset = next((item for item in release.get("assets", []) if item.get("name") == asset_name), None)
        digest = str((asset or {}).get("digest", ""))
        if asset and digest.startswith("sha256:"):
            return Release(version, asset_name, asset["browser_download_url"], digest[7:], int(asset["size"]))
    return None


def validate_update_package(path: Path, release: Release) -> None:
    if path.stat().st_size != release.size:
        raise RuntimeError("更新包大小不一致")
    if hashlib.sha256(path.read_bytes()).hexdigest() != release.sha256:
        raise RuntimeError("更新包 SHA-256 不一致")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("update-manifest.json"))
        if manifest.get("version") != release.version:
            raise RuntimeError("更新包版本不一致")
