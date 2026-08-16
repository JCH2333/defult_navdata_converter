from __future__ import annotations

import hashlib
import json
import os
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
from .baseline import NavaidDiff
from .default_navaids import DefaultNavaidSelection, select_default_navaids
from .iap_ocr_consensus import load_iap_ocr_role_evidence
from .model import NavModel
from .official_index import (
    OfficialIndexError,
    load_verified_official_navaid_index,
)
from .profile import Cycle
from .region_resolution import (
    OFFICIAL_REGION_TOLERANCE_NM,
    OfficialRegionResolution,
    RegionResolutionError,
    restore_regions_from_official_index,
)
from .source import load_naip, summarize_airway_source_metadata


BASE_PACKAGE = "navigraph-nav-base"
JEPP_PACKAGE = "navigraph-nav-jepp"
NAV_PACKAGE = "zzz-pmdg-china-navdata"
AIRPORT_PACKAGE = "zzz-pmdg-china-navdata-airport-patch"
_TARGET_MINIMUM_GAME_VERSION = "1.7.35"
_TARGET_MINIMUM_COMPATIBILITY_VERSION = "7.26.0.214"


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


def _normalize_package_tool_manifest(package_root: Path) -> None:
    """Restore the 2608R1 package compatibility contract after SDK compilation."""
    path = package_root / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Package Tool manifest is not an object: {path}")
    payload["minimum_game_version"] = _TARGET_MINIMUM_GAME_VERSION
    payload["minimum_compatibility_version"] = _TARGET_MINIMUM_COMPATIBILITY_VERSION
    _write_json(path, payload)


def _manifest(name: str, title: str, dependencies: list[dict[str, str]], size: int = 0) -> dict[str, object]:
    return {
        "dependencies": dependencies,
        "content_type": "SCENERY",
        "title": title,
        "manufacturer": "User NavData",
        "creator": "PMDG DFD v2 converter",
        "package_version": "0.1.0",
        "minimum_game_version": _TARGET_MINIMUM_GAME_VERSION,
        "minimum_compatibility_version": _TARGET_MINIMUM_COMPATIBILITY_VERSION,
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
    selected_navaids: tuple = (),
) -> dict[str, object]:
    work = package_root.parent / "_work" / "sdk-projects" / package_root.name
    work.mkdir(parents=True, exist_ok=True)
    input_dir = work / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    xml_paths: list[Path] = []
    projections = []
    if include_enroute:
        xml_path = input_dir / "00_enroute.xml"
        projections.append(write_bglcomp_xml(
            model,
            cycle,
            xml_path,
            scope="enroute",
            selected_navaids=selected_navaids,
        ))
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
            selected_navaids=selected_navaids,
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
        _normalize_package_tool_manifest(package_root)
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
    raw_root: Path,
    nav_base: Path,
    nav_jepp: Path,
    output: Path,
    cycle: Cycle,
    compiler: CompilerInfo,
    reference: Path | None = None,
    pdf_cache: Path | None = None,
    general_doc_cache: Path | None = None,
    general_doc_key_point_cache_directory: str = "enr-4.4",
    general_doc_airway_cache_directories: tuple[str, ...] = (),
    iap_ocr_cache_roots: tuple[Path, ...] = (),
    baseline_db: Path | None = None,
    baseline_tolerance_nm: float = 0.25,
) -> dict[str, object]:
    """复制全球官方基线并用 424 原始数据生成中国覆盖层候选。

    失败时仍保留完整来源报告和 XML 投影，绝不会把参考成品偷偷复制为输出。
    """
    if output.exists():
        raise FileExistsError(f"候选目录已存在: {output}")
    if pdf_cache is None:
        cache_root = Path(os.environ.get("LOCALAPPDATA", str(output.parent)))
        pdf_cache = cache_root / "default_navdata_converter" / f"pdf-evidence-cache-{cycle.number}r{cycle.revision}"
    pdf_cache = pdf_cache.resolve()
    iap_ocr_role_evidence = (
        load_iap_ocr_role_evidence(
            raw_root,
            iap_ocr_cache_roots,
            pdf_cache=pdf_cache,
        )
        if iap_ocr_cache_roots
        else None
    )
    output.mkdir(parents=True)
    _copy_tree(nav_base, output / BASE_PACKAGE)
    _copy_tree(nav_jepp, output / JEPP_PACKAGE)
    work = output / "_work"
    work.mkdir(exist_ok=True)
    model = load_naip(
        raw_root,
        pdf_cache=pdf_cache,
        general_doc_cache=general_doc_cache,
        general_doc_key_point_cache_directory=general_doc_key_point_cache_directory,
        general_doc_airway_cache_directories=general_doc_airway_cache_directories,
        iap_ocr_role_evidence=iap_ocr_role_evidence,
        include_terminal_documents=True,
    )
    navaid_diff: NavaidDiff | None = None
    navaid_selection: DefaultNavaidSelection | None = None
    region_resolution: OfficialRegionResolution | None = None
    selected_navaids: tuple = ()
    baseline_error: str | None = None
    region_resolution_report: dict[str, object] = {
        "verified": False,
        "reason": "未提供经过来源校验的官方 VOR/NDB/航点索引 SQLite",
        "coordinate_tolerance_nm": OFFICIAL_REGION_TOLERANCE_NM,
    }
    baseline_report: dict[str, object] = {
        "verified": False,
        "database": str(baseline_db) if baseline_db else None,
        "reason": "未提供经过来源校验的官方设施索引 SQLite",
    }
    navaid_selection_report: dict[str, object] = {
        "navaid_selection_verified": False,
        "reason": "未提供经过来源校验的官方设施索引 SQLite",
        "selected_missing": 0,
    }
    if baseline_db is not None:
        try:
            official_index = load_verified_official_navaid_index(
                baseline_db,
                nav_base=nav_base,
                nav_jepp=nav_jepp,
            )
            region_resolution = restore_regions_from_official_index(
                model,
                official_index,
                coordinate_tolerance_nm=OFFICIAL_REGION_TOLERANCE_NM,
            )
            baseline_index = official_index.baseline
            navaid_selection = select_default_navaids(
                model.navaids,
                baseline_index,
                coordinate_tolerance_nm=baseline_tolerance_nm,
            )
            navaid_diff = navaid_selection.strict_diff
            baseline_report = official_index.to_report()
            region_resolution_report = region_resolution.to_report()
            navaid_selection_report = navaid_selection.to_report()
            if navaid_selection.navaid_selection_verified:
                selected_navaids = navaid_selection.selected_navaids
        except (OfficialIndexError, RegionResolutionError, ValueError) as error:
            baseline_error = str(error)
            baseline_report = {
                "verified": False,
                "database": str(baseline_db),
                "reason": baseline_error,
            }
            region_resolution_report = {
                "verified": False,
                "reason": baseline_error,
                "coordinate_tolerance_nm": OFFICIAL_REGION_TOLERANCE_NM,
            }
            navaid_selection_report = {
                "navaid_selection_verified": False,
                "reason": baseline_error,
                "selected_missing": 0,
            }
    report: dict[str, object] = {
        "status": "candidate",
        "deployable": False,
        "test_build": True,
        "local_contract_verified": False,
        "airac": cycle.number,
        "revision": cycle.revision,
        "compiler": {"path": str(compiler.path) if compiler.path else None, "kind": compiler.kind, "reason": compiler.reason},
        "source": {"raw_424": str(raw_root)},
        "pdf_cache": str(pdf_cache),
        "general_doc_cache": str(general_doc_cache) if general_doc_cache else None,
        "general_doc_key_point_cache_directory": general_doc_key_point_cache_directory,
        "general_doc_airway_cache_directories": list(general_doc_airway_cache_directories),
        "official_baseline": {
            "base": str(nav_base),
            "jepp": str(nav_jepp),
            "navaid_index": str(baseline_db) if baseline_db else None,
            "navaid_index_verification": baseline_report,
        },
        "reference": str(reference) if reference else None,
        "model": {
            "airports": len(model.airports),
            "runways": len(model.runways),
            "navaids": len(model.navaids),
            "ad219_vor_evidence": len(model.ad219_vors),
            "selected_navaids": len(selected_navaids),
            "waypoints": len(model.waypoints),
            "source_fir_region_resolution": model.source_fir_region_resolution,
            "general_document_evidence": model.general_document_evidence,
            "airway_legs": len(model.airway_legs),
            "procedure_segments": len(model.procedure_segments),
            "ilses": len(model.ilses),
            "terminal_waypoints": len(model.terminal_waypoints),
            "holdings": len(model.holdings),
            "rejected_records": len(model.rejected_records),
            "rejected_procedures": len(model.rejected_procedures),
            "iap_ocr_evidence": (
                iap_ocr_role_evidence.report
                if iap_ocr_role_evidence is not None
                else {
                    "accepted": False,
                    "reason": "未提供三份以上 IAP OCR 共识缓存",
                }
            ),
        },
        "airway_source": summarize_airway_source_metadata(model),
        "terminal_navaid_evidence": {
            "ad219_vor_dme_records": len(model.ad219_vors),
            "ad219_vor_dme_projected": 0,
            "ad219_vor_dme_reason": (
                "AD 2.19 VOR/DME 表没有可验证的设施磁差；"
                "r52 语义差分证明其 DME 高程不能映射为默认 BGL 的 Vor/Dme.alt"
            ),
        },
        "iap_coverage": model.iap_coverage,
        "packages": {},
        "byte_equal_reference": False,
        "flight_validation": {
            "verified": False,
            "reason": "尚未完成 ZBCF、ZUNZ、ZUUU 的实机验证及退出稳定性验证",
        },
        "navaid_diff": (
            navaid_diff.to_report()
            if navaid_diff is not None
            else {
                "navaid_diff_verified": False,
                "reason": baseline_error or "未提供经过来源校验的官方设施索引 SQLite",
                "raw_count": len(model.navaids),
                "selected_missing": 0,
            }
        ),
        "navaid_selection": navaid_selection_report,
        "official_region_resolution": region_resolution_report,
        "limitations": [
            "没有合法的 BglComp.exe 时不能生成可加载的区域 BGL。",
            "默认 BGL 的字节级一致还需要相同版本的设施编译器、记录排序、索引和打包时间戳。",
        ],
    }
    projection = write_bglcomp_xml(
        model,
        cycle,
        work / "china-navdata.xml",
        selected_navaids=selected_navaids,
    )
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
                    selected_navaids=selected_navaids,
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
    navaid_diff_verified = bool(
        isinstance(report.get("navaid_diff"), dict)
        and report["navaid_diff"].get("navaid_diff_verified")
    )
    navaid_selection_verified = bool(
        isinstance(report.get("navaid_selection"), dict)
        and report["navaid_selection"].get("navaid_selection_verified")
    )
    index_verified = bool(baseline_report.get("verified"))
    region_resolution_verified = bool(region_resolution_report.get("verified"))
    report["local_contract_verified"] = (
        index_verified
        and navaid_diff_verified
        and navaid_selection_verified
        and region_resolution_verified
        and all(
        (output / name / "bglIndex.bout").is_file()
        and bool(list((output / name).rglob("*.bgl")))
        for name in (NAV_PACKAGE, AIRPORT_PACKAGE)
        )
    )
    # 每次 build 都是测试构建。是否可部署只能由后续的参考字节比对和实机
    # 验证共同决定，不能因为本地包结构完整就放开 Community 覆盖。
    report["deployable"] = False
    _write_json(output / "conversion-report.json", report)
    return report
