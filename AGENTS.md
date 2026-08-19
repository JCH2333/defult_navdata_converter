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

- 公开仓库：`https://github.com/JCH2333/defult_navdata_converter`；当前已推送提交为 `5af1a21 feat: audit unresolved airway endpoint sources`。开始工作前必须重新运行 `git status --short --branch`，不得把本地诊断或未提交工作误记为已推送。
- 当前唯一可比较候选：`output/candidate-2608-default-r162-airway-coordinate-precision`。它是测试候选：`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`。
- 参考范围已完整复现为主覆盖包 `15` 个文件、机场补丁覆盖包 `14` 个文件；候选无缺失或额外文件，逐文件 SHA-256 相等仍为 `0/29`。因此不能部署、不能标记 release，也不能将局部语义改善表述为字节一致。
- 全量自动化测试基线为 `384 passed`。这只证明代码回归通过；SDK 编译、离线读取器、参考语义差分、用户实机验证和正式发布必须分别报告，互不替代。
- 424 归一化模型已经可复建且可序列化：机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`。模型存在不等于目标内容或二进制已经收敛。
- 航路 r162 基线：候选 `4434` 行、参考 `4614` 行、严格相等 `1383` 行、字段差异 `2045` 行、候选独有逻辑键 `1006`、参考独有逻辑键 `1186`。脱敏审计确认 `2045` 条字段差异全部唯一关联当前 424 的 `(airway, sequence)`；其中 `2015` 条仅几何差异，`30` 条为几何加最低高度差异。
- IAP 有 `780` 个分组，仍有 `10` 个 `no_unique_primary`：`ZBAD/R29R`、`ZJSY/I08-X`、`ZSNJ/I25`、`ZSOF/R15`、`ZSOF/R33`、`ZSWY/I03`、`ZUAL/I15`、`ZYDD/R01`、`ZYDD/R01-Y`、`ZYTL/R10`。未形成唯一、可回溯的 424/PDF 证据链前必须保持拒绝。
- `Route` XML 已由 SDK XSD 确认合法顺序为 `Previous* -> Next*`，两类子节点都可多次出现。r169 的 `Next -> Previous` 仅是失败诊断，不能用于候选比较。正式投影已恢复合法顺序；线性、汇聚、分叉探针已经程序化，但尚未完成有效编译验证。
- 航路端点来源审计 r173 确认 r162 跳过的 `12` 条航段暂无安全恢复项：11 个空区域端点关联 25 条源航段，8 个是多地区邻接边界点，2 个无法建立唯一指定点身份，`LELIM` 虽有唯一邻接区域但 ACC 证据不一致。不得降低 FIR/ACC/邻接一致性门禁。
- 当前 `FlightSimulator2024.exe` 已确认不在运行。可以执行下一轮隔离 SDK 探针；在通过全部最终门禁前，仍不得覆盖 Community。

### 进度口径

不得用单一百分比掩盖格式契约和来源边界。状态报告必须使用下表，并同时报告参考文件哈希数。

| 阶段 | 当前状态 | 阶段出口条件 |
| --- | --- | --- |
| 输入锁定、424 解析与 `NavModel` | 基础链路完成 | AIRAC、输入清单、SHA-256、来源引用和模型快照可从干净输入重建 |
| 默认 BGL/Package Tool 构建 | 基础链路完成 | ASCII 暂存、异步进程等待、包结构、元数据与确定性构建检查通过 |
| 本地验证与脱敏审计 | r162 基线完成 | `validate`、BGL 布局审计、完整脱敏语义差分、来源缺口审计可重复 |
| 航路 SDK 表达和内容收敛 | 进行中 | 最小探针证明合法表达；完整候选可编译且严格相等增加或差异减少 |
| 来源缺口闭合 | 进行中 | 每个跳过航段和空区域端点都有可复用来源规则，或明确、可审计地拒绝 |
| IAP 未决闭合 | 进行中 | 10 组逐项具备正例、反例、来源链、审计计数和 BGL 回归，或明确拒绝 |
| BGL、索引和元数据字节收敛 | 未达标 | 参考范围内 `29/29` 个文件 SHA-256 全部一致 |
| 部署与实机验收 | 未开始 | 字节一致、可恢复备份、用户实机清单全部通过 |

可称为“转换基础管线已建立，内容和二进制收敛进行中”。整体工程只能粗略估为约 `40%` 到 `50%`；字节级验收进度必须单独表述为 `0/29`，不得与代码或测试完成度混淆。

### 接下来按顺序执行

1. **冻结 r162 并建立实验输入清单。** 不修改 r162 的输入、候选、报告或哈希。所有新工作使用递增 `rNNN`，每轮在报告开头写入单一假设、唯一变量、输入 SHA-256、工具版本、禁止读取的数据和预期指标。
2. **先完成航路 Route 形状 SDK 探针。** 在游戏保持关闭的前提下，以新 r 编号运行 `airway-route-child-order-probe`；必须验证线性、汇聚、分叉三种 `Previous* -> Next*` 形状。出口条件是 Package Tool 成功、读取器完整登记一个 BGL，且报告保存 XML、进程轨迹、BGL 头部/节表、fragment、sequence 和几何结果。失败只保留诊断，不修改正式投影。
3. **仅在探针通过后构建下一完整候选。** 依次运行 `build`、`validate`、完整脱敏 `semantic-diff`、`airway-diff-audit`、`source-gap-audit`、`bgl-layout-audit` 与 `airway-endpoint-audit`。候选只有在本地契约仍通过且核心指标改善时保留；否则记录否决原因并回到最小探针。
4. **按差异类别收敛航路。** 先隔离验证坐标序列化精度、包围盒生成、fragment/sequence 切分、同名航路分组、物理写入顺序和最低高度表达。禁止重复已否决的整体 `CODE_DIR=B` 反转、单向连接或无来源猜测。任何适配器改动必须先有最小 fixture、正反例和脱敏审计。
5. **保持来源缺口的保守边界。** 对 12 条跳过航段、5 个未决指定点以及参考独有对象，只接受当期 424 结构化表、可审计 PDF、受限可复跑 OCR、FIR/ACC 几何和邻接规则。严禁读取 Fenix `nd.db3`、参考 BGL/SQLite 记录、参考坐标或参考逻辑键来回填。
6. **逐组处理 IAP 未决。** 每条新规则必须同时包含直接来源、正例、拒绝例、审计字段、最小 fixture 和 BGL 投影回归。OCR 只可作为已有 PDF 与已有数据库主进近之间的多缓存共识证据，不得创建主进近、航段、图页匹配或坐标航点。
7. **分文件推进二进制收敛。** 先将 `00_enroute.bgl` 与机场分区 BGL 分开，再处理机场补丁 BGL、`bglIndex.bout`、`layout.json`、`manifest.json` 和 ContentInfo。固定 SDK、ASCII 暂存根、输入 XML 排序、包名、元数据和构建时序；先证明两次干净构建彼此一致，再将其与参考作只读哈希比较。
8. **执行最终验收和部署。** 达到 `29/29` 后从干净输入重建一次，确认结果和报告可重复；确认游戏关闭，创建带时间戳的完整 Community 备份和恢复清单并完成恢复演练；再由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只允许测试版，不得正式 Release。

### 可复用转换工作管线

所有未来 AIRAC 周期和目标格式必须遵循以下阶段，不得把目标专用规则写回 424 来源解析层：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 固化 424 CSV/PDF、官方目标模板、SDK/读取器/编译器版本、AIRAC、树清单与 SHA-256。
- `ingest-424` 和 `evidence-audit` 只产生可回溯来源；OCR 必须带缓存版本、渲染参数、模型/命令、页面哈希和回链验证，不能成为一次性人工判断。
- `normalize-model` 维护跨格式 `NavModel`、原始精度、来源引用、拒绝项和规则版本；任何目标 schema、字符串长度、空值、排序或元数据规则只能存在于目标 profile/adapter。
- `project-target` 为默认 BGL、Fenix、TFDI、PMDG、FSL/FSLabs、iFly 等分别建立独立 profile/adapter、降级策略、最小 fixture、目标验证器和实机清单；适配器消费模型快照，不重新解析 424。
- `build-target`、`validate-target` 和 `diff-and-audit` 只能写隔离候选目录。报告必须将自动化测试、结构构建、读取器诊断、语义差分、来源审计、文件树和 SHA-256 分开保存。
- `stage-backup-deploy` 是唯一可写游戏文件的阶段。GUI、CLI 和 GitHub 自动更新系统必须共用同一 profile、候选报告和 `deployable` 门禁，任何入口都不能绕过测试版或部署保护。

### 每轮 Codex 维护要求

1. 开始前读取根目录和仓库 `AGENTS.md`，检查 Git、游戏进程、最后可用候选和最新报告。
2. 实验前记录 r 编号、单一假设、单一变量、输入/工具快照、禁止数据和成功/失败指标。
3. 先写最小测试或最小 SDK 探针，再改正式 adapter；一次实验只改变一个变量。
4. 完成后更新本节和对应经验章节，记录候选或诊断路径、提交号、测试、构建、读取器、语义差分、`29` 文件哈希、来源审计及保留/否决结论。
5. 每次代码或仓库文档改动后运行适当测试和 `git diff --check`，仅暂存相关文件，创建一个可解释提交并推送 GitHub。数据库、备份、日志、诊断产物、SDK 中间输出和外部测试包不得提交。
6. 任何状态汇报必须分开说明：自动化测试、SDK 构建、本地读取器诊断、参考哈希、用户实机验证和正式发布状态。
