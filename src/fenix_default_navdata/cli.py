from __future__ import annotations

import argparse
import json
from pathlib import Path

from .convert import convert
from .deployment import deploy, restore
from .general_docs import (
    audit_enroute_navaid_ocr_rerun,
    write_enroute_navaid_ocr_rerun_audit,
)
from .iap_ocr import IAP_OCR_ELIGIBLE_STATUSES, build_iap_ocr_cache
from .iap_ocr_audit import audit_iap_ocr_cache, write_iap_ocr_audit
from .iap_ocr_consensus import (
    audit_iap_ocr_role_consensus,
    write_iap_ocr_role_consensus,
)
from .iap_ocr_recheck import audit_iap_ocr_role_recheck, write_iap_ocr_role_recheck
from .ocr_cache import build_ocr_cache
from .official_index import build_official_navaid_index
from .package_reader import DEFAULT_READER_TIMEOUT_SECONDS, read_package
from .paths import detect_paths
from .profile import DEFAULT_CYCLE
from .semantic_diff import SUPPORTED_TABLES, semantic_diff, write_semantic_diff
from .source import (
    audit_enroute_key_point_ocr_rerun,
    audit_enroute_navaid_ocr_source,
    load_naip,
)
from .source_gap import audit_source_gaps, load_semantic_diff, write_source_gap_audit
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
        "--general-doc-cache",
        help="航路 GeneralDoc 的 OCR 缓存目录；必须含已校验 SHA-256 的完整清单",
    )
    build.add_argument(
        "--general-doc-keypoint-cache-directory",
        default="enr-4.4",
        help="GeneralDoc 4.4 重要点 OCR 缓存子目录；默认 enr-4.4",
    )
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
    semantic = sub.add_parser(
        "semantic-diff",
        help="只读比较候选与参考 Navdatareader SQLite，不导出参考字段值",
    )
    semantic.add_argument("--candidate-db", required=True, help="候选包的 Navdatareader SQLite")
    semantic.add_argument("--reference-db", required=True, help="参考包的 Navdatareader SQLite")
    semantic.add_argument(
        "--tables",
        nargs="+",
        choices=SUPPORTED_TABLES,
        default=list(SUPPORTED_TABLES),
        help="要比较的读取器表（默认 VOR、NDB、航点、航路）",
    )
    semantic.add_argument("--sample-limit", type=int, default=50, help="每类差异最多输出的样本数")
    semantic.add_argument("--output", help="可选的本地诊断 JSON 输出路径")
    source_gap = sub.add_parser(
        "source-gap-audit",
        help="只读按 424 原始记录分类已脱敏的航点/航路来源缺口",
    )
    source_gap.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    source_gap.add_argument(
        "--semantic-diff",
        required=True,
        help="完整、只读且已脱敏的 semantic-diff JSON",
    )
    source_gap.add_argument(
        "--candidate-xml",
        help="可选的候选 BGL XML；仅用于区分源航路段未投影和片段连通性差异",
    )
    source_gap.add_argument("--output", help="可选的本地来源缺口审计 JSON 输出路径")
    ocr_cache = sub.add_parser(
        "ocr-cache",
        help="将原始 PDF 逐物理页 OCR 为带 SHA-256 清单、可断点续跑的本地缓存",
    )
    ocr_cache.add_argument("--pdf", required=True, help="424 原始 PDF 路径")
    ocr_cache.add_argument("--cache", required=True, help="PDF 对应的本地 OCR 缓存目录")
    ocr_cache.add_argument("--source-root", required=True, help="424 原始数据根目录")
    ocr_cache.add_argument("--ocr-command", default="ocr-skill", help="本地 OCR CLI 命令")
    ocr_cache.add_argument(
        "--backend",
        choices=("llamacpp", "deepseek"),
        default="llamacpp",
        help="OCR 后端；默认使用本机 llama.cpp 服务",
    )
    ocr_cache.add_argument(
        "--mode",
        choices=("markdown", "free", "figure", "ocr"),
        default="ocr",
        help="传给 OCR 引擎的识别模式",
    )
    ocr_cache.add_argument("--timeout", type=int, default=180, help="每页 OCR 超时秒数")
    ocr_cache.add_argument("--render-scale", type=float, default=2.0, help="PDF 页面渲染比例")
    ocr_cache.add_argument(
        "--image-profile",
        choices=("original", "autocontrast-grayscale"),
        default="original",
        help="渲染后的固定图像预处理；不同设置必须使用不同缓存目录",
    )
    ocr_cache.add_argument(
        "--runtime-profile",
        default="",
        help="可选的本地 OCR 运行时标识；不同标识不得复用同一缓存",
    )
    ocr_cache.add_argument("--first-page", type=int, help="可选的起始物理页")
    ocr_cache.add_argument("--last-page", type=int, help="可选的结束物理页")
    ocr_cache.add_argument("--force", action="store_true", help="重新识别已存在的有效页面")
    ocr_cache.add_argument(
        "--retries",
        type=int,
        default=0,
        help="单页 OCR 失败后的重试次数（默认 0）",
    )
    iap_ocr_cache = sub.add_parser(
        "iap-ocr-cache",
        help="对阻塞 IAP 图页匹配的源 PDF 建立本地 OCR 证据缓存，不修改投影",
    )
    iap_ocr_cache.add_argument("--source-root", required=True, help="424 原始数据根目录")
    iap_ocr_cache.add_argument("--pdf-cache", help="现有的终端 PDF 解析缓存目录")
    iap_ocr_cache.add_argument("--cache-root", required=True, help="IAP OCR 本地缓存根目录")
    iap_ocr_cache.add_argument(
        "--statuses",
        nargs="+",
        choices=IAP_OCR_ELIGIBLE_STATUSES,
        default=list(IAP_OCR_ELIGIBLE_STATUSES),
        help="要识别的 IAP 未决类别",
    )
    iap_ocr_cache.add_argument("--ocr-command", default="ocr-skill", help="本地 OCR CLI 命令")
    iap_ocr_cache.add_argument(
        "--backend",
        choices=("llamacpp", "deepseek"),
        default="llamacpp",
        help="OCR 后端；默认使用本机 llama.cpp 服务",
    )
    iap_ocr_cache.add_argument(
        "--mode",
        choices=("markdown", "free", "figure", "ocr"),
        default="markdown",
        help="传给 OCR 引擎的识别模式",
    )
    iap_ocr_cache.add_argument("--timeout", type=int, default=240, help="每页 OCR 超时秒数")
    iap_ocr_cache.add_argument("--render-scale", type=float, default=3.0, help="PDF 页面渲染比例")
    iap_ocr_cache.add_argument(
        "--image-profile",
        choices=("original", "autocontrast-grayscale"),
        default="original",
        help="渲染后的固定图像预处理；不同设置必须使用不同缓存根目录",
    )
    iap_ocr_cache.add_argument(
        "--runtime-profile",
        default="",
        help="可选的本地 OCR 运行时标识；不同标识不得复用同一缓存",
    )
    iap_ocr_cache.add_argument("--limit", type=int, help="只处理排序后的前 N 个源 PDF")
    iap_ocr_cache.add_argument("--force", action="store_true", help="重新识别已有有效页面")
    iap_ocr_cache.add_argument(
        "--retries",
        type=int,
        default=2,
        help="单页 OCR 失败后的重试次数（默认 2）",
    )
    iap_ocr_cache.add_argument("--dry-run", action="store_true", help="只输出计划，不调用 OCR")
    iap_ocr_audit = sub.add_parser(
        "iap-ocr-audit",
        help="只读审计 IAP OCR 缓存的源 SHA-256、航点命中与不可投影证据",
    )
    iap_ocr_audit.add_argument("--source-root", required=True, help="424 原始数据根目录")
    iap_ocr_audit.add_argument("--pdf-cache", help="现有的终端 PDF 解析缓存目录")
    iap_ocr_audit.add_argument("--cache-root", required=True, help="IAP OCR 本地缓存根目录")
    iap_ocr_audit.add_argument(
        "--statuses",
        nargs="+",
        choices=IAP_OCR_ELIGIBLE_STATUSES,
        default=list(IAP_OCR_ELIGIBLE_STATUSES),
        help="要审计的 IAP 未决类别",
    )
    iap_ocr_audit.add_argument("--output", help="可选的本地 JSON 审计输出路径")
    iap_ocr_recheck = sub.add_parser(
        "iap-ocr-recheck",
        help="比较同一 424 图页的两份完整 IAP OCR 角色证据缓存，不改变图页选择",
    )
    iap_ocr_recheck.add_argument("--source-root", required=True, help="424 原始数据根目录")
    iap_ocr_recheck.add_argument("--pdf-cache", help="现有的终端 PDF 解析缓存目录")
    iap_ocr_recheck.add_argument("--canonical-cache", required=True, help="已审计的完整 IAP OCR 缓存目录")
    iap_ocr_recheck.add_argument("--rerun-cache", required=True, help="独立重跑的完整 IAP OCR 缓存目录")
    iap_ocr_recheck.add_argument(
        "--statuses",
        nargs="+",
        choices=IAP_OCR_ELIGIBLE_STATUSES,
        default=list(IAP_OCR_ELIGIBLE_STATUSES),
        help="要比较的 IAP 未决类别",
    )
    iap_ocr_recheck.add_argument("--output", help="可选的本地 JSON 审计输出路径")
    iap_ocr_recheck.add_argument(
        "--require-agreement",
        action="store_true",
        help="角色证据或候选页不完全一致时返回非零，便于自动化门禁",
    )
    iap_ocr_consensus = sub.add_parser(
        "iap-ocr-consensus",
        help="比较至少三份完整 IAP OCR 缓存，生成不可投影的共识审计",
    )
    iap_ocr_consensus.add_argument("--source-root", required=True, help="424 原始数据根目录")
    iap_ocr_consensus.add_argument("--pdf-cache", help="现有的终端 PDF 解析缓存目录")
    iap_ocr_consensus.add_argument(
        "--cache-roots",
        nargs="+",
        required=True,
        help="至少三份独立 IAP OCR 缓存目录",
    )
    iap_ocr_consensus.add_argument(
        "--statuses",
        nargs="+",
        choices=IAP_OCR_ELIGIBLE_STATUSES,
        default=list(IAP_OCR_ELIGIBLE_STATUSES),
        help="要比较的 IAP 未决类别",
    )
    iap_ocr_consensus.add_argument("--output", help="可选的本地 JSON 审计输出路径")
    iap_ocr_consensus.add_argument(
        "--require-agreement",
        action="store_true",
        help="任一缓存与首份缓存不完全一致时返回非零，便于自动化门禁",
    )
    ocr_audit = sub.add_parser(
        "ocr-audit",
        help="比较同一原始 PDF 的完整 OCR 缓存与局部重跑缓存，仅输出证据审计",
    )
    ocr_audit.add_argument("--source-root", required=True, help="424 原始数据根目录")
    ocr_audit.add_argument("--canonical-cache", required=True, help="完整的已验证 OCR 缓存目录")
    ocr_audit.add_argument("--rerun-cache", required=True, help="同源 PDF 的局部或完整重跑缓存目录")
    ocr_audit.add_argument("--output", help="可选的本地审计 JSON 输出路径")
    ocr_audit.add_argument(
        "--require-agreement",
        action="store_true",
        help="重跑记录与主缓存不完全一致时返回非零，便于自动化门禁",
    )
    keypoint_ocr_audit = sub.add_parser(
        "keypoint-ocr-audit",
        help="比较同一 4.4 原始 PDF 的两份完整 OCR 缓存，并统计源 FIR 投影安全性",
    )
    keypoint_ocr_audit.add_argument("--source-root", required=True, help="2608 原始数据根目录")
    keypoint_ocr_audit.add_argument("--canonical-cache", required=True, help="完整的主 OCR 缓存目录")
    keypoint_ocr_audit.add_argument("--rerun-cache", required=True, help="同源完整 OCR 重跑缓存目录")
    keypoint_ocr_audit.add_argument("--output", help="可选的本地审计 JSON 输出路径")
    keypoint_ocr_audit.add_argument(
        "--allow-partial-rerun",
        action="store_true",
        help="仅按重跑缓存实际存在的物理页与主缓存比较；局部缓存始终不能参与构建",
    )
    keypoint_ocr_audit.add_argument(
        "--require-agreement",
        action="store_true",
        help="重跑记录与主缓存不完全一致时返回非零，便于自动化门禁",
    )
    ocr_source_audit = sub.add_parser(
        "ocr-source-audit",
        help="逐条审计一个完整 OCR 缓存是否能唯一回链到直接 424 导航台",
    )
    ocr_source_audit.add_argument("--source-root", required=True, help="424 原始数据根目录")
    ocr_source_audit.add_argument("--cache", required=True, help="完整 OCR 缓存目录")
    ocr_source_audit.add_argument("--output", help="可选的本地审计 JSON 输出路径")
    package_reader = sub.add_parser(
        "read-package",
        help="在纯 ASCII 暂存区镜像完整覆盖包并生成 Navdatareader SQLite",
    )
    package_reader.add_argument("--package", required=True, help="候选或参考 Community 包目录")
    package_reader.add_argument("--output", required=True, help="读取器 SQLite 输出路径")
    package_reader.add_argument("--reader", help="本机 Navdatareader.exe 路径")
    package_reader.add_argument("--cache-root", help="纯 ASCII 本地读取器暂存目录")
    package_reader.add_argument(
        "--filenames",
        nargs="+",
        default=["*.bgl"],
        help="要读取的 BGL 文件名模式，默认 *.bgl",
    )
    package_reader.add_argument(
        "--objects",
        nargs="+",
        default=[],
        help="可选的 Navdatareader BGL 对象过滤，例如 VOR NDB WAYPOINT AIRWAY",
    )
    package_reader.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_READER_TIMEOUT_SECONDS,
        help=f"读取器超时秒数（默认 {DEFAULT_READER_TIMEOUT_SECONDS}）",
    )
    validate = sub.add_parser("validate", help="验证候选")
    validate.add_argument("--candidate", required=True)
    validate.add_argument("--reference")
    deploy_parser = sub.add_parser("deploy", help="备份并覆盖 Community")
    deploy_parser.add_argument("--candidate", required=True)
    deploy_parser.add_argument("--target", help="Community 目录")
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
            general_doc_cache=_path(args.general_doc_cache),
            general_doc_key_point_cache_directory=args.general_doc_keypoint_cache_directory,
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
    if args.command == "semantic-diff":
        report = semantic_diff(
            Path(args.candidate_db),
            Path(args.reference_db),
            tables=args.tables,
            sample_limit=args.sample_limit,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_semantic_diff(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "source-gap-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        report = audit_source_gaps(
            load_naip(raw, include_terminal_documents=False),
            load_semantic_diff(Path(args.semantic_diff)),
            candidate_xml=_path(args.candidate_xml),
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_source_gap_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "ocr-cache":
        report = build_ocr_cache(
            Path(args.pdf),
            Path(args.cache),
            source_root=Path(args.source_root),
            command=args.ocr_command,
            backend=args.backend,
            mode=args.mode,
            timeout_seconds=args.timeout,
            render_scale=args.render_scale,
            first_page=args.first_page,
            last_page=args.last_page,
            force=args.force,
            image_profile=args.image_profile,
            runtime_profile=args.runtime_profile,
            retries=args.retries,
        )
        print(json.dumps(report.to_report(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "iap-ocr-cache":
        report = build_iap_ocr_cache(
            Path(args.source_root),
            Path(args.cache_root),
            pdf_cache=_path(args.pdf_cache),
            statuses=args.statuses,
            command=args.ocr_command,
            backend=args.backend,
            mode=args.mode,
            timeout_seconds=args.timeout,
            render_scale=args.render_scale,
            image_profile=args.image_profile,
            runtime_profile=args.runtime_profile,
            force=args.force,
            limit=args.limit,
            retries=args.retries,
            dry_run=args.dry_run,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "iap-ocr-audit":
        report = audit_iap_ocr_cache(
            Path(args.source_root),
            Path(args.cache_root),
            pdf_cache=_path(args.pdf_cache),
            statuses=args.statuses,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_iap_ocr_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "iap-ocr-recheck":
        report = audit_iap_ocr_role_recheck(
            Path(args.source_root),
            Path(args.canonical_cache),
            Path(args.rerun_cache),
            pdf_cache=_path(args.pdf_cache),
            statuses=args.statuses,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_iap_ocr_role_recheck(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["comparison"]["consistent"] or not args.require_agreement else 1
    if args.command == "iap-ocr-consensus":
        report = audit_iap_ocr_role_consensus(
            Path(args.source_root),
            [Path(value) for value in args.cache_roots],
            pdf_cache=_path(args.pdf_cache),
            statuses=args.statuses,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_iap_ocr_role_consensus(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["comparison"]["consistent"] or not args.require_agreement else 1
    if args.command == "ocr-audit":
        report = audit_enroute_navaid_ocr_rerun(
            Path(args.source_root),
            Path(args.canonical_cache),
            Path(args.rerun_cache),
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_enroute_navaid_ocr_rerun_audit(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["comparison"]["consistent"] or not args.require_agreement else 1
    if args.command == "keypoint-ocr-audit":
        report = audit_enroute_key_point_ocr_rerun(
            Path(args.source_root),
            Path(args.canonical_cache),
            Path(args.rerun_cache),
            allow_partial_rerun=args.allow_partial_rerun,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_enroute_navaid_ocr_rerun_audit(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["comparison"]["consistent"] or not args.require_agreement else 1
    if args.command == "ocr-source-audit":
        report = audit_enroute_navaid_ocr_source(
            Path(args.source_root),
            Path(args.cache),
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_enroute_navaid_ocr_rerun_audit(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "read-package":
        result = read_package(
            Path(args.package),
            Path(args.output),
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            filename_patterns=args.filenames,
            object_filter=args.objects,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(result.to_report(), ensure_ascii=False, indent=2, default=str))
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
        backup = deploy(Path(args.candidate), target)
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
