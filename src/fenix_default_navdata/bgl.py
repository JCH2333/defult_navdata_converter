from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .model import NavModel, is_china_icao
from .profile import Cycle


class CompilerUnavailable(RuntimeError):
    """本机没有可调用的合法 BGL 编译器。"""


@dataclass(frozen=True)
class CompilerInfo:
    path: Path | None
    kind: str
    reason: str


@dataclass(frozen=True)
class XmlProjection:
    path: Path
    airports: int
    runways: int
    waypoints: int
    navaids: int
    airway_routes: int
    procedure_segments: int
    rejected_records: int
    rejected_procedures: int


def _simulator_pids() -> set[int]:
    result = subprocess.run(
        [
            "tasklist",
            "/FI",
            "IMAGENAME eq FlightSimulator2024.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        encoding="cp936",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].lower() == "flightsimulator2024.exe":
            try:
                pids.add(int(row[1]))
            except ValueError:
                continue
    return pids


def _wait_for_package_tool_process(
    previous_pids: set[int],
    *,
    start_timeout: int = 45,
    build_timeout: int = 3600,
) -> bool:
    start_deadline = time.monotonic() + start_timeout
    launched: set[int] = set()
    while time.monotonic() < start_deadline:
        launched = _simulator_pids() - previous_pids
        if launched:
            break
        time.sleep(0.5)
    if not launched:
        return False
    build_deadline = time.monotonic() + build_timeout
    while time.monotonic() < build_deadline:
        if not (_simulator_pids() & launched):
            return True
        time.sleep(1)
    raise TimeoutError(f"MSFS Package Tool 构建超过 {build_timeout} 秒")


def find_compiler(explicit: Path | None = None) -> CompilerInfo:
    if explicit:
        path = explicit.expanduser()
        if not path.is_file():
            return CompilerInfo(None, "none", f"指定的编译器不存在: {path}")
        kind = "PackageTool" if path.name.lower() == "fspackagetool.exe" else "BglComp"
        return CompilerInfo(path.resolve(), kind, "found")
    candidates = []
    if os.environ.get("FSPACKAGETOOL"):
        candidates.append((Path(os.environ["FSPACKAGETOOL"]), "PackageTool"))
    if os.environ.get("BGLCOMP"):
        candidates.append((Path(os.environ["BGLCOMP"]), "BglComp"))
    candidates.extend([
        (Path(r"C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe"), "PackageTool"),
        (Path(r"F:\games\MSF tools\MSFS2024_SDK_Core_Installer_1.5.3\SDK\Tools\bin\fspackagetool.exe"), "PackageTool"),
        (Path(r"F:\games\MSF tools\MSFS2024_SDK_Core_Installer_1.5.3\SDK\Tools\bin\BglComp.exe"), "BglComp"),
        (Path(r"F:\SteamLibrary\steamapps\common\MSFS2024\BglComp.exe"), "BglComp"),
        (Path(r"C:\MSFS SDK\Tools\bin\BglComp.exe"), "BglComp"),
    ])
    for path, kind in candidates:
        if path.is_file():
            return CompilerInfo(path.resolve(), kind, "found")
    return CompilerInfo(
        None,
        "none",
        "未找到 MSFS 2024 SDK fspackagetool.exe 或兼容的 BglComp.exe",
    )


def _number_designator(ident: str) -> tuple[str, str]:
    value = re.sub(r"^RWY", "", (ident or "").upper().replace(" ", ""))
    match = re.fullmatch(r"(\d{1,2})([LRC]?)", value)
    if not match:
        raise ValueError(f"无法规范化跑道标识: {ident!r}")
    return match.group(1).zfill(2), match.group(2)


def _float(value: object, digits: int = 6) -> str:
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")


def _attrs(**values: object) -> dict[str, str]:
    return {key: str(value) for key, value in values.items() if value is not None and value != ""}


def _waypoint_type(ident: str) -> str:
    return "NAMED" if ident else "UNNAMED"


def _surface(value: str) -> str:
    return {
        "ASP": "ASPHALT",
        "CON": "CONCRETE",
        "GRE": "GRASS",
        "WAT": "WATER",
        "U": "UNKNOWN",
    }.get((value or "").upper(), "UNKNOWN")


def write_bglcomp_xml(model: NavModel, cycle: Cycle, output: Path, *, scope: str = "all") -> XmlProjection:
    """把统一中间模型投影为官方 XSD 约束下的 BglComp XML。

    XML 是公开 SDK 的输入格式，不等同于 Navigraph 的最终 BGL；最终字节仍由
    版本匹配的官方设施编译器决定。
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root = ET.Element("FSData", {
        "version": "9.0",
        "source": "fenix_to_default_navdata",
    })
    ET.SubElement(root, "AiracCycle", {
        "cycleBegin": cycle.begin,
        "cycleEnd": cycle.end,
        "cycleNumber": cycle.number[-2:],
    })

    airports = [airport for airport in model.airports.values() if is_china_icao(airport.icao)]
    airports.sort(key=lambda item: item.icao)
    airport_keys = {airport.key for airport in airports}
    runways = [runway for runway in model.runways if runway.airport_key in airport_keys]
    runways.sort(key=lambda item: (model.airports[item.airport_key].icao, item.ident, item.key))
    if scope not in {"all", "enroute", "airports"}:
        raise ValueError(f"未知 XML 投影范围: {scope}")
    projected_airports = airports if scope in {"all", "airports"} else []
    projected_runways = runways if scope in {"all", "airports"} else []
    for airport in projected_airports:
        airport_element = ET.SubElement(root, "Airport", _attrs(
            ident=airport.icao,
            name=airport.name[:48],
            region=airport.icao[:2],
            regionCode=airport.icao[:2],
            lat=_float(airport.latitude),
            lon=_float(airport.longitude),
            alt=_float(airport.elevation_ft),
            transitionAltitude=_float(airport.transition_altitude),
            transitionLevel=_float(airport.transition_level),
        ))
        for runway in [item for item in projected_runways if item.airport_key == airport.key]:
            number, designator = _number_designator(runway.ident)
            ET.SubElement(airport_element, "Runway", _attrs(
                lat=_float(airport.latitude),
                lon=_float(airport.longitude),
                alt=_float(runway.elevation_ft),
                surface=_surface(runway.surface),
                heading=_float(runway.true_heading, 3),
                length=_float(runway.length_ft),
                width=_float(runway.width_ft),
                number=number,
                designator=designator,
                primaryTakeoff="TRUE",
                primaryLanding="TRUE",
                secondaryTakeoff="TRUE",
                secondaryLanding="TRUE",
            ))

    points = list(model.waypoints) if scope in {"all", "enroute"} else list(model.terminal_waypoints)
    for leg in model.airway_legs if scope in {"all", "enroute"} else ():
        if leg.start_latitude is not None and leg.start_longitude is not None:
            points.append(type("_Point", (), {
                "ident": leg.start_ident,
                "country": leg.start_country or "CN",
                "latitude": leg.start_latitude,
                "longitude": leg.start_longitude,
                "name": leg.start_ident,
                "key": f"airway-start:{leg.airway}:{leg.sequence}",
            })())
        if leg.end_latitude is not None and leg.end_longitude is not None:
            points.append(type("_Point", (), {
                "ident": leg.end_ident,
                "country": leg.end_country or "CN",
                "latitude": leg.end_latitude,
                "longitude": leg.end_longitude,
                "name": leg.end_ident,
                "key": f"airway-end:{leg.airway}:{leg.sequence}",
            })())
    deduped: dict[tuple[str, int, int], object] = {}
    for point in points:
        key = (str(point.ident).upper(), round(float(point.latitude), 6), round(float(point.longitude), 6))
        deduped.setdefault(key, point)
    ordered_points = sorted(deduped.values(), key=lambda item: (
        str(item.ident).upper(), float(item.latitude), float(item.longitude), str(item.key),
    ))
    for point in ordered_points:
        ET.SubElement(root, "Waypoint", _attrs(
            lat=_float(point.latitude),
            lon=_float(point.longitude),
            waypointType=_waypoint_type(point.ident),
            waypointRegion=(point.country or "CN")[:2],
            waypointIdent=str(point.ident).upper()[:8],
        ))

    navaids = sorted(model.navaids, key=lambda item: (item.kind, item.ident, item.key)) if scope in {"all", "enroute"} else []
    for navaid in navaids:
        if navaid.kind == "VOR":
            ET.SubElement(root, "Vor", _attrs(
                lat=_float(navaid.latitude),
                lon=_float(navaid.longitude),
                alt=_float(navaid.elevation_ft),
                type="HIGH",
                frequency=_float(navaid.frequency, 3),
                magvar=_float(navaid.magnetic_variation, 3),
                region=navaid.country[:2],
                ident=navaid.ident[:8],
                name=navaid.name[:48],
                nav="TRUE",
                dme="TRUE",
            ))
        elif navaid.kind == "NDB":
            ET.SubElement(root, "Ndb", _attrs(
                lat=_float(navaid.latitude),
                lon=_float(navaid.longitude),
                alt=_float(navaid.elevation_ft),
                type="H",
                frequency=_float(navaid.frequency, 1),
                magvar=_float(navaid.magnetic_variation, 3),
                region=navaid.country[:2],
                ident=navaid.ident[:8],
                name=navaid.name[:48],
            ))

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return XmlProjection(
        path=output,
        airports=len(projected_airports),
        runways=len(projected_runways),
        waypoints=len(ordered_points),
        navaids=len(navaids),
        airway_routes=len({leg.airway for leg in model.airway_legs}),
        procedure_segments=len(model.procedure_segments),
        rejected_records=len(model.rejected_records),
        rejected_procedures=len(model.rejected_procedures),
    )


def write_package_project(
    project_root: Path,
    *,
    package_name: str,
    title: str,
    output_dir: str,
    source_xmls: tuple[Path, ...],
    package_order_hint: str,
) -> Path:
    """生成可由 MSFS 2024 Package Tool 构建的最小项目。"""
    project_root.mkdir(parents=True, exist_ok=True)
    source_dir = project_root / "PackageSources" / "NavData"
    definition_dir = project_root / "PackageDefinitions"
    source_dir.mkdir(parents=True, exist_ok=True)
    definition_dir.mkdir(parents=True, exist_ok=True)
    for source in source_xmls:
        shutil.copy2(source, source_dir / source.name)

    package = ET.Element("AssetPackage", {"Version": "0.1.0"})
    ET.SubElement(package, "PackageOrderHint").text = package_order_hint
    settings = ET.SubElement(package, "ItemSettings")
    ET.SubElement(settings, "ContentType").text = "SCENERY"
    ET.SubElement(settings, "Title").text = title
    ET.SubElement(settings, "Manufacturer").text = "User NavData"
    ET.SubElement(settings, "Creator").text = "Fenix to Default NavData Converter"
    flags = ET.SubElement(package, "Flags")
    ET.SubElement(flags, "VisibleInStore").text = "false"
    ET.SubElement(flags, "CanBeReferenced").text = "false"
    groups = ET.SubElement(package, "AssetGroups")
    group = ET.SubElement(groups, "AssetGroup", {"Name": "NavData"})
    ET.SubElement(group, "Type").text = "BGL"
    group_flags = ET.SubElement(group, "Flags")
    ET.SubElement(group_flags, "FSXCompatibility").text = "false"
    ET.SubElement(group, "AssetDir").text = r"PackageSources\NavData"
    ET.SubElement(group, "OutputDir").text = output_dir.replace("/", "\\")
    ET.indent(package, space="\t")
    definition_path = definition_dir / f"{package_name}.xml"
    ET.ElementTree(package).write(definition_path, encoding="utf-8", xml_declaration=True)

    project = ET.Element("Project", {
        "Version": "2",
        "Name": package_name,
        "FolderName": "Packages",
        "MetadataFolderName": "PackagesMetadata",
    })
    ET.SubElement(project, "OutputDirectory").text = "."
    ET.SubElement(project, "TemporaryOutputDirectory").text = "_PackageInt"
    packages = ET.SubElement(project, "Packages")
    ET.SubElement(packages, "Package").text = f"PackageDefinitions\\{package_name}.xml"
    ET.SubElement(project, "PublishingGroups")
    ET.indent(project, space="\t")
    project_path = project_root / f"{package_name}.xml"
    ET.ElementTree(project).write(project_path, encoding="utf-8", xml_declaration=True)
    return project_path


def compile_package(
    project_path: Path,
    compiler: CompilerInfo,
    *,
    package_name: str,
    timeout_seconds: int = 3600,
) -> dict[str, object]:
    if compiler.path is None:
        raise CompilerUnavailable(compiler.reason)
    if compiler.kind != "PackageTool":
        raise CompilerUnavailable(f"编译器 {compiler.path} 不是 MSFS Package Tool")
    stage_parent = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "fenix_default_navdata"
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix="sdk-build-", dir=stage_parent))
    try:
        simulator_pids = _simulator_pids()
        if simulator_pids:
            raise RuntimeError(
                "FlightSimulator2024.exe 正在运行；Package Tool 构建前请完全关闭模拟器"
            )
        shutil.copytree(project_path.parent, stage_root, dirs_exist_ok=True)
        staged_project = stage_root / project_path.name
        command = [
            str(compiler.path),
            str(staged_project),
            "-outputtoseparateconsole",
            "-nopause",
            "-rebuild",
            "-forcesteam",
        ]
        result = subprocess.run(
            command,
            cwd=str(stage_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            _wait_for_package_tool_process(
                simulator_pids,
                build_timeout=timeout_seconds,
            )
        staged_package_root = stage_root / "Packages" / package_name
        required = (
            staged_package_root / "manifest.json",
            staged_package_root / "layout.json",
            staged_package_root / "bglIndex.bout",
        )
        missing = [str(path.relative_to(stage_root)) for path in required if not path.is_file()]
        bgls = sorted(staged_package_root.rglob("*.bgl")) if staged_package_root.is_dir() else []
        if missing or not bgls:
            details = "\n".join(filter(None, (result.stdout, result.stderr)))
            builder_log = (
                Path(os.environ.get("APPDATA", ""))
                / "Microsoft Flight Simulator 2024"
                / "BuilderLogError.txt"
            )
            if builder_log.is_file():
                details = f"{details}\n{builder_log.read_text(encoding='utf-8', errors='replace')[-4000:]}"
            raise RuntimeError(
                "Package Tool 未生成完整导航包；"
                f"包装器退出代码={result.returncode}，缺少={missing}，"
                f"BGL={len(bgls)}，输出={details[-4000:]}"
            )
        package_root = project_path.parent / "_compiled" / package_name
        if package_root.exists():
            shutil.rmtree(package_root)
        shutil.copytree(staged_package_root, package_root)
        copied_bgls = sorted(package_root.rglob("*.bgl"))
        return {
            "compiler": str(compiler.path),
            "kind": compiler.kind,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "package_root": str(package_root),
            "bgls": [str(path) for path in copied_bgls],
        }
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


def compile_bgl(xml_path: Path, compiler: CompilerInfo, output_bgl: Path) -> dict[str, object]:
    if compiler.path is None:
        raise CompilerUnavailable(compiler.reason)
    output_bgl.parent.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in xml_path.parent.glob("*.bgl")}
    result = subprocess.run(
        [str(compiler.path), str(xml_path)],
        cwd=str(xml_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    after = [path.resolve() for path in xml_path.parent.glob("*.bgl") if path.resolve() not in before]
    if result.returncode != 0:
        raise RuntimeError(f"BglComp 退出代码 {result.returncode}: {result.stderr or result.stdout}")
    produced = next((path for path in after if path.is_file()), None)
    if produced is None:
        raise RuntimeError("BglComp 未在 XML 目录生成 BGL；请确认编译器版本和调用契约")
    produced.replace(output_bgl)
    return {
        "compiler": str(compiler.path),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output": str(output_bgl),
    }
