from __future__ import annotations

import argparse
import json
from .route_restrict_source_audit import (
    audit_route_restrict_source,
    write_route_restrict_source_audit,
)
from .airspace_source_audit import (
    audit_airspace_source,
    write_airspace_source_audit,
)
from .general_doc_source_audit import (
    audit_general_doc_source,
    write_general_doc_source_audit,
)
from pathlib import Path

from .ad219_ndb import (
    audit_ad219_ndb_ocr,
    build_ad219_ndb_ocr_cache,
    write_ad219_ndb_ocr_audit,
)
from .airway_diff_audit import (
    audit_airway_differences,
    load_airway_diff_report,
    load_source_audit,
    write_airway_diff_audit,
)
from .airway_endpoint_audit import (
    audit_unresolved_airway_endpoints,
    write_unresolved_airway_endpoint_audit,
)
from .airway_endpoint_card_audit import (
    audit_airway_endpoint_card,
    audit_non_designated_airway_endpoint_card,
    write_airway_endpoint_card_audit,
)
from .airway_projection_matrix_audit import (
    audit_airway_projection_matrix,
    write_airway_projection_matrix_audit,
)
from .sdk_bgl_expression_matrix import (
    audit_sdk_bgl_expression_matrix,
    write_sdk_bgl_expression_matrix,
)
from .airport_source_inventory import (
    build_airport_source_inventory,
    write_airport_source_inventory,
)
from .source_model_completeness_audit import (
    audit_source_model_completeness,
    write_source_model_completeness_audit,
)
from .route_holding_source_audit import (
    audit_route_holding_source,
    write_route_holding_source_audit,
)
from .airport_bgl_cardinality_audit import (
    audit_airport_bgl_cardinality,
    write_airport_bgl_cardinality_audit,
)
from .enroute_bgl_cardinality_audit import (
    audit_enroute_bgl_cardinality,
    write_enroute_bgl_cardinality_audit,
)
from .default_gap_cards import (
    audit_default_gap_cards,
    write_default_gap_cards,
)
from .iap_primary_source_audit import (
    audit_iap_primary_sources,
    write_iap_primary_source_audit,
)
from .iap_uncached_pdf_audit import (
    audit_uncached_iap_pdfs,
    write_uncached_iap_pdf_audit,
)
from .unclassified_procedure_audit import (
    audit_unclassified_procedures,
    write_unclassified_procedure_audit,
)
from .unclassified_procedure_card_audit import (
    audit_unclassified_procedure_card,
    write_unclassified_procedure_card_audit,
)
from .bgl import find_compiler
from .airway_connection_shape_probe import run_airway_connection_shape_probe
from .airway_coordinate_precision_probe import (
    run_airway_coordinate_precision_probe,
    write_source_airway_coordinate_precision_audit,
)
from .airway_route_child_order_probe import run_airway_route_child_order_probe
from .bgl_format import (
    audit_bgl_layouts,
    audit_file_convergence,
    write_bgl_layout_audit,
    write_file_convergence_audit,
)
from .package_metadata_audit import (
    audit_package_derived_metadata,
    write_package_derived_metadata_audit,
)
from .convert import convert, export_intermediate_model
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
from .model_io import load_model
from .model_replay_audit import (
    audit_model_replay,
    load_difference_allowlist,
    write_model_replay_audit,
)
from .ocr_cache import build_ocr_cache
from .ocr_runtime import resolve_runtime_profile
from .ocr_runtime_probe import run_ocr_runtime_probe, write_ocr_runtime_probe
from .official_index import build_official_navaid_index
from .package_reader import DEFAULT_READER_TIMEOUT_SECONDS, read_package
from .paths import detect_paths
from .profile import DEFAULT_CYCLE
from .route_fragment_probe import run_route_fragment_probe
from .semantic_diff import (
    SUPPORTED_TABLES,
    semantic_diff,
    semantic_reproducibility_audit,
    write_semantic_diff,
    write_semantic_reproducibility_audit,
)
from .source import (
    _load_terminal_coordinate_pages,
    audit_enroute_key_point_ocr_rerun,
    audit_enroute_navaid_ocr_source,
    load_naip,
)
from .source_gap import (
    audit_general_document_key_point_reference_coverage,
    audit_source_gaps,
    audit_terminal_coordinate_field_delta_coverage,
    audit_terminal_coordinate_reference_coverage,
    load_semantic_diff,
    write_source_gap_audit,
)
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
        "--general-doc-airway-cache-directories",
        nargs="*",
        default=[],
        help="要投影最低飞行高度的完整 3.2 航路表 OCR 缓存子目录",
    )
    build.add_argument(
        "--iap-ocr-cache-roots",
        nargs="+",
        default=[],
        help="至少三份完全一致的 IAP OCR 缓存；仅用于多图进近页的受限消歧",
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
    build.add_argument(
        "--model",
        help="已导出的中间模型 JSON/JSON.GZ；提供后跳过 424 解析，只运行官方设施选择和 BGL 适配器",
    )
    build.add_argument(
        "--preserve-package-tool-times",
        action="store_true",
        help="仅限 --model 隔离探针：保留 Package Tool 的 layout/index FILETIME",
    )
    export_model = sub.add_parser("export-model", help="导出可复用的 424 中间模型快照")
    export_model.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    export_model.add_argument("--output", required=True, help="中间模型 JSON 或 JSON.GZ 输出路径")
    export_model.add_argument("--pdf-cache", help="可复用的 PDF 解析缓存目录")
    export_model.add_argument(
        "--general-doc-cache",
        help="航路 GeneralDoc 的 OCR 缓存目录；必须含已校验 SHA-256 的完整清单",
    )
    export_model.add_argument(
        "--general-doc-keypoint-cache-directory",
        default="enr-4.4",
        help="GeneralDoc 4.4 重要点 OCR 缓存子目录；默认 enr-4.4",
    )
    export_model.add_argument(
        "--general-doc-airway-cache-directories",
        nargs="*",
        default=[],
        help="要投影最低飞行高度的完整 3.2 航路表 OCR 缓存子目录",
    )
    export_model.add_argument(
        "--iap-ocr-cache-roots",
        nargs="+",
        default=[],
        help="至少三份完全一致的 IAP OCR 缓存；仅用于多图进近页的受限消歧",
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
        "--candidate-bgl-count",
        required=True,
        type=int,
        help="候选读取器请求且必须登记的 BGL 数",
    )
    semantic.add_argument(
        "--reference-bgl-count",
        required=True,
        type=int,
        help="参考读取器请求且必须登记的 BGL 数",
    )
    semantic.add_argument(
        "--tables",
        nargs="+",
        choices=SUPPORTED_TABLES,
        default=list(SUPPORTED_TABLES),
        help="要比较的读取器表（默认 VOR、NDB、航点、航路）",
    )
    semantic.add_argument("--sample-limit", type=int, default=50, help="每类差异最多输出的样本数")
    semantic.add_argument("--output", help="可选的本地诊断 JSON 输出路径")
    reproducibility = sub.add_parser(
        "semantic-reproducibility-audit",
        help="只读检查同一包重复读取 SQLite 的语义结果是否一致",
    )
    reproducibility.add_argument(
        "--databases",
        nargs="+",
        required=True,
        help="至少两个重复读取产生的 Navdatareader SQLite",
    )
    reproducibility.add_argument(
        "--bgl-count",
        required=True,
        type=int,
        help="每次读取必须完整登记的 BGL 数",
    )
    reproducibility.add_argument(
        "--tables",
        nargs="+",
        choices=SUPPORTED_TABLES,
        default=list(SUPPORTED_TABLES),
        help="要审计的读取器表（默认 VOR、NDB、航点、航路）",
    )
    reproducibility.add_argument("--output", help="可选的本地诊断 JSON 输出路径")
    bgl_layout = sub.add_parser(
        "bgl-layout-audit",
        help="只读比较候选与参考 BGL 的文件和节表布局，不导出导航记录",
    )
    bgl_layout.add_argument("--candidate", required=True, help="候选包根目录")
    bgl_layout.add_argument(
        "--reference",
        help="Default navdata 2608R1 参考包根目录；省略时自动检测",
    )
    bgl_layout.add_argument("--output", help="可选的本地 BGL 布局审计 JSON 输出路径")
    convergence = sub.add_parser(
        "file-convergence-audit",
        help="只读建立候选、重复候选与参考包的逐文件收敛看板，不导出导航记录",
    )
    convergence.add_argument("--candidate", required=True, help="候选包根目录")
    convergence.add_argument(
        "--reference",
        help="Default navdata 2608R1 参考包根目录；省略时自动检测",
    )
    convergence.add_argument(
        "--repeat-candidate",
        help="可选的同输入重复候选，用于逐文件重放确定性比较",
    )
    convergence.add_argument("--output", required=True, help="本地收敛看板 JSON 输出路径")
    package_metadata = sub.add_parser(
        "package-derived-metadata-audit",
        help="只读归因 Package Tool 派生包元数据，不读取参考导航 payload",
    )
    package_metadata.add_argument("--candidate", required=True, help="候选包根目录")
    package_metadata.add_argument(
        "--reference",
        help="Default navdata 2608R1 参考包根目录；省略时自动检测",
    )
    package_metadata.add_argument(
        "--output",
        required=True,
        help="本地派生元数据审计 JSON 输出路径",
    )
    airport_bgl_cardinality = sub.add_parser(
        "airport-bgl-cardinality-audit",
        help="只读比较机场 BGL 节表基数与 NavModel 区域来源计数，不读取参考记录",
    )
    airport_bgl_cardinality.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    airport_bgl_cardinality.add_argument("--candidate", required=True, help="候选包根目录")
    airport_bgl_cardinality.add_argument(
        "--reference",
        help="Default navdata 2608R1 参考包根目录；省略时自动检测",
    )
    airport_bgl_cardinality.add_argument(
        "--output",
        required=True,
        help="本地机场 BGL 节表基数审计 JSON 输出路径",
    )
    enroute_bgl_cardinality = sub.add_parser(
        "enroute-bgl-cardinality-audit",
        help="只读比较航路 BGL 节表基数与 NavModel 来源规模，不读取参考记录",
    )
    enroute_bgl_cardinality.add_argument("--model", required=True)
    enroute_bgl_cardinality.add_argument("--candidate", required=True)
    enroute_bgl_cardinality.add_argument("--reference")
    enroute_bgl_cardinality.add_argument("--output", required=True)
    model_replay = sub.add_parser(
        "model-replay-audit",
        help="只读比较两个 NavModel 快照，并以精确路径和哈希执行白名单门禁",
    )
    model_replay.add_argument("--baseline", required=True, help="冻结的 NavModel 快照")
    model_replay.add_argument("--replay", required=True, help="待验证的 NavModel 快照")
    model_replay.add_argument("--output", required=True, help="本地模型重放审计 JSON 输出路径")
    model_replay.add_argument(
        "--allowlist",
        help="可选的精确差异白名单 JSON；每项必须含路径和两侧 SHA-256",
    )
    model_replay.add_argument(
        "--fail-on-unexpected",
        action="store_true",
        help="存在白名单外模型差异时返回非零，供自动化门禁使用",
    )
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
    endpoint_audit = sub.add_parser(
        "airway-endpoint-audit",
        help="只读审计因来源区域未决而无法投影的航路端点",
    )
    endpoint_audit.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    endpoint_audit.add_argument("--output", required=True, help="本地诊断 JSON 输出路径")
    endpoint_card = sub.add_parser(
        "airway-endpoint-card-audit",
        help="只读复核一条精确指定点航路端点的 424 FIR/ACC/邻接证据",
    )
    endpoint_card.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    endpoint_card.add_argument("--model", required=True)
    endpoint_card.add_argument("--ident", required=True)
    endpoint_card.add_argument("--output", required=True, help="本地诊断 JSON 输出路径")
    non_designated_endpoint_card = sub.add_parser(
        "non-designated-airway-endpoint-card-audit",
        help="只读复核地名点等非指定点航路端点，禁止跨类型补写身份",
    )
    non_designated_endpoint_card.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    non_designated_endpoint_card.add_argument("--model", required=True)
    non_designated_endpoint_card.add_argument("--ident", required=True)
    non_designated_endpoint_card.add_argument("--endpoint-type", required=True)
    non_designated_endpoint_card.add_argument(
        "--output",
        required=True,
        help="本地诊断 JSON 输出路径",
    )
    airport_inventory = sub.add_parser(
        "airport-source-inventory",
        help="只读盘点 NavModel 中可用于机场 BGL 的来源对象与拒绝边界",
    )
    airport_inventory.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    airport_inventory.add_argument(
        "--candidate-xml",
        help="可选的当前候选机场 XML；仅统计自身 XML 标签，不读取参考 BGL",
    )
    airport_inventory.add_argument(
        "--output",
        required=True,
        help="本地机场来源对象库存 JSON 输出路径",
    )
    source_model_completeness = sub.add_parser(
        "source-model-completeness-audit",
        help="只读盘点已解析 424 字段组与 NavModel 消费边界",
    )
    source_model_completeness.add_argument(
        "--raw-root",
        required=True,
        help="2608 原始 CSV/PDF 目录；只读取声明的 CSV 字段组",
    )
    source_model_completeness.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    source_model_completeness.add_argument(
        "--output",
        required=True,
        help="本地来源完整性库存 JSON 输出路径",
    )
    airspace_source = sub.add_parser(
        "airspace-source-audit",
        help="只读复核 424 管制区、限制区与特别空域关系",
    )
    airspace_source.add_argument(
        "--raw-root",
        required=True,
        help="2608 原始 CSV/PDF 目录",
    )
    airspace_source.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    airspace_source.add_argument(
        "--output",
        required=True,
        help="本地空域关系审计 JSON 输出路径",
    )
    general_doc_source = sub.add_parser(
        "general-doc-source-audit",
        help="只读复核 424 GENERAL_DOC 目录元数据与 PDF 文件关系",
    )
    general_doc_source.add_argument(
        "--raw-root",
        required=True,
        help="2608 原始 CSV/PDF 目录",
    )
    general_doc_source.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    general_doc_source.add_argument(
        "--output",
        required=True,
        help="本地 GENERAL_DOC 关系审计 JSON 输出路径",
    )
    route_restrict_source = sub.add_parser(
        "route-restrict-source-audit",
        help="???? 424 ROUTE_RESTRICT ? ROUTE_RESTRICT_RTE ???????",
    )
    route_restrict_source.add_argument(
        "--raw-root",
        required=True,
        help="2608 ?? CSV/PDF ??",
    )
    route_restrict_source.add_argument(
        "--model",
        required=True,
        help="??? NavModel ???JSON ? JSON.GZ?",
    )
    route_restrict_source.add_argument(
        "--output",
        required=True,
        help="?? ROUTE_RESTRICT ???? JSON ????",
    )
    route_holding_source = sub.add_parser(
        "route-holding-source-audit",
        help="只读审计 424 ROUTE_HOLDING 的固定点关系与默认数据作用域",
    )
    route_holding_source.add_argument(
        "--raw-root",
        required=True,
        help="2608 原始 CSV/PDF 目录",
    )
    route_holding_source.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    route_holding_source.add_argument(
        "--output",
        required=True,
        help="本地 ROUTE_HOLDING 来源审计 JSON 输出路径",
    )
    unclassified_procedure_audit = sub.add_parser(
        "unclassified-procedure-audit",
        help="只读审计未分类程序段的直接 424/PDF 证据与目标拒绝边界",
    )
    unclassified_procedure_audit.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    unclassified_procedure_audit.add_argument(
        "--output",
        required=True,
        help="本地未分类程序审计 JSON 输出路径",
    )
    unclassified_procedure_card_audit = sub.add_parser(
        "unclassified-procedure-card-audit",
        help="只读审计一张精确未分类程序卡的直接 PDF 类别证据",
    )
    unclassified_procedure_card_audit.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    unclassified_procedure_card_audit.add_argument(
        "--card",
        required=True,
        help="缺口卡精确键，例如 ZGBS:RNP-0:12:0",
    )
    unclassified_procedure_card_audit.add_argument(
        "--output",
        required=True,
        help="本地未分类程序卡审计 JSON 输出路径",
    )
    default_gap_cards = sub.add_parser(
        "default-gap-cards-audit",
        help="只读汇总默认通用数据候选的航路、航点、IAP 与未分类程序来源缺口卡",
    )
    default_gap_cards.add_argument(
        "--model",
        required=True,
        help="冻结的可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    default_gap_cards.add_argument(
        "--candidate-report",
        required=True,
        help="本工具生成的 candidate conversion-report.json",
    )
    default_gap_cards.add_argument(
        "--iap-primary-source-audit",
        help="可选的本工具 IAP 主段来源审计 JSON；只读绑定已证实的拒绝结论",
    )
    default_gap_cards.add_argument(
        "--output",
        required=True,
        help="本地来源缺口卡 JSON 输出路径",
    )
    iap_primary_source_audit = sub.add_parser(
        "iap-primary-source-audit",
        help="只读审计 IAP 未决组在精确来源数据库编码页中的主段、过渡和复飞证据",
    )
    iap_primary_source_audit.add_argument(
        "--model",
        required=True,
        help="冻结的可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    iap_primary_source_audit.add_argument(
        "--pdf-evidence-cache",
        nargs="+",
        required=True,
        help="一个或多个受审计的 PDF 直接证据缓存 JSON；只允许精确 SourceRef 匹配",
    )
    iap_primary_source_audit.add_argument(
        "--card",
        action="append",
        help="可重复指定的精确 IAP 卡 AIRPORT:LABEL；仅输出所选未决卡并验证仪表图缓存",
    )
    iap_primary_source_audit.add_argument(
        "--output",
        required=True,
        help="本地 IAP 主段来源审计 JSON 输出路径",
    )
    uncached_iap_pdf_audit = sub.add_parser(
        "uncached-iap-pdf-audit",
        help="只读分类 IAP 未缓存原始 PDF 的直接文本证据，不调用 OCR",
    )
    uncached_iap_pdf_audit.add_argument(
        "--inventory",
        required=True,
        help="iap-evidence-cache-coverage-inventory JSON",
    )
    uncached_iap_pdf_audit.add_argument(
        "--raw-root",
        required=True,
        help="当期 424 原始数据根目录",
    )
    uncached_iap_pdf_audit.add_argument(
        "--output",
        required=True,
        help="本地未缓存 IAP PDF 直接文本审计 JSON 输出路径",
    )
    airway_diff = sub.add_parser(
        "airway-diff-audit",
        help="只读分类航路字段差异并生成脱敏的 424 航路序号关联摘要",
    )
    airway_diff.add_argument(
        "--model",
        required=True,
        help="可复用 NavModel 快照（JSON 或 JSON.GZ）",
    )
    airway_diff.add_argument(
        "--semantic-diff",
        required=True,
        help="完整、只读且已脱敏的 airway semantic-diff JSON",
    )
    airway_diff.add_argument(
        "--source-audit",
        help="可选的 source-gap-audit JSON，仅作为脱敏聚合旁证",
    )
    airway_diff.add_argument(
        "--association-sample-limit",
        type=int,
        default=100,
        help="最多输出多少条哈希化关联样本（默认 100）",
    )
    airway_diff.add_argument("--output", help="可选的本地航路差异审计 JSON 输出路径")
    airway_projection_matrix = sub.add_parser(
        "airway-projection-matrix-audit",
        help="只读关联 NavModel 航路腿与候选 XML 的 Route/Previous/Next 序列化",
    )
    airway_projection_matrix.add_argument("--model", required=True)
    airway_projection_matrix.add_argument("--candidate-xml", required=True)
    airway_projection_matrix.add_argument("--output", required=True)
    sdk_matrix = sub.add_parser("sdk-bgl-expression-matrix-audit")
    sdk_matrix.add_argument("--inventory", required=True)
    sdk_matrix.add_argument("--projection-matrix", required=True)
    sdk_matrix.add_argument("--enroute-cardinality", required=True)
    sdk_matrix.add_argument("--connection-probe", required=True)
    sdk_matrix.add_argument("--child-order-probe", required=True)
    sdk_matrix.add_argument("--output", required=True)
    terminal_coordinate = sub.add_parser(
        "terminal-coordinate-audit",
        help="只读分类参考缺失航点在 424 终端坐标页中的来源覆盖",
    )
    terminal_coordinate.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    terminal_coordinate.add_argument(
        "--semantic-diff",
        required=True,
        help="完整、只读且已脱敏的 semantic-diff JSON",
    )
    terminal_coordinate.add_argument(
        "--pdf-cache",
        help="可复用的终端 PDF 解析缓存目录；省略时直接只读解析源 PDF",
    )
    terminal_coordinate.add_argument(
        "--general-doc-cache",
        help="可选：与候选构建相同的 GeneralDoc OCR 缓存根目录",
    )
    terminal_coordinate.add_argument(
        "--general-doc-keypoint-cache-directory",
        default="enr-4.4",
        help="与候选构建相同的 GeneralDoc 4.4 缓存子目录",
    )
    terminal_coordinate.add_argument(
        "--check-retention",
        action="store_true",
        help="额外加载完整来源模型，区分同机场坐标页条目是否被当前保留规则保留",
    )
    terminal_coordinate.add_argument(
        "--output",
        help="可选的本地终端坐标页来源覆盖审计 JSON 输出路径",
    )
    terminal_coordinate_delta = sub.add_parser(
        "terminal-coordinate-delta-audit",
        help="只读分类候选航点字段差异在 424 终端坐标页中的来源覆盖",
    )
    terminal_coordinate_delta.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    terminal_coordinate_delta.add_argument(
        "--semantic-diff",
        required=True,
        help="完整、只读且已脱敏的 semantic-diff JSON",
    )
    terminal_coordinate_delta.add_argument(
        "--pdf-cache",
        help="可复用的终端 PDF 解析缓存目录；省略时直接只读解析源 PDF",
    )
    terminal_coordinate_delta.add_argument(
        "--general-doc-cache",
        help="可选：与候选构建相同的 GeneralDoc OCR 缓存根目录",
    )
    terminal_coordinate_delta.add_argument(
        "--general-doc-keypoint-cache-directory",
        default="enr-4.4",
        help="与候选构建相同的 GeneralDoc 4.4 缓存子目录",
    )
    terminal_coordinate_delta.add_argument(
        "--check-retention",
        action="store_true",
        help="额外加载完整来源模型，区分终端坐标条目是否被当前保留规则保留",
    )
    terminal_coordinate_delta.add_argument(
        "--output",
        help="可选的本地终端坐标页字段差异审计 JSON 输出路径",
    )
    general_doc_keypoint = sub.add_parser(
        "general-doc-keypoint-audit",
        help="只读分类参考缺失全局航点在 ENR 4.4 关键点 OCR 证据中的来源覆盖",
    )
    general_doc_keypoint.add_argument("--raw", help="2608 原始 CSV/PDF 目录")
    general_doc_keypoint.add_argument(
        "--semantic-diff",
        required=True,
        help="完整、只读且已脱敏的 semantic-diff JSON",
    )
    general_doc_keypoint.add_argument(
        "--general-doc-cache",
        required=True,
        help="已校验 SHA-256 的 GeneralDoc OCR 缓存根目录",
    )
    general_doc_keypoint.add_argument(
        "--general-doc-keypoint-cache-directory",
        default="enr-4.4",
        help="GeneralDoc 4.4 关键点 OCR 缓存子目录",
    )
    general_doc_keypoint.add_argument(
        "--output",
        help="可选的本地 GeneralDoc 关键点来源覆盖审计 JSON 输出路径",
    )
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
        choices=("llamacpp-direct", "llamacpp", "deepseek"),
        default="llamacpp-direct",
        help="OCR 后端；默认使用内置 llama.cpp 请求适配器",
    )
    ocr_cache.add_argument(
        "--mode",
        choices=("markdown", "free", "figure", "ocr"),
        default="ocr",
        help="传给 OCR 引擎的识别模式",
    )
    ocr_cache.add_argument("--timeout", type=int, default=180, help="每页 OCR 超时秒数")
    ocr_cache.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="内置 llama.cpp 单页输出 token 上限；写入缓存识别设置",
    )
    ocr_cache.add_argument(
        "--engine-timeout",
        type=int,
        help="可选：覆盖本地 OCR 引擎单页等待秒数",
    )
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
    ocr_cache.add_argument(
        "--runtime-profile-file",
        help="由本地 OCR 服务启动脚本生成的可验证运行时描述 JSON",
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
    ad219_ndb_cache = sub.add_parser(
        "ad219-ndb-ocr-cache",
        help="为机场非索引 PDF 建立带 SHA-256 的 AD 2.19 NDB OCR 证据缓存",
    )
    ad219_ndb_cache.add_argument("--source-root", required=True, help="424 原始数据根目录")
    ad219_ndb_cache.add_argument("--cache-root", required=True, help="本地 AD 2.19 NDB OCR 缓存根目录")
    ad219_ndb_cache.add_argument(
        "--airports",
        nargs="*",
        default=[],
        help="可选：仅识别指定 ICAO 机场目录",
    )
    ad219_ndb_cache.add_argument("--ocr-command", default="ocr-skill", help="本地 OCR CLI 命令")
    ad219_ndb_cache.add_argument(
        "--backend",
        choices=("llamacpp-direct", "llamacpp", "deepseek"),
        default="llamacpp-direct",
        help="OCR 后端；默认使用内置 llama.cpp 请求适配器",
    )
    ad219_ndb_cache.add_argument(
        "--mode",
        choices=("markdown", "free", "figure", "ocr"),
        default="ocr",
        help="传给 OCR 引擎的识别模式",
    )
    ad219_ndb_cache.add_argument("--timeout", type=int, default=240, help="每页 OCR 超时秒数")
    ad219_ndb_cache.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="内置 llama.cpp 单页输出 token 上限；写入缓存识别设置",
    )
    ad219_ndb_cache.add_argument("--engine-timeout", type=int, help="可选：本地 OCR 引擎单页等待秒数")
    ad219_ndb_cache.add_argument("--render-scale", type=float, default=3.0, help="PDF 页面渲染比例")
    ad219_ndb_cache.add_argument(
        "--image-profile",
        choices=("original", "autocontrast-grayscale"),
        default="original",
        help="渲染后的固定图像预处理",
    )
    ad219_ndb_cache.add_argument(
        "--runtime-profile",
        default="",
        help="可选的本地 OCR 运行时标识",
    )
    ad219_ndb_cache.add_argument(
        "--runtime-profile-file",
        help="由本地 OCR 服务启动脚本生成的可验证运行时描述 JSON",
    )
    ad219_ndb_cache.add_argument("--limit", type=int, help="只处理排序后的前 N 个 PDF")
    ad219_ndb_cache.add_argument("--force", action="store_true", help="重新识别已有有效页面")
    ad219_ndb_cache.add_argument("--retries", type=int, default=2, help="单页 OCR 失败后的重试次数")
    ad219_ndb_cache.add_argument("--dry-run", action="store_true", help="只输出计划，不调用 OCR")
    ad219_ndb_audit = sub.add_parser(
        "ad219-ndb-ocr-audit",
        help="只读对账 AD 2.19 NDB OCR 缓存与直接 424 NDB.csv",
    )
    ad219_ndb_audit.add_argument("--source-root", required=True, help="424 原始数据根目录")
    ad219_ndb_audit.add_argument("--cache-root", required=True, help="本地 AD 2.19 NDB OCR 缓存根目录")
    ad219_ndb_audit.add_argument(
        "--airports",
        nargs="*",
        default=[],
        help="可选：只审计指定 ICAO 机场目录",
    )
    ad219_ndb_audit.add_argument(
        "--coordinate-tolerance-nm",
        type=float,
        default=0.02,
        help="与直接 424 NDB.csv 对账的坐标阈值（海里）",
    )
    ad219_ndb_audit.add_argument("--output", help="可选的本地 JSON 审计输出路径")
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
        choices=("llamacpp-direct", "llamacpp", "deepseek"),
        default="llamacpp-direct",
        help="OCR 后端；默认使用内置 llama.cpp 请求适配器",
    )
    iap_ocr_cache.add_argument(
        "--mode",
        choices=("markdown", "free", "figure", "ocr"),
        default="ocr",
        help="传给 OCR 引擎的识别模式；IAP 角色识别默认 ocr",
    )
    iap_ocr_cache.add_argument("--timeout", type=int, default=240, help="每页 OCR 超时秒数")
    iap_ocr_cache.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="内置 llama.cpp 单页输出 token 上限；写入缓存识别设置",
    )
    iap_ocr_cache.add_argument(
        "--engine-timeout",
        type=int,
        help="可选：覆盖本地 OCR 引擎单页等待秒数",
    )
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
    iap_ocr_cache.add_argument(
        "--runtime-profile-file",
        help="由本地 OCR 服务启动脚本生成的可验证运行时描述 JSON",
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
    route_fragment_probe = sub.add_parser(
        "route-fragment-probe",
        help="以合成航路验证 SDK 的片段和类型编码，不修改转换候选",
    )
    route_fragment_probe.add_argument(
        "--output",
        required=True,
        help="新的本地诊断目录",
    )
    route_fragment_probe.add_argument(
        "--bglcomp",
        help="合法 fspackagetool.exe 路径；未提供时自动探测",
    )
    route_fragment_probe.add_argument(
        "--reader",
        help="本机 Navdatareader.exe 路径",
    )
    route_fragment_probe.add_argument(
        "--cache-root",
        help="纯 ASCII 的本地读取器暂存目录",
    )
    route_fragment_probe.add_argument(
        "--build-timeout",
        type=int,
        default=3600,
        help="Package Tool 构建超时秒数（默认 3600）",
    )
    route_fragment_probe.add_argument(
        "--reader-timeout",
        type=int,
        default=DEFAULT_READER_TIMEOUT_SECONDS,
        help=f"读取器超时秒数（默认 {DEFAULT_READER_TIMEOUT_SECONDS}）",
    )
    connection_shape_probe = sub.add_parser(
        "airway-connection-shape-probe",
        help="以合成 Route 连接形态验证 SDK 航路几何编码，不修改转换候选",
    )
    connection_shape_probe.add_argument(
        "--output",
        required=True,
        help="新的本地诊断目录",
    )
    connection_shape_probe.add_argument(
        "--bglcomp",
        help="合法 fspackagetool.exe 路径；未提供时自动探测",
    )
    connection_shape_probe.add_argument(
        "--reader",
        help="本机 Navdatareader.exe 路径",
    )
    connection_shape_probe.add_argument(
        "--cache-root",
        help="纯 ASCII 的本地读取器暂存目录",
    )
    connection_shape_probe.add_argument(
        "--build-timeout",
        type=int,
        default=3600,
        help="Package Tool 构建超时秒数（默认 3600）",
    )
    connection_shape_probe.add_argument(
        "--reader-timeout",
        type=int,
        default=DEFAULT_READER_TIMEOUT_SECONDS,
        help=f"读取器超时秒数（默认 {DEFAULT_READER_TIMEOUT_SECONDS}）",
    )
    coordinate_precision_probe = sub.add_parser(
        "airway-coordinate-precision-probe",
        help="以合成航路端点验证 SDK 坐标和包围盒编码，不修改转换候选",
    )
    coordinate_precision_probe.add_argument(
        "--output",
        required=True,
        help="新的本地诊断目录",
    )
    coordinate_precision_probe.add_argument(
        "--bglcomp",
        help="合法 fspackagetool.exe 路径；未提供时自动探测",
    )
    coordinate_precision_probe.add_argument(
        "--reader",
        help="本机 Navdatareader.exe 路径",
    )
    coordinate_precision_probe.add_argument(
        "--cache-root",
        help="纯 ASCII 的本地读取器暂存目录",
    )
    coordinate_precision_probe.add_argument(
        "--build-timeout",
        type=int,
        default=3600,
        help="Package Tool 构建超时秒数（默认 3600）",
    )
    coordinate_precision_probe.add_argument(
        "--reader-timeout",
        type=int,
        default=DEFAULT_READER_TIMEOUT_SECONDS,
        help=f"读取器超时秒数（默认 {DEFAULT_READER_TIMEOUT_SECONDS}）",
    )
    route_child_order_probe = sub.add_parser(
        "airway-route-child-order-probe",
        help="验证同一 Route 的 Next/Previous 子节点顺序是否影响 SDK 航路记录",
    )
    route_child_order_probe.add_argument("--output", required=True, help="新的探针诊断目录")
    route_child_order_probe.add_argument("--bglcomp", help="MSFS 2024 SDK Package Tool 路径")
    route_child_order_probe.add_argument("--reader", help="本机 Navdatareader.exe 路径")
    route_child_order_probe.add_argument("--cache-root", help="纯 ASCII 的读取器临时目录")
    route_child_order_probe.add_argument(
        "--build-timeout",
        type=int,
        default=3600,
        help="SDK 构建超时秒数（默认 3600）",
    )
    route_child_order_probe.add_argument(
        "--reader-timeout",
        type=int,
        default=DEFAULT_READER_TIMEOUT_SECONDS,
        help="读取器超时秒数",
    )
    coordinate_precision_audit = sub.add_parser(
        "airway-coordinate-precision-audit",
        help="只读审计 424 DMS 航路坐标在 SDK float32 前是否被 6 位格式化改变",
    )
    coordinate_precision_audit.add_argument(
        "--raw",
        help="2608 原始 CSV/PDF 目录",
    )
    coordinate_precision_audit.add_argument(
        "--output",
        required=True,
        help="本地只读审计 JSON 输出路径",
    )
    ocr_runtime_probe = sub.add_parser(
        "ocr-runtime-probe",
        help="重复调用本机 OCR 并比较不含文本的语义摘要",
    )
    ocr_runtime_probe.add_argument("--pdf", required=True, help="待识别 PDF")
    ocr_runtime_probe.add_argument(
        "--runtime-profile-file",
        required=True,
        help="由 start_local_ocr_server.ps1 写入的运行时描述",
    )
    ocr_runtime_probe.add_argument(
        "--output",
        required=True,
        help="本地只读审计 JSON 输出路径",
    )
    ocr_runtime_probe.add_argument(
        "--ocr-command",
        default="ocr-skill",
        help="OCR 命令或可执行文件路径",
    )
    ocr_runtime_probe.add_argument(
        "--runs",
        type=int,
        default=2,
        help="重复次数，至少为 2",
    )
    ocr_runtime_probe.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="每次 OCR 的超时秒数",
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
        model_path = _path(args.model)
        model = load_model(model_path) if model_path else None
        baseline_db = _path(args.baseline_db)
        if args.preserve_package_tool_times and model is None:
            raise SystemExit("--preserve-package-tool-times 必须与 --model 一起使用")
        if model is None:
            raw, base, jepp, reference = _defaults(args)
        else:
            detected = detect_paths()
            raw = _path(args.raw) or detected.raw_root or model.root
            base = _path(args.nav_base) or detected.nav_base
            jepp = _path(args.nav_jepp) or detected.nav_jepp
            reference = _path(args.reference) or detected.reference_root
            if not base or not jepp:
                raise SystemExit("无法自动检测 navigraph-nav-base 或 navigraph-nav-jepp，请显式传参")
            if baseline_db is None:
                raise SystemExit(
                    "使用 --model 构建必须传入已校验的 --baseline-db 官方设施索引 SQLite"
                )
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
            general_doc_airway_cache_directories=tuple(
                args.general_doc_airway_cache_directories
            ),
            iap_ocr_cache_roots=tuple(
                Path(value) for value in args.iap_ocr_cache_roots
            ),
            baseline_db=baseline_db,
            baseline_tolerance_nm=args.baseline_tolerance_nm,
            model=model,
            model_path=model_path,
            normalize_package_tool_times=not args.preserve_package_tool_times,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "export-model":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        report = export_intermediate_model(
            raw,
            Path(args.output),
            pdf_cache=_path(args.pdf_cache),
            general_doc_cache=_path(args.general_doc_cache),
            general_doc_key_point_cache_directory=args.general_doc_keypoint_cache_directory,
            general_doc_airway_cache_directories=tuple(
                args.general_doc_airway_cache_directories
            ),
            iap_ocr_cache_roots=tuple(
                Path(value) for value in args.iap_ocr_cache_roots
            ),
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
            expected_candidate_bgl_count=args.candidate_bgl_count,
            expected_reference_bgl_count=args.reference_bgl_count,
            tables=args.tables,
            sample_limit=args.sample_limit,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_semantic_diff(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "semantic-reproducibility-audit":
        report = semantic_reproducibility_audit(
            [Path(value) for value in args.databases],
            expected_bgl_count=args.bgl_count,
            tables=args.tables,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_semantic_reproducibility_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "bgl-layout-audit":
        reference = _path(args.reference) or detect_paths().reference_root
        if not reference:
            raise SystemExit("无法自动检测 Default navdata 2608R1 参考目录，请显式传入 --reference")
        report = audit_bgl_layouts(Path(args.candidate), reference)
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_bgl_layout_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "file-convergence-audit":
        reference = _path(args.reference) or detect_paths().reference_root
        if not reference:
            raise SystemExit("无法自动检测 Default navdata 2608R1 参考目录，请显式传入 --reference")
        output = Path(args.output).expanduser().resolve()
        report = audit_file_convergence(
            Path(args.candidate),
            reference,
            repeat_candidate_root=_path(args.repeat_candidate),
        )
        report["output"] = str(output)
        write_file_convergence_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "package-derived-metadata-audit":
        reference = _path(args.reference) or detect_paths().reference_root
        if not reference:
            raise SystemExit("无法自动检测 Default navdata 2608R1 参考目录，请显式传入 --reference")
        output = Path(args.output).expanduser().resolve()
        report = audit_package_derived_metadata(Path(args.candidate), reference)
        report["output"] = str(output)
        write_package_derived_metadata_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airport-bgl-cardinality-audit":
        reference = _path(args.reference) or detect_paths().reference_root
        if not reference:
            raise SystemExit("无法自动检测 Default navdata 2608R1 参考目录，请显式传入 --reference")
        model_path = Path(args.model).expanduser().resolve()
        output = Path(args.output).expanduser().resolve()
        report = audit_airport_bgl_cardinality(
            load_model(model_path),
            Path(args.candidate),
            reference,
            model_path=model_path,
        )
        report["output"] = str(output)
        write_airport_bgl_cardinality_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "enroute-bgl-cardinality-audit":
        reference = _path(args.reference) or detect_paths().reference_root
        if not reference:
            raise SystemExit("无法自动检测 Default navdata 2608R1 参考目录，请显式传入 --reference")
        model_path = Path(args.model).expanduser().resolve()
        output = Path(args.output).expanduser().resolve()
        report = audit_enroute_bgl_cardinality(
            load_model(model_path),
            Path(args.candidate),
            reference,
            model_path=model_path,
        )
        report["output"] = str(output)
        write_enroute_bgl_cardinality_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "model-replay-audit":
        output = Path(args.output).expanduser().resolve()
        allowlist = (
            load_difference_allowlist(Path(args.allowlist))
            if args.allowlist
            else ()
        )
        report = audit_model_replay(
            load_model(Path(args.baseline)),
            load_model(Path(args.replay)),
            allowed_differences=allowlist,
        )
        report["output"] = str(output)
        write_model_replay_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        if args.fail_on_unexpected and report["unexpected_difference_count"]:
            return 1
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
    if args.command == "airway-endpoint-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        report = audit_unresolved_airway_endpoints(
            load_naip(raw, include_terminal_documents=False)
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_unresolved_airway_endpoint_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-endpoint-card-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        output = Path(args.output).expanduser().resolve()
        report = audit_airway_endpoint_card(
            raw,
            load_model(Path(args.model)),
            ident=args.ident,
        )
        report["output"] = str(output)
        write_airway_endpoint_card_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "non-designated-airway-endpoint-card-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        output = Path(args.output).expanduser().resolve()
        report = audit_non_designated_airway_endpoint_card(
            raw,
            load_model(Path(args.model)),
            ident=args.ident,
            endpoint_type=args.endpoint_type,
        )
        report["output"] = str(output)
        write_airway_endpoint_card_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airport-source-inventory":
        report = build_airport_source_inventory(
            load_model(Path(args.model)),
            candidate_xml=_path(args.candidate_xml),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_airport_source_inventory(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "source-model-completeness-audit":
        report = audit_source_model_completeness(
            Path(args.raw_root),
            load_model(Path(args.model)),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_source_model_completeness_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airspace-source-audit":
        report = audit_airspace_source(
            Path(args.raw_root),
            load_model(Path(args.model)),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_airspace_source_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "general-doc-source-audit":
        report = audit_general_doc_source(
            Path(args.raw_root),
            load_model(Path(args.model)),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_general_doc_source_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "route-restrict-source-audit":
        report = audit_route_restrict_source(
            Path(args.raw_root),
            load_model(Path(args.model)),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_route_restrict_source_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "route-holding-source-audit":
        report = audit_route_holding_source(
            Path(args.raw_root),
            load_model(Path(args.model)),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_route_holding_source_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "unclassified-procedure-audit":
        report = audit_unclassified_procedures(load_model(Path(args.model)))
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_unclassified_procedure_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "unclassified-procedure-card-audit":
        report = audit_unclassified_procedure_card(
            load_model(Path(args.model)),
            args.card,
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_unclassified_procedure_card_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "default-gap-cards-audit":
        report = audit_default_gap_cards(
            load_model(Path(args.model)),
            Path(args.candidate_report),
            iap_primary_source_audit_path=_path(args.iap_primary_source_audit),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_default_gap_cards(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "iap-primary-source-audit":
        report = audit_iap_primary_sources(
            load_model(Path(args.model)),
            [Path(path) for path in args.pdf_evidence_cache],
            card_keys=args.card,
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_iap_primary_source_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "uncached-iap-pdf-audit":
        report = audit_uncached_iap_pdfs(
            Path(args.inventory),
            Path(args.raw_root),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_uncached_iap_pdf_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-diff-audit":
        report = audit_airway_differences(
            load_model(Path(args.model)),
            load_airway_diff_report(Path(args.semantic_diff)),
            source_audit=(
                load_source_audit(Path(args.source_audit))
                if args.source_audit
                else None
            ),
            association_sample_limit=args.association_sample_limit,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_airway_diff_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-projection-matrix-audit":
        report = audit_airway_projection_matrix(
            load_model(Path(args.model)),
            Path(args.candidate_xml),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_airway_projection_matrix_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "sdk-bgl-expression-matrix-audit":
        report = audit_sdk_bgl_expression_matrix(
            Path(args.inventory), Path(args.projection_matrix),
            Path(args.enroute_cardinality), Path(args.connection_probe),
            Path(args.child_order_probe),
        )
        output = Path(args.output).expanduser().resolve()
        report["output"] = str(output)
        write_sdk_bgl_expression_matrix(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "terminal-coordinate-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        pdf_cache = _path(args.pdf_cache)
        model = load_naip(
            raw,
            pdf_cache=pdf_cache,
            general_doc_cache=_path(args.general_doc_cache),
            general_doc_key_point_cache_directory=(
                args.general_doc_keypoint_cache_directory
            ),
            include_terminal_documents=False,
        )
        _load_terminal_coordinate_pages(model, pdf_cache)
        retained_terminal_waypoints = None
        if args.check_retention:
            retained_model = load_naip(
                raw,
                pdf_cache=pdf_cache,
                general_doc_cache=_path(args.general_doc_cache),
                general_doc_key_point_cache_directory=(
                    args.general_doc_keypoint_cache_directory
                ),
            )
            retained_terminal_waypoints = retained_model.terminal_waypoints
        report = audit_terminal_coordinate_reference_coverage(
            model,
            load_semantic_diff(Path(args.semantic_diff)),
            retained_terminal_waypoints=retained_terminal_waypoints,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_source_gap_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "terminal-coordinate-delta-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        pdf_cache = _path(args.pdf_cache)
        model = load_naip(
            raw,
            pdf_cache=pdf_cache,
            general_doc_cache=_path(args.general_doc_cache),
            general_doc_key_point_cache_directory=(
                args.general_doc_keypoint_cache_directory
            ),
            include_terminal_documents=False,
        )
        _load_terminal_coordinate_pages(model, pdf_cache)
        retained_terminal_waypoints = None
        if args.check_retention:
            retained_model = load_naip(
                raw,
                pdf_cache=pdf_cache,
                general_doc_cache=_path(args.general_doc_cache),
                general_doc_key_point_cache_directory=(
                    args.general_doc_keypoint_cache_directory
                ),
            )
            retained_terminal_waypoints = retained_model.terminal_waypoints
        report = audit_terminal_coordinate_field_delta_coverage(
            model,
            load_semantic_diff(Path(args.semantic_diff)),
            retained_terminal_waypoints=retained_terminal_waypoints,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            report["output"] = str(output)
            write_source_gap_audit(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "general-doc-keypoint-audit":
        raw = _path(args.raw) or detect_paths().raw_root
        if not raw:
            raise SystemExit("无法自动检测 424 原始目录，请显式传入 --raw")
        report = audit_general_document_key_point_reference_coverage(
            load_naip(raw, include_terminal_documents=False),
            load_semantic_diff(Path(args.semantic_diff)),
            source_root=raw,
            cache_root=Path(args.general_doc_cache).expanduser(),
            cache_directory=args.general_doc_keypoint_cache_directory,
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
            runtime_profile=resolve_runtime_profile(
                args.runtime_profile,
                _path(args.runtime_profile_file),
            ),
            engine_timeout_seconds=args.engine_timeout,
            max_tokens=args.max_tokens,
            retries=args.retries,
        )
        print(json.dumps(report.to_report(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "ad219-ndb-ocr-cache":
        report = build_ad219_ndb_ocr_cache(
            Path(args.source_root),
            Path(args.cache_root),
            airports=args.airports,
            command=args.ocr_command,
            backend=args.backend,
            mode=args.mode,
            timeout_seconds=args.timeout,
            render_scale=args.render_scale,
            image_profile=args.image_profile,
            runtime_profile=resolve_runtime_profile(
                args.runtime_profile,
                _path(args.runtime_profile_file),
            ),
            engine_timeout_seconds=args.engine_timeout,
            max_tokens=args.max_tokens,
            force=args.force,
            limit=args.limit,
            retries=args.retries,
            dry_run=args.dry_run,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "ad219-ndb-ocr-audit":
        report = audit_ad219_ndb_ocr(
            Path(args.source_root),
            Path(args.cache_root),
            airports=args.airports,
            coordinate_tolerance_nm=args.coordinate_tolerance_nm,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            write_ad219_ndb_ocr_audit(output, report)
            report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
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
            runtime_profile=resolve_runtime_profile(
                args.runtime_profile,
                _path(args.runtime_profile_file),
            ),
            engine_timeout_seconds=args.engine_timeout,
            max_tokens=args.max_tokens,
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
    if args.command == "route-fragment-probe":
        report = run_route_fragment_probe(
            Path(args.output),
            compiler=find_compiler(_path(args.bglcomp)),
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            build_timeout_seconds=args.build_timeout,
            reader_timeout_seconds=args.reader_timeout,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-connection-shape-probe":
        report = run_airway_connection_shape_probe(
            Path(args.output),
            compiler=find_compiler(_path(args.bglcomp)),
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            build_timeout_seconds=args.build_timeout,
            reader_timeout_seconds=args.reader_timeout,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-coordinate-precision-probe":
        report = run_airway_coordinate_precision_probe(
            Path(args.output),
            compiler=find_compiler(_path(args.bglcomp)),
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            build_timeout_seconds=args.build_timeout,
            reader_timeout_seconds=args.reader_timeout,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-route-child-order-probe":
        compiler = find_compiler(_path(args.bglcomp))
        report = run_airway_route_child_order_probe(
            Path(args.output),
            compiler=compiler,
            reader=_path(args.reader),
            cache_root=_path(args.cache_root),
            build_timeout_seconds=args.build_timeout,
            reader_timeout_seconds=args.reader_timeout,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "airway-coordinate-precision-audit":
        detected = detect_paths()
        raw = _path(args.raw) or detected.raw_root
        if raw is None:
            raise SystemExit("无法自动检测 2608 原始目录，请显式传入 --raw")
        report = write_source_airway_coordinate_precision_audit(
            raw,
            Path(args.output),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "ocr-runtime-probe":
        output = Path(args.output).expanduser().resolve()
        report = run_ocr_runtime_probe(
            Path(args.pdf),
            Path(args.runtime_profile_file),
            ocr_command=args.ocr_command,
            runs=args.runs,
            timeout_seconds=args.timeout_seconds,
        )
        report["output"] = str(output)
        write_ocr_runtime_probe(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report["summary"]["repeatable"] else 1
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
