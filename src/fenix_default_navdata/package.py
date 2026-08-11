from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .bgl import (
    CompilerInfo,
    CompilerUnavailable,
    compile_bgl,
    compile_package,
    write_bglcomp_xml,
    write_package_project,
)
from .model import NavModel
from .profile import Cycle


BASE_PACKAGE = "navigraph-nav-base"
JEPP_PACKAGE = "navigraph-nav-jepp"
NAV_PACKAGE = "zzz-pmdg-china-navdata"
AIRPORT_PACKAGE = "zzz-pmdg-china-navdata-airport-patch"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, target, dirs_exist_ok=True)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _manifest(name: str, title: str, dependencies: list[dict[str, str]], size: int = 0) -> dict[str, object]:
    return {
        "dependencies": dependencies,
        "content_type": "SCENERY",
        "title": title,
        "manufacturer": "User NavData",
        "creator": "Fenix to Default NavData Converter",
        "package_version": "0.1.0-test",
        "minimum_game_version": "1.7.35",
        "minimum_compatibility_version": "7.26.0.214",
        "export_type": "Community",
        "builder": "Microsoft Flight Simulator 2024",
        "package_order_hint": "CUSTOM_NAVDATA_PATCH",
        "release_notes": {"neutral": {"LastUpdate": "", "OlderHistory": ""}},
        "total_package_size": str(size),
    }


def _package_layout(package_root: Path) -> dict[str, object]:
    files = []
    for path in sorted(package_root.rglob("*")):
        if path.is_file() and path.name.lower() not in {"manifest.json", "layout.json"}:
            files.append({
                "path": path.relative_to(package_root).as_posix().lower(),
                "size": path.stat().st_size,
                "date": 0,
            })
    return {"content": files}


def _write_package_metadata(package_root: Path, name: str, title: str, dependencies: list[dict[str, str]]) -> None:
    content_info = package_root / "ContentInfo" / name
    _write_json(content_info / "ContentHistory.json", {"package-name": name, "items": []})
    _write_json(package_root / "manifest.json", _manifest(name, title, dependencies))
    _write_json(package_root / "layout.json", _package_layout(package_root))


def _compile_xml_package(
    package_root: Path,
    model: NavModel,
    cycle: Cycle,
    compiler: CompilerInfo,
    *,
    package_name: str,
    airport_prefixes: tuple[str, ...],
    scope: str,
    dependencies: list[dict[str, str]],
    package_order_hint: str,
) -> dict[str, object]:
    work = package_root.parent / "_work" / "sdk-projects" / package_root.name
    work.mkdir(parents=True, exist_ok=True)
    input_dir = work / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    xml_path = input_dir / "00_enroute.xml"
    projection = write_bglcomp_xml(model, cycle, xml_path, scope=scope)
    if compiler.kind == "PackageTool":
        project_path = write_package_project(
            work,
            package_name=package_root.name,
            title=f"China NavData AIRAC {cycle.number}",
            output_dir=f"scenery\\{package_name}",
            source_xmls=(xml_path,),
            package_order_hint=package_order_hint,
        )
        compile_report = compile_package(
            project_path,
            compiler,
            package_name=package_root.name,
        )
        built_root = Path(str(compile_report["package_root"]))
        shutil.copytree(built_root, package_root, dirs_exist_ok=True)
    else:
        bgl_path = package_root / "scenery" / package_name / "00_enroute.bgl"
        compile_report = compile_bgl(xml_path, compiler, bgl_path)
        _write_package_metadata(package_root, package_root.name, f"China NavData AIRAC {cycle.number}", dependencies)
    return {
        "projection": {**projection.__dict__, "path": str(projection.path)},
        "compile": compile_report,
        "prefixes": airport_prefixes,
    }


def build_candidate(
    *,
    raw_root: Path,
    nav_base: Path,
    nav_jepp: Path,
    output: Path,
    cycle: Cycle,
    compiler: CompilerInfo,
    reference: Path | None = None,
) -> dict[str, object]:
    """复制全球官方基线并生成中国覆盖层候选。

    失败时仍保留完整来源报告和 XML 投影，绝不会把参考成品偷偷复制为输出。
    """
    if output.exists():
        raise FileExistsError(f"候选目录已存在: {output}")
    output.mkdir(parents=True)
    _copy_tree(nav_base, output / BASE_PACKAGE)
    _copy_tree(nav_jepp, output / JEPP_PACKAGE)
    from .source import load_naip

    model = load_naip(raw_root, output / "_work" / "pdf-evidence-cache")
    report: dict[str, object] = {
        "status": "candidate",
        "deployable": False,
        "test_build": True,
        "airac": cycle.number,
        "revision": cycle.revision,
        "compiler": {"path": str(compiler.path) if compiler.path else None, "kind": compiler.kind, "reason": compiler.reason},
        "source": str(raw_root),
        "official_baseline": {"base": str(nav_base), "jepp": str(nav_jepp)},
        "reference": str(reference) if reference else None,
        "model": {
            "airports": len(model.airports),
            "runways": len(model.runways),
            "navaids": len(model.navaids),
            "waypoints": len(model.waypoints),
            "airway_legs": len(model.airway_legs),
            "procedure_segments": len(model.procedure_segments),
            "rejected_records": len(model.rejected_records),
            "rejected_procedures": len(model.rejected_procedures),
        },
        "packages": {},
        "byte_equal_reference": False,
        "limitations": [
            "没有合法的 BglComp.exe 时不能生成可加载的区域 BGL。",
            "默认 BGL 的字节级一致还需要相同版本的设施编译器、记录排序、索引和打包时间戳。",
        ],
    }
    work = output / "_work"
    work.mkdir(exist_ok=True)
    projection = write_bglcomp_xml(model, cycle, work / "china-navdata.xml")
    report["projection"] = {**projection.__dict__, "path": str(projection.path)}
    if compiler.path is None:
        blocked = {"status": "blocked", "reason": compiler.reason}
        report["packages"][NAV_PACKAGE] = blocked
        report["packages"][AIRPORT_PACKAGE] = blocked
    else:
        try:
            nav_root = output / NAV_PACKAGE
            nav_root.mkdir()
            report["packages"][NAV_PACKAGE] = _compile_xml_package(
                nav_root, model, cycle, compiler, package_name="pmdg-china-navdata",
                airport_prefixes=("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"),
                scope="all",
                dependencies=[
                    {"name": BASE_PACKAGE, "package_version": "0.1.0"},
                    {"name": JEPP_PACKAGE, "package_version": "2.26.16"},
                ],
                package_order_hint="CUSTOM_NAVDATA_PATCH",
            )
            airport_root = output / AIRPORT_PACKAGE
            airport_root.mkdir()
            report["packages"][AIRPORT_PACKAGE] = _compile_xml_package(
                airport_root, model, cycle, compiler, package_name="pmdg-china-airport-patch",
                airport_prefixes=("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY"),
                scope="airports",
                dependencies=[{"name": NAV_PACKAGE, "package_version": "0.1.0"}],
                package_order_hint="CUSTOM_AIRPORT_PATCH",
            )
        except CompilerUnavailable as error:
            report["packages"][NAV_PACKAGE] = {"status": "blocked", "reason": str(error)}
            report["packages"][AIRPORT_PACKAGE] = {"status": "blocked", "reason": str(error)}
        except Exception as error:
            report["packages"][NAV_PACKAGE] = {"status": "failed", "reason": str(error)}
            report["packages"][AIRPORT_PACKAGE] = {"status": "failed", "reason": str(error)}
    report["deployable"] = all(
        (output / name / "bglIndex.bout").is_file()
        and bool(list((output / name).rglob("*.bgl")))
        for name in (NAV_PACKAGE, AIRPORT_PACKAGE)
    )
    _write_json(output / "conversion-report.json", report)
    return report
