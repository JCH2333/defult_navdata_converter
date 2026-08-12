from __future__ import annotations

import argparse
import json
from pathlib import Path

from .convert import convert
from .deployment import deploy, restore
from .official_index import build_official_navaid_index
from .paths import detect_paths
from .profile import DEFAULT_CYCLE
from .validation import validate_candidate


def _path(value: str | None) -> Path | None:
    return Path(value).expanduser() if value else None


def _defaults(args: argparse.Namespace) -> tuple[Path, Path, Path, Path | None]:
    detected = detect_paths()
    raw = _path(args.raw) or detected.raw_root
    base = _path(args.nav_base) or detected.nav_base
    jepp = _path(args.nav_jepp) or detected.nav_jepp
    reference = _path(args.reference) or detected.reference_root
    if not raw or not base or not jepp:
        raise SystemExit("无法自动检测 424 原始目录、navigraph-nav-base 或 navigraph-nav-jepp，请显式传参")
    return raw, base, jepp, reference


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="default-navdata-converter", description="424/2608 到 MSFS 2024 默认通用导航数据转换器")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="生成隔离候选")
    build.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    build.add_argument("--nav-base", help="官方 navigraph-nav-base 目录")
    build.add_argument("--nav-jepp", help="官方 navigraph-nav-jepp 目录")
    build.add_argument("--reference", help="Default navdata 2608R1 参考目录")
    build.add_argument("--output", required=True, help="新的候选目录")
    build.add_argument("--bglcomp", help="合法 BglComp.exe 路径")
    build.add_argument("--pdf-cache", help="可复用的 PDF 解析缓存目录")
    build.add_argument(
        "--baseline-db",
        help="已验证的官方 VOR/NDB 设施索引 SQLite；未提供时只能生成不可部署的诊断候选",
    )
    build.add_argument(
        "--baseline-tolerance-nm",
        type=float,
        default=0.25,
        help="424 与官方设施坐标匹配阈值（海里，默认 0.25）",
    )
    index = sub.add_parser("index", help="从当前官方双包生成并验证 VOR/NDB 设施索引")
    index.add_argument("--nav-base", help="官方 navigraph-nav-base 目录")
    index.add_argument("--nav-jepp", help="官方 navigraph-nav-jepp 目录")
    index.add_argument("--output", help="设施索引 SQLite 输出路径；默认使用本机内容寻址缓存")
    index.add_argument("--reader", help="本机 Navdatareader.exe 路径")
    index.add_argument("--cache-root", help="纯 ASCII 的本地索引/暂存缓存目录")
    index.add_argument("--force", action="store_true", help="覆盖同名本地索引并重新生成")
    index.add_argument("--timeout", type=int, default=3600, help="读取器超时秒数（默认 3600）")
    validate = sub.add_parser("validate", help="验证候选")
    validate.add_argument("--candidate", required=True)
    validate.add_argument("--reference")
    deploy_parser = sub.add_parser("deploy", help="备份并覆盖 Community")
    deploy_parser.add_argument("--candidate", required=True)
    deploy_parser.add_argument("--target", help="Community 目录")
    deploy_parser.add_argument("--allow-test-build", action="store_true")
    restore_parser = sub.add_parser("restore", help="恢复备份")
    restore_parser.add_argument("--backup", required=True)
    restore_parser.add_argument("--target", help="Community 目录")
    sub.add_parser("detect", help="显示本机路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "detect":
        detected = detect_paths()
        print(json.dumps(detected.__dict__, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "build":
        raw, base, jepp, reference = _defaults(args)
        report = convert(
            raw,
            base,
            jepp,
            Path(args.output),
            cycle=DEFAULT_CYCLE,
            reference=reference,
            compiler=_path(args.bglcomp),
            pdf_cache=_path(args.pdf_cache),
            baseline_db=_path(args.baseline_db),
            baseline_tolerance_nm=args.baseline_tolerance_nm,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "index":
        detected = detect_paths()
        base = _path(args.nav_base) or detected.nav_base
        jepp = _path(args.nav_jepp) or detected.nav_jepp
        if not base or not jepp:
            raise SystemExit("无法自动检测官方 navigraph-nav-base 或 navigraph-nav-jepp，请显式传参")
        index = build_official_navaid_index(
            nav_base=base,
            nav_jepp=jepp,
            output=_path(args.output),
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            force=args.force,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(index.to_report(), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "validate":
        report = validate_candidate(Path(args.candidate), _path(args.reference))
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report["valid"] else 1
    if args.command == "deploy":
        detected = detect_paths()
        target = Path(args.target) if args.target else detected.community_root
        if not target:
            raise SystemExit("未找到 Community 目录")
        backup = deploy(Path(args.candidate), target, allow_test_build=args.allow_test_build)
        print(json.dumps({"backup": str(backup), "target": str(target)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "restore":
        detected = detect_paths()
        target = Path(args.target) if args.target else detected.community_root
        if not target:
            raise SystemExit("未找到 Community 目录")
        restore(Path(args.backup), target)
        print(f"已恢复: {target}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
