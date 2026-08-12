from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
FILES = [
    ROOT / "README.md",
    ROOT / "pyproject.toml",
    ROOT / "run_gui.bat",
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    text = (ROOT / "src" / "fenix_default_navdata" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if match is None:
        raise RuntimeError("无法读取版本号")
    version = match.group(1)
    archive_path = OUT / f"default-navdata-converter-v{version}.zip"
    entries = {}
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        sources = sorted((ROOT / "src").rglob("*.py"))
        for path in [*FILES, *sources]:
            data = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            archive.writestr(name, data)
            entries[name] = hashlib.sha256(data).hexdigest()
        manifest = {"version": version, "files": entries}
        archive.writestr("update-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(archive_path)
    print(hashlib.sha256(archive_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
