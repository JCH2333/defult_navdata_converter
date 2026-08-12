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
        "creator": "PMDG DFD v2 converter",
        "package_version": "0.1.0",
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
    include_enroute: bool,
    duplicate_terminal_waypoints: bool,
    dependencies: list[dict[str, str]],
    package_order_hint: str,
    title: str,
) -> dict[str, object]:
    work = package_root.parent / "_work" / "sdk-projects" / package_root.name
    work.mkdir(parents=True, exist_ok=True)
    input_dir = work / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    xml_paths: list[Path] = []
    projections = []
    if include_enroute:
        xml_path = input_dir / "00_enroute.xml"
        projections.append(write_bglcomp_xml(model, cycle, xml_path, scope="enroute"))
        xml_paths.append(xml_path)
    for prefix in airport_prefixes:
        xml_path = input_dir / f"{prefix}_airports.xml"
        projections.append(write_bglcomp_xml(
            model,
            cycle,
            xml_path,
            scope="airports",
            airport_prefix=prefix,
            duplicate_terminal_waypoints=duplicate_terminal_waypoints,
        ))
        xml_paths.append(xml_path)
    if compiler.kind == "PackageTool":
        project_path = write_package_project(
            work,
            package_name=package_root.name,
            title=title,
            output_dir=f"scenery\\{package_name}",
            source_xmls=tuple(xml_paths),
            package_order_hint=package_order_hint,
            dependencies=tuple(dependencies),
        )
        compile_report = compile_package(
            project_path,
            compiler,
            package_name=package_root.name,
        )
        built_root = Path(str(compile_report["package_root"]))
        shutil.copytree(built_root, package_root, dirs_exist_ok=True)
    else:
        compile_reports = []
        for xml_path in xml_paths:
            bgl_path = (
                package_root / "scenery" / package_name / f"{xml_path.stem}.bgl"
            )
            compile_reports.append(compile_bgl(xml_path, compiler, bgl_path))
        _write_package_metadata(package_root, package_root.name, f"China NavData AIRAC {cycle.number}", dependencies)
        compile_report = {
            "kind": compiler.kind,
            "reports": compile_reports,
            "bgls": [
                str(package_root / "scenery" / package_name / f"{path.stem}.bgl")
                for path in xml_paths
            ],
        }
    return {
        "projections": [
            {**projection.__dict__, "path": str(projection.path)}
            for projection in projections
        ],
        "compile": compile_report,
        "prefixes": airport_prefixes,
    }


def build_candidate(
    *,
    fenix_db: Path,
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
    from .fenix_source import load_fenix_model

    model = load_fenix_model(fenix_db, raw_root, cycle)
    report: dict[str, object] = {
        "status": "candidate",
        "deployable": False,
        "test_build": True,
        "airac": cycle.number,
        "revision": cycle.revision,
        "compiler": {"path": str(compiler.path) if compiler.path else None, "kind": compiler.kind, "reason": compiler.reason},
        "source": {"fenix": str(fenix_db), "raw_424": str(raw_root)},
        "official_baseline": {"base": str(nav_base), "jepp": str(nav_jepp)},
        "reference": str(reference) if reference else None,
        "model": {
            "airports": len(model.airports),
            "runways": len(model.runways),
            "navaids": len(model.navaids),
            "waypoints": len(model.waypoints),
            "airway_legs": len(model.airway_legs),
            "procedure_segments": len(model.procedure_segments),
            "ilses": len(model.ilses),
            "terminal_waypoints": len(model.terminal_waypoints),
            "holdings": len(model.holdings),
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
        prefixes = ("ZB", "ZG", "ZH", "ZJ", "ZL", "ZP", "ZS", "ZU", "ZW", "ZY")
        package_specs = (
            (
                NAV_PACKAGE,
                "pmdg-china-navdata",
                "China NavData AIRAC 2608",
                True,
                True,
                [
                    {"name": BASE_PACKAGE, "package_version": "0.1.0"},
                    {"name": JEPP_PACKAGE, "package_version": "2.26.16"},
                ],
                "CUSTOM_NAVDATA_PATCH",
            ),
            (
                AIRPORT_PACKAGE,
                "pmdg-china-airport-patch",
                "China NavData AIRAC 2608 Airport Procedure Patch",
                False,
                False,
                [{"name": NAV_PACKAGE, "package_version": "0.1.0"}],
                "CUSTOM_AIRPORT_PATCH",
            ),
        )
        for (
            output_name,
            package_name,
            title,
            include_enroute,
            duplicate_terminal_waypoints,
            dependencies,
            package_order_hint,
        ) in package_specs:
            package_root = output / output_name
            package_root.mkdir()
            try:
                report["packages"][output_name] = _compile_xml_package(
                    package_root,
                    model,
                    cycle,
                    compiler,
                    package_name=package_name,
                    airport_prefixes=prefixes,
                    include_enroute=include_enroute,
                    duplicate_terminal_waypoints=duplicate_terminal_waypoints,
                    dependencies=dependencies,
                    package_order_hint=package_order_hint,
                    title=title,
                )
            except CompilerUnavailable as error:
                report["packages"][output_name] = {
                    "status": "blocked",
                    "reason": str(error),
                }
            except Exception as error:
                report["packages"][output_name] = {
                    "status": "failed",
                    "reason": str(error),
                }
    report["deployable"] = all(
        (output / name / "bglIndex.bout").is_file()
        and bool(list((output / name).rglob("*.bgl")))
        for name in (NAV_PACKAGE, AIRPORT_PACKAGE)
    )
    _write_json(output / "conversion-report.json", report)
    return report
