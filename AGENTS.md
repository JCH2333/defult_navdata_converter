# Fenix 默认通用数据转换器协作规则

- 所有用户信息使用中文。
- 424 原始 CSV/PDF 与官方 Community 包只作为本地输入，不提交任何导航数据或生成包；Fenix `nd.db3` 不参与本工具转换。
- 默认包必须保留官方 `nav-base`/`nav-jepp` 全球基线，区域覆盖层独立生成。
- 参考成品只读比较，禁止复制参考 BGL 冒充转换结果。
- 没有版本匹配的 Package Tool、没有本地验证或未完成实机测试时，输出只能标记测试版。
- 覆盖 Community 前必须确认 `FlightSimulator2024.exe` 已退出，并备份目标包与元数据。
- 每次代码/文档改动都要提交并推送 Git；未经实机验证不得创建正式 Release。

## OCR 证据门禁

- 新建 IAP OCR 缓存必须使用内置 `llamacpp-direct` 适配器。该适配器固定请求 `temperature=0`、`seed=2608`、`top_k=1`，并显式提交正整数 `max_tokens`。
- IAP 共识和候选构建必须同时校验 OCR 适配器版本、`max_tokens`、渲染设置与完整运行时模型指纹；旧 `ocr-skill/llamacpp` 缓存只能保留为只读审计证据，不能与新缓存混合作为候选构建证据。

## 2608R1 已确认契约

- 官方全球基线为 Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`，候选复制后分别有 475 和 1752 个文件，2026-08-11 全量 SHA-256 树比较均字节一致。
- 参考成品不是完整全球包，而是 `zzz-pmdg-china-navdata` 与 `zzz-pmdg-china-navdata-airport-patch` 两个中国覆盖包。
- MSFS 2024 SDK 1.5.7 的正式设施编译入口为 `fspackagetool.exe`。2026-08-11 已用一个机场和一条跑道完成真实构建，生成 BGL、`bglIndex.bout`、布局、清单与 ContentInfo。
- Package Tool 项目必须先镜像到纯 ASCII 暂存路径；中文路径会在游戏命令行中损坏并导致 `Main_Z ProgramInit` 启动崩溃。
- `fspackagetool.exe` 可能因 Steam 进程附着竞态先返回非零代码，但后台 `FlightSimulator2024.exe` 仍在构建；必须等待新进程退出，以实际包产物判定成功后再清理暂存目录。
- Package Tool 启动恢复（2608R1，证据：2026-08-14 的 r35/r37 项目输入逐文件 SHA-256 一致；r37 两次调用均退出代码 1、没有新模拟器进程、没有新 Builder 日志或产物）：仅当首次非零退出、完整启动等待期内未发现新的 `FlightSimulator2024.exe` 时，允许以同一纯 ASCII 暂存项目重试一次。发现新进程时仍只能等待其退出并以完整包产物判定；第二次失败不得继续重试。自动化测试：`test_package_tool_retries_one_startup_failure_without_simulator_process`。
- 内容来源为当期 424 `2608` 原始 CSV/PDF，负责机场、跑道、ILS、终端航点、SID/STAR/IAP、航路和等待航线；官方包只负责全球基线和加载契约。
- 中间模型快照（2608R1，证据：`model_io.py`、`export-model`/`build --model` 与 `tests/test_model_io.py`，2026-08-18）：`NavModel` 是 424 CSV/PDF 的可复用来源快照，格式 id 为 `default-navdata-intermediate-model`。BGL/Package Tool 只是其中一个适配器；其他机模适配器应消费该快照，不得再解析 424，也不得读取 Fenix `nd.db3` 或把 OCR 缓存目录当作内容来源。
- SID/STAR SDK 名称去重（2608R1，证据：`bglcomp.xsd` 的 `stString6`/`stString5`、r127 候选 XML 中同一机场 362 个重复 `Departure` 名称、r128 隔离 SDK 构建与独立 `validate`，以及 `tests/test_bgl.py`，2026-08-18）：`Departure`/`Arrival` 名称最长 6 字符，航路过渡名称最长 5 字符。适配器必须在每个机场内为不同的 424 标签分配唯一输出名，优先保留原前缀，冲突时保留变体后缀；不得把 `APAKA-1A`/`APAKA-1B` 都截成 `APAKA-`。该规则只改 BGL 适配器投影，不改 `NavModel`。r128 主包 XML 为 `Departure` 2653/2653、`Arrival` 2794/2794 且每机场 0 重名；r127 为 189 个冲突机场、239 个重复 `Departure` 名（601 次）、208 个重复 `Arrival` 名（566 次）。相对 r127，全部覆盖层 BGL 体积不变、哈希改变；覆盖层文件数仍为 15/15 与 14/14，相对参考仍全部哈希不同。独立 `validate`：`valid=true`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`。回归：`test_unique_limited_ident_preserves_short_names_and_variant_suffixes`、`test_airport_projection_keeps_truncated_sid_star_names_unique`。
- Package Tool 嵌入 magvar 节（默认通用数据、2608R1、MSFS 2024 SDK 1.5.7，证据：577 字节单机场烟雾 XML 编译为 2,359,801 字节 `smoke.bgl`、r128 候选全部机场/航路 BGL、参考 `00_enroute.bgl`、参考机场覆盖 BGL 与官方 `APX`/`NAX` 的 20 字节节表，以及 `tests/test_bgl_format.py`，2026-08-19）：当前 Package Tool 会在每个编译出的 BGL 中写入类型 `0x20`、大小 `2,359,296` 的 magvar 网格（`0x18000` 条 24 字节记录）。参考 `00_enroute.bgl` 同样含该节，因此航路体积接近（候选 2,867,006 对参考 2,910,826，差 43,820）。参考机场覆盖 BGL 与官方 `APX`/`NAX` 不含该节。r128 相对 r127 的 SID/STAR 去重未改变任何 BGL 体积，因此 ZJ/ZH/ZP 大于参考、其余机场分区小于参考，不是名称碰撞导致的编译合并。该网格由 XML 中的 `AiracCycle` 触发。2026-08-19 无 `AiracCycle` 单机场烟雾包编译为 455 字节 `smoke.bgl`，节表仅为 `0x3`/`0x35`，QMID 为区域瓦片 `0x9255e`，`embedded_magvar_size=0`。因此机场分区 XML 不得写入 `AiracCycle`；航路 `00_enroute.xml` 必须保留，以匹配参考航路 BGL 的 `0x20` 节。覆盖层依赖的 `navigraph-nav-base` 已提供官方 `AIRACCycle.bgl`。不得事后剥离 magvar 节。回归：`test_airport_scope_omits_airac_cycle`、`test_enroute_scope_keeps_airac_cycle`、`test_parse_bgl_header_reads_package_tool_magvar_section`、`test_parse_bgl_header_detects_reference_airport_without_magvar`。
- BGL 布局审计（默认通用数据、2608R1，证据：`bgl-layout-audit`、`tests/test_bgl_format.py`，2026-08-19）：审计以参考包的顶层包名确定比较范围，只能输出候选和参考最终包中 BGL 的相对路径、文件大小、SHA-256 相等性以及 BGL 头部版本/QMID/节表类型、计数和尺寸；候选根目录下 SDK `_work` 的中间产物及不在参考范围内的官方依赖副本必须排除，数量记入 `scope`。不得读取或输出参考导航记录，也不得作为任何内容反向来源。它用于将 SDK 编译布局差异与来源投影差异分开，单独的节表差异不构成实机加载或字节一致性结论。回归：`test_bgl_layout_audit_reports_only_file_and_header_contract`、`test_bgl_layout_audit_ignores_sdk_work_area`、`test_bgl_layout_audit_excludes_candidate_support_packages`。
- 机场 SDK 隔离构建布局探针（默认通用数据、2608R1，证据：`scripts/airport_subset_probe.py`、ZUAL 的 `zu-one-runway-only`/`zu-one-full`/`zu-one-with-root-waypoints` Package Tool 构建与 `test_probe_layout_summary_reads_only_bgl_headers`，2026-08-19）：探针报告必须自动记录每个生成 BGL 的文件大小、头部版本、QMID 和节表类型/计数/尺寸，且不得读取参考 BGL 记录。只保留 `ZUAL` 跑道时节为 `0x3/0x13/0x32/0x35`、计数均为 1；保留机场内航点、程序和等待航线时增加 `0x22`/`0x34`、计数为 `1/1/10/1/1/1`；另保留 2,586 个根节点终端点时只使 `0x22` 增至 153，仍不会生成参考机场 BGL 的 `0x17/0x33`。因此不能把根节点终端点重复写入当作参考索引节差异的充分解释，后续只可用隔离 SDK 探针继续验证其他可控输入。
- 机场 SDK 子对象布局反证（默认通用数据、2608R1，证据：`scripts/airport_subset_probe.py` 的 `--append-airport-child`/`--append-root-child`、r140/r141 `ZUAL` Package Tool 构建、`ZBCF` 独立 Navdatareader 读取与 `test_airport_child_specs_are_attribute_only_and_append_in_order`、`test_root_children_reuse_diagnostic_specs_without_reparenting`，2026-08-19）：探针可在不修改 `NavModel` 或正式候选的前提下，按稳定顺序附加属性型 SDK 子对象。`Com`、`Tower`、`Start` 和完整的 `RunwayAlias` 不改变 ZUAL 的 `0x3/0x13/0x22/0x32/0x34/0x35` 布局；完整属性的根节点或机场内 `Ndb` 均稳定增加 `0x17` 与 `0x33` 各一条，因此作用域位置不能解释参考的节计数。`Ndb` 与 `onlyAddIfReplace=TRUE` 组合可产生参考同类节类型集合，但该属性不能作为机场覆盖规则：新增机场 `ZBCF` 的离线读取结果为机场/跑道均 0，仅保留航点与 ILS。该实验只说明 NDB 是两个节的充分触发条件，不说明参考机场 BGL 的数千条记录来自 424 机场关联 NDB：2608 `NDB.csv` 只有 39 条可精确关联中国机场的记录，不能解释参考各分区 2,003 至 3,614 的节计数。不得据此接入机场 NDB 投影；只有获得能同时解释记录数量、作用域与加载契约的独立 424 来源规则后才可实现。
- GeneralDoc 4.1 本地 OCR 重跑（2608R1，证据：2026-08-15 完整 33 页 `llamacpp` 重跑、`ocr-audit`、`ocr-source-audit` 与 `tests/test_ocr_cache.py`、`tests/test_general_docs.py`、`tests/test_source.py`）：缓存必须绑定渲染比例、图像预处理、OCR 命令、后端和模式；不同设置不得混用页面。3 倍渲染的自动对比度灰度缓存解析到 178 条，直接 424 回链为 170 条完全匹配、6 条唯一物理身份 OCR 标识纠正、0 条缺失、0 条冲突，`PA`（第 1 页）和 `HG`（第 24 页）因直接 424 同身份不唯一保持未决。该重跑与 2 倍原图主缓存只有 102 条完全一致，协议一致率为 `0.476636`；因此新缓存仅作诊断，不能替换主缓存、不能参与投影。自动化命令 `ocr-source-audit` 必须输出未决页码和原因。
- GeneralDoc 4.1 3 倍原图 OCR 重跑（2608R1，证据：2026-08-15 完整 33 页本地 `llamacpp` 缓存 `enr-4.1-navaids-rerun-3x-original-20260815`、`ocr-audit`、`ocr-source-audit`）：解析到 177 条，169 条直接 424 完全匹配、6 条唯一物理身份 OCR 标识纠正、0 条缺失、0 条冲突；`PA`（第 1 页）和 `HG`（第 24 页）仍因直接 424 同身份不唯一保持未决。与 2 倍原图主缓存只有 101 条完全一致，协议一致率 `0.471963`，低于 3 倍自动对比度灰度重跑；该缓存同样仅作诊断，不能替换主缓存或参与投影。
- GeneralDoc 4.4 重要点名称代码三倍原图 OCR 重跑（2608R1，证据：2026-08-15 完整 54 页本地 `llamacpp` 缓存 `enr-4.4-rerun-3x-original-20260815`、`keypoint-ocr-audit`、`tests/test_general_docs.py`）：缓存 PDF SHA-256 为 `96ef851d32ab7e2029e862d00fd5e4b59faf5ba5caabf0b3155ae797c50da4b5`。本地模型输出“单元格文字 + 坐标框”且会损坏 DMS 分隔符，因此解析器必须按同一表行的点名、纬度、经度几何关系重建，并仅接受受限的非数字、非 ASCII 字母 DMS 分隔符。该缓存解析 1,513 条，主缓存 2,108 条，交集 1,107 条，协议一致率 `0.440334`；重跑独有 406 条中 326 条可由 424 FIR 多边形安全恢复区域，但缺少独立一致性证明。重跑缓存仅为诊断，`keypoint-ocr-audit` 必须保持 `projection_allowed=false`；不得替换 `enr-4.4` 或参与候选投影。后续候选若要选择非默认缓存，必须显式提供 `--general-doc-keypoint-cache-directory` 并先取得新的来源验收证据。
- GeneralDoc 4.4 三倍原图 `markdown` OCR 复核（2608R1，证据：2026-08-15 完整 54 页本地 `llamacpp` 缓存 `enr-4.4-rerun-3x-markdown-original-20260815`、五页独立重跑 `enr-4.4-rerun-3x-markdown-recheck-pages-9-21-24-26-31-20260815`、`keypoint-ocr-audit --allow-partial-rerun` 与 `tests/test_general_docs.py`）：完整缓存解析 2,108 条，与旧 `enr-4.4` 交集 2,065 条，协议一致率 `0.960019`，差异只在第 9、21、24、26、31 页。五页独立重跑与完整 `markdown` 缓存 160/160 条一致，却与旧缓存仅 117/203 条一致，证明新配置在争议页可重复。仍不得替换主缓存：两套缓存加载后的 GeneralDoc 新航点均为 489、总航点均为 2,647，但各有 2 个互斥投影点；新缓存还产生 1 个 `identity_conflict`。无可证明的来源侧投影增益前，完整和局部 `markdown` 缓存都仅作诊断，局部审计必须显式传入 `--allow-partial-rerun` 且永远不可参与构建。
- 指定点区域优先级（2608R1，证据：`DESIGNATED_POINT.csv`、r54 只读来源审计与 `tests/test_source.py`，2026-08-14）：严格匹配 `Z[A-Z]{3}` 的中国 `SERVICED_AIRPORT` 是指定点最具体的源侧归属，必须优先于 `CODE_FIR`；无有效服务机场时才使用首个源列 FIR、既有空 FIR 覆盖或 FIR 多边形恢复。对 r54 的 335 个“指定点区域不同”来源项，12 个具有严格有效服务机场，其中 9 个与只读参考逻辑区域一致、3 个与原区域一致，未发现第三方区域反例。该规则只选择 424 源区域键，不读取或回填参考字段。自动化测试：`test_waypoint_country_prefers_valid_serviced_airport_over_fir`、`test_load_naip_uses_strict_serviced_airport_prefix_for_blank_waypoint_fir`。
- 官方索引用于区域码恢复前，必须同时验证 VOR、NDB 与 WAYPOINT 三类读取器记录可反向映射到当前 `nav-base`/`nav-jepp` 的中性镜像 BGL；侧车必须记录三类行数与来源统计。缺少 `waypoint.file_id/ident/region/laty/lonx`、来源越界或侧车版本不匹配时，索引不得复用。
- 默认通用数据适配器可仅为 424 中空白的航路端点/指定点恢复区域码：端点类型、标识必须相同，坐标距离不得超过 `0.01 NM`，且命中的官方区域必须唯一。VOR/NDB/指定点不得跨表匹配；歧义、无匹配、无坐标或不支持的端点类型必须保持为空并计入转换报告。对应回归：`test_region_resolution.py`。
- Fenix 解析模块仅保留为历史适配器回归材料，不得从 Fenix `nd.db3` 生成默认通用数据候选。
- Fenix 2608 的增量 VOR 块为 `Navaids.ID=11396..11515`，共 120 条，全部可在参考 `00_enroute.bgl` 中按标识和坐标匹配。参考 BGL 另有 15 条 VOR 与当前 Fenix 块不重合，具体合法来源规则仍待确认。
- 默认通用数据导航台区域冲突（2608R1，证据：54 条 VOR 与 4 条 NDB 的 424 字段审计、r39/r40 只读逻辑身份差分、r48/r49/r51 真实 SDK 构建与 Navdatareader 读取，2026-08-14）：当 `SERVICED_AIRPORT` 前缀与非空 `CODE_FIR` 映射不同，现有 424 标志字段无法判别目标区域；VOR 参考身份中 23 条命中服务机场前缀、5 条命中 FIR、26 条两者均不出现，4 条 NDB 均命中服务机场前缀。它们的 `CODE_IN_AIRWAY`、`PURPOSE`、`IS_REP_ATC`、`ROUTE_RESTRICT`、`IS_TRANS_POINT`、`IS_BORDER_POINT` 组合没有区分力。将单一 FIR 一律置于服务机场之前时，r49/r50 的 `00_enroute.bgl` 会使 Navdatareader 在约 2.78 MB 偏移重复读取 `0x0` 边界记录而不退出；恢复服务机场优先后的 r51 在约一秒完成读取，得到 VOR 121、NDB 133、航点 2555，并与可读取的 r48 生成相同覆盖 BGL。该读取器结果只构成本地诊断，不替代实机验证。不得将“所有显式 FIR 优先”或参考身份例外写成转换规则；当前保留 `r39` 的服务机场优先保守基线，未决差异必须继续标记为来源取证缺口。回归：`test_navaid_country_prefers_serviced_airport_when_fir_conflicts`、`test_navaid_country_rejects_cross_region_fir_without_serviced_airport`。
- 默认通用数据导航台防重（2608R1，证据：424 `VOR.csv` 与经来源校验的官方 VOR/NDB 索引，2026-08-12）：424 与官方记录的 `region` 不可单独作为物理身份键。默认覆盖层先保留区域严格差分报告，再对其“缺失”项按类型、标识、频率和不超过 `0.25 NM` 的坐标作全索引物理匹配；不同区域但唯一物理匹配时必须抑制输出，多个不同实体命中时必须使选择验证失败。该规则只消除已存在的官方实体，绝不从参考成品补写内容。回归：`test_default_navaids.py`、`test_candidate_suppresses_cross_region_official_navaid_duplicate`。
- 默认通用数据 NDB 修订投影（2608R1，证据：424 `NDB.csv` 与经来源校验的官方 NDB 索引，2026-08-12）：仅当直接来自 424 `NDB.csv` 的记录以相同区域、标识、频率和不超过 `0.25 NM` 的坐标唯一匹配官方实体，且坐标、磁差、高程或可表达名称存在差异时，才必须把该 424 原始 NDB 作为覆盖修订投影；官方索引只用于确认物理身份和记录差异，不能反向提供字段。无差异的实体不重复写出，VOR 属性差异仍仅报告、不得借此规则输出；任何严格或物理身份歧义仍会使导航台选择不通过验证。回归：`test_default_selection_projects_source_backed_ndb_property_correction`、`test_default_selection_requires_direct_ndb_csv_provenance_for_correction`、`test_candidate_projects_source_backed_ndb_property_correction`。
- 默认通用数据官方 NDB 保留投影（2608R1，证据：经来源校验的官方 `nav-base`/`nav-jepp` NDB 索引、424 `NDB.csv` 全量物理匹配审计与最小 fixture，2026-08-13）：中国区域官方 NDB 必须在覆盖层中恰好表达一次。直接 `NDB.csv` 的唯一、同区域物理匹配且带可表达属性变化时由 424 修订替换；所有其余中国区域官方 NDB 以原官方字段重新投影为 `official_baseline_preservation`，424 无匹配、跨区域匹配、无变化或来源不满足修订条件时都不得臆造 424 覆盖。424 新增设施仍标记 `raw_424_addition`。单条 424 NDB 对多条官方实体、或多条不同 424 物理身份对同一官方实体时，必须清空本批导航台输出并标记不通过验证；磁差/高程缺失等不能无损投影的官方 NDB 同样拒绝。回归：`test_default_navaids.py` 官方保留、同标识不同实体、跨区域和歧义 fixture，以及 `test_candidate_projects_verified_official_baseline_ndb_preservation`。
- 默认通用数据 SDK 导航台身份冲突（2608R1，证据：Package Tool 实际错误、参考覆盖包 `00_enroute.bgl` 的只读 XML 读取和 424 `NDB.csv` 行 57，2026-08-13）：`NDB/GJ/ZG/245 kHz` 的 424 坐标（`N280426 E1121241`）与官方基线坐标相距约 `0.63 NM`，但 SDK 仍将二者视为同一输出身份并拒绝重复写入；参考覆盖层保留官方基线实体。适配器对该完整 2608R1 来源键使用 `official_baseline_precedence`，抑制 424 新增并在报告中记录冲突；任何未登记的同类冲突必须保持 `unresolved`、清空导航台输出并使验证失败。回归：`test_default_selection_uses_verified_official_precedence_for_2608_gj_conflict`、`test_default_selection_rejects_unlisted_sdk_identity_conflict`。
- IAP 来源审计（2608R1，证据：424 CSV/PDF、版本 34 PDF 证据缓存的冷读与热读、`tests/test_iap_coverage.py`、`r45` SDK 候选验证，2026-08-14）：743 个 IAP 程序分组中 665 个具有唯一且非空的主进近数据库编码段；608 个分组的图页角色已安全利用，其中 373 个由唯一图页确定、233 个由唯一 `MAP/MAPT` 终点完成多图消歧，2 个由唯一多角色证据完成消歧（`ZHNY/R05`、`ZUPL/R15`），1 个只有唯一图页但没有可用角色标记。多图的多角色消歧要求恰好一张图页对至少两个不同数据库腿给出明确角色，至少一个为 `FAF`、`MAP` 或 `MAPT`，且其余候选没有同腿角色证据；单一角色不能消歧。28 个无主段基础标签组仅含同页后缀进近已消费的共享过渡/复飞段，报告必须计为 `shared_section_groups` 而非未决；跨页或无唯一后缀主段时仍拒绝。54 个分组存在多图歧义，2 个没有匹配图页，50 个没有唯一主进近编码段，未决分组合计 106。角色证据计数为 `IAF=1242`、`IF=605`、`FAF=559`、`MAP=1`、`MAPT=548`；未决分组必须拒绝写入不完整进近语义并保留报告计数。回归：`test_iap_coverage_uses_unique_multi_role_evidence_when_final_leg_is_not_mapt`、`test_iap_coverage_does_not_select_a_chart_with_only_one_matching_role`、`test_iap_coverage_does_not_reject_same_page_shared_variant_sections`、`test_iap_coverage_keeps_base_sections_when_variant_is_from_another_page`。
- Navdatareader 语义差分（2608R1，证据：读取器 SQLite 实际 `vor`、`ndb`、`waypoint`、`airway` schema 与最小 SQLite fixture，2026-08-12）：诊断器必须以 SQLite `mode=ro` 打开候选和参考，执行完整性检查，并按稳定逻辑身份报告严格行数、候选新增、候选缺失、字段差异和逻辑身份歧义。报告只能含逻辑身份、字段名、数量和不可逆摘要，不得输出参考坐标、频率、名称或其他可反向写入的字段值；空值与文本混合的身份键也必须确定性排序。回归：`test_semantic_diff.py`。
- Navdatareader 单 BGL 诊断边界（默认通用数据、2608R1，证据：2026-08-16 r67 候选与参考主导航包的 `read-package` 实测；2026-08-17 r88 九机场 `ZU_airports.bgl` 探针）：对 11 个 BGL 的 `*.bgl` 请求，候选读取器只登记 `3/11`，因此必须拒绝全包扫描。逐项仅 `00_enroute.bgl`、`ZG_airports.bgl`、`ZJ_airports.bgl` 在候选和参考两侧都达到 `1/1` 登记；其余 8 个机场分区不得用于语义结论。r88 已在纯 ASCII 临时根目录中同时镜像 `navigraph-nav-base`、`navigraph-nav-jepp`，并将两者映射为可识别的 `Official/Steam/fs-base` 与 `fs-base-nav`；读取器确认发现 Navigraph 更新后，九机场探针仍在相同机场记录偏移报告 `Unexpected record type` 与 `read past file end`。因此基线缺失不是该探针失败原因，且该类离线读取失败不得推导为 SDK 构建失败、MSFS 加载失败或 424 源记录错误。三项单 BGL 差分只是受限诊断，禁止聚合为完整 11 BGL 主包或 21 BGL 双包的覆盖率、字节一致性或实机加载结论。回归：`test_rejects_reader_output_when_not_every_requested_bgl_is_registered`。
- Navdatareader `AIRWAY` 对象过滤限制（默认通用数据、2608R1，证据：2026-08-17 r67/r69/参考 `00_enroute.bgl` 的受控 `read-package`）：读取 `00_enroute.bgl` 时不得传入 `--objects AIRWAY`；该外部读取器过滤会使 `bgl_file` 登记为 `0`，即使不带过滤时同一输入可稳定登记 `1/1`。航路语义差分必须读取完整单 BGL SQLite 后再由 `semantic-diff --tables airway` 选择表，不能把过滤后的零登记误判为 BGL 或候选失败。
- `WaypointLookup` 的主键不是单独的 `ID`；直接连接会把中国程序腿从 69795 条错误展开到 70642 条。加载器必须先按 waypoint ID 归一国家码，对应回归测试为 `test_fenix_loader_uses_fenix_content_and_raw_route_model`。
- 全量 `china-navdata.xml` 为 544433 字节，并通过 SDK `bglcomp.xsd`。没有 BGL、`bglIndex.bout` 和两包元数据时，验证器必须返回 `valid=false`，即使显式允许测试版也不得部署。
- 最小回归覆盖 AIRAC 周期、确定性 XML、SDK 字段格式、候选包完整性、更新版本排序和不完整测试候选的部署拒绝。
- 来源覆盖率限制（2608R1，证据：2026-08-14 r38 真实构建与只读 Navdatareader 语义差分）：候选覆盖层读取为 VOR 120、NDB 133、航路点 2519、航路 4300；参考覆盖层为 VOR 135、NDB 143、航路点 3266、航路 4614。参考侧存在一批逻辑设施标识未能以当前 VOR/NDB 424 加载记录或官方索引的同一物理身份证明。它们必须继续追溯到允许的 424 结构化来源；不得从参考 BGL/SQLite 反向回填。未完成来源证明前，字节级参考一致性与部署均不成立。
- 实机验证仍须检查 ZBCF、ZUNZ、ZUUU 的机场、跑道、SID/STAR/IAP，以及退出飞行和退出模拟器。完成前不得创建正式 Release。
- 来源缺口复核（默认通用数据、2608R1，证据：2026-08-14 `r45` 当前候选与当前参考 `00_enroute.bgl` 的 Navdatareader 只读语义差分，以及对当期 `VOR.csv`、`NDB.csv`、`RTE_SEG.csv` 的逐身份回查）：候选/参考分别解析为 VOR `121/135`、NDB `133/143`、航点 `2519/3266`、航路 `4300/4614`。其中 14 个参考 VOR 逻辑身份和 18 个参考 NDB 逻辑身份既不出现在当期 424 的直接 VOR/NDB 记录中，也不作为同周期航路端点出现；另有 6 个 VOR 和 3 个 NDB 仅以不同的 424 区域键出现。前一类必须继续追溯到允许的当期 424 结构化来源；后一类仍受已记录的区域冲突规则约束。不得用参考 BGL/SQLite 字段值、Fenix 数据或“按名称猜测”补写这些缺口。自动化保护：`test_default_navaids.py`、`test_semantic_diff.py`；此结论未改变候选内容，继续禁止部署。
- 补充来源审计（默认通用数据、2608R1，证据：2026-08-14 对 `FLIGHT_AIRLINE_POINT.csv` 的全量索引及完整 `load_naip(..., include_terminal_documents=True)` 重建）：航路点表包含名称、标识、频道/频率、起止点磁差和 UUID，但没有可投影导航台所需的类型、坐标和区域；它可对 267 条已有直接 VOR 的唯一标识/频率磁差交叉匹配做到 267 条完全一致、0 条冲突，却不能独立构成设施投影。当前 14 个参考缺失 VOR 均没有该表中可用的唯一磁差记录，不能借此补齐。终端程序腿对少数同标识仅保留裸固定点文本，未同时提供类型、区域和坐标。两类资料均不得独立新增或重区域化 VOR/NDB。
- AD 2.19 VOR/DME 证据边界（默认通用数据、2608R1，证据：2026-08-14 对直接 `VOR.csv` 与同服务机场 `AD_HP.csv.VAL_MAG_VAR` 的全量交叉校验，以及 275 机场真实 `load_naip(..., include_terminal_documents=True)` 加载）：346 条可按服务机场关联的 VOR 中仅 3 条磁差相同、343 条不同；因此机场磁差不能代替设施磁差。真实加载从 AD 2.19 取得 386 条 VOR/DME 证据，其中 53 个唯一物理身份不在当前模型的直接 VOR 记录中。表头中的 `VAR` 不表示每行均给出磁差；CZW 的 `013°MAG/2000m` 和 HOK 的 `337°MAG/122982m` 等字段是天线相对位置，不得误作磁差或高程。AD 2.19 表中直接读取到的 VOR/DME 频率、坐标和明确打印的 DME 高程必须以页码和 SHA-256 保存为审计证据，但在取得当期 424 对设施磁差的独立证明前，不得写入 `model.navaids`、导航台选择或 BGL。自动化保护：`test_ad219_vor_evidence_keeps_direct_facts_without_a_magnetic_variation`、`test_ad219_vor_evidence_does_not_treat_position_distance_as_elevation`、`test_ad219_vor_evidence_is_not_promoted_to_a_navaid`。
- WMM 推导禁止项（默认通用数据、2608R1，证据：2026-08-14 以全部 362 条直接 `VOR.csv.VAL_MAG_VAR` 对本机 `pygeomag` WMM-2020/WMM-2025 扫描）：最佳组合为 WMM-2020、2024 年，仍只有 37 条在 `0.01°` 内，中位绝对误差 `0.0497°`、90 分位 `0.1739°`、最大 `2.1818°`。WMM-2025 在 2026-08-06 时中位绝对误差约 `0.1191°`。两者都不能复现 424 设施磁差，不得用于补写 AD 2.19 缺失 VOR。
- 来源缺口审计 v3（默认通用数据、2608R1，证据：`source-gap-audit`、`tests/test_source_gap.py`、2026-08-14 r54 完整只读差分）：审计只接受 `read_only=true`、`reference_values_redacted=true` 且所有参考缺失样本未截断的 `semantic-diff`；仅使用 424 的 2,158 个结构化指定点与 4,446 条航路段分类，并且输出不得包含参考逻辑身份。r54 的 1,032 个参考缺失航点中，667 个不在结构化指定点或航路端点中，335 个仅有不同区域的指定点，15 个指定点区域未决，15 个仅以不同区域出现在航路端点中。1,214 个参考缺失航路中，607 个有同名同序号源段，123 个只有同名不同序号，484 个不在 `RTE_SEG.csv`。全部 1,354 个 424 `EN_ROUTE_RTE_ID` 与航路名一一对应，且各源航路在序号和端点上连续；默认 BGL 片段号由投影后连通图决定，不能从参考身份反推或硬编码。`FLIGHT_AIRLINE_POINT.csv` 的 390,659 条记录均以端点 ID 回链到直接 424 点，且全部对应现有 `RTE_SEG` 的正向 263,184 条或反向 127,475 条；对 54 个 RTE 缺席参考航路名零命中，因此它只能作为既有航路引用审计，不能新增航路。
- 来源缺口审计 v4 候选连通图复核（默认通用数据、2608R1，证据：2026-08-15 r58 候选 `china-navdata.xml`、完整只读语义差分、`source-gap-audit --candidate-xml` 与 `tests/test_source_gap.py`）：审计可选读取候选 XML 的 `Route/Next|Previous` 连通关系，但只能输出 424 分类计数，不得读取或导出参考字段。r58 的 1,261 个参考缺失航路逻辑身份中，608 个有同名同序号的源航段且其完整端点对已经存在于候选连通图，差异仅为读取器片段/连通图表达，不能据此硬编码参考片段号；46 个有同名同序号的源航段未投影全部因至少一个源端点区域码为空，0 个完整源区域端点对从候选 XML 缺失；其余 123 个只有同名不同序号，484 个不在 `RTE_SEG.csv`。候选 XML 读取到 8,802 条 Route 链接和 4,401 个唯一有向端点对。该结论不改变候选内容，区域未决段必须继续跳过并保持测试版。
- `ROUTE_HOLDING.csv` 来源边界（默认通用数据、2608R1，证据：2026-08-14 对当期 116 条记录的只读审计与 `test_source_gap_audit_marks_route_holdings_without_unique_named_identity`）：64 条 `POINT_ID` 已直接回链到现有 424 航点或导航台；其余 52 条均带坐标，但只复用一个 `LOCATION_POINT` 值且没有区域键，无法形成 MSFS 所需的唯一“区域 + 标识”航点身份。它们不得被投影为独立 enroute 航点，只能作为既有点引用审计。
## AD 2.19 VOR/DME 高程投影结论（2608R1）

- AD 2.19 继续保留为带页码和 SHA-256 的独立审计证据；不得新增、重区域化或修改任何 VOR 本体字段，也不得写入 `Vor/Dme.alt`。
- 证据：2026-08-14 的 r52 真实 SDK 构建和受控 Navdatareader 差分中，投影 108 条已匹配 VOR 的 PDF DME 高程后，VOR 严格一致行从 40 降至 36、字段差异从 75 增至 79、含 `dme_altitude` 的差异样本从 27 增至 44。故该高程不是默认 BGL `Vor/Dme.alt` 的可证明来源。
- 回归：`test_load_naip_keeps_ad219_vor_evidence_separate_from_direct_vor`、`test_ad219_vor_evidence_is_not_promoted_to_a_navaid`。
- IAP 图页严格占优消歧（默认通用数据、2608R1，证据：2026-08-15 全量 424 CSV/PDF 只读加载、113 份源侧 IAP PDF 的可续跑 OCR 缓存、`tests/test_iap_coverage.py` 与全量 180 项测试）：当多个候选图页都与同一主进近段匹配时，只有一张图页对至少两个不同数据库腿提供 `IAF`、`IF`、`FAF`、`MAP` 或 `MAPT` 角色，其中至少一个为 `FAF`、`MAP` 或 `MAPT`，且其不同腿角色数量严格高于每一张其他候选图页，才可选中；同分和单角色仍必须拒绝。`iap_coverage.version=4` 的实际统计为 743 组、665 个唯一非空主段、642 组已使用图页角色、20 个多图歧义、2 个无匹配图页、50 个无唯一主段，未决共 72。OCR 缓存仅作可复用来源证据，不能直接写入候选包或解除其他 IAP 拒绝。
- IAP OCR 重跑与位置角色审计（默认通用数据、2608R1，证据：2026-08-15 本机 DeepSeek-OCR-2/llama.cpp 通过 `scripts/start_local_ocr_server.ps1` 启动，44 份未决 IAP 源 PDF 的 44 页 `ocr` 模式、3 倍渲染完整缓存 `iap-ocr-cache-2608r1/ocr-3x-rerun-20260815`、`iap-ocr-audit` 与 `tests/test_iap_ocr_audit.py`、`tests/test_iap_ocr_roles.py`）：缓存源 SHA-256、渲染比例与识别设置均可复查。22 个未决组中，按航点标识命中得到 12 个 `unique_identifier_only` 和 10 个不可区分组。`iap-ocr-evidence-audit-v2` 在 9 个组、12 个候选页中提取 17 个去重后的“角色-当前数据库腿”近邻证据：`IAF=3`、`IF=8`、`FAF=4`、`MAPT=2`；结构化 PDF `ChartRouteFix` 未提供这些候选页的可用角色。位置解析器只接受当前数据库腿标识与独立角色标签处于同一 OCR 文本项、同一行或垂直相邻的严格关系，并拒绝 `FAF/VIP` 这类复合/易混淆标签。结果只能写入审计报告，始终保持 `evidence_only=true` 和 `projection_allowed=false`；在同源、独立的第二次 OCR 重跑与角色-腿唯一性回归通过前，不得按角色或最大标识数自动选择图页、解除 IAP 拒绝或写入 BGL。
- IAP OCR 独立重跑否决（默认通用数据、2608R1，证据：2026-08-15 新建完整缓存 `iap-ocr-cache-2608r1/ocr-3x-role-recheck-20260815`，44/44 页均重新识别、零复用；`iap-ocr-recheck --require-agreement`、`iap-ocr-role-recheck-v1` 与 `tests/test_iap_ocr_recheck.py`）：两份缓存的 44 个候选图页集合与源 SHA-256 完全一致，但仅有 17 条角色-腿证据相交；第二份额外得到 `ZBAD/R35L/35L` 的 `Terminal/ZBAD/ZBAD-5P-7.pdf` 第 1 页 `AD601/MAPT/same_row`，使角色证据由 17 增至 18，协议一致率仅 `0.944444`。该差异直接来自同一源 PDF 的 OCR 文本可见性，不能以“第二次识别更多”作为选择依据。比较器必须输出源图页、页码、角色、航点和相邻关系差异；只要候选集合、角色-腿配对或关系任一不一致，`--require-agreement` 必须非零退出。此结果否决 OCR 角色证据进入图页选择或 BGL 投影，继续保持 `projection_allowed=false`。
- IAP OCR 三次共识门禁（默认通用数据、2608R1，证据：2026-08-15 本机 DeepSeek-OCR-2/llama.cpp 的 `ocr-3x-deterministic-a-20260815`、`ocr-3x-deterministic-b-20260815` 与新建的 `ocr-3x-deterministic-d-20260815`，`iap-ocr-consensus --require-agreement`、`tests/test_iap_ocr_consensus.py`）：A/B/D 的 44 个源 PDF、50 个候选页、OCR 命令、后端、模式、图像预处理、渲染比例、非空运行时标识、17 条角色-腿证据及相邻关系完全一致，`agreement_ratio=1.0`。D 在 `ZWHJ-5B` 遇到本地 OCR 默认 300 秒内部等待后，以显式 `--engine-timeout 900 --timeout 960` 断点完成；该执行等待只决定何时放弃无响应页，IAP 缓存报告必须记录它，但不替代识别设置门禁。历史 C 缓存将命令记为 `E:\python\3.12\Scripts\ocr-skill.exe`，而 A/B 为 `ocr-skill`，因此虽然角色证据一致，也不得作为完整识别设置共识成员。共识命令必须要求至少三份不同缓存，并逐份输出差异；任意一份不一致时门禁失败。此证据只证明本地 OCR 链路在固定模型、种子、温度和渲染配置下可重复，不能代替结构化图页语义，继续保持 `evidence_only=true` 与 `projection_allowed=false`，不得直接选择图页或写入 BGL。
- OCR 运行时描述门禁（默认通用数据、2608R1，证据：2026-08-15 本机 `ocr-3x-deterministic-e-20260815` 的 44/44 页零复用重跑、`iap-ocr-audit`、A/B/D/E 四缓存比较、`scripts/start_local_ocr_server.ps1` 的真实 `already_ready` 输出、`tests/test_ocr_runtime.py` 与 `tests/test_cli.py`）：E 的 50 个候选页、17 条角色-腿证据和相邻关系与 A/B/D 完全一致，但简写 `deepseek-ocr-2-q8_0-seed2608-temp0` 不包含 llama 构建或模型/视觉投影哈希，因此严格门禁必须拒绝其加入共识。启动脚本现在原子写入 `%LOCALAPPDATA%\default_navdata_converter\ocr-server\runtime-profile.json`，其中记录 `b10331`、模型 SHA-256、视觉投影 SHA-256、种子和温度；`ocr-cache` 与 `iap-ocr-cache` 可用 `--runtime-profile-file` 验证描述和完整标识一致后写入缓存。不得回填或修改既有简写缓存元数据；它们只能保留为不可投影的只读审计证据。
- IAP OCR 第四次完整共识（默认通用数据、2608R1，证据：2026-08-16 本机 DeepSeek-OCR-2/llama.cpp 在固定 `b10331`、模型/视觉投影 SHA-256、种子 `2608`、温度 `0`、`ocr` 模式、原图、3 倍渲染配置下新建 `iap-ocr-cache-2608r1/ocr-3x-deterministic-f-20260815`，44/44 页零复用；`iap-ocr-audit`、`iap-ocr-consensus --require-agreement`、`tests/test_iap_ocr_audit.py`、`tests/test_iap_ocr_consensus.py`）：F 覆盖 22 个未决组、50 个候选页，角色-腿近邻证据为 17 条（`IAF=3`、`IF=8`、`FAF=4`、`MAPT=2`）。A/B/D/F 四份完整缓存的候选页集合、完整运行时描述、识别设置、角色-腿配对和相邻关系均一致，`agreement_ratio=1.0`。共识命令本身仍只输出 `evidence_only=true` 和 `projection_allowed=false`；其结果不能脱离受限构建规则直接写入 BGL。
- IAP OCR 受限构建接入（默认通用数据、2608R1，证据：A/B/D/F 共识缓存、`load_iap_ocr_role_evidence`、`tests/test_iap_ocr_consensus.py`、`tests/test_iap_coverage.py`、`tests/test_bgl.py` 与 `tests/test_package.py`，2026-08-16）：构建仅在至少三份独立完整缓存对源 PDF 相对路径/SHA-256、完整运行时描述、识别设置、角色-航点对和相邻关系完全一致时，才加载其中的 `IAF`、`IF`、`FAF`、`MAP`、`MAPT` 角色。先执行结构化 PDF 图页角色选择；仅当该结果仍为 `ambiguous_chart` 时，才允许把 OCR 角色与同一机场、程序标签、跑道、源 PDF 哈希绑定的既有候选页合并，并且仍要求唯一 MAP/MAPT 或严格多角色占优。不得处理 `no_unique_primary`、`empty_primary`、`no_matching_chart`，不得新增主进近、程序、航段或图页匹配；两页同样命中时继续拒绝。OCR 使用不改变测试版、参考字节比对和实机验证门禁。自动化测试：`test_iap_ocr_consensus_loads_only_unanimous_roles_for_matching_chart_pages`、`test_iap_coverage_uses_consensus_ocr_mapt_only_for_one_matching_chart`、`test_iap_coverage_keeps_two_consensus_ocr_mapt_candidates_ambiguous`、`test_bgl_iap_chart_roles_reuses_consensus_ocr_selection`、`test_candidate_does_not_create_output_when_iap_ocr_consensus_rejects`。
- IAP OCR 受限构建复核（默认通用数据、2608R1，证据：2026-08-16 `bounded-max4096-ocr-a/b/c-20260816` 三份独立 `llamacpp-direct` 缓存、`iap-ocr-consensus-bounded-max4096-20260816.json`、r65 候选和 `tests/test_iap_coverage.py`）：三份缓存均固定 `temperature=0`、`seed=2608`、`top_k=1`、`max_tokens=4096`，对 50 个候选图页的 17 条角色-航点证据及相邻关系达到 `agreement_ratio=1.0`。r65 仅以严格多角色占优放行 `ZUDC/R34`、`ZULS/R10L`、`ZWKN/R30-Y` 三组；`iap_coverage.version=6` 的 `ocr_role_selections` 必须记录每项的程序键、选择方法、候选图页数、来源页和参与选择的数据库腿角色。其余 17 个 `ambiguous_chart`、2 个 `no_matching_chart`、50 个 `no_unique_primary` 继续拒绝。直接对 `ZBDH-4H.pdf` 的本地 OCR 复核确认泛化 `R26` 主段仅含共享 `IF DH503`，两张候选图页均包含该点，不构成可投影的图页区分字段。自动化测试：`test_iap_coverage_uses_consensus_ocr_mapt_only_for_one_matching_chart`。
- IAP OCR 当前候选缓存契约（默认通用数据、2608R1，证据：2026-08-17 `iap-ocr-consensus-r69-bounded-20260817.json`、r69 构建与 `tests/test_iap_ocr_consensus.py`）：候选构建必须使用 `bounded-max4096-ocr-a/b/c-20260816` 三份完整缓存。它们的候选页、完整运行时描述、识别设置、17 条角色-航点证据和相邻关系均一致；旧 `ocr-3x-deterministic-a/b/d/f-20260815` 即使角色证据相同，也因缺少完整的显式识别设置元数据而必须由严格门禁拒绝，不能降级或混用。
- IAP 直接固定点图页选择（默认通用数据、2608R1，证据：424 `Terminal/ZUNP/ZUNP-4Z04.pdf`、`ZUNP-9C.pdf`、`ZUNP-9D.pdf`、`ZLGL-5L-1.pdf`、`ZLGL-5R-3.pdf`、`ZUDC-5A.pdf`、`ZUDC-9B.pdf`、`ZWHJ-5B.pdf`、`ZWHJ-9C.pdf` 的直接文本，r74 隔离构建及 `tests/test_iap_coverage.py`，2026-08-17）：直接 PDF 角色选择失败后、OCR 选择前，当已有两个以上同机场同跑道的标题候选，或通常标题匹配为空但图题是未标变体的 `RNP ... (AR)` 且数据库标签为 `R<跑道>-...` 时，只有恰好一张候选图页的直接 `waypoints` 集合包含主段全部至少两个不同的非空固定点，才允许关联该页。直接 `MAP/MAPT` 或严格多角色选择必须优先于固定点选择。`R24-Z` 的 7 个固定点只完整命中 `ZUNP-9C.pdf`，`R24-Y` 的 `NP716/NP714` 只完整命中 `ZUNP-9D.pdf`；标题候选的 `ZLGL/R30` 仅 `ZLGL-5R-3.pdf` 完整包含 12 点，`ZUDC/R34` 仅 `ZUDC-9B.pdf` 完整包含 7 点，`ZWHJ/R06-Y` 仅 `ZWHJ-9C.pdf` 完整包含 7 点。r74 报告记录上述 5 个图页选择，IAP 未决从 r73 的 67 降至 65；相对 r73 仅 `ZL`、`ZU`、`ZW` 分区 BGL 及其 SDK 索引/布局文件发生变化。固定点缺失、少于两个、显式图题变体的无匹配情形或两个以上完整候选一律拒绝。图页归属不等于角色归属：只有图页角色的标识实际命中主段腿时才可计为角色证据或写入 BGL；r72 的两个 ZUNP 归属都没有这种角色交集，故相对 r70 的 `ZP_airports.bgl` SHA-256 不变。此规则不读取 OCR、Fenix 或参考成品；覆盖报告必须记录 `source_fixed_point_selections`。自动化测试：`test_iap_coverage_selects_unqualified_rnp_ar_chart_by_complete_direct_fixes`、`test_iap_coverage_selects_ambiguous_title_match_by_complete_direct_fixes`、`test_iap_coverage_prefers_direct_role_selection_before_complete_direct_fixes`、`test_iap_coverage_rejects_equal_unqualified_rnp_ar_direct_fix_candidates`、`test_iap_coverage_keeps_equal_complete_direct_fix_title_matches_ambiguous`、`test_iap_coverage_rejects_unqualified_rnp_ar_chart_with_only_one_direct_fix`、`test_iap_coverage_does_not_use_fixed_points_when_rnp_ar_title_declares_variant`。
- IAP 角色交集审计（默认通用数据、2608R1，证据：r72/r73 隔离构建、`conversion-report.json` 与 `tests/test_iap_coverage.py`，2026-08-17）：`role_evidence_used` 和 `role_evidence_counts` 只能统计“已选图页角色标识与主进近腿固定点相交”的角色，不能因图页存在其他共享过渡或复飞角色而计数。r73 将角色覆盖组从 648 更正为 638，`roles_unique_chart` 从 376 更正为 366，`unique_chart_without_roles` 从 1 更正为 13；IAP 未决仍为 67。r72/r73 的两个覆盖包中所有 BGL、manifest 和 ContentHistory 均字节一致，只有 SDK 重建的 `bglIndex.bout`、`layout.json` 改变，说明本次是审计修正而非导航内容修改。自动化测试：`test_iap_coverage_selects_unqualified_rnp_ar_chart_by_complete_direct_fixes`。
- IAP OCR 图像预处理隔离（默认通用数据、2608R1，证据：2026-08-15 本机 DeepSeek-OCR-2/llama.cpp 新建 `iap-ocr-cache-2608r1/ocr-3x-autocontrast-a-20260815`，44/44 页零复用、`iap-ocr-audit`、`iap-ocr-recheck` 与 `tests/test_iap_ocr_audit.py`、`tests/test_iap_ocr_recheck.py`、`tests/test_iap_ocr_consensus.py`）：3 倍自动对比度灰度处理得到 19 条角色-腿证据，原图确定性缓存得到 17 条；两者仅 13 条交集，协议一致率 `0.565217`。图像预处理会实质改变 OCR 文本与角色邻接关系，因此 IAP 审计必须记录 OCR 命令、后端、模式、图像预处理、渲染比例和运行时标识；`iap-ocr-recheck` 与 `iap-ocr-consensus` 必须把整组识别设置作为一致性门禁。不同预处理缓存只能做只读差分，不能参与同一共识、选择图页、解除 IAP 拒绝或写入 BGL。
- IAP OCR 自动对比度三方共识无投影增量（默认通用数据、2608R1，证据：2026-08-17 本机 `autocontrast-max4096-r94-a/b/c-20260817` 三份独立 `llamacpp-direct` 缓存均对 27 份 PDF、27 页零复用完成；`iap-ocr-audit`、`iap-ocr-consensus --require-agreement`、r94 隔离构建与 `validate`）：三份缓存固定 `temperature=0`、`seed=2608`、`top_k=1`、`max_tokens=4096`、`ocr` 模式、3 倍渲染和 `autocontrast-grayscale`，对 14 个待审组的 29 条候选页记录达到 `agreement_ratio=1.0`，共有 13 条角色-腿近邻证据（`IF=8`、`FAF=3`、`MAPT=2`）。r94 构建虽接受 8 个候选页、13 条 OCR 证据，但其 `iap_coverage` 与 r93 的规范化 SHA-256 相同，程序段仍为 10,313、未决程序仍为 39，两个覆盖包内全部 BGL 也与 r93 相同。因此该预处理只作为可复用的只读审计证据，不产生新图页选择、不放宽 `ambiguous_chart`、`no_unique_primary` 或 `no_matching_chart`，常规候选继续使用已登记的 `bounded-max4096-ocr-r80-a/b/c-20260817` 三缓存契约。
- 终端坐标页全局航点提升（默认通用数据、2608R1，证据：全部 `Terminal/*/Charts.csv` 索引的源 PDF 坐标页、r70 完整只读加载、`conversion-report.json`、单 `00_enroute.bgl` Navdatareader 读取、`source-gap-audit` 与 `tests/test_source.py`，2026-08-17）：`_promote_shared_terminal_coordinate_waypoints()` 必须在 `_load_terminal_coordinate_pages()` 之后、`_retain_database_referenced_terminal_waypoints()` 之前运行。只有同一区域、原始标识完全一致且不超过 8 字符、坐标六位小数一致、至少两个不同机场独立发布、且未被既有规范化全局航点或 VOR/NDB 身份占用的坐标页组，才提升为全局 `Waypoint`；提升后仍保留原终端点给程序与等待航线。r70 全量审计：12,991 个坐标点、12,417 个身份组，提升 96；拒绝单机场 11,967、多坐标 79、既有全局身份 275，空标识/标识变体/超长均为 0。候选/参考单 BGL 读取为 VOR `121/135`、NDB `133/143`、航点 `3139/3266`、航路 `4401/4614`；完整来源缺口审计仍有 1,019 个参考缺失航点和 1,186 个参考缺失航路，绝不得从参考 BGL/SQLite 或 Fenix 回填。`source-gap-audit` 必须输入 `sample_limit` 足够覆盖全部参考缺失样本的脱敏差分；默认 50 条截断样本会被审计器拒绝。自动化测试：`test_promotes_shared_terminal_coordinate_waypoint_to_global_model`、`test_shared_terminal_coordinate_waypoint_requires_two_airports`、`test_shared_terminal_coordinate_waypoint_rejects_coordinate_conflicts`、`test_shared_terminal_coordinate_waypoint_keeps_existing_global_identity`、`test_candidate_reports_terminal_coordinate_waypoint_promotion`。
- 终端坐标页缺口审计（默认通用数据、2608R1，证据：`terminal-coordinate-audit`、r70 完整脱敏差分、同一 r35 PDF 缓存与 `test_terminal_coordinate_audit_keeps_source_categories_redacted`，2026-08-17）：该只读命令必须复用与候选相同的 424 全局模型和 PDF 缓存，只输出类别计数，严禁输出或保存参考身份。r70 的 1,019 个参考缺失全局航点中，862 个未出现在终端坐标页、146 个仅单机场发布、11 个有多个源坐标，`terminal_source_promotable=0`。因此禁止放宽单机场或多坐标条件来追随参考差分；只有未来独立的 424 来源规则与最小 fixture 都成立后才可改变投影。
- ENR 4.4 关键点缺口审计（默认通用数据、2608R1，证据：`general-doc-keypoint-audit`、r70 完整脱敏差分、已校验 GeneralDoc OCR 缓存与 `test_general_doc_keypoint_audit_keeps_source_categories_redacted`，2026-08-17）：该只读命令必须使用 ENR 4.4 的 SHA-256 校验缓存和构建同一套 424 FIR 几何规则，只输出类别计数，严禁输出或保存参考身份。r70 的 1,019 个参考缺失全局航点中，816 个不在关键点表、154 个同名但区域不同、39 个在 FIR 边界 5 海里内、9 个在 FIR 外、1 个区域歧义，`general_doc_source_promotable=0`。因此禁止放宽 FIR 边界、区域或身份冲突条件追随参考差分；只有未来独立的 424 来源规则与最小 fixture 都成立后才可改变投影。

- 无固定点限定 RNP AR 单角色选择（默认通用数据、2608R1，证据：424 `Terminal/ZUNP/ZUNP-4Z03.pdf`、`ZUNP-9A.pdf`、`ZUNP-9B.pdf` 的直接图页角色，r88 隔离 SDK 构建、独立 `validate` 与 `tests/test_iap_coverage.py`、`tests/test_bgl.py`，2026-08-17）：只有所有标题候选都是无非跑道固定点限定的 RNP AR 图，且恰好一张图把数据库主进近腿标为 `IAF`、`IF`、`FAF`、`MAP` 或 `MAPT` 时，才可选择该图页；任一图题带固定点限定、混入非 RNP AR 图、没有命中或多个候选命中时继续拒绝。r88 只新增 `ZUNP/R06 -> ZUNP-9B.pdf -> LIP/IAF`，IAP 未决由 43 降至 42；相对 r87 只改变两个覆盖包的 `ZU_airports.bgl`、相应索引/布局与报告。选择必须记录为 `source_unqualified_rnp_ar_direct_role_selections`，并且只投影与数据库腿相交的直接图页角色；规则不读取 OCR、参考成品或 Fenix。自动化测试：`test_iap_coverage_selects_unqualified_rnp_ar_chart_by_unique_direct_role`、`test_iap_coverage_rejects_qualified_or_nonunique_rnp_ar_direct_role_matches`、`test_bgl_iap_chart_roles_reuse_unqualified_rnp_ar_direct_role_selection`。
- I 标签纯 ILS 图页消歧（默认通用数据、2608R1，证据：424 `Terminal/ZPNL/ZPNL-4H.pdf`、`ZPNL-5A.pdf`、`ZPNL-5B.pdf`，r89 完整 SDK 构建、独立 `validate` 与 `tests/test_iap_coverage.py`，2026-08-17）：当数据库主进近标签显式以 `I` 开头、标题兼容候选同时包含 `RNP ILS/DME` 和普通 `ILS/DME` 图页时，只有恰好一张候选明确含 `ILS` 且不含 `RNP` 才可作为该 ILS 主进近图页。没有普通 ILS 图、普通 ILS 候选不唯一、或数据库标签不是 `I` 的情形一律保持原有消歧规则。r89 将 `ZPNL/I23` 从图页歧义恢复为唯一普通 ILS 图页，IAP 未决由 42 降至 41；候选已通过本地契约验证但仍未与参考包字节一致，继续保持测试版。自动化测试：`test_iap_coverage_prefers_unique_plain_ils_title_for_database_i_label`。
- 数据库编码无分隔符“进近复飞”标题拆分（默认通用数据、2608R1，证据：424 `Terminal/ZWTL/ZWTL-4M.pdf` 的直接 PDF 提取、r91 完整 SDK 冷缓存构建、独立 `validate` 与 `tests/test_pdf_charts.py`，2026-08-17）：数据库编码表标题中的 `进近复飞Y/Z` 与带连接字的 `进近及复飞Y/Z` 语义相同，必须先归为组合段，再在首个复飞腿类型处分割为进近与复飞。`ZWTL/R09-Y` 的 `IF TL916`、`TF TL104`、`TF RW09` 属于进近，`CF TL501`、`DF TL908` 属于复飞；`ZWTL/R09-Z` 的 `IF TL103`、`TF TL104`、`TF RW09` 属于进近，`CA 087`、`DF TL101` 属于复飞。任何影响终端腿分组的规则改动必须提升 `_EVIDENCE_CACHE_VERSION` 并使用独立 PDF 证据缓存；当前版本为 `37`，候选构建应使用 `pdf-evidence-cache-2608r1-r37`。r91 相对 r90 增加 8 个程序段，`ZWTL/R09`、`ZWTL/R27` 由 `no_unique_primary` 解决，IAP 未决由 41 降至 39；仅 `ZW_airports.bgl` 与相应索引/布局发生导航内容变化。自动化测试：`test_database_combined_approach_missed_without_separator_splits_at_missed_legs`。
- 数据库编码主进近表头腿型防误归类（默认通用数据、2608R1，证据：424 `Terminal/ZHCC/ZHCC-4Z12.pdf`、`ZHCC-4Z13.pdf`、r38 完整 PDF 证据缓存、r99 隔离 Package Tool 构建、独立 `validate` 与 `tests/test_pdf_charts.py`，2026-08-17）：`进近` 表头后被解析为 `CF/DF/TF/CA/IF/HM/RF/AF/FA/FC/FD/FM/HA/HF/PI/VI/VM` 的枚举值是表内腿类型，绝不是命名进近过渡；必须保留为空过渡，使其作为主进近分组。该规则仅影响真实 2608 的 `ZHCC/R12R` 与 `ZHCC/R30R`，r99 将 IAP 未决由 39 降至 37，分发包只改变两层的 `ZH_airports.bgl` 与相应索引/元数据。任何终端编码解析规则改动都必须提升 `_EVIDENCE_CACHE_VERSION`；当前版本为 `38`，候选构建应使用 `pdf-evidence-cache-2608r1-r38`。自动化测试：`test_database_approach_leg_type_is_not_a_transition_name`。
- 多图 IAP 的直接角色唯一选择（默认通用数据、2608R1，证据：424 `Terminal/ZLGL/ZLGL-4H.pdf`、`ZLGL-5R-1.pdf`、`ZLGL-5R-2.pdf`、`Terminal/ZSWA/ZSWA-4Z04.pdf`、`ZSWA-5C.pdf`、`ZSWA-9B.pdf` 的直接文本、全量来源重建与 `tests/test_iap_coverage.py`，2026-08-17）：多个标题兼容候选中，只有恰好一张图的直接 `IAF`、`IF`、`FAF`、`MAP` 或 `MAPT` 标记与来源主进近腿相交时，才可选择该图页，并记录到 `source_unique_direct_role_selections`。规则不使用 OCR、参考成品或 Fenix。候选标题标准化后必须彼此不同；RNP AR 候选不得与非 AR 图题混用，所有 RNP AR 候选的固定点限定状态必须一致；重复标题、多个命中、零命中或混合类别一律拒绝。自动化测试：`test_iap_coverage_selects_unique_direct_source_role_without_ar_title_mixing`、`test_iap_coverage_selects_uniform_qualified_rnp_ar_by_unique_direct_role`、既有 `test_iap_coverage_does_not_select_a_chart_with_only_one_matching_role`、`test_iap_coverage_rejects_qualified_or_nonunique_rnp_ar_direct_role_matches`。
- RNP 子集直接角色共识（默认通用数据、2608R1，证据：424 `Terminal/ZUNZ/ZUNZ-4G05.pdf`、`ZUNZ-9A.pdf`、`ZUNZ-9B.pdf`、`ZUNZ-9C.pdf` 的直接源字段、r119 完整 SDK 构建、独立 `validate` 与 `tests/test_iap_coverage.py`，2026-08-18）：只有数据库主进近的每一腿都显式编码为 RNP、至少两张纯 RNP（不含 ILS）标题兼容图页给出完全相同且非空的直接角色集合、其余纯 RNP 候选对主段不提供直接角色，且任何非纯 RNP 候选也不提供直接角色时，才可投影该共同角色；任何不同的非空角色集合一律拒绝。该规则不选择某一图页、不推断变体，只向已有数据库腿投影角色。r119 对 `ZUNZ/R05` 的 `DUMIX`、`ELNUN`、`LZ302` 三张 RNP AR 图投影共同的 `LZ250/IF`，IAP 未决由 21 降至 20；只改变两个覆盖层的 `ZU_airports.bgl`、相应索引/布局与报告。不得使用 OCR、参考成品或 Fenix。自动化测试：`test_iap_coverage_projects_pure_rnp_subset_consensus_with_roleless_rnp_candidate`、`test_iap_coverage_rejects_rnp_subset_consensus_when_other_chart_has_direct_role`、`test_bgl_iap_chart_roles_reuse_rnp_subset_direct_role_consensus`。
- RNP/ILS 混合图页 IF 角色兼容性（默认通用数据、2608R1，证据：424 `Terminal/ZWTK/ZWTK-0C-2.pdf`、`ZWTK-5L-1.pdf`、`ZWTK-5R-3.pdf`、`ZWTK-5R-4.pdf` 的直接源字段、r120 完整 SDK 构建、独立 `validate` 与 `tests/test_iap_coverage.py`，2026-08-18）：在 RNP 子集直接角色共识中，混合 `RNP ILS` 图页若将 `IF` 标记赋给数据库主进近中不存在 `IF` 腿的固定点，该标记属于同页 ILS 路径，不能阻止纯 RNP 图页的共识；过滤仅适用于混合标题的 `IF` 角色和该子集共识，其他图页、其他角色或主进近中实际存在 `IF` 腿时均维持原有冲突拒绝。r120 对 `ZWTK/R33` 忽略混合图的 `TK801/IF`（源腿为 RF），投影两张纯 RNP 图共同的 `TK802/IF`，IAP 未决由 20 降至 19；只改变两个覆盖层的 `ZW_airports.bgl`、相应索引/布局与报告。不得使用 OCR、参考成品或 Fenix。自动化测试：`test_iap_coverage_ignores_mixed_rnp_ils_if_marker_on_non_if_primary_leg`、`test_iap_coverage_rejects_rnp_subset_consensus_when_other_chart_has_direct_role`。
- FAP/VIP 终端图页终点角色（默认通用数据、2608R1，证据：424 `Terminal/ZUBD/ZUBD-9C.pdf`、`ZUBD-9D.pdf`、`Terminal/ZLGL/ZLGL-5R-1.pdf`、`ZLGL-5R-2.pdf` 的直接 PDF 文本对象，以及 `tests/test_pdf_charts.py`，2026-08-18）：只有精确文本标签 `FAP/VIP` 才可归一为 `FAF`。仍必须复用同一 PDF 文本块、垂直间距不大于 12、横向重叠不小于 -1 的固定点几何门禁；不得由相邻图形、OCR、参考成品或 Fenix 推断。规则可为 `ZUBD/R14` 的 `BD658` 与 `ZUBD/R32` 的 `BD635` 提供直接 `FAF` 证据；`ZLGL/R12` 的两个候选图页均标注 `GL606`，因此仍保持歧义拒绝。此类终端 PDF 角色解析变更必须提升 `_EVIDENCE_CACHE_VERSION`，当前为 `42`。自动化测试：`test_positioned_route_fixes_maps_exact_fap_vip_label_to_faf`。
- 同页 RNAV ILS 主段共享投影（默认通用数据、2608R1，来源证据：424 `Terminal/ZSNJ/ZSNJ-4K.pdf`、`ZSNJ-4L.pdf`、`ZSNJ-4N.pdf`、`ZSNJ-4P.pdf` 的数据库编码表与 `ZSNJ-5A/5C/5E/5G/5J.pdf`、普通 ILS 图页的直接标题；最小 fixture 测试）：当 `Ixx` 只含 ILS 复飞段、同一数据库页存在唯一非 AR 的精确 `Rxx` 主进近、且同跑道存在一张或多张 `RNAV ILS` 标题图时，可以把该 `Rxx` 主段投影到 `Ixx`；多个 RNAV ILS 变体只作为共同证据，不选择具体变体。`RNAV ILS` 不得被归入普通 ILS 图页；跨数据库页不得使用该规则，因此 `ZSNJ/I25` 继续拒绝。r122 完整 SDK 构建与独立 `validate` 新增 `ZSNJ/I06`、`I07`、`I24`，IAP 未决由 17 降至 14；只改变两个覆盖层的 `ZS_airports.bgl`、相应索引/布局与报告。`ZSNJ/I25` 因跨页继续拒绝。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_rnav_ils_title_does_not_project_cross_page_rnp_primary`。
- 同页无后缀主段供 Y/Z 复飞变体继承（默认通用数据、2608R1，证据：424 `Terminal/ZBAD/ZBAD-0C-18.pdf` 的 `RWY35L 进近` 与 `RWY35L 复飞 y/z` 直接编码，`ZBAD-5P-7.pdf`/`ZBAD-5P-8.pdf` 的直接图页角色，ZBAD 只读全页核对与 `tests/test_iap_coverage.py`、`tests/test_bgl.py`，2026-08-18）：当后缀标签恰好为无后缀身份加单个 `W/X/Y/Z`、该后缀组没有主进近段、同机场同跑道的无后缀组有且仅有一个非空主进近，且全部后缀段与该主段位于同一数据库页时，后缀组继承该主段。跨页、多个无后缀主段、后缀组已有主段或 `R10-AR-Z` 这类复合后缀一律拒绝。BGL 必须把继承的主段和同页无后缀过渡写入带后缀的进近，并把后缀复飞写入 `MissedApproachLegs`。该规则不使用 OCR、参考成品或 Fenix。r123 完整 SDK 构建与独立 `validate` 将 `ZBAD/R35L-Y` 与 `R35L-Z` 投影为同页无后缀主段加各自复飞，IAP 未决由 14 降至 12；相对 r122 只改变两个覆盖层的 `ZB_airports.bgl`、相应索引/布局与报告。`R29R` 继续拒绝。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_iap_coverage_inherits_same_page_base_primary_for_suffixed_missed_variants`、`test_iap_coverage_rejects_cross_page_base_primary_inheritance`、`test_bgl_projects_inherited_base_primary_onto_suffixed_missed_variant`。
- 多图 IAP 的直接角色严格包含选择（默认通用数据、2608R1，证据：424 `Terminal/ZUAL/ZUAL-4Z05.pdf`、`ZUAL-5A.pdf`、`ZUAL-9A.pdf` 的直接文本、全量来源重建与 `tests/test_iap_coverage.py`，2026-08-17）：候选图的直接“固定点、角色”集合中，只有恰好一张严格包含每一张其他候选的集合时，才可选择该图页，并记录到 `source_dominant_direct_role_selections`。该规则复用标题不同、RNP AR 分类一致和限定状态一致的门禁，不使用 OCR、参考成品或 Fenix；相同、不可比较、重复标题或混合类别一律拒绝。自动化测试：`test_iap_coverage_selects_strict_direct_role_superset`、`test_iap_coverage_rejects_incomparable_direct_role_sets`。
- 普通 RNP 标题末级选择（默认通用数据、2608R1，证据：424 `Terminal/ZBDH/ZBDH-4H.pdf`、`ZBDH-5B.pdf`、`ZBDH-9B.pdf` 的直接文本、全量来源审计、r103 隔离 SDK 构建与独立 `validate`、`tests/test_iap_coverage.py`、`tests/test_bgl.py`，2026-08-17）：只有在已有直接角色、固定点和 RNP AR 规则均无法消歧时，数据库主进近标签以 `R` 开头且候选恰有一张非 AR 的 `RNP` 图与一张非 AR 的 `RNP ILS` 图，才选择普通 RNP 图，并记录到 `source_plain_rnp_title_selections`。两图与来源腿相交的直接角色-固定点集合必须相同且非空；AR 图、额外候选、非 R 标签、角色集合不一致或任何更强的既有选择一律不受此规则影响。r103 仅选择 `ZBDH/R26`、`ZGWZ/R22`、`ZHHH/R23L`、`ZLDH/R08`、`ZSNT/R36`，IAP 未决由 34 降至 29，局部变更限于 ZB/ZG/ZH/ZL/ZS 机场 BGL 和索引/布局；候选本地契约通过但仍不与参考包字节一致。该规则不使用 OCR、参考成品或 Fenix。自动化测试：`test_iap_coverage_prefers_plain_rnp_title_after_stronger_rules_fail`、`test_bgl_iap_chart_roles_reuse_plain_rnp_title_selection`。
- 首条 IF 角色选择（默认通用数据、2608R1，证据：424 `Terminal/ZWTK/ZWTK-0C-3.pdf`、`ZWTK-5L-1.pdf`、`ZWTK-5R-3.pdf` 的直接文本、全量来源审计、r104 隔离 SDK 构建与独立 `validate`、`tests/test_iap_coverage.py`、`tests/test_bgl.py`，2026-08-17）：仅在已有直接角色、固定点和标题规则均无法消歧时，来源主进近的第一条腿明确为 `IF`、固定点非空且恰好一张候选图将该固定点直接标为 `IF`，才选择该图，并记录到 `source_unique_first_if_selections`。首腿不是 IF、固定点为空、多张图同样命中或任何更强既有选择一律不受此规则影响。r104 仅选择 `ZWTK/R33-Z -> RNP z RWY33(AR)`，IAP 未决由 29 降至 28，局部变更限于 `ZW_airports.bgl` 和索引/布局；候选本地契约通过但仍不与参考包字节一致。该规则不使用 OCR、参考成品或 Fenix。自动化测试：`test_iap_coverage_selects_unique_first_source_if_chart`、`test_bgl_iap_chart_roles_reuse_unique_first_if_selection`。

## 3.2 航路最低高度 OCR（开发中）

- 来源限定为 `GeneralDoc/航路_3.2.1A系列航路.pdf` 至 `航路_3.2.9X系列航路.pdf`。缓存必须逐页完整、PDF SHA-256 匹配且运行时描述与本地 OCR 服务一致；不完整缓存仅可续跑，不得投影。
- 解析器只接受同页坐标列确认的航点、航路前缀和最低飞行高度表列；跨页时保留航路、前序航点与待配对高度状态。OCR 标识必须精确命中唯一的 `RTE_SEG.csv` “航路 + 起点 + 终点”身份；多/少字符、冲突、缺失或多重命中一律计入审计而不写入候选。
- 当前仅可把唯一回链的发布高度（米）换算并写入 `AirwayLeg.minimum_altitude_ft`；`RTE_SEG.CODE_TYPE` 仍是 PBN 语义，绝不可据此或根据航路名称推断 SDK `routeType`。
- 全册投影审计（默认通用数据、2608R1，证据：2026-08-17 `%LOCALAPPDATA%\default_navdata_converter\general-doc-ocr-cache-2608r1` 的 A/B/G/H/J/R/V/W/X 九册完整缓存、`r69` 候选和受控 Navdatareader 差分）：455 页共解析 4,069 条最低高度记录，其中 3,827 条唯一回链到直接 `RTE_SEG.csv` 并投影，242 条没有直接 424 航段，歧义与冲突均为 0。r69 相比 r67 仅增加已回链航路的 `minimum_altitude`，`00_enroute.bgl` 的航路逻辑身份不变；缺少直接来源的记录不得因 OCR 出现而新增航路或端点。
- GeneralDoc 缓存适配器隔离（默认通用数据、2608R1，证据：2026-08-19 r136/r137/r138 的隔离 Package Tool 构建、独立 `validate`、完整脱敏单 `00_enroute.bgl` 差分与 `source-gap-audit-v4`）：ENR 3.2 A/B/G/H/J/R/V/W/X 的发布最低高度是可复用 `NavModel` 证据，只有显式传入 `--general-doc-airway-cache-directories` 才能投影。r137 使用九册缓存后，3,827 条唯一回链高度使航路 `minimum_altitude` 差异从 r136 的 30 条增至 3,044 条，严格相等行从 2,688 降至 1,625；当前没有默认 BGL 加载契约证据支持该字段。r138 使用相同 `--general-doc-cache` 但不传入 ENR 3.2 目录，保留 ENR 4.4 的 489 个安全关键点投影，`00_enroute.bgl` 航点为 `3150/3266`、严格相等行 2,699、最低高度字段差异维持 30。因此默认 BGL 适配器不得隐式启用 ENR 3.2 高度；其他目标适配器可消费中间模型证据，但必须先建立自身字段和加载契约。该结论不允许 OCR 新增航路、端点或区域键。
- 航路 `CODE_DIR` 简单方向映射否决（默认通用数据、2608R1，证据：2026-08-16 r61 候选的隔离 SDK 构建 `diagnostics/route-direction-probe-20260816`、`00_enroute.xml`、Package Tool 产物与 Navdatareader 受控读取）：把 1,302 个 `F` 段裁剪为仅 `Next`、152 个 `B` 段裁剪为仅 `Previous`、`X` 保持双向后，SDK 仍生成 BGL，但读取器持续输出边界记录并触发 16 MiB 日志保护。编译成功不构成加载契约成立。不得把 `F -> Next`、`B -> Previous`、`X -> 双向` 写入默认投影；在取得 424 来源语义和独立加载验证前，`AirwayLeg.direction` 仅保留为来源字段，已解析端点仍由 `_append_enroute` 同时写出 `Next` 与 `Previous`。自动化测试：`test_enroute_projection_does_not_reduce_links_from_raw_424_code_dir`。
- SDK 航路 `routeType` 回读不可用（默认通用数据、2608R1，证据：2026-08-17 `route-type-probe-r71-20260817`、`route-type-hint-probe-r71-20260817`、`route-type-name-fixed-probe-r71-20260817` 的三组隔离 Package Tool 构建和 Navdatareader SQLite）：SDK 可分别编译 `VICTOR`、`JET`、`BOTH`，但读取器三组均输出 `airway.route_type=NULL`；即使三条航路使用相同名称、不同 `routeType`，仍不能回读字段。该读取器不能为目标类型提供取证，严禁由航路名称、`RTE_SEG.CODE_TYPE`、`SEGMENT.TXT_DESIG_RNP` 或 `EN_ROUTE_RTE.TXT_LOC_TYPE` 推断 `AirwayLeg.route_type`；继续保持空值，直到取得独立的 424 语义或真实加载器证据。自动化保护：`test_load_naip_separates_source_pbn_from_target_route_type_and_links_airway_tables`。
- SDK 航路片段编码（默认通用数据、2608R1，证据：2026-08-17 `route-fragment-probe-r92-20260817` 的单 `00_enroute.bgl` 真实 Package Tool 构建、完整 Navdatareader SQLite 登记及 `tests/test_route_fragment_probe.py`）：同名同 `routeType=BOTH` 的连续双航段被读为同一片段、序号 `1,2`；端点不连通的同名同类型双航段被拆为两个片段、各自序号 `1`；跨 `waypointRegion` 的连续双航段仍为同一片段；同名连续航路中由 `BOTH` 切换至 `VICTOR` 时，读取器保留同一片段和连续序号，同时将两段分别编码为 `B`、`V`。片段边界由航路图连通性决定，不能仅按区域或类型切分。未来若取得独立 424 来源证据为某些段设置目标类型，`_append_enroute()` 必须按 `(航路名, routeType)` 分组 Route 子节点，不能将同名不同类型折叠；本证据不建立任何 `RTE_SEG` 到 `routeType` 映射，当前投影仍保持未解析类型为 `BOTH`。
- `RTE_SEG.Airspace_Remark` 来源保留（默认通用数据、2608R1，证据：2026-08-17 真实 424 全量 `load_naip(..., include_terminal_documents=False)`、`summarize_airway_source_metadata` 与 `test_load_naip_separates_source_pbn_from_target_route_type_and_links_airway_tables`）：4,446 条航路段中 4,433 条带非空备注，具有 295 个不同的非空原始值。`AirwayLeg.source_airspace_remark` 必须逐段原样保留，候选报告仅记录非空、空值和不同值计数，避免把原始文本扩散到诊断结果。该字段当前仅为来源溯源信息；不得据此推断 SDK `routeType`、航路片段边界或方向，直到取得独立的 424 语义与加载验证证据。
- ACC 边界前缀区域恢复（默认通用数据、2608R1，证据：`AIRSPACE.csv` FIR `TXT_NAME`、`RTE_SEG.csv.Airspace_Remark`、r95/r96 全量加载、r96 Package Tool 构建/`validate` 和 `tests/test_source.py`，2026-08-17）：仅对在既有严格服务机场、显式 FIR、FIR 多边形规则后仍为空的、且按类型/标识/六位坐标连接航路的指定点，才可读取备注中的 `中文ACC` 名称。解析可且只能剥离名称前的精确 `以上`/`以下` 边界词，故 `以下广州ACC` 归一为 `广州`；归一名必须唯一匹配同源 `AIRSPACE.csv` 中以 `飞行情报区` 结尾的 FIR 标题，且该点所有非空 ACC 证据都必须可映射为同一地区。未知 ACC、多个地区、没有 ACC 或未连接航路继续保持空；恢复后必须以同源精确身份回写匹配的 `RTE_SEG` 端点。2608 复核中 FIR 几何后 51 个空点恢复 18，30 个未知、2 个多地区、1 个未连接；r96 的“以下”解析修正未改变这 18 个现有恢复项，且 r95/r96 的 2,258 个 BGL SHA-256 全部相同，因此它只修复未来同类来源行，不能作为本周期差分收敛证据。自动化测试：`test_load_naip_recovers_blank_waypoint_region_from_unambiguous_source_acc`。
- ACC 显式端点标签区域恢复（默认通用数据、2608R1，证据：`RTE_SEG.csv.Airspace_Remark`、`AIRSPACE.csv` FIR `TXT_NAME`、真实 424 全量加载与 `tests/test_source.py`，2026-08-17）：当同一条航路备注以真实起止点标识紧跟半角/全角冒号的形式标注 ACC 时，标签后的文本只归属该端点，并在下一个真实起止点标签前截断；此端点级证据优先于把整条备注同时归属两端的泛化 ACC 证据。仅在标签片段内所有 ACC 均可唯一映射到同源 FIR 区域时恢复，多个地区、未知 ACC、没有 ACC 或跨条标签冲突一律拒绝。该规则不做地理推断，也不使用参考 BGL 内容；2608 从 ACC 阶段后的 33 个空区域点中恢复 6 个（`AIWD50/CH`、`APESI`、`APUKO`、`IKELA`、`P245`、`P255`），剩余 27 个继续保留为空。自动化测试：`test_load_naip_prefers_explicit_endpoint_acc_label_over_generic_leg_accs`。
- 航路邻接区域恢复（默认通用数据、2608R1，证据：424 `DESIGNATED_POINT.csv`/`RTE_SEG.csv`、r123 跳过航路明细与 `tests/test_source.py`，2026-08-18）：在服务机场、显式 FIR、FIR 多边形和 ACC 规则之后仍为空的指定点，若其精确身份所连接的、当时已恢复区域的航路邻接端点全部属于同一地区，且相连航段上已映射的 FIR/ACC 地区为空或与该唯一邻接地区一致，则可继承该地区并回写匹配的 `RTE_SEG` 端点。空白邻接和无法映射的城市 ACC 名称不参与投票；多地区邻接、已映射 ACC 与邻接冲突、或 `RTE_SEG` 独有且不在 `DESIGNATED_POINT.csv` 中的标识（例如 `****`）一律保持为空。该规则不读取官方索引、参考成品或 Fenix。r123 源侧 27 个空指定点中邻接恢复 17 个，其中包括 `P45`/`P212`/`P213`；FIR 边界点 `P121`/`P127`/`P188`/`P225`/`P239` 因多地区邻接继续拒绝。r124 完整 SDK 构建与独立 validate 将跳过航路段由 20 降至 12、跳过航路点由 8 降至 5；相对 r123 只改变两个覆盖层的 00_enroute.bgl、相应索引/布局与报告。IAP 未决仍为 12。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_load_naip_recovers_blank_waypoint_region_from_unanimous_airway_neighbors`。
- 数据库编码 VIA 关键词不得作为过渡名（默认通用数据、2608R1，证据：424 `Terminal/ZSOF/ZSOF-4M.pdf`、`ZSOF-4P.pdf`、`Terminal/ZBCD/ZBCD-4Z02.pdf`、`Terminal/ZSWX/ZSWX-4H.pdf`/`4K.pdf`/`4L.pdf`、`Terminal/ZUYB/ZUYB-4G.pdf`/`4H.pdf` 的直接标题，r125 完整 SDK 构建、独立 `validate` 与 `tests/test_pdf_charts.py`，2026-08-18）：`RWYxx进近过渡 via IDENT` 中的 `VIA` 是关键词，过渡名必须取随后的定位点标识。`_DATABASE_APPROACH_PROCEDURE` 与 `_DATABASE_TARGET_FAMILY_APPROACH` 的 `transition` 组必须排除 `VIA`，才能让 `via_transition` 生效。r124 把 ZBCD/ZSWX/ZUYB 的多条过渡合并为 `name="VIA"`；r125 拆成 `CD605`/`CD604`/`CD704`/`CD705`、`WX205`/`WX207`/`WX211`/`WX912`/`WX306`/`WX304`、`YB516`/`YB518`/`YB616`/`YB618`。ZSOF/R15 与 R33 仍无主段，继续 `no_unique_primary`。`_EVIDENCE_CACHE_VERSION` 升至 43，候选构建应使用 `pdf-evidence-cache-2608r1-r43`。相对 r124 只改变两个覆盖层的 `ZB_airports.bgl`、`ZS_airports.bgl`、`ZU_airports.bgl`、相应索引/布局与报告。IAP 未决仍为 12。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_database_via_keyword_is_not_a_transition_name`。
- 同标签 RNP AR 标题限定词分区（默认通用数据、2608R1，证据：424 `Terminal/ZUNZ/ZUNZ-4G06.pdf`、`ZUNZ-4G07.pdf`、`ZUNZ-9D.pdf` 至 `ZUNZ-9G.pdf` 的直接图页角色，r127 隔离 SDK 构建、独立 `validate`、`tests/test_iap_coverage.py` 与 `tests/test_bgl.py`，2026-08-18）：当同一 `Rxx` 组有多个 RNP AR 主进近时，只有全部匹配图都是不含 `ILS` 的带非跑道标题限定词 RNP AR 图、每个限定词只对应一张图、每个主进近占据不同数据库页、每个过渡名唯一拥有一张图且位于某个主进近页、全部图都被拥有且其余 IAP 段与某个主进近同页时，才可按所有权拆成多条 `rnpAr` 进近。不得发明 Y/Z 后缀。多图所有权只投影完全一致的直接角色或其后的非空交集，不选择具体变体。混入 ILS、共享限定词、跨主进近重叠所有权、剩余未拥有图、或两个主进近同页时继续拒绝。该规则只读取 424 直接文本，不使用 OCR、参考成品或 Fenix。r127 将 `ZUNZ/R23` 拆为 `LZ306`（DUMIX/ELNUN/LZ430，交集 `LZ295/FAF`）与 `LZ404`（GOMON，无主进近角色），IAP 未决由 11 降至 10；相对 r126 只改变两个覆盖包的 `ZU_airports.bgl`、相应索引/布局/包大小与报告。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_iap_coverage_partitions_same_label_rnp_ar_primaries_by_title_qualifiers`、`test_iap_coverage_rejects_invalid_rnp_ar_title_qualifier_partitions`、`test_bgl_projects_same_label_rnp_ar_primaries_partitioned_by_title_qualifiers`。
- 多图 RNP 直接角色交集投影（默认通用数据、2608R1，证据：424 `Terminal/ZUNZ/ZUNZ-4G05.pdf`、`ZUNZ-9A.pdf`、`ZUNZ-9B.pdf`、`ZUNZ-9C.pdf` 的直接图页角色，r126 完整 SDK 构建、独立 `validate` 与 `tests/test_iap_coverage.py`、`tests/test_bgl.py`，2026-08-18）：当唯一图页选择失败后，只要全部标题兼容候选都是不含 `ILS` 的 RNP 图、`(AR)` 属性一致、非 AR 标题互异，并且每张图对数据库主进近腿都给出非空直接角色，就可投影这些角色集合的交集，而不选择或假定任一图页对应具体变体。同一 ident 被赋给互斥角色时整组拒绝；只出现在部分图页上的额外角色省略。该规则不得抢占已有的唯一 `MAPT`、主角色或标题选择。混入 ILS、混合 AR/非 AR、非 AR 重复标题、空交集或角色冲突时继续拒绝。只读取 424 直接文本，不使用 OCR、参考成品或 Fenix；审计字段为 `source_intersecting_direct_role_selections`。r126 对 `ZUNZ/R05` 的三张 RNP AR 图投影共同的 `LZ186/FAF`，IAP 未决由 12 降至 11；相对 r125 只改变两个覆盖层的 `ZU_airports.bgl`、相应索引/布局与报告。候选本地契约通过但仍不与参考包字节一致。自动化测试：`test_iap_coverage_projects_intersecting_direct_roles_without_selecting_a_variant`、`test_iap_coverage_rejects_conflicting_intersecting_direct_roles`、`test_iap_coverage_rejects_mixed_ils_intersecting_direct_roles`、`test_iap_coverage_rejects_mixed_ar_intersecting_direct_roles`、`test_iap_coverage_keeps_unique_mapt_when_shared_faf_could_intersect`、`test_bgl_iap_chart_roles_reuse_intersecting_direct_role_consensus`。
- 关键点来源覆盖审计无新增规则（默认通用数据、2608R1，证据：r98 完整 `00_enroute.bgl` 只读语义差分、`general-doc-keypoint-audit`、`terminal-coordinate-audit --check-retention`、经 SHA-256 校验的 `GeneralDoc/航路_4.4重要点名称代码.pdf` OCR 缓存与终端 PDF 缓存，2026-08-17）：1,016 个参考独有全局航点身份中，GeneralDoc 4.4 分类为 814 个标识不存在、1 个区域歧义、154 个区域不一致、38 个 FIR 边界附近、9 个 FIR 多边形外，`general_doc_source_promotable=0`；终端坐标页分类为 861 个不存在、10 个多坐标、145 个仅单机场，亦无可安全提升项。当前可用 424 结构化数据和已审核图表不能新增这批全局航点，禁止按参考身份、坐标或区域反向填充。自动化保护：`test_general_doc_keypoint_audit_keeps_source_categories_redacted`、`test_terminal_coordinate_audit_keeps_source_categories_redacted`、`test_terminal_coordinate_audit_reports_unretained_airport_coordinate`。

## 2026-08-19 项目状态与后续计划

以下状态优先于早期“开发中”描述。它只记录当前仓库可复现的事实；参考成品仍是只读差分对象，不是内容来源。

### 状态面板

- 仓库：`main` 与 `origin/main` 同步于 `43caa66`，工作区干净，公开仓库为 `JCH2333/defult_navdata_converter`。
- 自动化测试：`372 passed`。
- 最新候选：`output/candidate-2608-default-r162-airway-coordinate-precision`。
- 候选状态：`status=candidate`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`、实机验证未完成。
- 参考文件集合：主包 `15/15`、机场补丁 `14/14`，缺失 `0`、额外 `0`；当前逐文件 SHA-256 相等为 `0/29`。
- 中间模型数量：机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`。
- IAP：`780` 个程序分组，`10` 个 `no_unique_primary` 未决；未决清单由转换报告生成，不能由参考成品补齐。
- 航路：候选 `4434` 行、参考 `4614` 行；严格相等 `1383` 行（`31.19%`），字段差异 `2045` 行，候选独有逻辑键 `1006`，参考独有逻辑键 `1186`。
- 航路来源：4446 条源段中 4434 条已投影，12 条因端点区域为空跳过；5 个指定点区域仍未解析。来源审计显示 2030 条字段差异行拥有同源航路、同序号和候选端点对。
- 航路拓扑：1354 条航路无序号重复、缺口、按序端点断裂和多连通分量；r163 已证明必须同时写 `Next` 与 `Previous`；r167 整体反转 `CODE_DIR=B` 使严格相等降至 `1305`，已否决。
- 官方无 NAIP 基线：已备份于工作区 `backups/default_navdata_2608_official_no_naip_20260811_162644`；本次检查存在，包含 2228 个文件。
- 交付状态：没有覆盖 Community，没有正式 Release，没有用户实机验证。当前“管线开发完成度较高”不等于“字节一致完成”。

### 下一阶段执行顺序

1. **冻结 r162 基线**：保存候选报告、29 个文件清单、BGL layout audit、完整脱敏 semantic diff、airway field delta source audit 和 source-gap audit 的相互引用；所有新实验使用新 r 编号，不修改 r162。
2. **航路差异分类**：围绕 2030 条同源字段差异，按端点 `float32`、包围盒、fragment、sequence、airway type、空值、最低高度和区域键建立只输出字段名/计数的分类器。源拓扑序号已经证明连续，不再重复做同名序号审计。
3. **最小 SDK 探针**：一次只改变一个变量，依次验证 Route 子节点排序、同名航路分组、fragment 边界、物理插入顺序、端点文本精度、包围盒触发和最低高度表达。每次保留 XML、进程轨迹、BGL 头部、读取器登记数和结论。
4. **来源缺口审计**：对 12 条跳过航段、5 个未解析航点和参考独有航点/航路，只允许使用当期 424 直接表、可验收 PDF/OCR、FIR/ACC/邻接等来源规则。不能由参考逻辑键、坐标、字段或 Fenix 记录反向填充。
5. **IAP 十组逐组处理**：当前为 `ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。仅在形成唯一来源链和正反例测试时加入正式规则；否则保持拒绝。
6. **机场 BGL 与索引收敛**：逐文件比较 `00_enroute`、十个区域机场 BGL 和十个机场补丁 BGL 的路径、大小、头部、节表、输入 XML 排序和 SHA-256。机场 XML 不写 `AiracCycle`，航路 XML 保留；机场替换先写 `DeleteAirport`。
7. **确定性与可复用性加固**：为输入锁定、证据缓存、模型快照、目标 profile、构建工具、输入哈希、输出哈希、验证报告建立统一 manifest；其他 424 周期和其他目标适配器只替换输入/profile，不复制解析逻辑。
8. **验收与部署**：只有参考范围内 `29/29` 文件 SHA-256 一致、本地验证全通过、干净重建可重复、游戏关闭、完成带时间戳备份并通过 `ZBCF`/`ZUNZ`/`ZUUU` 和退出稳定性实机验证，才允许 `status=release`、覆盖 Community 和创建正式 Release。

### 固定工作流

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `source.py` 只负责 424 来源和规范化模型，不加入目标机模分支。
- `bgl.py`/`package.py` 只负责默认 BGL profile、SDK XML、ASCII 暂存、Package Tool 和产物组装。
- 语义差分必须 `read_only=true`、`reference_values_redacted=true`，且所有请求的 BGL 都完整登记。
- 诊断失败实验保留在 `diagnostics`，不修改正式适配器；被否决的假设必须记录，避免重复试错。
- GUI、CLI 和部署函数共用同一验证/门禁；GUI 不得提供绕过 `deployable` 的覆盖入口。
- 新目标格式必须先登记官方基线、加载路径、schema、排序、元数据、降级策略、最小 fixture 和实机清单，再实现独立 adapter。

### 每轮状态更新要求

每次 Codex 继续工作时，先读取本文件和工作区根目录 `AGENTS.md`，运行 `git status --short --branch`，确认最新候选和测试结果。开始实验前记录假设、唯一变量、输入快照和预期指标；结束后记录候选目录、提交号、测试、构建、差分计数、来源审计、改善/恶化及保留/否决结论。每次代码或仓库文档改动后运行测试与 `git diff --check`，检查暂存区并提交、推送 GitHub。报告必须区分自动化测试、结构化构建、本地读取器诊断、用户实机验证和正式发布。

### 当前首个执行任务

从 r162 完整脱敏航路差分和 `r162-airway-field-delta-source-audit.json` 开始，生成“候选逻辑键 -> 424 航路名/序号”的脱敏关联统计，并定位 fragment、sequence、端点字段三类差异的最小复现实验。完成前不修改 `CODE_DIR` 投影、不回填参考记录、不覆盖 Community。
## 当前进度与详细执行计划（2026-08-19）

### 状态摘要

- 当前提交：`98f3ebb docs: record current status and reusable conversion plan`；工作区干净；`main` 与 `origin/main` 同步。
- 当前候选：`output/candidate-2608-default-r162-airway-coordinate-precision`。
- 候选状态：`status=candidate`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`；未覆盖 Community、未进行实机验证、未创建正式 Release。
- 参考范围：主包 `15/15`、机场补丁 `14/14`，缺失 `0`、额外 `0`；SHA-256 相等 `0/29`。
- 自动化测试：`372 passed`。这只证明当前代码回归通过，不代表参考包一致或游戏运行时通过。
- 当前模型规模：机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`。
- IAP：`780` 个分组，`10` 个 `no_unique_primary` 未决；未决清单以转换报告为准。
- 航路：候选 `4434` 行、参考 `4614` 行；严格相等 `1383` 行（31.19%）；字段差异 `2045` 行；候选独有逻辑键 `1006`、参考独有键 `1186`；`12` 条因端点区域未解析跳过，`5` 个指定点区域仍未决。
- 源拓扑：`1354` 条航路、`4446` 条航段无序号重复、无序号缺口、无按序端点断裂、无多连通分量。r163 已确认同一航段必须同时写 `Next` 和 `Previous`；r167 整体反转 `CODE_DIR=B` 已否决。

### 分阶段门禁

1. **来源与中间模型：已完成基础链。** 424 CSV/PDF 已进入可序列化 `NavModel`，保留来源引用、原始精度、拒绝项和证据边界。
2. **默认 BGL 构建链：已完成测试链。** 可生成两套覆盖包、索引、布局和元数据；已验证 ASCII 暂存和 Package Tool 进程等待规则。
3. **本地契约和自动化：已完成当前基线。** 结构化验证、BGL 审计、差分脱敏和 GUI/CLI 门禁可运行。
4. **内容收敛：进行中。** 航路、来源缺口、IAP 和编译布局仍存在差异。
5. **逐文件字节一致：未完成。** 必须达到参考范围 `29/29` SHA-256 一致。
6. **部署和实机：未开始。** 在前两项未完成时禁止覆盖 Community。

### 后续工作顺序

#### A. 冻结 r162

- 不修改 r162；保存报告、29 个文件清单、BGL layout audit、完整脱敏 semantic diff、字段来源审计和 source-gap audit 的路径引用。
- 新实验使用递增的 `rNNN`，每轮只改变一个变量；开始前记录输入 SHA-256、工具版本、假设、预期指标和禁止读取的数据。

#### B. 航路差异分类器

- 新增独立模块，例如 `airway_diff_audit.py`，不修改正式投影。
- 输入 r162 完整脱敏差分、`r162-airway-field-delta-source-audit.json`、`NavModel` 或候选 XML 的来源映射。
- 输出只保留字段名、计数、来源完整性、候选逻辑键摘要和分类标签；禁止输出参考坐标、参考记录和可反向补齐的参考身份。
- 覆盖最小 fixture：端点字段、包围盒、fragment/sequence、最低高度、来源缺失、来源完整，并测试报告不泄漏参考值。

#### C. 最小 SDK 探针

- 只针对分类后仍无法解释的字段，逐一改变 Route 子节点顺序、同名航路分组、fragment 边界、物理插入顺序、端点文本精度、包围盒触发字段和最低高度表达。
- 每个探针保存 XML、输入哈希、构建轨迹、BGL 头部/节表、读取器登记数、输出哈希和结论。
- 若严格相等行没有增加或字段差异恶化，保留诊断并否决，不修改正式适配器。

#### D. 来源缺口与 IAP

- 对 `12` 条跳过航段、`5` 个未解析指定点和参考独有对象，只允许使用 424 直接表、同机场坐标页、标准程序路线表、已验收 GeneralDoc/AD 证据及明确 FIR/ACC/邻接规则。
- IAP 十组逐组取证：`ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。
- OCR 只可参与已有数据库主进近和已有匹配 PDF 的多缓存共识；不能新增主进近、航段、图页匹配或坐标页航点。
- 每条正式规则必须有正例、拒绝例、报告计数和 BGL 回归；不能形成唯一证据链时保持拒绝。

#### E. BGL、索引和确定性

- 分别比较 `00_enroute.bgl`、十个主包机场 BGL、十个补丁包机场 BGL 的路径、大小、SHA-256、BGL 头部、QMID、节表、输入 XML 和投影计数。
- 机场 XML 不写 `AiracCycle`；航路 XML 保留。机场替换先写 `DeleteAirport`，再按稳定顺序写跑道、终端点、程序和等待航线。
- 固定 SDK/Package Tool 版本、ASCII 暂存路径、包名、文件名、元数据、布局排序和构建时序；先验证候选自身可重复，再做参考差分。

#### F. 复用管线和其他格式

固定管线为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `source.py` 只解析 424 并生成中间模型，不加入目标机模分支。
- `NavModel` 是跨格式边界；BGL、Fenix、TFDI、PMDG、FSL/FSLabs、iFly 等适配器分别消费快照。
- 每个新目标先登记 profile：官方基线、实际加载路径、schema、字段/单位、空值语义、物理顺序、元数据、降级策略、最小 fixture、验证命令和实机清单。
- GUI、CLI、自动更新和部署共用同一 profile、报告格式和门禁；任何界面都不能绕过 `deployable=false`。
- 每次输出保存输入 manifest、模型版本、适配器版本、构建工具版本、候选文件清单、逐文件哈希、验证报告和差分报告，便于未来周期复用。

#### G. 最终验收

- 达到 `29/29` 字节一致后，从干净输入重建一次，验证输出、报告和构建过程可重复。
- 部署前确认 `FlightSimulator2024.exe` 完全退出，备份目标包、周期文件、布局和元数据，执行恢复演练。
- 用户实机验证至少覆盖 `ZBCF`、`ZUNZ`、`ZUUU`、机场输入、出发/抵达、跑道、SID、STAR、IAP、航路查询、典型点选、退出飞行和退出模拟器。
- 只有逐文件字节一致、本地验证通过、备份可恢复和实机通过全部成立，才允许 `status=release`、覆盖 Community 和创建正式 Release。

### 每轮 Codex 更新格式

1. 先读本节、根目录 `AGENTS.md`、`git status` 和最新候选报告。
2. 记录本轮唯一假设、输入快照、禁止数据、预期指标和实验编号。
3. 先加最小回归或运行最小探针，再决定是否修改正式适配器。
4. 记录候选/诊断目录、提交号、测试、构建、参考文件数、严格相等行、字段差异、来源审计和保留/否决结论。
5. 代码或文档变更后运行测试、`git diff --check`，检查暂存区，只提交一个可解释变更并推送 GitHub。
6. 状态报告必须分别说明自动化测试、结构化构建、本地读取器诊断、用户实机验证和正式发布状态。
### 2026-08-19 航路差异分类器执行日志

- 实验编号：`airway-diff-audit-v1`；输入为 r162 完整脱敏 `semantic-diff`、r162 `source-gap` 审计和 `output/intermediate-2608-r155-airway-identities.json.gz`。未读取 Fenix 数据、参考字段值或参考 BGL 记录，未修改正式 `CODE_DIR` 投影。
- 新增 `src/fenix_default_navdata/airway_diff_audit.py` 和 CLI 子命令 `airway-diff-audit`。模块消费 `NavModel` 快照，按几何、拓扑、最低/最高高度、航路元数据分组，并对候选逻辑键与 424 `(airway, sequence)` 输出 SHA-256 关联摘要。
- 新增 `tests/test_airway_diff_audit.py`，覆盖字段分组、混合字段、来源匹配/缺失、脱敏、截断输入、未知字段和 CLI 输出。
- 定向测试：`25 passed`（航路分类器、source-gap 和 CLI）。
- r162 实际诊断：总字段差异 `2045`；几何组 `2045`；高度组 `30`；独占分类为几何 `2015`、混合 `30`；2045 条均为 `same_source_airway_and_sequence`，来源航路名数量 `1354`，唯一来源 `(airway, sequence)` 摘要 `2045`。报告路径：`diagnostics/r162-airway-diff-audit.json`。
- 结论：本轮确认 r162 字段差异不是来源航路名/序号缺失造成的，主要应继续研究目标 BGL 的坐标/包围盒表达与 Package Tool 记录归并。该结论只用于下一轮最小 SDK 探针，不直接改变正式适配器。
## 2026-08-19 当前状态与后续执行计划（必须维护）

### 1. 当前真实状态

- 公开仓库：`https://github.com/JCH2333/defult_navdata_converter`；最近已推送提交为 `9dc8795 feat: add redacted airway diff audit`。开始工作前必须重新检查 `git status --short --branch`，不得把未提交实验误记为已完成或已推送功能。
- 最后一个可用候选是 `output/candidate-2608-default-r162-airway-coordinate-precision`：
  - `status=candidate`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`；
  - 参考范围为主包 15 个文件和机场补丁包 14 个文件，文件集合缺失/额外均为 0，但 SHA-256 一致为 `0/29`；
  - 没有覆盖 Community，没有用户实机验证，没有正式 GitHub Release。
- r162 中间模型规模：机场 275、跑道方向 640、导航台 438、全局航点 2741、航路段 4446、终端航点 12549、程序段 10409、ILS 430、等待航线 1297。基础来源解析与可序列化 `NavModel` 已具备，不能把“模型已生成”表述为“字节一致已完成”。
- r162 航路语义基线：候选 4434 行、参考 4614 行、严格相等 1383 行（31.19%）、字段差异 2045 行、候选独有逻辑键 1006、参考独有逻辑键 1186。脱敏 `airway-diff-audit` 已确认 2045 条字段差异全部能唯一关联到已有 424 `(airway, sequence)`；其中 2015 条仅几何、30 条为几何加高度。因此不能把问题归因于源航路名或序号缺失。
- IAP 当前有 780 个程序分组，仍有 10 个 `no_unique_primary` 未决分组：`ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。它们必须保持拒绝，直至形成唯一、可回溯的 424/PDF 证据规则。
- 当前工作区包含未提交的航路 `Route` 子节点探针及其临时投影修改。`bglcomp.xsd` 已明确 `ctRoute` 为 `Previous*` 后 `Next*`，两者均允许多个；r169 将同一 `Route` 排序为 `Next` 后 `Previous`，因此主导航包在 `00_enroute.xml` 第 26030 等行被 SDK 以“`Previous` 为意外元素，期望 `Next`”拒绝。r169 的 `local_contract_verified=false`，只是失败诊断，不是可比较候选，也不计入字节一致进度。

### 2. 进度口径

不得用单一百分比掩盖未解的格式契约。每次状态报告必须同时列出以下阶段及出口条件：

| 阶段 | 当前状态 | 通过条件 |
| --- | --- | --- |
| 输入锁定与 424 归一化 | 已完成基础链路 | 输入清单、SHA-256、AIRAC 和 `NavModel` 可重建 |
| 默认 BGL/Package Tool 构建 | 已完成基础链路 | ASCII 暂存、过程等待、包结构与元数据检查通过 |
| 本地验证和脱敏审计 | 已完成 r162 基线 | `validate`、布局审计、语义差分、来源审计均可重复 |
| 航路 SDK 表达与语义收敛 | 进行中 | 最小探针确认合法表达；新候选可编译且指标改善 |
| 来源缺口闭合 | 进行中 | 12 条跳过航段、5 个未决指定点逐项有来源规则或明确拒绝 |
| IAP 未决闭合 | 进行中 | 10 组逐项有正反例和可审计规则，不能靠参考成品补齐 |
| 逐文件字节一致 | 未开始达标 | 参考范围 SHA-256 为 `29/29` |
| 部署与实机验收 | 未开始 | 字节一致、可恢复备份、用户实机清单全部通过 |

当前可称为“转换基础管线已建立、内容收敛阶段进行中”；不得称为“完成度接近上线”。若必须估算整体工程进度，只能说明约 40% 至 50%，而字节级一致进度仍是 `0/29`。

### 3. 固定工作管线

未来任何 424 周期或新目标格式均按以下链路执行：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

1. `lock-inputs`：记录原始 CSV/PDF、官方模板、SDK、读取器和工具的版本、路径、AIRAC、文件树及 SHA-256。
2. `ingest-424` 与 `evidence-audit`：只解析 424 CSV/PDF；OCR 仅在其自身缓存契约、可复跑参数和来源回链都满足时作为受限证据，不能成为一次性人工识别结果。
3. `normalize-model` 与 `model-audit`：生成可序列化 `NavModel`，保留来源引用、原始精度、拒绝原因和规则版本；目标专用逻辑不得写入 `source.py`。
4. `project-target`：每个目标只增加独立 profile/adapter，负责目标 schema、字段单位、空值语义、字符串限制、排序、元数据、降级策略和目标验证器。
5. `build-target`、`validate-target`、`diff-and-audit`：在隔离候选目录构建；报告必须分别标明自动化测试、SDK 构建、本地读取器诊断、语义差分和字节哈希，不能以其中任一项替代另一项。
6. `stage-backup-deploy`：只在全部门禁通过后执行。部署前确认游戏关闭，创建带时间戳的完整备份和恢复清单；测试包、诊断、数据库和备份不得提交 Git。

### 4. 接下来按顺序执行

#### A. 先闭合航路 XML 合法表达

1. 冻结 r162，不修改其输入、产物或报告；r168/r169 只作为诊断证据。
2. 从 `C:\MSFS 2024 SDK\Tools\bin\bglcomp.xsd` 提取 `Route`、`Next`、`Previous` 的顺序和出现次数约束，写成最小、可测试的契约。
3. 扩展 `airway-route-child-order-probe`，每次仅改变一个变量并保留 XML、构建轨迹、BGL 头和读取器结果：
   - 一个 `Previous` 后一个 `Next`；
   - 多个 `Next`；
   - 多个 `Previous`；
   - 多个 `Route` 元素，每个仅表达一对连接；
   - 分叉、汇聚和同名航路片段边界。
4. 只有最小探针证明某一表达可被 SDK 编译并被读取器完整登记后，才修改 `_append_enroute`。若 XSD 要求拆分 `Route`，必须按证明的关系拆分，不得靠全局排序、反转 `CODE_DIR` 或丢弃端点规避错误。
5. 新建 r170 或更高编号候选，先确认全包编译和 `validate` 成功，再运行完整脱敏语义差分、`airway-diff-audit`、布局审计和来源缺口审计。新候选仅在严格相等增加、字段差异减少且来源审计没有违规时保留。

#### B. 航路内容与来源缺口收敛

1. 对 12 条跳过航段和 5 个未决指定点逐项建立来源卡片：原始文件、唯一身份键、允许恢复的字段、拒绝条件、最小 fixture 和报告计数。
2. 允许的证据仅限当前 424 直接表、可审计 PDF/OCR、FIR/ACC/邻接等可复现来源规则；严禁读取参考 BGL/SQLite、参考坐标、参考记录或 Fenix 数据回填。
3. 将航路差异按几何、边界框、fragment、sequence、高度、区域、空值和物理写入顺序继续分类。已否决的 `CODE_DIR` 简单映射、整体反转、单向连接、猜测 `routeType` 等方向不得重复尝试，除非有新的独立证据。

#### C. IAP 与机场内容收敛

1. 逐组处理 10 个未决 IAP；每条正式规则必须有一个正例、至少一个拒绝例、来源路径、审计字段和 BGL 投影回归。
2. OCR 只能用于已存在的数据库主进近和已匹配 PDF 的多缓存共识，不能新增主进近、航段、图页匹配或坐标航点。
3. 分开审计 `00_enroute.bgl`、每个区域机场 BGL、每个机场补丁 BGL、`bglIndex.bout`、`layout.json`、`manifest.json` 和 ContentInfo。SDK 节表差异是诊断信号，不得直接反推参考记录。

#### D. 可复用性与确定性加固

1. 为每次候选生成统一 manifest：输入哈希、证据缓存版本、`NavModel` 格式版本、profile/adapter 版本、SDK/读取器版本、命令、候选文件清单、逐文件 SHA-256、验证和差分报告路径。
2. 将“输入检测、模型导出、目标投影、目标验证、只读差分、备份/部署”保持为 CLI、GUI 和自动更新系统共用服务；GUI 不得绕过 `deployable=false`。
3. 新格式接入前先在本文件登记 profile 契约：官方基线、真实加载路径、格式/schema、字段与单位、NULL/default、排序、元数据、不可表达字段降级、fixture、验证命令、实机清单和已知限制。

#### E. 最终验收与部署

1. 只有参考范围 `29/29` 文件 SHA-256 一致后，才从干净输入完整重建一次，并证明候选、报告和哈希可重复。
2. 然后确认 `FlightSimulator2024.exe` 已关闭，备份 Community 中的目标覆盖包及全部元数据，执行恢复演练，再进行覆盖。
3. 用户实机验收至少覆盖 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点选择、退出飞行和退出模拟器。全部通过前仅允许测试版，禁止正式 Release。

### 5. 每轮必须更新的记录

每轮开始前读取根目录与仓库 `AGENTS.md`、检查 Git 状态和最后可用候选。实验前记录：r 编号、唯一假设、唯一变量、输入快照、禁止读取的数据、预期指标。实验后记录：候选或诊断目录、提交号、测试结果、SDK 构建结果、读取器登记完整性、`29` 文件哈希统计、严格相等/字段差异、来源审计、保留或否决结论。

代码或仓库文档变更后必须运行对应测试、`git diff --check`、审查暂存区、创建单一可解释提交并推送 GitHub。根目录 `AGENTS.md` 不属于仓库，但其同一项目规则必须同步更新。

### 6. 2026-08-19 航路 Route 子节点契约更正日志

- 证据：`C:\MSFS 2024 SDK\Tools\bin\bglcomp.xsd` 的 `ctRoute`。它定义为 `Previous` 的 `minOccurs=0/maxOccurs=unbounded`，随后是 `Next` 的 `minOccurs=0/maxOccurs=unbounded`。因此合法顺序是 `Previous* -> Next*`，而不是反向；分叉和汇聚不受单个子节点数量限制。
- r169 失败根因：临时实现把同一 `Route` 排成 `Next -> Previous`，在候选 `00_enroute.xml` 第 26030 等行触发 Package Tool 的“`Previous` 为意外元素，期望 `Next`”。该候选 `local_contract_verified=false`，不得用于语义差分、部署或任何进度改善结论。
- 正式投影已改为稳定的 `Previous* -> Next*` 排序；`airway-route-child-order-probe` 改为三种 XSD 合法场景：线性、两个 `Previous` 的汇聚、两个 `Next` 的分叉。回归：`test_enroute_projection_writes_previous_before_next_in_shared_route`。
- r171：探针已生成 XML、项目和 `probe-report.json`，但检测到 `FlightSimulator2024.exe` 仍在运行而在编译门禁退出。报告的 `status=failed`、`failure_stage=compile` 是外部状态阻断，不是 XML 合法性或目标投影失败。探针现在保证在编译或读取器失败时仍写入结构化报告；对应自动化测试：`test_run_probe_writes_compile_failure_report`。
- 待执行：模拟器关闭后，使用 r171 的同一三种场景重新运行新的 r 编号，要求 Package Tool 成功、读取器完整登记一个 BGL，并检查三种场景的片段号、序号和几何。该验证通过后才可把阶段 A 标记为完成并构建新的完整候选。

### 7. 2026-08-19 未决航路端点来源审计日志

- 新增可复用 CLI `airway-endpoint-audit`，只消费 `DESIGNATED_POINT.csv` 和 `RTE_SEG.csv` 归一化后的 `NavModel`；报告 `read_only=true`、`reference_values_redacted=true`，用于输出空区域端点、相邻地区、ACC 名称、关联源行和拒绝类别，不能作为参考成品回填通道。
- r173 报告：11 个空区域端点身份关联 25 条源航段。其中 8 个是多地区邻接的 FIR 边界点，2 个为不在 `DESIGNATED_POINT.csv` 唯一身份集合中的端点，1 个 `LELIM` 虽只有 `ZG` 邻接但其 `M503` 航段同时含上海/广州 ACC 证据，不能绕过 ACC 一致性门禁恢复。r162 的 12 条未投影航段仍无可安全恢复项。
- 自动化覆盖：`tests/test_airway_endpoint_audit.py` 与 CLI 回归。后续只有发现能唯一绑定到端点、且与全部 FIR/ACC/邻接证据一致的当前 424 直接来源时，才可新增恢复规则；否则保持拒绝并在候选报告计数。
## 2026-08-19 权威状态与执行计划（后续维护入口）

本节优先于本文件中较早的状态摘要和执行计划；历史章节保留为实验记录。每次继续本项目时，先核对并更新本节。

### 当前真实基线

- 公开仓库：`https://github.com/JCH2333/defult_navdata_converter`；当前已推送提交为 `372c8d6 feat: audit reader semantic reproducibility`。开始工作前必须重新运行 `git status --short --branch`，不得把本地诊断或未提交工作误记为已推送。
- 冻结的内容比较基线是 `output/candidate-2608-default-r162-airway-coordinate-precision`；最新有效候选是 `output/candidate-2608-default-r175-route-shape-verified`。r175 使用同一正式投影，`00_enroute.bgl` 与 r162 同为 `2,867,006` 字节且 SHA-256 相同；它只确认 Route XML 的 SDK 合法性，不代表内容收敛改善。两者均为测试候选：`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`。
- 参考范围已完整复现为主覆盖包 `15` 个文件、机场补丁覆盖包 `14` 个文件；r175 无缺失或额外文件，逐文件 SHA-256 相等仍为 `0/29`。因此不能部署、不能标记 release，也不能将局部语义改善表述为字节一致。
- 全量自动化测试基线为 `387 passed`。这只证明代码回归通过；SDK 编译、离线读取器、参考语义差分、用户实机验证和正式发布必须分别报告，互不替代。
- 424 归一化模型已经可复建且可序列化：机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`。模型存在不等于目标内容或二进制已经收敛。
- 航路 r162 基线：候选 `4434` 行、参考 `4614` 行、严格相等 `1383` 行、字段差异 `2045` 行、候选独有逻辑键 `1006`、参考独有逻辑键 `1186`。脱敏审计确认 `2045` 条字段差异全部唯一关联当前 424 的 `(airway, sequence)`；其中 `2015` 条仅几何差异，`30` 条为几何加最低高度差异。
- IAP 有 `780` 个分组，仍有 `10` 个 `no_unique_primary`：`ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。未形成唯一、可回溯的 424/PDF 证据链前必须保持拒绝。
- `Route` XML 已由 SDK XSD 和 r174 Package Tool 探针确认合法顺序为 `Previous* -> Next*`，两类子节点都可多次出现。线性、汇聚、分叉均已真实编译，并由读取器完整登记 `1/1` 个 BGL、`8` 条航路；r169 的 `Next -> Previous` 仅是失败诊断，不能用于候选比较。读取器的航路表尚不稳定，不能直接作为内容收敛指标。
- 航路端点来源审计 r173 确认 r162 跳过的 `12` 条航段暂无安全恢复项：11 个空区域端点关联 25 条源航段，8 个是多地区邻接边界点，2 个无法建立唯一指定点身份，`LELIM` 虽有唯一邻接区域但 ACC 证据不一致。不得降低 FIR/ACC/邻接一致性门禁。
- 当前 `FlightSimulator2024.exe` 已确认不在运行。可以执行下一轮隔离 SDK 探针；在通过全部最终门禁前，仍不得覆盖 Community。

### 进度口径

不得用单一百分比掩盖格式契约和来源边界。状态报告必须使用下表，并同时报告参考文件哈希数。

| 阶段 | 当前状态 | 阶段出口条件 |
| --- | --- | --- |
| 输入锁定、424 解析与 `NavModel` | 基础链路完成 | AIRAC、输入清单、SHA-256、来源引用和模型快照可从干净输入重建 |
| 默认 BGL/Package Tool 构建 | 基础链路完成 | ASCII 暂存、异步进程等待、包结构、元数据与确定性构建检查通过 |
| 本地验证与脱敏审计 | r162 基线完成 | `validate`、BGL 布局审计、完整脱敏语义差分、来源缺口审计可重复 |
| 航路 SDK 表达 | 探针完成 | r174 已证明三种 `Previous* -> Next*` 形状可编译并完整登记；不得重试已否决形状 |
| 航路内容收敛 | 进行中且受诊断门禁约束 | 先通过 `semantic-reproducibility-audit`，再以稳定表的严格相等增加或差异减少作为指标 |
| 机场来源对象盘点 | r176 完成 | 每类已建模 424 对象均有来源分组、归属、可表达性和拒绝原因；通信仍需独立来源契约 |
| 机场 SDK 表达 | 进行中 | 对 r176 中来源完整且尚无已否决实验的对象执行单变量探针；不得将空域无线电或诊断对象伪装为机场子对象 |
| 来源缺口闭合 | 进行中 | 每个跳过航段和空区域端点都有可复用来源规则，或明确、可审计地拒绝 |
| IAP 未决闭合 | 进行中 | 10 组逐项具备正例、反例、来源链、审计计数和 BGL 回归，或明确拒绝 |
| BGL、索引和元数据字节收敛 | 未达标 | 参考范围内 `29/29` 个文件 SHA-256 全部一致 |
| 部署与实机验收 | 未开始 | 字节一致、可恢复备份、用户实机清单全部通过 |

可称为“转换基础管线已建立，内容和二进制收敛进行中”。整体工程只能粗略估为约 `40%` 到 `50%`；字节级验收进度必须单独表述为 `0/29`，不得与代码或测试完成度混淆。

### 接下来按顺序执行

1. **冻结 r162/r175 并建立候选指标摘要。** 不修改两个候选的输入、报告或哈希。新实验使用递增 `rNNN`，在报告开头记录单一假设、唯一变量、输入 SHA-256、工具版本、禁止读取的数据和预期指标；候选摘要必须同时列出 `29` 文件哈希、IAP 未决、跳过航段、BGL 布局和可重复性门禁。
2. **把读取器可重复性设为语义差分前置条件。** 对同一单 BGL 至少独立读取两次，执行 `semantic-reproducibility-audit`。只有表的归一化行多集指纹稳定时，才能把该表的严格相等、逻辑键和字段差异用于“改善/退化”判断；r175 已确认 VOR、NDB、航点稳定，而航路表出现三种指纹，当前只能做结构与来源审计。
3. **维持 r176 机场来源对象库存。** `airport-source-inventory` 只读取 `NavModel` 和可选候选 XML，不读取参考导航记录。每次模型、机场投影或来源规则变化后必须重跑；库存需保留对象数、来源文件分组、机场归属、SDK 作用域、可表达性和拒绝原因。
4. **以库存驱动单变量 SDK 探针。** 每次选择一个能由 424 独立证明、尚无已否决实验的机场对象，在 `airport_subset_probe.py` 中构建最小输入。报告必须保存 XML、Package Tool 轨迹、BGL 头部/节表、读取器登记、输出哈希和结论。`CONTROLLED_RADIO.csv` 等空域扇区频率不构成机场 `Com/Tower` 来源；不得再尝试仅靠 `Ndb`、`onlyAddIfReplace`、根节点终端点重复或参考节表计数解释机场 BGL。
5. **按来源与目标表达分别收敛航路。** 对稳定表继续隔离坐标序列化精度、包围盒、fragment/sequence 切分、同名航路分组、物理写入顺序和最低高度表达；对 12 条跳过航段、5 个未决指定点及参考独有对象，只接受当期 424 结构化表、可审计 PDF、受限可复跑 OCR、FIR/ACC 几何和邻接规则。严禁读取 Fenix `nd.db3`、参考 BGL/SQLite 记录、参考坐标或参考逻辑键来回填。
6. **逐组处理 IAP 未决。** 每条新规则必须同时包含直接来源、正例、拒绝例、审计字段、最小 fixture 和 BGL 投影回归。OCR 只可作为已有 PDF 与已有数据库主进近之间的多缓存共识证据，不得创建主进近、航段、图页匹配或坐标航点。
7. **分文件推进确定性和二进制收敛。** 先证明同一干净输入的两次构建彼此字节一致，再将 `00_enroute.bgl`、机场分区 BGL、机场补丁 BGL、`bglIndex.bout`、`layout.json`、`manifest.json` 和 ContentInfo 分开对参考做只读哈希比较。固定 SDK、ASCII 暂存根、输入 XML 排序、包名、元数据和构建时序；机场 XML 不写 `AiracCycle`，航路 XML 保留，机场替换先写 `DeleteAirport`。
8. **执行最终验收和部署。** 达到 `29/29` 后从干净输入重建一次，确认结果和报告可重复；确认游戏关闭，创建带时间戳的完整 Community 备份和恢复清单并完成恢复演练；再由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只允许测试版，不得正式 Release。

### 可复用转换工作管线

所有未来 AIRAC 周期和目标格式必须遵循以下阶段，不得把目标专用规则写回 424 来源解析层：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 固化 424 CSV/PDF、官方目标模板、SDK/读取器/编译器版本、AIRAC、树清单与 SHA-256。
- `ingest-424` 和 `evidence-audit` 只产生可回溯来源；OCR 必须带缓存版本、渲染参数、模型/命令、页面哈希和回链验证，不能成为一次性人工判断。
- `normalize-model` 维护跨格式 `NavModel`、原始精度、来源引用、拒绝项和规则版本；任何目标 schema、字符串长度、空值、排序或元数据规则只能存在于目标 profile/adapter。
- `project-target` 为默认 BGL、Fenix、TFDI、PMDG、FSL/FSLabs、iFly 等分别建立独立 profile/adapter、降级策略、最小 fixture、目标验证器和实机清单；适配器消费模型快照，不重新解析 424。
- `build-target`、`validate-target` 和 `diff-and-audit` 只能写隔离候选目录。报告必须将自动化测试、结构构建、读取器诊断、语义差分、来源审计、文件树和 SHA-256 分开保存。
- 对同一 BGL 使用 Navdatareader 做航路语义差分前，必须至少执行两次独立读取并运行 `semantic-reproducibility-audit`。只有目标表的归一化行多集指纹一致时，才能将该表的严格相等、逻辑键和字段差异作为候选进展指标；不一致时仅保留读取器诊断，不得据此修改来源或 adapter。
- `stage-backup-deploy` 是唯一可写游戏文件的阶段。GUI、CLI 和 GitHub 自动更新系统必须共用同一 profile、候选报告和 `deployable` 门禁，任何入口都不能绕过测试版或部署保护。

### 每轮 Codex 维护要求

1. 开始前读取根目录和仓库 `AGENTS.md`，检查 Git、游戏进程、最后可用候选和最新报告。
2. 实验前记录 r 编号、单一假设、单一变量、输入/工具快照、禁止数据和成功/失败指标。
3. 先写最小测试或最小 SDK 探针，再改正式 adapter；一次实验只改变一个变量。
4. 完成后更新本节和对应经验章节，记录候选或诊断路径、提交号、测试、构建、读取器、语义差分、`29` 文件哈希、来源审计及保留/否决结论。
5. 每次代码或仓库文档改动后运行适当测试和 `git diff --check`，仅暂存相关文件，创建一个可解释提交并推送 GitHub。数据库、备份、日志、诊断产物、SDK 中间输出和外部测试包不得提交。
6. 任何状态汇报必须分开说明：自动化测试、SDK 构建、本地读取器诊断、参考哈希、用户实机验证和正式发布状态。

### 2026-08-19 r174-r175 工作日志

- r174 假设为“SDK XSD 合法的 `Previous* -> Next*` Route 子节点形状可被 Package Tool 编译并由离线读取器完整登记”。游戏关闭后，`airway-route-child-order-probe` 对线性 `Previous -> Next`、汇聚 `Previous -> Previous -> Next`、分叉 `Previous -> Next -> Next` 三个场景均通过：Package Tool 生成一个 `00_enroute.bgl`，读取器登记 `1/1` 个 BGL 和 `8` 条航路。读取器进程仍返回代码 `1` 并写 `_BROKEN.sqlite`，但 SQLite 完整、BGL 登记完整且目标行存在，这是已记录的离线读取器限制，不是 SDK 编译失败。结论：正式 `_append_enroute` 的 `Previous* -> Next*` 顺序是可编译、可读取契约；r169 的反序实验继续保持否决。
- r175 使用冻结的 `output/intermediate-2608-r155-airway-identities.json.gz`、已验证官方设施索引、官方 `navigraph-nav-base`/`navigraph-nav-jepp` 模板和 2608R1 只读参考构建。`validate` 通过，仍为 `status=candidate`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`，参考文件 SHA-256 仍为 `0/29`。候选与 r162 的 `00_enroute.bgl` 均为 `2,867,006` 字节、SHA-256 `d2abf742...d3b1`，因此 Route 形状验证没有改变正式投影或二进制内容；r175 仅作为可复现的 SDK 合法性确认，不计为字节收敛改善。
- r175 布局审计：21/21 个参考范围 BGL 都不相等。机场覆盖候选保持 `0x3/0x13/0x22/0x32/0x34/0x35`，参考普遍为 `0x3/0x13/0x17/0x22/0x32/0x33/0x34` 且分桶计数远高于候选。既有 r140/r141 已证明用 `Ndb` 或 `onlyAddIfReplace` 触发 `0x17/0x33` 不能解释来源数量和新增机场加载契约，故不得把该诊断结果接入正式 adapter。下一轮应继续以来源可证明的对象和隔离 SDK 探针研究机场 BGL 结构，而非根据参考节表反向填充。
- r175 三次独立 `read-package` 对相同 `00_enroute.bgl` 均完整登记 `1/1` 个 BGL，VOR/NDB/航点行数和归一化指纹稳定为 `121/133/3150`；航路行数均为 `4434`，但归一化行多集指纹有 `3` 个不同值。定位到 `H35` 的 fragment/sequence 几何解释在读取之间发生变化。新增 `semantic-reproducibility-audit` CLI 和回归测试；该审计不输出设施值，只输出指纹和稳定性。航路表在读取器一致性未恢复前不能作为严格相等、字段差异或候选改善的强验收依据，仍可用于受限的结构和来源审计。
- 下一轮计划已调整为“来源侧机场对象库存 -> 单变量 SDK 探针 -> 仅对稳定读取器表做语义收敛”。这是为了先区分 424 尚未投影的对象、SDK 编译布局和外部读取器不确定性，避免把参考节表或不稳定诊断误当作内容来源。库存和探针应成为未来 424 周期及其他目标格式 adapter 可直接复用的证据层输入。
- r176 新增 `airport-source-inventory`，使用冻结的 r155 `NavModel` 和 r175 自身 `china-navdata.xml` 输出 `diagnostics/r176-airport-source-inventory.json`。它只读模型和候选 XML，声明 `reference_records_read=false`。盘点到机场 `275`、跑道方向 `640`、终端航点 `12549`、ILS `430`、离场 `3530`、进场 `3949`、进近过渡 `1505`、进近 `721`、复飞 `691`、等待航线 `1297`；`13` 个空/未知程序枚举保持拒绝，`10` 个 IAP `no_unique_primary` 保持拒绝，`18` 个 `serviced_airport` 不属于来源机场集合的导航台不得投影为机场子对象。候选 XML 仅含来源已投影对象，不含 `Com`/`Tower`。2608 的 `CONTROLLED_RADIO.csv` 经表头与 `CONTROLLED.csv` 关联核验为 `APP_SECTOR` 空域扇区频率，不是机场通信数据，禁止作为 `Com`/`Tower` 来源。下一轮应从来源完整且没有既有否决结论的对象选择最小 SDK 探针，或先建立新的 424 来源契约；不得为追逐节表而伪造对象。
- r177 使用 r175 的 `ZU_airports.xml` 中来源完整的 `ZUAL` 跑道与 `Ils ident=IKS` 建立严格单变量 SDK 探针。两组均删除同一机场的航点、离场、进场、进近和等待航线，保留跑道；仅第二组通过诊断选项 `--drop-runway-child-tag Ils` 删除跑道内 ILS。Package Tool 均成功：保留 ILS 的 `zu_airports.bgl` 为 `687` 字节、节表 `0x3/0x13/0x32/0x35`；删除 ILS 后为 `459` 字节、节表 `0x3/0x35`。结论：来源完整 ILS 是 `0x13` 与 `0x32` 的充分触发条件，但不触发参考机场 BGL 中仍缺失的 `0x17/0x33`；当前适配器已投影 `430` 条来源 ILS，故本实验不改正式投影，也不能从节表计数推导应补写的对象。诊断目录：`diagnostics/r177-zual-runway-with-ils-20260819` 与 `diagnostics/r177-zual-runway-without-ils-20260819`。

## 2026-08-19 权威状态、进度与执行计划（r177 后续维护入口）

本节优先于此前所有默认通用数据状态摘要；历史章节仅保留为可复核实验记录。每次继续本仓库前，先检查本节、根目录 `AGENTS.md`、`git status --short --branch`、最后有效候选的 `conversion-report.json` 与最新诊断报告。发现状态不一致时，以实际 Git、候选报告和本轮测试结果为准，并在本节同步修正。

### 当前真实状态

- 仓库：`https://github.com/JCH2333/defult_navdata_converter`，`main` 已与 `origin/main` 同步；当前已推送 HEAD 为 `4006348 feat: probe runway child layout effects`。此前 `53b0af4 feat: audit airport source inventory` 与 `cd476a1 docs: refresh default navdata convergence plan` 已包含在该历史中。
- 冻结内容比较基线：`output/candidate-2608-default-r162-airway-coordinate-precision`。最新有效候选：`output/candidate-2608-default-r175-route-shape-verified`。r175 为隔离测试候选，`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`；不得部署 Community、不得创建正式 Release。
- 参考范围包含主覆盖包 `15` 个文件与机场补丁包 `14` 个文件。r175 的参考范围文件集合完整，但 SHA-256 相等仍为 `0/29`。字节级验收没有任何已确认的完成文件，不能把局部 SDK、读取器或单元测试结果表述为二进制收敛。
- 全量自动化测试基线为 `390 passed`。这只表示代码回归通过；SDK 构建、读取器诊断、参考哈希、用户实机和正式发布必须独立报告。
- 424 可序列化 `NavModel` 已覆盖机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`。模型是跨格式输入边界，不代表默认 BGL 内容已收敛。
- IAP 共 `780` 个程序分组，仍有 `10` 个 `no_unique_primary`：`ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。未形成唯一、可回溯的 424/PDF 证据链前必须保持拒绝。
- r176 来源库存还识别出 `13` 条 `kind=""` 的未分类程序段：ZGBS 的 `RNP-0`、ZHCC 的 `CC3-09/CC5-17/CC5-32`、ZPDQ/ZUKD/ZUSH 的 `EO-*`。它们当前不被正式投影分类覆盖；`EO-*` 不能仅凭名称猜测为发动机失效离场并写入目标。下一步首先做只读来源审计和显式拒绝报告，不得静默丢失或提前映射。
- 航路 SDK XML 形状已由 r174 确认为 `Previous* -> Next*`，线性、汇聚和分叉均可编译并被读取器完整登记；r175 的读取器仍对航路归一化产生三种指纹，因此航路读取器语义差分尚不能作为收敛强指标。VOR、NDB、航点表稳定，航路表只能进行结构和来源审计。
- r176 已证明 `CONTROLLED_RADIO.csv`/`CONTROLLED.csv` 是 `APP_SECTOR` 空域扇区频率，不能投影为机场 `Com`/`Tower`。r177 已证明来源完整 ILS 是机场 BGL `0x13`/`0x32` 的充分 SDK 触发条件；正式适配器已有全部 `430` 条来源 ILS，禁止按参考节表伪造对象。

### 进度口径

不得使用单一百分比掩盖未闭合的格式、来源和字节契约。整体工程只能粗略估为 `40%` 至 `50%`：基础管线已建成，内容与二进制收敛仍是主体工作。字节级目标必须单列为 `0/29`，直至实际 SHA-256 统计改变。

| 阶段 | 当前状态 | 阶段出口条件 |
| --- | --- | --- |
| 输入锁定、424 解析与 `NavModel` | 基础链路完成 | AIRAC、清单、SHA-256、来源引用和模型快照可从干净输入重建 |
| 默认 BGL/Package Tool 构建 | 基础链路完成 | ASCII 暂存、进程等待、包结构、元数据与确定性构建检查通过 |
| 本地验证与脱敏审计 | r162/r175 基线完成 | `validate`、布局审计、来源审计和稳定表差分均可重复 |
| 未分类程序来源审计 | 未开始 | 13 条均有直接来源分类依据，或有显式拒绝类别、原因和计数 |
| 航路内容收敛 | 进行中 | 先通过读取器可重复性门禁，再以稳定表指标验证改善 |
| 机场目标表达收敛 | 进行中 | 来源完整对象经单变量 SDK 探针验证；无依据对象保持拒绝 |
| 来源缺口闭合 | 进行中 | 跳过航段、空区域端点和未表达对象均有可复用规则或可审计拒绝 |
| IAP 未决闭合 | 进行中 | 每组均有来源链、正反例、审计计数和 BGL 回归，或明确拒绝 |
| BGL、索引和元数据字节收敛 | 未达标 | 参考范围 `29/29` 文件 SHA-256 全部一致 |
| 部署与实机验收 | 未开始 | 字节一致、可恢复备份和用户实机清单全部通过 |

### 接下来按顺序执行

1. **建立未分类程序审计器。** 新增只读 `unclassified-procedure-audit`，只消费 `NavModel`、直接 424 CSV/PDF 和可验证的源文件哈希。报告每条的机场、标签族、跑道、数据库编码页、腿类型、现有图页类型、可证明分类与拒绝原因；明确 `reference_records_read=false`。先写最小 fixture 与 CLI 测试，不修改 `source.py` 或 BGL 投影。
2. **按标签族建立来源规则或永久拒绝。** 将 `RNP-0`、`CC*-*`、`EO-*` 分开处理。只有字段或直接标题唯一证明其是可表达的离场、进场或进近类别时，才增加模型 `kind` 规则；无法无损表达的程序进入显式 `RejectedProcedure`/审计计数，保留来源位置和原因。每条规则必须有正例、至少一个拒绝例、模型快照回归和 BGL 回归。
3. **继续来源驱动的机场 SDK 探针。** 每次只选择一个来源完整、尚无否决结论的机场对象。最小探针必须保存输入 XML、唯一变量、Package Tool 轨迹、BGL 头部/节表、读取器登记、文件哈希和结论。SDK 节表仅作诊断，不得成为添加对象的内容来源；禁止重复已否决的 `Ndb`、`onlyAddIfReplace`、根节点终端点重复和空域通信映射方向。
4. **航路只在可重复诊断条件下收敛。** 对同一 BGL 至少独立读取两次，运行 `semantic-reproducibility-audit`。只有归一化行多集指纹稳定的表，才可用严格相等、逻辑键和字段差异判断新候选改善；航路表不稳定时只处理 XML 合法性、来源完整性、坐标精度、边界框、fragment/sequence、同名分组和最低高度的最小探针。
5. **闭合来源缺口。** 对 `12` 条跳过航段、`5` 个未决指定点、`18` 个服务机场未落入来源机场集合的导航台及其他不可表达对象建立来源卡片。允许证据仅为当期 424 直接表、可审计 PDF、受限可复跑 OCR、FIR/ACC 几何和邻接规则；严禁 Fenix、参考 BGL/SQLite、参考坐标、参考节表或参考逻辑键回填。
6. **逐组解决 IAP 未决。** 继续按十组清单建立“直接来源 -> 唯一规则 -> 正例/拒绝例 -> 审计 -> BGL 投影”闭环。OCR 只能在已有数据库主进近和已匹配 PDF 的三份可复跑缓存共识下参与消歧，不能创建主进近、航段、图页匹配或坐标航点。
7. **分文件推进二进制收敛与确定性。** 先验证同一干净输入两次构建彼此字节一致，再逐类比较 `00_enroute.bgl`、区域机场 BGL、机场补丁 BGL、`bglIndex.bout`、`layout.json`、`manifest.json` 和 ContentInfo。每个候选固定 SDK、ASCII 暂存根、输入 XML 排序、包名、元数据和构建时序，并保存输入 manifest、模型/profile/工具版本、文件树和逐文件哈希。
8. **最终验收与部署。** 仅当 `29/29` 后，从干净输入重建、验证报告和哈希可重复；确认 `FlightSimulator2024.exe` 已退出，创建完整时间戳备份并完成恢复演练；随后由用户验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前始终是测试版。

### 可复用 424 转换管线

固定阶段为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 固化 AIRAC、CSV/PDF、官方目标模板、SDK/读取器/编译器版本、文件树和 SHA-256。
- `ingest-424`/`evidence-audit` 只产生可回溯来源。OCR 必须记录缓存格式、页面哈希、渲染参数、模型和命令；它是可复跑的受限证据，不是一次性人工补录渠道。
- `normalize-model`/`model-audit` 维护通用 `NavModel`、原始精度、来源引用、拒绝项、规则版本、身份唯一性、引用完整性和计数。目标 schema、字符串限制、空值、排序、元数据和运行时契约不得写入 `source.py`。
- `project-target` 为默认 BGL、Fenix、TFDI、PMDG、FSL/FSLabs、iFly 等分别建立独立 profile/adapter。每个 profile 先登记官方基线、真实加载路径、格式/schema、字段单位、NULL/default、物理顺序、元数据、降级策略、最小 fixture、验证命令和实机清单；adapter 只消费模型快照，不重新解析 424。
- `build-target`/`validate-target`/`diff-and-audit` 只写隔离候选目录，分别输出自动化测试、结构构建、读取器诊断、来源审计、语义差分、布局审计、文件树和 SHA-256。GUI、CLI、自动更新和部署必须共用 profile、候选报告和 `deployable` 门禁，任何入口不能绕过。
- `stage-backup-deploy` 是唯一可写游戏文件的阶段，必须受字节一致、干净重建、游戏关闭、时间戳备份、恢复演练和实机清单共同约束。

### 每轮 Codex 更新规则

1. 实验前记录递增 `rNNN`、唯一假设、唯一变量、输入/工具 SHA-256、禁止读取的数据、预期成功/失败指标。
2. 先增加最小测试或最小 SDK 探针，再决定是否修改正式 adapter；失败实验只保留诊断，不污染候选或来源规则。
3. 实验后记录候选/诊断目录、提交号、测试、SDK 构建、读取器完整性与可重复性、参考 `29` 文件哈希、稳定表语义差分、来源审计、保留或否决结论。
4. 代码或仓库文档修改后运行相应测试、`git diff --check`、审查暂存区，只提交单一可解释变更并推送。数据库、备份、日志、诊断产物、SDK 中间输出和外部测试包不得进入 Git。
5. 所有状态报告必须分别说明自动化测试、SDK 构建、本地读取器诊断、参考哈希、用户实机验证和正式发布，任何一项都不能替代另一个阶段。

### 2026-08-19 r178 未分类程序来源审计日志

- 实验编号：`r178-unclassified-procedure-audit`。假设为“可以先以来源模型和直接 terminal-database-coding 图页建立未分类程序的可复用审计边界，而不猜测目标程序类型”。唯一变量是新增只读审计器；输入为冻结的 `output/intermediate-2608-r155-airway-identities.json.gz`。未读取 Fenix、参考 BGL/SQLite、参考坐标、参考节表或候选投影记录，未修改 `source.py`、BGL adapter 或候选包。
- 新增 `unclassified-procedure-audit` CLI、来源审计模块和最小 fixture。报告逐条保留机场、标签、标签族、跑道、航段类型/固定点、原始 PDF SHA-256、直接图页类型及目标拒绝原因；固定声明 `read_only=true`、`reference_records_read=false`、`fenix_records_read=false`。
- 实际报告：`diagnostics/r178-unclassified-procedure-audit.json`。`13` 条均唯一回链到 `terminal_database_coding` 图页；标签族为 `rnp_numeric=4`（ZGBS `RNP-0`）、`cc_numeric=3`（ZHCC `CC3-09`/`CC5-17`/`CC5-32`）、`eo_numeric=6`（ZPDQ/ZUKD/ZUSH 的 `EO-*`）。全部 `target_mapping_allowed=0`、`source_proven_kind=null`、`disposition=rejected_for_target_mapping`。
- 结论：`EO-*` 的名称、`RNP-0` 的字面形式以及 `CC*-*` 的前缀都不是离场、进场或进近的直接类型证据，不能写入 BGL 或改变 `ProcedureSegment.kind`。下一轮只允许对每个标签族继续读取同一 424 PDF 的直接标题/编码字段，或以其显式拒绝状态进入未来目标 profile 的降级策略；不得以“减少未分类数”为目标伪造映射。

### 2026-08-19 r179 未分类程序直接标题取证暂停日志

- 使用 r178 所列 PDF SHA-256 在已验证的 `pdf-evidence-cache-2608r1-r43` 中复核，缓存可重放各页的 terminal-database-coding 航段和固定点，但这些 13 条的已解析图页标题均只为“数据库编码”，没有可用的离场、进场或进近类型标题字段。因此缓存不能单独提升任何 `source_proven_kind`。
- 按可复跑 OCR 约束对 `Terminal/ZPDQ/ZPDQ-4J.pdf` 使用本机 `ocr-skill extract --backend llamacpp` 重新尝试。运行于 2026-08-19，结果为 `engine_unavailable`、`WinError 10061`，即 `llama-server` 未监听。本轮未使用 mock、未手工转录、未改写模型或候选。
- 结论：这不是程序内容缺失的许可，也不是可用的映射依据。等待可复跑 OCR 运行时恢复并通过缓存/来源门禁前，`RNP-0`、`CC*-*`、`EO-*` 继续全部拒绝；机场 SDK 下一轮不得重复已否决的等待航线隔离布局实验。

## 2026-08-19 r180 权威状态、进度与后续计划

本节取代此前默认通用数据状态摘要中的过期 Git 提交、测试数和“最新候选”描述。恢复工作前必须先检查本节、工作区根 `AGENTS.md`、`git status --short --branch`、r180 的 `conversion-report.json` 和最新诊断；事实冲突时，以本轮 Git、候选报告、验证命令和测试结果为准，并在同一轮同步修正两份 `AGENTS.md`。

### 已核验状态

- 仓库为 `https://github.com/JCH2333/defult_navdata_converter`，分支 `main` 已同步 `origin/main`；本轮盘点前 HEAD 为 `f8a8b42 docs: record unclassified procedure evidence gap`，工作树干净。
- 当前构建基线为冻结模型 `output/intermediate-2608-r155-airway-identities.json.gz`、已验证的官方设施索引 `official-navaids-b5d1c7b7a3c00b834896.sqlite` 和官方 `navigraph-nav-base` / `navigraph-nav-jepp`。内容来源仍严格限定为当期 424 CSV/PDF 与受审计 OCR；Fenix、参考成品导航记录、参考坐标和参考节表不能成为投影输入。
- r180 候选为 `output/candidate-2608-default-r180-rebuild-determinism`。`validate` 已确认 `valid=true`、`local_contract_verified=true`、`package_contract=true`、`bgl_count=21`；它仍是 `status=candidate`、`test_build=true`、`deployable=false`。
- 参考范围为两个中国覆盖包的 `29` 个文件。r180 两包的文件集合与参考完整一致，但 SHA-256 一致数仍为 `0/29`；两包内每一个 BGL、索引、布局、元数据文件均尚未与参考同字节。不得部署 Community、不得要求实机测试、不得创建正式 Release。
- r175 与 r180 在排除 `_work` 和 `conversion-report.json` 后，共比较 `2256` 个候选文件：`2252` 个相同，差异仅为两个包的 `bglIndex.bout` 和 `layout.json`。这只证明绝大部分复制基线和生成载荷可重放；索引/布局哈希树尚未确定性闭环，因此不得称为“完全确定性构建”。
- 自动化测试基线为 `393 passed`。此结果仅覆盖代码回归，不代表 SDK 运行时加载、参考字节收敛、游戏实机验证或可发布状态。
- 当前模型/投影可量化缺口：`275` 机场、`640` 跑道方向、`438` 导航设施、`2741` 全局航点、`10409` 程序段已进入模型；仍有 `12` 条航路段因端点区域未证明而跳过、`5` 个全局航点区域未决、`10` 组 IAP 因无唯一主进近证据而拒绝、`13` 条未分类程序段保持拒绝。它们是来源与表达缺口，不得以参考数据反向补齐。

### 进度口径与阶段出口

整体工程只能粗略估为 `45%`：输入、模型、默认 BGL 适配器、GUI/CLI、Package Tool 构建和本地审计已经建立；真正的内容闭合、SDK 二进制确定性和 `29/29` 字节验收仍是剩余主体。百分比不得替代独立验收指标。

| 阶段 | 状态 | 出口条件 |
| --- | --- | --- |
| 输入锁定与 424 规范化模型 | 已建立 | 从干净输入重建模型，AIRAC、文件清单、来源哈希与模型计数可复核 |
| 默认 BGL 投影与 Package Tool 构建 | 已建立 | ASCII 暂存、进程等待、包布局和基础本地契约持续通过 |
| 载荷重放确定性 | 部分通过 | 两次同输入构建在目标范围内逐文件全相同，包含 `bglIndex.bout` 与 `layout.json` |
| 来源缺口与程序语义 | 进行中 | 每个缺口都有 424/PDF/OCR 可回溯规则，或显式可复用拒绝/降级 |
| SDK 表达与读取器诊断 | 进行中 | 每项正式规则先有单变量探针、最小 fixture、构建证据和稳定的读取器结论 |
| 二进制收敛 | 未达标 | 参考范围 `29/29` 文件 SHA-256 一致，并可从干净输入复现 |
| 部署与实机验证 | 未开始 | 字节一致、备份/恢复演练、游戏关闭与用户飞行清单全部满足 |

### 后续执行计划

1. **先完成 r180 确定性闭环。** 对 `bglIndex.bout` 与 `layout.json` 建立只读差异分类：区分输入 BGL 哈希、文件枚举顺序、时间戳、绝对/暂存路径和 Package Tool 非确定性。每次只固定一个变量；只有两次独立构建在同一比较范围逐文件一致，才允许将其作为后续字节收敛基线。不得通过修改参考、复制参考产物或过滤目标文件获得“确定性”。
2. **建立逐文件收敛看板。** 为 29 个目标文件记录候选自比较、与参考比较、BGL 结构、来源对象组和最近影响实验；按 `00_enroute.bgl`、九个区域机场 BGL、九个机场补丁 BGL、各包索引/布局/清单/ContentInfo 分组。看板只保存哈希、计数、结构分类和来源键摘要，不保存参考导航字段值。
3. **优先关闭可证明来源缺口。** 对 12 条航路段和 5 个未决区域航点，继续只用 424 直接表、FIR/ACC 几何、已受控的邻接规则和可审计 OCR。任何多区域、边界、身份冲突或 `RTE_SEG` 独有标识仍显式拒绝；不得把“减少跳过数”作为放宽规则的理由。
4. **恢复后处理未分类程序。** 只有本地 OCR 运行时可复跑、缓存含完整运行时画像且可通过页面 SHA-256/多次一致性审计时，才继续读取 r178 所列同源 PDF 标题或编码字段。`RNP-0`、`CC*-*`、`EO-*` 在得到直接类型证据前保持 `RejectedProcedure`；任何新规则必须有正例、反例、模型快照回归和 BGL 回归。
5. **逐组解决 10 个 IAP 未决。** 固定闭环为“数据库主段已存在 -> 424 直接图页/受限 OCR 证据 -> 唯一且保守的选择规则 -> 来源审计 -> 最小测试 -> BGL 投影 -> 独立 validate”。OCR 只能帮助消歧已有主进近，不能创建主进近、航段、图页匹配或坐标。
6. **继续来源完整的机场 SDK 探针。** 从 `airport-source-inventory` 选择一个尚未被否决、来源字段完整的对象；探针必须保存输入 XML、唯一变量、Package Tool 轨迹、BGL 头/节表、读取器登记、文件哈希和结论。不得重复 NDB、`onlyAddIfReplace`、根节点终端点重复、空域通信映射或等待航线隔离布局等已否决方向。
7. **只在可重复读取表上使用语义差分。** 航路读取器归一化仍不稳定时，只验证 XML 合法性、来源完整性、坐标精度、边界、fragment/sequence 与高度字段；VOR/NDB/航点等稳定表才可作为语义收敛指标。任何读取器异常必须先通过完整 BGL 登记和重复性门禁。
8. **最终收敛、部署与发布。** `29/29` 后从干净输入至少重建两次；复核所有文件树、哈希、候选报告和验证结果。确认 `FlightSimulator2024.exe` 已退出，执行时间戳备份和恢复演练，才可覆盖 Community。随后由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。完成前仅可标记为测试版。

### 可复用工作管线与每轮状态更新

固定管线为 `lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`。`NavModel` 是跨 AIRAC、跨格式的唯一内容边界；新目标只能新增独立 profile/adapter、验证器和部署器，且只消费模型快照。目标 schema、字符串限制、NULL/default、排序、元数据和加载契约留在 profile，不得回写 `source.py`。

每个 rNNN 必须先写出：单一假设、单一变量、冻结输入/工具哈希、禁止读取的数据、预期指标和失败判据。完成后必须更新：候选或诊断路径、代码/文档提交号、测试、SDK 构建、读取器完整性/重复性、29 文件哈希、来源审计、明确的保留或否决结论，以及上表各阶段的状态。代码或仓库文档变更后运行相关测试、`git diff --check`、审查暂存区、单主题提交并推送；数据库、备份、日志、诊断、SDK 中间产物和外部测试包继续排除在 Git 之外。

### 2026-08-19 r181/r182 Package Tool 时间确定性日志

- 假设：r180 的四个自比较差异仅来自 Package Tool 写入 `layout.json` 和 `bglIndex.bout` 的墙钟 FILETIME，而不是 424 内容、XML 排序或 BGL 载荷。唯一变量是 Package Tool 输出后的严格时间元数据规范化；输入继续冻结为 `output/intermediate-2608-r155-airway-identities.json.gz` 和已验证官方设施索引。未读取 Fenix、参考 BGL/SQLite 导航记录、参考坐标或参考节表。
- 取证：r175/r180 的 BGL 均相同；两个 `layout.json` 仅改变 11 个 BGL、`bglIndex.bout` 和 ContentInfo 的 Windows FILETIME。两个 BGL 索引各有 11 组变化，固定记录步长为 394 字节；每组编码均与同路径 `layout.json` 的 BGL FILETIME 相等，格式为高 32 位小端后接低 32 位小端。
- 实现：`_normalize_package_tool_time_metadata` 只在每一个 layout BGL 时间戳在索引中出现次数与 BGL 条目数精确相同后，才将该 8 字节字段归零，并以确定性路径/大小/零日期重写 `layout.json`。缺少内容列表、没有 BGL 时间戳或任一索引匹配次数不正确均失败；不得按偏移、包名或参考内容盲改索引。自动化测试覆盖成功规范化与索引/布局关联失败拒绝。
- r181 `candidate-2608-default-r181-package-time-normalized` 与 r182 `candidate-2608-default-r182-package-time-repeat` 均由真实 Package Tool 从同一冻结输入独立构建，均通过独立 `validate`（21 个 BGL、`local_contract_verified=true`、`deployable=false`）。排除 `_work` 与 `conversion-report.json` 后，候选有效树 `2256/2256` 文件 SHA-256 全部一致；构建载荷重放确定性阶段因此通过。
- 边界：该证明仅覆盖本地包契约和两次构建的字节重放，尚不构成游戏运行时加载证明；`bglIndex.bout` 经规范化后的实机接受性仍须在最终字节一致、备份和部署门禁满足后与用户飞行验证一起确认。参考范围仍为 `0/29`，不得部署或发布。
- 后续顺序更新为：先把 29 文件候选/参考哈希、BGL 结构、来源对象组和影响实验固化为逐文件收敛看板；然后按来源证据处理航路/区域缺口、10 个 IAP 未决和来源完整的机场 SDK 探针。后续候选全部必须沿用 r181 的时间元数据规范化和“两次独立构建全树相等”门禁。

## 2026-08-19 r183 权威状态、统计与收敛计划

本节优先于本文件此前所有默认通用数据的进度估算、最新候选和下一步描述。继续工作前必须核对本节、工作区根 `AGENTS.md`、`git status --short --branch`、最后两个有效候选的 `conversion-report.json`、`file-convergence-audit` 输出和本轮测试结果；发生冲突时以本轮可复跑命令、候选报告和 Git 提交为准，并同步更正两份 `AGENTS.md`。

### 已核验状态与统计

- 公开仓库为 `https://github.com/JCH2333/defult_navdata_converter`；当前分支为 `main`。r183 代码完成提交和推送前不得把工作树状态描述为干净或把该轮功能记为已发布。
- 内容输入固定为 `424源数据\2608\2608` 的 CSV/PDF、冻结的 `output/intermediate-2608-r155-airway-identities.json.gz`、经验证的官方设施索引及官方 `navigraph-nav-base`/`navigraph-nav-jepp` 基线。Fenix、`Default navdata 2608R1` 的导航记录、参考坐标和参考节表都不是内容输入。
- r181 `candidate-2608-default-r181-package-time-normalized` 与 r182 `candidate-2608-default-r182-package-time-repeat` 均由真实 Package Tool 从相同冻结输入独立生成，并已独立通过 `validate`：`21` 个 BGL、`local_contract_verified=true`、`deployable=false`。
- 排除 `_work` 与 `conversion-report.json` 后，r181/r182 的有效文件树为 `2256/2256` 个 SHA-256 一致。载荷重放确定性阶段已通过；此结论只适用于本地候选重建，不构成运行时加载、参考一致或可部署证据。
- r183 `file-convergence-audit` 已对两个中国覆盖包建立只读的逐文件看板：参考范围 `29` 文件、与参考相同 `0/29`、r181/r182 重复候选相同 `29/29`。文件角色为 `1` 个航路 BGL、`10` 个区域机场 BGL、`10` 个机场补丁 BGL、`2` 个索引、`2` 个布局、`2` 个清单和 `2` 个 ContentHistory。看板仅保存路径、角色、来源对象组、大小、SHA-256 和 BGL 头/节表摘要，固定声明 `read_only=true`、`reference_records_exported=false`。
- 当前来源缺口保持：`12` 条航路段因端点区域未证实而跳过、`5` 个全局航点区域未决、`10` 组 IAP `no_unique_primary` 未决、`13` 条 `RNP-0`/`CC*-*`/`EO-*` 未分类程序段拒绝投影。它们必须通过直接来源规则闭合或保留显式拒绝，不得由参考产物反向填充。
- 工程总量只能粗略估为 `45%` 至 `50%`。输入、模型、默认 BGL adapter、GUI/CLI、Package Tool 构建、本地验证和候选自重放已建立；剩余主体是来源闭合、SDK 表达证据和参考范围 `29/29` 字节收敛。百分比不得替代下列阶段出口，更不得替代用户实机验证。

### 阶段出口与后续执行顺序

| 阶段 | 当前状态 | 必须完成的出口条件 |
| --- | --- | --- |
| 输入锁定与 424 规范化 | 已建立 | 从干净输入重建模型；AIRAC、清单、来源哈希、规则版本与模型计数一致 |
| 默认 BGL 投影与 Package Tool 构建 | 已建立 | ASCII 暂存、进程等待、包结构、时间元数据规范化和本地 `validate` 持续通过 |
| 候选载荷重放确定性 | 已通过 | 同一冻结输入的两次独立构建在排除 SDK 工作目录和报告后全树 SHA-256 一致 |
| 逐文件收敛观测 | 已建立，未收敛 | 对参考范围 `29` 文件持续记录候选自比、参考比、角色、来源组、BGL 摘要和最近实验；禁止导出参考导航记录 |
| 来源缺口与程序语义 | 进行中 | 每个缺口具有 424/PDF/受控 OCR 的可回溯规则，或明确的可复用拒绝/降级 |
| SDK 表达与读取器诊断 | 进行中 | 每条正式规则先经单变量探针、最小 fixture、真实构建和读取器完整性/重复性门禁 |
| 参考二进制收敛 | 未达标 | 参考范围 `29/29` 文件 SHA-256 一致，并可由干净输入至少重建两次 |
| 部署与实机验收 | 未开始 | 二进制一致、备份与恢复演练、游戏关闭和用户飞行清单全部通过 |

1. **固化并使用 r183 收敛看板。** 每个有效候选都运行 `file-convergence-audit`，以前一有效候选作为 `--repeat-candidate`。按文件角色而不是“总哈希数量”制定单变量实验：航路、区域机场、机场补丁、索引/布局、清单和 ContentHistory 分开处理。看板用于定位变化范围，不能给正式 adapter 提供参考字段或反向映射。
2. **先关闭来源侧的可证明缺口。** 对 `12` 条航路段和 `5` 个未决区域航点，只允许使用当期 424 直接表、FIR/ACC 几何、受控邻接规则与已审计 OCR。多地区邻接、边界点、身份冲突和 `RTE_SEG` 独有标识继续拒绝。每条新规则必须先有最小正例、反例和来源审计，再修改 `NavModel` 投影。
3. **恢复 OCR 后再处理未分类程序。** 只有本地 OCR 可复跑、运行时画像完整、页面 SHA-256 和多次结果可审计一致时，才可继续检查同源 PDF 的直接标题或编码字段。`RNP-0`、`CC*-*`、`EO-*` 在获得直接类别证据前保持 `RejectedProcedure`；不得因名称、参考差异或减少拒绝计数而猜测类别。
4. **按固定闭环解决 10 个 IAP 未决组。** 每组必须完成“已有数据库主段 -> 424 直接图页或受限 OCR 证据 -> 唯一保守规则 -> 来源审计 -> 最小正反例 -> BGL 投影 -> 独立 validate”。OCR 只能消歧既有主进近，不能创建主进近、航段、图页匹配或坐标。
5. **只对来源完整对象进行机场 SDK 探针。** 从 `airport-source-inventory` 选择一个尚无否决结论的对象；每次仅改变一个 XML 输入，并保留输入 XML、工具与输入哈希、Package Tool 轨迹、BGL 头/节表、读取器登记、文件哈希和结论。不得重试已否决的 NDB、`onlyAddIfReplace`、根节点终端点重复、空域通信映射和等待航线隔离方向。
6. **限制读取器语义差分的适用范围。** 航路读取器归一化未稳定前，只审计 XML 合法性、来源完整性、坐标精度、边界、fragment/sequence 和高度字段；VOR/NDB/航点等通过重复性门禁的表才可作为严格语义收敛指标。读取器报告必须完整登记全部请求 BGL。
7. **以单文件为单位推进字节收敛。** 任何影响候选的规则变更后，先确认 r183 看板中受影响的文件集合是否符合预期，再检查候选自重放 `29/29` 和参考相同数。若某次实验不能解释其文件角色、来源对象和 BGL 摘要变化，则否决该方向并保留诊断，不把它接入正式 adapter。
8. **最终部署门禁不提前放宽。** 只有参考范围 `29/29`、干净输入两次重建一致、完整 `validate` 与来源审计通过后，才可确认 `FlightSimulator2024.exe` 已退出、执行时间戳备份和恢复演练，并覆盖 Community。随后由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器；此前始终是不可部署测试候选。

### 可复用 424 转换管线与每轮更新要求

固定管线为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `NavModel` 是唯一跨 AIRAC、跨格式的内容边界。未来目标格式只能新增 profile、adapter、验证器和部署器，且只消费冻结模型快照；不得重新解析 424、读取 Fenix，或把参考成品、OCR 缓存当作内容数据库。
- `profile` 负责目标 schema、单位、字符串限制、NULL/default、物理顺序、元数据、加载契约、不可表达字段的降级策略、最小 fixture 和实机清单；不得把目标专有规则回写到 `source.py`。
- GUI、CLI、自动更新与部署必须共享同一 profile、候选报告和 `deployable` 门禁。任何入口都不能直接写 Community 或跳过 `stage-backup-deploy`。
- 每个 `rNNN` 实验开始前记录：单一假设、单一变量、冻结输入与工具 SHA-256、禁止读取的数据、预期成功指标和失败判据。结束后记录：候选/诊断路径、代码或文档提交、测试、SDK 构建、读取器完整性和重复性、r183 文件收敛统计、来源审计以及明确的保留或否决结论。
- 代码或仓库文档变更后，运行相应测试、`git diff --check`、审查暂存区、创建单主题提交并推送。数据库、备份、日志、诊断、SDK 中间产物、外部测试包和生成导航包继续排除在 Git 之外。

### 2026-08-19 r184/r185 中文导航台标签边界规则与候选否决

- 假设：`RTE_SEG.csv` 的 ACC 注记可能用同一条航路另一端的 424 导航台中文名加 `VOR/DME:` 或 `NDB:` 标出边界；若现有解析只识别 ident，则后一个端点的 ACC 会错误泄漏到前一个指定点。唯一变量是将同一 424 `VOR.csv`/`NDB.csv` 中按类型、ident 和坐标精确匹配的名称加入注记分段标签，名称仅用于定位下一个标签，不能单独提供区域。
- 先增加最小 fixture：`ALIAS:北京ACC黄城VOR/DME:广州ACC`。旧实现失败；新实现只恢复 `ALIAS=ZB`，同时保留冲突、未知 ACC 和未标记样本拒绝。`tests/test_source.py -k explicit_endpoint_acc_label` 与完整 `tests/test_source.py` 分别通过 `1` 和 `49` 项。
- 真实 2608 直接来源重载仅新增恢复 `DOVIV=ZB`：ACC 阶段空区域点 `27 -> 26`、显式标签恢复 `6 -> 7`；不使用 Fenix、参考 BGL/SQLite 导航记录、参考坐标或参考节表。其余 `P225`、`P239`、`P127`、`LELIM`、`BEBAN`、`P188`、`P121`、`OTBUG`、`APOGO` 仍分别因跨地区、未知 ACC 或不一致证据保持未决。
- r184 使用未附加 r155 的 GeneralDoc/IAP 证据缓存重新导出模型，得到 `2252` 个航点、`1` 条拒绝记录与 `11` 条拒绝程序；而冻结 r155 含 `2741` 个航点、`435` 条拒绝记录和 `10` 条拒绝程序。r184/r185 虽均通过独立 `validate`，且 `file-convergence-audit` 自重放为 `29/29`，但相对 r181 有 `27` 个有效文件哈希变化，输入并不等价，不能把变化归因于该规则，也不得作为正式收敛候选。
- r184/r185 参考范围仍为 `0/29`，`deployable=false`。它们只保留为输入来源不等价诊断；最新有效确定性候选仍是 r181/r182。未覆盖 Community、未实机验证、未正式 Release。
- 下一轮先建立“冻结模型来源重放”门禁：从 r155 的证据元数据恢复相同的 GeneralDoc、关键点和 IAP OCR 输入；导出重放模型后必须除预期 `DOVIV`/关联航段外与 r155 保持字段级一致。只有该门禁通过，才允许构建新的两次候选、检查受影响文件范围、运行 `validate` 和 `file-convergence-audit`。若缓存不可恢复，则保持该规则为已测试源码能力，不得接入字节收敛基线。

## 2026-08-19 r186 权威状态、进度口径与可复用收敛计划

本节优先于本文件和工作区根 `AGENTS.md` 中更早的默认通用数据进度描述。每次继续前，Codex 必须重新检查：本节、根目录 `AGENTS.md`、`git status --short --branch`、最近两个有效候选的 `conversion-report.json`、最新 `file-convergence-audit`，以及本轮实验输出。发生冲突时，以本轮可复跑命令、候选产物、Git 提交和测试输出为准，并在同一轮修正两份 `AGENTS.md`。

### 当前真实状态

- 公开仓库为 `https://github.com/JCH2333/defult_navdata_converter`，分支为 `main`。本轮盘点时 HEAD 为 `4509ad1 fix: parse navaid name ACC label boundaries`；远端复核因本机代理 `127.0.0.1:7897` 不可连接而失败。网络恢复后必须执行普通 `git push` 和 `git ls-remote --heads origin main` 复核，禁止强推。
- 内容边界不变：候选只能由 `424源数据\2608\2608` 的 CSV/PDF、经审计的证据缓存和官方 `navigraph-nav-base`/`navigraph-nav-jepp` 的全球基线与加载契约生成。Fenix、`Default navdata 2608R1` 的导航记录、参考坐标、参考 BGL 节表和参考数据库字段都不得成为内容投影输入。
- 最近有效的确定性基线仍是 r181/r182：冻结 r155 模型的两次独立 Package Tool 构建在排除 `_work` 与 `conversion-report.json` 后为 `2256/2256` 文件 SHA-256 一致；参考范围仍为 `0/29`。该结论仅证明候选自重放，不证明参考一致、游戏加载或可部署。
- r184/r185 验证和自重放均通过，但其证据缓存输入未与 r155 等价，故只是诊断候选，不得作为收敛基线。r186 已使用 r155 同类 GeneralDoc/IAP 缓存导出 `intermediate-2608-r186-navaid-label-replay.json.gz`；其机场、跑道、导航设施、航点、航路、终端航点、程序段、拒绝记录和拒绝程序的顶层计数均与 r155 相同，但快照 SHA-256 不同，字段级白名单比较尚未完成，因此不得启动基于它的正式候选构建。
- 已建模型规模以 r155 有效基线计：机场 `275`、跑道方向 `640`、导航设施 `438`、全局航点 `2741`、航路段 `4446`、程序段 `10409`。仍有 `12` 条航路段、`5` 个全局航点区域、`10` 个 IAP 分组和 `13` 条未分类程序段保持显式拒绝或跳过。
- 文件收敛看板覆盖两个中国覆盖包 `29` 个文件：`1` 个航路 BGL、`10` 个区域机场 BGL、`10` 个机场补丁 BGL、`2` 个索引、`2` 个布局、`2` 个清单和 `2` 个 ContentHistory。候选与参考相同数为 `0/29`；r181/r182 的同范围重复候选相同数为 `29/29`。
- 已用标准 Python `json.load` 复核 r181、r185 的候选报告及 r183/r184 的收敛审计，均可解析；此前 PowerShell 的路径转义错误不是报告序列化缺陷。所有未来报告仍须经过标准 JSON 解析门禁，不能依赖单一调用端的容错行为。

### 进度统计

百分比仅描述工程能力，不得替代验收门禁。

| 工作流 | 当前状态 | 量化证据 | 出口条件 |
| --- | --- | --- | --- |
| 输入锁定与 424 规范化 | 已建立 | 可导出带来源引用的 `NavModel` | 清单、AIRAC、输入/工具哈希和快照可从干净输入复核 |
| 证据缓存与模型重放 | 进行中 | r184/r185 已证明“缓存缺失会改变模型”；r186 顶层计数已与 r155 一致 | r186 与 r155 除单一、已声明规则外字段级一致 |
| 默认 BGL 适配与 SDK 构建 | 已建立测试链 | 两包、21 个 BGL、ASCII 暂存与异步 Package Tool 等待已验证 | 每项新增投影均有最小 fixture、单变量 SDK 探针和本地验证 |
| GUI、更新、备份、部署门禁 | 已建立 | GUI/CLI 共用候选报告和 `deployable` 门禁 | 所有入口不得绕过 `stage-backup-deploy` |
| 候选自重放确定性 | 已通过 | r181/r182 有效树 `2256/2256` 一致 | 后续每个有效候选继续两次构建验证 |
| 来源缺口闭合 | 进行中 | 航路 `12`、航点区域 `5`、IAP `10`、未分类程序 `13` 未决 | 每项获得直接来源规则或保留可复用拒绝策略 |
| 参考二进制收敛 | 未达标 | `0/29` | 同范围 `29/29` SHA-256 一致，且不通过参考记录反向填充 |
| 部署与实机验收 | 未开始 | `deployable=false` | 二进制一致、恢复演练、游戏关闭和用户飞行清单全部通过 |

整体工程能力估算为约 `45%`；最终上线验收进度仍为 `0%`，因为参考字节一致、部署和实机验证均未完成。

### 后续工作计划与关键节点

1. **完成 r186 模型来源重放门禁。**
   - 记录 r155 与 r186 的输入目录、PDF/OCR 缓存清单、页面 SHA-256、运行时画像、解析器版本和模型哈希。
   - 编写字段级模型比较器，只允许预先声明的 DOVIV/关联航段差异；机场、跑道、导航台、航点、航路、程序、拒绝记录和证据来源的其他差异一律失败。
   - r186 通过后，再把“模型快照 + 证据清单 + 比较报告”固化为每个 AIRAC 的强制产物；失败则将 r184 的中文导航台标签规则保留为已测试能力，不接入字节收敛基线。

2. **固化报告可解析性门禁。**
   - 所有 `conversion-report.json`、收敛审计、来源审计和探针报告必须用标准 JSON 库从磁盘重新解析；路径必须正确转义，禁止手工拼接 JSON。
   - 增加回归测试：中文路径、反斜杠路径、嵌套报告、候选报告和诊断报告均可解析；失败时 CLI 返回非零，GUI 仅显示失败状态。
   - 这一项只验证报告可信度，不得改变模型或 BGL 内容；候选构建后必须重跑标准 JSON 解析、看板和文件哈希核对。

3. **建立每轮固定实验记录和单文件收敛闭环。**
   - 每个 `rNNN` 开始前记录单一假设、单一变量、冻结模型、输入/工具 SHA-256、禁止读取的数据、预期受影响文件角色和失败判据。
   - 结束后必须记录候选/诊断路径、测试、SDK 构建、读取器完整性、候选自重放、`29` 文件参考比较、来源审计、保留或否决结论。
   - 先按角色而非总哈希推进：`00_enroute.bgl`、区域机场 BGL、机场补丁 BGL、索引/布局、清单/ContentHistory 分组。无法解释影响集合的实验一律否决。

4. **先闭合允许证明的 424 来源缺口。**
   - 对 `12` 条航路段和 `5` 个航点区域逐项建立来源卡：精确身份、原始行、允许恢复的字段、FIR/ACC/邻接证据、反例和拒绝条件。
   - 只允许使用当期 424 直接表、FIR 多边形、ACC 显式标签、已验证的邻接规则和有完整画像的 OCR。多区域、边界点、冲突、`RTE_SEG` 独有标识和缺坐标继续拒绝。
   - 对 `10` 个 IAP 未决组固定执行“已有数据库主段 -> 424/PDF 直接证据或受限一致 OCR -> 唯一保守规则 -> 正反例 -> 来源审计 -> BGL 投影 -> 独立 validate”。OCR 绝不创建主进近、航段、图页匹配或坐标。
   - `RNP-0`、`CC*-*`、`EO-*` 在得到直接类型字段或可复跑且可审计的图页标题证据前持续导出为 `RejectedProcedure`，不根据名称猜测。

5. **以来源完整对象继续 SDK 表达取证。**
   - 机场 BGL 与参考相比缺少 `0x17/0x33` 等节，且候选区域 BGL 体积显著更小；这只能作为“目标表达尚未解释”的结构差异，不能把参考记录或节计数倒推成要伪造的对象。
   - 从 `airport-source-inventory` 选择一个来源完整、尚未被否决的 424 对象，每次仅改变一个 XML 对象/属性。保留 XML、输入哈希、工具轨迹、BGL 头/节表、读取器完整登记和文件哈希。
   - 已否决方向不得重复：机场关联 NDB 伪投影、`onlyAddIfReplace`、根节点终端点重复、空域通信映射、等待航线隔离、`CODE_DIR` 简单反转和无来源的 routeType 猜测。

6. **推进真正的字节级验收。**
   - 每个来源规则或 SDK 规则进入适配器后，先从同一冻结模型两次构建；只有有效树自重放仍为全等，才运行只读 `file-convergence-audit`。
   - 只接受“参考相同文件数增加且受影响角色符合假设”的进展。参考 `29/29` 达成后，从干净输入再完整重建两次，并核对候选包、报告、输入清单和 SHA-256。
   - 若经完整 424/PDF/SDK 取证仍无法推导某个参考二进制差异，必须记录为“来源或目标编译契约未证实”，不得以复制参考、解析参考记录或添加无来源对象伪造一致。

7. **最后才允许部署和用户实机验证。**
   - 前置条件：`29/29`、干净输入双重构建、完整验证、来源审计、报告 JSON 解析门禁均通过。
   - 再确认 `FlightSimulator2024.exe` 已完全退出；为两个 Community 覆盖包、`layout.json`、`manifest.json`、ContentHistory 和相关元数据建立时间戳 SHA-256 备份并完成恢复演练。
   - 覆盖后由用户验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只能是测试版，不得创建正式 Release。

### 面向其他 AIRAC 与其他格式的可复用管线

固定管线为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `NavModel` 及其版本化快照是唯一的跨 AIRAC、跨目标内容边界。源层只解析 424 CSV/PDF 与受限证据，保留原始精度、`SourceRef`、拒绝原因和规则版本；不写入 BGL、SQLite 或机模专用字段。
- 每个新目标格式必须新增独立 `profile`、`adapter`、`validator` 和 `deployer`。profile 记录官方基线、真实加载路径、schema/文件契约、单位、NULL/default、字符串限制、排序、元数据、降级策略、最小 fixture、运行时模拟器和实机清单；不得把目标分支写回 `source.py`。
- OCR 必须是可复跑的证据提供器，而不是一次性人工答案：缓存要绑定 PDF SHA-256、页码、渲染/预处理、模型与命令版本、运行时画像、解析器版本和多次一致性结果；证据不满足门禁时只能生成审计报告，不能进入模型投影。
- CLI、GUI、自动更新、构建、验证和部署必须共用同一 profile、候选清单、报告 schema 与 `deployable` 决策。任何界面入口都不能直接覆盖 Community。
- 每个 AIRAC 先执行输入检测与锁定，再导出可比较模型快照；每个新格式先写 profile 契约、建立最小 fixture 与真实加载证据，再允许构建完整候选。数据库、备份、OCR 缓存、日志、诊断、SDK 中间物和测试包始终排除在 Git 之外。

## 2026-08-19 r186 否决结论与 r187 强制门禁

本节优先于本文件中所有“r186 待比较”或“r186 可继续构建”的历史表述。r186 只是一份输入配置错误的重放诊断，不能作为候选基线，也不能用它的顶层计数相同来推断模型等价。

### 已确认状态

- 本轮字段级递归比较 `encode(load_model(r155))` 与 r186，得到 `167` 处结构差异；因此 r186 未通过模型来源重放门禁。
- 其中允许继续验证的候选变化只有 DOVIV 相关的来源恢复：`4` 个航路端点 `country` 由空值恢复为 `ZB`，`1` 个航点 `country` 由空值恢复为 `ZB`，以及由此产生的 ACC/邻接统计变化。该规则仍必须由字段级白名单和正反例测试约束，不能仅凭结果合理性接受。
- r186 的重大非预期差异是 ENR 4.1 导航台证据丢失：r155 有 `138` 条 `enroute_navaid_evidence`，r186 为零，且 `general_document_evidence.navaids.available=false`。根因是命令把具体 `enr-4.1-navaids` 目录传给 `--general-doc-cache`；加载器会再拼接该子目录，实际寻找了重复的 `...\enr-4.1-navaids\enr-4.1-navaids\manifest.json`。
- r186 还把 `iap_coverage.version` 从 `23` 变为 `24`，并新增 `7` 条 `source_incomplete_chart_title_matches`。即使 IAP OCR 三缓存共识仍为 `4` 条角色证据和 `1` 个候选页，这些元数据变化也必须逐条定位到规则、来源与投影影响；未解释前不得列入允许差异。
- r181/r182 仍是唯一有效确定性候选：有效树自重放 `2256/2256`，与参考中国覆盖包为 `0/29`。工程能力仍约 `45%`，上线验收仍为 `0%`；未覆盖 Community，未进行实机验证，未创建 Release。
- 本地 `main` 当前含 `f03752f docs: record r186 convergence plan`，比 `origin/main` 领先一个提交。推送因 `http://127.0.0.1:7897` 不可达而暂缓；网络恢复后只允许普通 `git push`，随后执行 `git ls-remote --heads origin main` 复核。

### r187 阶段 A：恢复等价证据输入

1. 只重跑模型导出，不构建 BGL、不运行部署、不读取参考成品记录或 Fenix 数据。
2. `--general-doc-cache` 必须传入父目录：
   `C:\Users\Administrator\AppData\Local\default_navdata_converter\general-doc-ocr-cache-2608r1`
   加载器才能自行定位 `enr-4.1-navaids`。`--general-doc-keypoint-cache-directory` 继续使用其 `enr-4.4` 子目录。
3. 固定复用三个 r80 IAP OCR 缓存根；导出前记录原始 424 目录、全部缓存根、缓存 manifest/PDF SHA-256、解析器版本、Python 版本、命令文本和输出模型 SHA-256。
4. 产物命名为 `output/intermediate-2608-r187-navaid-label-replay.json.gz`。导出后先以标准库 `json.load` 复核相关报告，再继续任何比较。

### r187 阶段 B：模型来源重放审计

1. 实现独立、可复用的 `model-replay-audit`，输入两个 `NavModel` 快照，不读取参考 BGL、SQLite、Fenix 或候选包。
2. 审计输出必须包含：顶层计数、按字段路径分类的差异数、稳定脱敏哈希、允许差异清单、未允许差异清单和可机读 JSON 报告；提供 `--fail-on-unexpected` 供 CLI、GUI 和自动更新共用。
3. 最小自动化覆盖必须包含：完全一致通过、单字段白名单通过、白名单外差异失败、报告可由标准 JSON 库重读。白名单必须使用精确对象身份和字段路径，不能用“某类区域变化”或计数阈值放宽。
4. r187 对 r155 的初始白名单只可包含 DOVIV 及其精确关联航路端点/航点的 `country` 和派生统计。ENR 4.1 证据条目、IAP 覆盖版本、IAP 标题匹配、程序、拒绝记录和其他来源元数据均不在白名单内。
5. r187 通过的出口条件是：ENR 4.1 证据恢复为 `138` 条，除精确白名单外无任何差异，报告可解析且测试通过。任一条件失败即否决 r187，不构建候选；先建立最小复现和来源审计，再开始下一轮。

### r188 及以后：受控收敛循环

1. 只有 r187 通过后，才允许从同一冻结模型两次构建候选；两次有效候选树仍必须 `2256/2256` 一致，随后执行 `validate`、标准 JSON 解析和只读 `file-convergence-audit`。
2. 每轮只解决一个来源缺口或一个 SDK 表达问题。开始前明确预期影响的文件角色；结束后按 `00_enroute.bgl`、区域机场 BGL、机场补丁 BGL、索引/布局、清单/ContentHistory 分组报告参考相同数变化。
3. 只接受“未引入未解释差异、候选自重放保持全等、参考相同文件数增加且影响范围符合假设”的结果。`0/29` 不因局部 schema、OCR 或 SDK 冒烟成功而改变结论。
4. 无法由 424/PDF、受审计 OCR 或 SDK 契约证明的差异必须沉淀为显式拒绝策略和最小 fixture；不得用参考成品解析、复制或人工抄录伪造字节一致。
5. 达到 `29/29` 后仍须从干净输入完整重建两次、完成恢复演练并确认游戏关闭，随后才可由用户实机验证。任何一个前置条件缺失时 `deployable=false`。

## 2026-08-19 r187 模型来源重放结果

本节优先于上一节中“r187 对 r155 的初始白名单”的临时限制；该限制已按本轮实际代码、来源和投影边界完成验证并收紧为精确哈希清单。

- r187 使用正确的 `--general-doc-cache` 父目录、r155 的 ENR 4.4 keypoint 缓存和三份 r80 IAP OCR 缓存导出。输出为 `output/intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。顶层规模保持机场 `275`、跑道 `640`、导航台 `438`、航点 `2741`、航路 `4446`、程序段 `10409`、拒绝记录 `435`、拒绝程序 `10`。
- 无白名单的 `model-replay-audit` 得到 `15` 项差异。ENR 4.1 导航台证据已恢复；因此 r186 的 `138` 条证据丢失不再出现。审计报告 `diagnostics/r187-model-replay-audit.json` 由标准 JSON 库重读成功。
- 其中 `13` 项是已测试的 DOVIV 规则：四个精确航路端点与一个航点的 `country` 由空恢复为 `ZB`，以及八项 ACC/邻接派生统计。该规则仍只能以精确路径、旧/新哈希和现有正反例测试接受。
- 另 `2` 项来自 `885058f fix: refresh snapshot IAP coverage audit`：`iap_coverage.version` 从 `23` 升至 `24`，并新增七组 `source_incomplete_chart_title_matches`。代码只在无主进近时收集标题命中审计，未修改 `procedure_segments`、`rejected_records` 或 IAP 投影选择；`package.py` 构建前也会从模型内容重新计算覆盖报告。因此它是已验证的审计元数据升级，不是 424、PDF/OCR 缓存或目标内容漂移。
- 本轮局部白名单 `diagnostics/r187-model-replay-allowlist.json` 含全部 `15` 项的精确路径和两侧 SHA-256。带 `--fail-on-unexpected` 的复跑报告 `diagnostics/r187-model-replay-audit-allowed.json` 为 `allowed_difference_count=15`、`unexpected_difference_count=0`、`consistent=true`。白名单和报告均为本地诊断产物，不得提交；不得把路径前缀、类别或计数阈值改成宽松白名单。
- r187 已通过模型来源门禁，允许进入 r188/r189 的双重候选构建；仍须使用同一 r187 冻结模型、同一官方基线与设施索引。只有有效文件树再次完全自重放、`validate`、标准 JSON 解析和 `file-convergence-audit` 全部完成，才能评价参考 `0/29` 是否变化。继续禁止部署、实机验收和 Release。
