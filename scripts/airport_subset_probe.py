from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from fenix_default_navdata.bgl import (
    compile_package,
    find_compiler,
    write_package_project,
)
from fenix_default_navdata.bgl_format import (
    BglFormatError,
    header_summary,
    parse_bgl_file,
)
from fenix_default_navdata.package_reader import PackageReaderError, read_package


def inspect_bgl_layouts(package_root: Path) -> list[dict[str, object]]:
    """Return only BGL header/layout facts for a controlled SDK probe."""

    rows: list[dict[str, object]] = []
    for path in sorted(package_root.rglob("*.bgl")):
        row: dict[str, object] = {
            "path": path.relative_to(package_root).as_posix().lower(),
            "size": path.stat().st_size,
        }
        try:
            header = parse_bgl_file(path)
        except BglFormatError as error:
            row["layout_error"] = str(error)
        else:
            row["layout"] = {
                **header_summary(header),
                "version": f"{header.version:#x}",
                "section_counts": [section.count for section in header.sections],
                "section_sizes": [section.size for section in header.sections],
            }
        rows.append(row)
    return rows


def select_holding_patterns(
    airport: ET.Element,
    *,
    holding_idents: tuple[str, ...],
    start: int | None,
    end: int | None,
) -> tuple[str, ...]:
    """Retain a deterministic holding subset without changing its source order."""

    holdings = list(airport.findall("HoldingPattern"))
    if holding_idents:
        if start is not None or end is not None:
            raise ValueError(
                "--holding-ident 不能与 --holding-start/--holding-end 同时使用"
            )
        if len(set(holding_idents)) != len(holding_idents):
            raise ValueError("--holding-ident 不能包含重复固定点标识")
        by_ident = {
            (holding.get("fixIdent") or "").upper(): holding
            for holding in holdings
        }
        if len(by_ident) != len(holdings):
            raise ValueError("机场等待航线的 fixIdent 不唯一，无法按标识选择")
        unknown = sorted(set(holding_idents) - set(by_ident))
        if unknown:
            raise ValueError(
                "--holding-ident 包含当前机场不存在的固定点: "
                + ", ".join(unknown)
            )
        retained = set(holding_idents)
        for holding in holdings:
            if (holding.get("fixIdent") or "").upper() not in retained:
                airport.remove(holding)
    elif start is not None or end is not None:
        selected_start = start or 0
        selected_end = end if end is not None else len(holdings)
        if selected_start < 0 or selected_end < selected_start:
            raise ValueError("--holding-start/--holding-end 必须是有效的半开区间")
        kept_ids = {id(holding) for holding in holdings[selected_start:selected_end]}
        for holding in holdings:
            if id(holding) not in kept_ids:
                airport.remove(holding)

    return tuple(
        (holding.get("fixIdent") or "").upper()
        for holding in airport.findall("HoldingPattern")
    )


def normalize_holding_file_groups(
    groups: list[list[str]],
    *,
    selected_holding_idents: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    """Validate a file-level partition without changing source holding values."""

    normalized = tuple(
        tuple(
            ident.strip().upper()
            for ident in group
            if ident.strip()
        )
        for group in groups
    )
    if not normalized:
        return ()
    if any(not group for group in normalized):
        raise ValueError("--holding-file-group 不能包含空分组")
    flattened = tuple(ident for group in normalized for ident in group)
    if len(set(flattened)) != len(flattened):
        raise ValueError("--holding-file-group 不能重复包含同一固定点")
    if set(flattened) != set(selected_holding_idents):
        raise ValueError(
            "--holding-file-group 必须恰好覆盖当前保留的全部等待航线"
        )
    return normalized


def parse_holding_attributes(values: list[str]) -> dict[str, str]:
    """Parse explicit diagnostic-only attribute assignments."""

    return parse_attribute_assignments(
        values,
        option="--set-holding-attribute",
    )


def parse_airport_attributes(values: list[str]) -> dict[str, str]:
    """Parse explicit diagnostic-only Airport attribute assignments."""

    return parse_attribute_assignments(
        values,
        option="--set-airport-attribute",
    )


def parse_airport_child_specs(values: list[str]) -> tuple[ET.Element, ...]:
    """Parse diagnostic-only SDK child elements without touching source models.

    Each spec is a compact ``Tag;name=value`` sequence.  The probe intentionally
    accepts attributes only: it is for locating BGL section-layout effects before
    a source-backed child-object adapter is designed.
    """

    children: list[ET.Element] = []
    for raw in values:
        parts = [part.strip() for part in raw.split(";")]
        tag = parts[0] if parts else ""
        if not tag or not tag.isidentifier():
            raise ValueError(
                "--append-airport-child 必须以 XML 元素名开头，例如 Com;frequency=118.0"
            )
        attributes = parse_attribute_assignments(
            [part for part in parts[1:] if part],
            option="--append-airport-child",
        )
        children.append(ET.Element(tag, attributes))
    return tuple(children)


def append_airport_children(
    airport: ET.Element,
    children: tuple[ET.Element, ...],
) -> None:
    """Append independent diagnostic children in the caller's stable order."""

    for child in children:
        airport.append(deepcopy(child))


def append_root_children(
    root: ET.Element,
    children: tuple[ET.Element, ...],
) -> None:
    """Append independent diagnostic root objects in the caller's stable order."""

    for child in children:
        root.append(deepcopy(child))


def parse_attribute_assignments(
    values: list[str],
    *,
    option: str,
) -> dict[str, str]:
    """Parse deterministic diagnostic-only XML attribute assignments."""

    attributes: dict[str, str] = {}
    for raw in values:
        key, separator, value = raw.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise ValueError(
                f"{option} 必须使用 name=value 形式"
            )
        if key in attributes:
            raise ValueError(
                f"{option} 重复设置属性: {key}"
            )
        attributes[key] = value
    return attributes


def add_airport_procedure_deletion(airport: ET.Element) -> None:
    """Insert the standard procedure replacement marker for a probe only."""

    deletion = ET.Element(
        "DeleteAirport",
        {
            "deleteAllApproaches": "TRUE",
            "deleteAllDepartures": "TRUE",
            "deleteAllArrivals": "TRUE",
        },
    )
    airport.insert(0, deletion)


def parse_airport_waypoint_selectors(
    values: list[str],
) -> set[tuple[str, str]]:
    """Normalize diagnostic-only AIRPORT:IDENT selectors."""

    selectors: set[tuple[str, str]] = set()
    for raw in values:
        airport, separator, ident = raw.partition(":")
        airport = airport.strip().upper()
        ident = ident.strip().upper()
        if not separator or len(airport) != 4 or not ident:
            raise ValueError(
                "--drop-airport-waypoint 必须使用 ICAO:IDENT 形式"
            )
        selector = (airport, ident)
        if selector in selectors:
            raise ValueError(
                "--drop-airport-waypoint 不能包含重复的机场航点"
            )
        selectors.add(selector)
    return selectors


def drop_selected_waypoints(
    root: ET.Element,
    *,
    airport_selectors: set[tuple[str, str]],
    root_idents: set[str],
) -> None:
    """Remove only explicitly selected waypoints from a diagnostic XML tree."""

    for point in list(root.findall("Waypoint")):
        if (point.get("waypointIdent") or "").upper() in root_idents:
            root.remove(point)
    for airport in root.findall("Airport"):
        airport_ident = (airport.get("ident") or "").upper()
        for point in list(airport.findall("Waypoint")):
            selector = (
                airport_ident,
                (point.get("waypointIdent") or "").upper(),
            )
            if selector in airport_selectors:
                airport.remove(point)


def select_airports(
    airports: list[ET.Element],
    *,
    start: int | None,
    end: int | None,
    airport_idents: tuple[str, ...],
) -> list[ET.Element]:
    """Select a source-ordered airport subset from exactly one CLI mode."""

    if airport_idents:
        if start is not None or end is not None:
            raise ValueError("--airport-ident 不能与 --start/--end 同时使用")
        if len(set(airport_idents)) != len(airport_idents):
            raise ValueError("--airport-ident 不能包含重复机场标识")
        by_ident = {
            (airport.get("ident") or "").upper(): airport
            for airport in airports
        }
        if len(by_ident) != len(airports):
            raise ValueError("源 XML 包含重复机场标识，无法按标识选择")
        unknown = sorted(set(airport_idents) - set(by_ident))
        if unknown:
            raise ValueError(
                "--airport-ident 包含源 XML 不存在的机场: "
                + ", ".join(unknown)
            )
        selected_idents = set(airport_idents)
        return [
            airport
            for airport in airports
            if (airport.get("ident") or "").upper() in selected_idents
        ]

    if start is None or end is None or start < 0 or end <= start:
        raise ValueError(
            "--start/--end 与 --airport-ident 必须二选一，且区间必须有效"
        )
    return airports[start:end]


def isolate_holding_group(
    airport: ET.Element,
    *,
    holding_idents: tuple[str, ...],
    include_waypoints: bool = True,
) -> None:
    """Keep only source-backed holding patterns and their required waypoints."""

    selected = set(holding_idents)
    for child in list(airport):
        if child.tag == "HoldingPattern":
            if (child.get("fixIdent") or "").upper() not in selected:
                airport.remove(child)
        elif child.tag == "Waypoint":
            if (
                not include_waypoints
                or (child.get("waypointIdent") or "").upper() not in selected
            ):
                airport.remove(child)
        else:
            airport.remove(child)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将机场 XML 的受控子集编译并交给 Navdatareader 读取。",
    )
    parser.add_argument("--source-xml", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument(
        "--airport-ident",
        action="append",
        nargs="+",
        default=[],
        help="仅保留指定机场，可重复传入；保留源 XML 中的物理顺序。",
    )
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--reader-output", type=Path)
    parser.add_argument(
        "--package-name",
        default="zzz-pmdg-china-navdata",
    )
    parser.add_argument(
        "--output-dir",
        default=r"scenery\pmdg-china-navdata",
    )
    parser.add_argument("--drop-tag", action="append", default=[])
    parser.add_argument("--waypoint-start", type=int)
    parser.add_argument("--waypoint-end", type=int)
    parser.add_argument("--holding-start", type=int)
    parser.add_argument("--holding-end", type=int)
    parser.add_argument(
        "--holding-ident",
        action="append",
        nargs="+",
        default=[],
        help="仅保留指定 fixedIdent 的等待航线，可重复传入；保留 XML 原始顺序。",
    )
    parser.add_argument(
        "--holding-ident-order",
        nargs="+",
        help="按指定固定点标识重排保留的等待航线；必须恰好覆盖当前保留集合。",
    )
    parser.add_argument(
        "--holding-file-group",
        action="append",
        nargs="+",
        default=[],
        help="将完整等待航线集合拆到多个输入 XML；每组会编译为独立 BGL。",
    )
    parser.add_argument(
        "--holding-file-group-mode",
        choices=("duplicate-airport", "isolated-holdings"),
        default="duplicate-airport",
        help="拆分诊断模式；isolated-holdings 保留一个无等待航线主机场和仅含等待航线的分组 BGL。",
    )
    parser.add_argument(
        "--omit-isolated-holding-waypoints",
        action="store_true",
        help="仅诊断用：isolated-holdings 分组 BGL 不重复写入主机场已有的固定点。",
    )
    parser.add_argument(
        "--drop-holding-attribute",
        action="append",
        default=[],
        help="仅诊断用：从每条保留等待航线移除一个可选 XML 属性。",
    )
    parser.add_argument(
        "--set-holding-attribute",
        action="append",
        default=[],
        help="仅诊断用：为每条保留等待航线设置 name=value 属性。",
    )
    parser.add_argument(
        "--set-airport-attribute",
        action="append",
        default=[],
        help="仅诊断用：为每个保留机场设置 name=value 属性。",
    )
    parser.add_argument(
        "--append-airport-child",
        action="append",
        default=[],
        metavar="TAG;NAME=VALUE",
        help=(
            "仅诊断用：在每个保留机场末尾附加属性型 SDK 子对象；"
            "例如 Com;frequency=118.0;type=GROUND"
        ),
    )
    parser.add_argument(
        "--append-root-child",
        action="append",
        default=[],
        metavar="TAG;NAME=VALUE",
        help=(
            "仅诊断用：在 FSData 根节点末尾附加属性型 SDK 对象；"
            "例如 Ndb;frequency=385;ident=PROBE"
        ),
    )
    parser.add_argument(
        "--delete-airport-procedures",
        action="store_true",
        help="仅诊断用：在每个保留机场首部写入程序覆盖删除标记。",
    )
    parser.add_argument("--move-waypoints-to-root", action="store_true")
    parser.add_argument("--keep-root-waypoints", action="store_true")
    parser.add_argument(
        "--drop-airport-waypoint",
        action="append",
        default=[],
        metavar="ICAO:IDENT",
        help="仅诊断用：从保留机场删除精确匹配的局部航点",
    )
    parser.add_argument(
        "--drop-root-waypoint",
        action="append",
        default=[],
        metavar="IDENT",
        help="仅诊断用：从根节点删除精确匹配的全局航点",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    source_xml = args.source_xml.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    if not source_xml.is_file():
        raise SystemExit(f"源 XML 不存在: {source_xml}")

    probe_root = output_root / args.label
    if probe_root.exists():
        raise SystemExit(f"诊断输出已存在，拒绝覆盖: {probe_root}")

    tree = ET.parse(source_xml)
    root = tree.getroot()
    airports = list(root.findall("Airport"))
    requested_airport_idents = tuple(
        ident.strip().upper()
        for values in args.airport_ident
        for ident in values
        if ident.strip()
    )
    try:
        selected = select_airports(
            airports,
            start=args.start,
            end=args.end,
            airport_idents=requested_airport_idents,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not selected:
        raise SystemExit("机场选择为空")

    if not args.keep_root_waypoints:
        for waypoint in list(root.findall("Waypoint")):
            root.remove(waypoint)
    selected_ids = {id(airport) for airport in selected}
    for airport in airports:
        if id(airport) not in selected_ids:
            root.remove(airport)

    dropped_tags = {tag.strip() for tag in args.drop_tag if tag.strip()}
    requested_holding_idents = tuple(
        ident.strip().upper()
        for values in args.holding_ident
        for ident in values
        if ident.strip()
    )
    try:
        assigned_holding_attributes = parse_holding_attributes(
            args.set_holding_attribute
        )
        assigned_airport_attributes = parse_airport_attributes(
            args.set_airport_attribute
        )
        appended_airport_children = parse_airport_child_specs(
            args.append_airport_child
        )
        appended_root_children = parse_airport_child_specs(
            args.append_root_child
        )
        dropped_airport_waypoints = parse_airport_waypoint_selectors(
            args.drop_airport_waypoint
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    dropped_root_waypoints = {
        ident.strip().upper()
        for ident in args.drop_root_waypoint
        if ident.strip()
    }
    if len(dropped_root_waypoints) != len([
        ident for ident in args.drop_root_waypoint if ident.strip()
    ]):
        raise SystemExit("--drop-root-waypoint 不能包含重复的航点标识")
    append_root_children(root, appended_root_children)
    selected_holding_idents: tuple[str, ...] = ()
    for airport in selected:
        for attribute, value in assigned_airport_attributes.items():
            airport.set(attribute, value)
        append_airport_children(airport, appended_airport_children)
        if args.delete_airport_procedures:
            add_airport_procedure_deletion(airport)
        for child in list(airport):
            if child.tag in dropped_tags:
                airport.remove(child)
        if args.waypoint_start is not None or args.waypoint_end is not None:
            points = list(airport.findall("Waypoint"))
            start = args.waypoint_start or 0
            end = args.waypoint_end if args.waypoint_end is not None else len(points)
            kept_ids = {id(point) for point in points[start:end]}
            for point in points:
                if id(point) not in kept_ids:
                    airport.remove(point)
        if args.move_waypoints_to_root:
            for point in list(airport.findall("Waypoint")):
                airport.remove(point)
                root.append(point)
        try:
            selected_holding_idents = select_holding_patterns(
                airport,
                holding_idents=requested_holding_idents,
                start=args.holding_start,
                end=args.holding_end,
            )
        except ValueError as error:
            raise SystemExit(str(error)) from error
        if args.holding_ident_order:
            holdings = list(airport.findall("HoldingPattern"))
            by_ident = {
                (holding.get("fixIdent") or "").upper(): holding
                for holding in holdings
            }
            requested = [ident.upper() for ident in args.holding_ident_order]
            if (
                len(by_ident) != len(holdings)
                or len(requested) != len(holdings)
                or set(requested) != set(by_ident)
            ):
                raise SystemExit(
                    "--holding-ident-order 必须唯一且完整覆盖当前保留的等待航线"
                )
            for holding in holdings:
                airport.remove(holding)
            for ident in requested:
                airport.append(by_ident[ident])
        for holding in airport.findall("HoldingPattern"):
            for attribute in args.drop_holding_attribute:
                holding.attrib.pop(attribute, None)
            for attribute, value in assigned_holding_attributes.items():
                holding.set(attribute, value)

    drop_selected_waypoints(
        root,
        airport_selectors=dropped_airport_waypoints,
        root_idents=dropped_root_waypoints,
    )

    try:
        holding_file_groups = normalize_holding_file_groups(
            args.holding_file_group,
            selected_holding_idents=selected_holding_idents,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if holding_file_groups and len(selected) != 1:
        raise SystemExit("--holding-file-group 目前只支持单机场探针")

    input_dir = probe_root / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_xmls: tuple[Path, ...]
    if holding_file_groups:
        grouped_paths: list[Path] = []
        if args.holding_file_group_mode == "isolated-holdings":
            primary_tree = deepcopy(tree)
            primary_airport = primary_tree.getroot().find("Airport")
            if primary_airport is None:
                raise SystemExit("拆分等待航线时未找到主机场 XML 节点")
            for holding in list(primary_airport.findall("HoldingPattern")):
                primary_airport.remove(holding)
            primary_xml = input_dir / source_xml.name
            primary_tree.write(primary_xml, encoding="utf-8", xml_declaration=True)
            grouped_paths.append(primary_xml)
        for index, group in enumerate(holding_file_groups, start=1):
            grouped_tree = deepcopy(tree)
            grouped_airport = grouped_tree.getroot().find("Airport")
            if grouped_airport is None:
                raise SystemExit("拆分等待航线时未找到机场 XML 节点")
            if args.holding_file_group_mode == "isolated-holdings":
                isolate_holding_group(
                    grouped_airport,
                    holding_idents=group,
                    include_waypoints=not args.omit_isolated_holding_waypoints,
                )
            else:
                group_idents = set(group)
                for holding in list(grouped_airport.findall("HoldingPattern")):
                    if (holding.get("fixIdent") or "").upper() not in group_idents:
                        grouped_airport.remove(holding)
            grouped_xml = input_dir / (
                f"{source_xml.stem}-holding-group-{index:02d}{source_xml.suffix}"
            )
            grouped_tree.write(grouped_xml, encoding="utf-8", xml_declaration=True)
            grouped_paths.append(grouped_xml)
        input_xmls = tuple(grouped_paths)
    else:
        input_xml = input_dir / source_xml.name
        tree.write(input_xml, encoding="utf-8", xml_declaration=True)
        input_xmls = (input_xml,)

    project = write_package_project(
        probe_root / "project",
        package_name=args.package_name,
        title="China NavData AIRAC 2608",
        output_dir=args.output_dir,
        source_xmls=input_xmls,
        package_order_hint="CUSTOM_NAVDATA_PATCH",
    )
    compiler = find_compiler(args.compiler)
    report = compile_package(
        project,
        compiler,
        package_name=args.package_name,
    )
    package_root = Path(str(report["package_root"]))
    reader_status: dict[str, object] | None = None
    if args.reader_output:
        try:
            reader = read_package(
                package_root,
                args.reader_output.expanduser().resolve(),
                timeout_seconds=180,
                failure_artifacts=probe_root / "reader-failure",
            )
            reader_status = {"ok": True, "scan": reader.scan}
        except PackageReaderError as error:
            artifacts = probe_root / "reader-failure"
            reader_status = {
                "ok": False,
                "error": str(error),
                "failure_artifacts": str(artifacts) if artifacts.is_dir() else None,
            }

    print(json.dumps(
        {
            "label": args.label,
            "source_xml": str(source_xml),
            "airport_range": [args.start, args.end],
            "airport_selection": (
                "ident" if requested_airport_idents else "range"
            ),
            "airport_idents": [airport.attrib["ident"] for airport in selected],
            "dropped_tags": sorted(dropped_tags),
            "waypoint_range": [args.waypoint_start, args.waypoint_end],
            "holding_range": [args.holding_start, args.holding_end],
            "holding_idents": list(selected_holding_idents),
            "holding_ident_order": args.holding_ident_order,
            "holding_file_groups": [list(group) for group in holding_file_groups],
            "holding_file_group_mode": args.holding_file_group_mode,
            "omit_isolated_holding_waypoints": args.omit_isolated_holding_waypoints,
            "dropped_holding_attributes": args.drop_holding_attribute,
            "assigned_holding_attributes": assigned_holding_attributes,
            "assigned_airport_attributes": assigned_airport_attributes,
            "appended_airport_children": [
                {"tag": child.tag, "attributes": dict(child.attrib)}
                for child in appended_airport_children
            ],
            "appended_root_children": [
                {"tag": child.tag, "attributes": dict(child.attrib)}
                for child in appended_root_children
            ],
            "delete_airport_procedures": args.delete_airport_procedures,
            "root_waypoints": (
                "kept" if args.keep_root_waypoints
                else "removed"
            ),
            "dropped_airport_waypoints": [
                f"{airport}:{ident}"
                for airport, ident in sorted(dropped_airport_waypoints)
            ],
            "dropped_root_waypoints": sorted(dropped_root_waypoints),
            "waypoint_placement": (
                "root" if args.move_waypoints_to_root else "airport"
            ),
            "package_root": str(package_root),
            "bgl_layouts": inspect_bgl_layouts(package_root),
            "reader": reader_status,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
