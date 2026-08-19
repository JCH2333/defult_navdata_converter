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

## 2026-08-19 r188/r189 DOVIV 候选重复构建结果

- r188 `output/candidate-2608-default-r188-doviv-replay` 与 r189 `output/candidate-2608-default-r189-doviv-replay-repeat` 均从同一 r187 模型、同一官方双包和同一已验证官方设施索引独立调用 Package Tool 构建。两份候选均为 `status=candidate`、`local_contract_verified=true`、`valid=true`、`deployable=false`，各含 `21` 个 BGL。
- `diagnostics/r190-r188-r189-file-convergence-audit.json` 使用标准 JSON 库复核，结果为候选重复范围 `29/29` SHA-256 一致，参考范围仍为 `0/29`。这再次证明本地构建确定性，不证明参考一致、游戏加载或可部署。
- 与 r181 的只读影响范围审计 `diagnostics/r190-r188-vs-r181-file-convergence-audit.json` 显示 `25/29` 相同；四个变化文件精确为主覆盖包的 `00_enroute.bgl`、`bglindex.bout`、`layout.json` 和 `manifest.json`。十个区域机场 BGL、十个机场补丁 BGL、两个 ContentHistory 和补丁包元数据均未变化，符合 DOVIV 仅恢复航路区域的单变量假设。

## 2026-08-19 权威状态、进度与后续计划（r192 后续维护入口）

本节优先于本文件中此前的默认通用数据状态、百分比和后续计划；历史章节保留为可复核实验记录。每次继续工作前必须依次核对本节、根目录 `AGENTS.md`、`git status --short --branch`、最后有效候选的 `conversion-report.json`、最新 `rNNN` 诊断及本轮测试。若文档与实际产物冲突，以实际 Git、候选报告、标准 JSON 重读和测试结果为准，并在本节同步修正。

### 1. 当前真实状态与量化进度

- 仓库为 `fenix_to_default_navdata`，公开远端为 `JCH2333/defult_navdata_converter`。本地 `main` 的 HEAD 是本节对应的文档提交，当前相对 `origin/main` 领先 `6` 个提交，工作树干净。此前普通推送因 `http://127.0.0.1:7897` 不可达而失败；网络恢复后只允许普通 `git push`，随后以 `git ls-remote --heads origin main` 复核，不得强推或重写历史。
- 当前有效输入快照为 `output/intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。模型规模：机场 `275`、跑道方向 `640`、导航台 `438`、航点 `2741`、航路 `4446`、程序段 `10409`、拒绝记录 `435`、拒绝程序 `10`。
- r188/r189 从同一冻结模型、同一官方双包和同一官方设施索引独立构建。两份候选均为 `status=candidate`、`valid=true`、`local_contract_verified=true`、`deployable=false`，各含 `21` 个 BGL；候选重复构建文件树为 `29/29` SHA-256 一致，参考成品范围仍为 `0/29` 一致。
- r188 相对 r181 仅改变主覆盖包 `00_enroute.bgl` 及其派生 `bglindex.bout`、`layout.json`、`manifest.json`，其余 `25/29` 文件不变，符合 DOVIV 航路区域恢复的单变量假设。
- 工程能力进度仍估计约 `45%`：424 输入、可复用 `NavModel`、证据审计、BGL/Package Tool 构建、CLI/GUI、候选验证与文件收敛审计均已存在；剩余工作集中在来源缺口、目标 SDK 表达契约和参考二进制收敛。字节级验收进度必须单独报告为 `0/29`，部署、实机验证和正式 Release 均为 `0%`。
- 未覆盖 Community，未创建本轮备份，未进行用户实机测试，未创建 Release。即使游戏当前未运行，也不得因本地契约通过而部署。

### 2. r191/r192 已完成诊断与结论

- `diagnostics/r191-airway-endpoint-source-audit.json` 审计了 `10` 个未决航路端点和 `21` 条关联航段：`7` 个为多地区邻接的边界点，`2` 个没有可用的 `DESIGNATED_POINT.csv` 精确身份，`1` 个 `LELIM` 虽有单一 `ZG` 邻接但 `M503` 的上海/广州 ACC 证据与恢复门禁冲突。`DXG` 不在可解析的 VOR/NDB 直接表中，不能凭邻接发明地区。结论是本轮没有新的来源恢复规则；这些对象继续显式拒绝，不得为追求差异数量而放宽 FIR、ACC 或身份约束。
- `diagnostics/r192-airport-source-inventory.json` 确认候选已投影来源完整的 `275` 个机场、`640` 个跑道方向、`12549` 个终端航点、`430` 个 ILS 和 `1297` 个等待航线。`346` 个具有 `SERVICED_AIRPORT` 的导航台只具备航路层投影资格，不能伪造为机场 NDB；`CONTROLLED_RADIO.csv` 是空域扇区频率，不能映射为机场 `Com`/`Tower`。
- 参考机场 BGL 仍具有候选缺失的 `0x17`、`0x33` 等节且体积明显更大。这只说明目标 SDK 表达尚未取证；禁止根据参考节表、参考记录或参考坐标反向伪造对象。
- 已否决方向继续有效：机场关联 NDB 伪投影、`onlyAddIfReplace`、根节点终端航点重复、空域通信映射、等待航线隔离、`CODE_DIR` 简单反转、无来源 `routeType` 猜测。任何重提都必须先给出新的直接 424 来源或真实 SDK/运行时证据，并建立最小正反例。

### 3. 下一轮强制工作流

每个 `rNNN` 必须只验证一个假设、只改变一个变量。开始前创建实验记录，写清：目标问题、允许读取的内容来源、明确禁止读取的数据、冻结模型/官方模板/工具 SHA-256、预期受影响的文件角色、成功条件和否决条件。结束后必须保留候选或诊断路径、测试命令、Package Tool 轨迹、标准 JSON 重读结果、文件树哈希、来源审计和保留或否决结论；随后更新本节和根目录 `AGENTS.md`。

1. **r196 起先读取 r195 候选清单，再做来源完整 SDK 单变量探针。** r193/r194 已完成：r193 因保留根 `AiracCycle`、`Vor`、`Ndb` 而发生根对象污染，结论无效；r194 已以根级排除完成 ZUAL 跑道表面对照，但没有产生可解释参考缺失节，不能接入适配器。r195 已建立 `airport-source-inventory-v2`：阈值位移是唯一未否决且具直接 424/SDK 对应的候选，但其最小构建不产生 `0x17/0x33`，暂不接入 adapter。r196 必须先重跑当前库存，选择另一个 `eligible_for_sdk_probe` 对象，或转入剩余航路/IAP 来源卡；禁止重复表面、阈值位移、机场关联导航台或空域通信探针。探针不得修改 `NavModel` 或正式候选。每个探针必须同时保存源 XML 与生成 XML 哈希、探针脚本哈希、编译命令/工具路径/尝试/日志轨迹、Package Tool 产物树哈希、BGL 头/节表、读取器完整登记和文件 SHA-256。只有可解释来源、作用域和目标 BGL 变化的结论才可进入适配器。
2. **逐项关闭已知 424 内容缺口。** 对 `10` 个拒绝 IAP 组、`13` 个未分类程序段、`12` 条未投影航路段和 `5` 个未投影航路点建立来源卡。顺序固定为“数据库已有主段或结构化 424 记录 -> PDF 直接文本 -> 受审计且可复跑的 OCR 共识 -> 唯一保守规则 -> 正例/拒绝例 -> 来源审计 -> BGL 投影 -> 独立 validate”。OCR 只能提供可审计证据，不能生成主进近、航段、图页对应、坐标或任何人工一次性答案。
3. **将已证实的探针结论最小化投影到适配器。** 每条规则必须有最小 fixture、正例和反例测试、来源字段与降级理由、预期影响 BGL 文件角色。变更后先导出新的冻结模型，再执行 `model-replay-audit`；除精确允许清单外出现差异即否决该轮，不构建候选。
4. **执行候选双构建和逐文件收敛。** 仅在模型门禁通过后，从同一冻结模型独立构建两次，要求有效文件树全等、`validate` 通过、报告可被标准 JSON 库重读。再运行只读 `file-convergence-audit`，按 `00_enroute.bgl`、区域机场 BGL、机场补丁 BGL、索引/布局、清单/ContentHistory 分组报告 `29` 个文件的参考一致数。只有影响范围符合假设且参考一致数增加，才算字节收敛进展。
5. **完成字节验收后才进入部署门禁。** 达到参考 `29/29` 后，必须从干净输入重建两次，并核对输入清单、模型、报告和包树 SHA-256；随后确认 `FlightSimulator2024.exe` 已退出，为两个 Community 覆盖包及其 `layout.json`、`manifest.json`、ContentHistory 建立带时间戳备份并执行恢复演练。仅在这些门禁完成后，才可覆盖 Community 并交由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只能标记为测试版。

### 4. 可复用转换管线与跨格式边界

固定跨 AIRAC、跨目标格式的内容管线为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `NavModel` 和版本化冻结快照是唯一的内容边界。`ingest-424` 只读取当期 424 CSV/PDF 和受审计 OCR 证据，保留 `SourceRef`、原始精度、拒绝原因和规则版本；不得读取 Fenix、参考成品导航记录或目标二进制作为内容输入。
- 每个新目标必须新建独立 `profile`、`adapter`、`validator`、`deployer`。profile 记录官方基线、真实加载路径、schema/文件契约、排序、单位、NULL/default、长度上限、元数据、降级策略、最小 fixture、运行时模拟器和实机清单。不得把目标专有字段和规则回写进 `source.py`。
- OCR 是可重放的证据提供器，不是转换结果。缓存必须绑定 PDF SHA-256、页码、裁剪/预处理、模型与命令版本、运行时图像、解析器版本和多次一致性；不满足门禁只能产出审计或拒绝记录，不能进入模型投影。
- CLI、GUI、GitHub 自动更新、构建、验证和部署必须调用同一 profile、候选清单、报告 schema 与 `deployable` 门禁。GUI 只呈现状态和调用受控 CLI，不能绕过模型审计或直接覆盖 Community；自动更新只分发已提交、已验证的工具代码，不能携带本地数据库、OCR 缓存、诊断或候选包。
- 每个 AIRAC 至少保留输入 manifest、证据 manifest、模型快照与重放审计、profile、构建/验证/差分报告、拒绝策略和可恢复部署记录。未来转换 TFDI、FSL/FSLabs、PMDG、iFly 或其他格式时，只消费冻结 `NavModel` 并新增目标适配器，不重新解析 424，也不把某一机模的中间产物作为通用来源。
- 两份候选的独立 `validate` 均确认官方设施索引、官方区域恢复、导航台选择、包契约和本地候选契约通过；飞行验证清单仍全部未验证。构建后再次确认 `FlightSimulator2024.exe` 未运行；未覆盖 Community，未创建备份，未部署，未创建 Release。
- 本轮 DOVIV 规则已完成“来源模型重放 -> 双构建 -> 本地验证 -> 影响范围审计”闭环。后续不得仅为重复此规则再构建候选；下一轮应从剩余 `12` 条航路段/`5` 个航点区域的明确来源卡，或一个来源完整的 SDK 表达缺口中选择单一假设，并继续要求影响文件角色与结果严格一致。

## 2026-08-19 r193/r194 ZUAL 跑道表面探针结论

- r193 的 `diagnostics/r193-zual-runway-surface-concrete-20260819` 不是单变量实验。它只移除了根航点，却保留根 `AiracCycle`、`Vor`、`Ndb`，生成 BGL 包含 `0x17`、`0x20`、`0x33` 和嵌入 magvar；因此不能把其节表或读取器结果归因于 ZUAL 跑道表面。该目录保留作污染诊断，不得引用为适配器规则或参考差异解释。
- r194 使用同一 r188 冻结候选的 `_work/china-navdata.xml`，仅保留 `ZUAL` 及其来源 ILS，并在根级移除 `AiracCycle`、`Vor`、`Ndb`；机场内移除 `DeleteAirport`、航点、程序和等待航线。唯一变量为每条既有 `Runway` 的 `surface=CONCRETE` 与 `surface=ASPHALT`。两份生成 XML 分别为 `975`/`974` 字节，SHA-256 分别为 `3c436b8ac763362d62dc8718ba2e1c55d08a6e2976a8cdc125fc756fc3003af5` 与 `459255366d2646f2ce1d88dd7d814fbfc5ae12888f9bff117accf562ac61bedb`。
- 两份 r194 BGL 都是 `675` 字节，节类型及计数同为 `0x3/0x13/0x32/0x35`、各 `1`；但 BGL SHA-256 分别为 `04b9a5946d2f3d847845b8acaf7fadbdf88906f3fc260b64d72bbb7d6bfc7212` 与 `d1868f9a7553942a7f901b411493a6f9f307944fa9237e921bc58cf87e4787a1`。因此 Package Tool 确实把表面差异编码进既有跑道记录，但不生成候选缺失的 `0x17`/`0x33`，不能解释参考机场覆盖包的额外节或记录量。
- r194 的离线 Navdatareader 均登记 `bgl_file_rows=1`、`ils=1`，机场与跑道为 `0`。这与既有读取器对最小机场 BGL 的限制一致，不得据此推导游戏加载行为。424 直接来源 `RWY.csv:279` 的 ZUAL `15/33` 表面为水泥混凝土，正式适配器现有 `CONCRETE` 投影保持不变。
- `airport_subset_probe.py` 的复现契约现要求报告写入源 XML、生成 XML、探针脚本、全部包文件的大小和 SHA-256，以及 Package Tool 的命令、编译器路径、尝试、进程轨迹和 Builder log。诊断输出继续被 `.gitignore` 排除；代码、测试和本节才进入 Git。后续探针不得删除这些证据字段。

## 2026-08-19 r195 跑道阈值位移候选清单与探针结论

- `airport-source-inventory-v2` 现在把机场来源对象分为已投影、明确拒绝和 `eligible_for_sdk_probe`。它只读冻结 `NavModel`、当期 `RWY.csv`/`RWY_DIRECTION.csv` 与可选候选 XML，不读取参考导航记录。真实 2608 中 `RWY_DIRECTION.VAL_THR_DISPLACE>0` 有 `33` 条，能由同一 `RWY_ID` 回链 `RWY.csv` 和机场，且 SDK `ctRunway` 明确有 `OffsetThreshold`，因此列为唯一可探针对象；跑道表面、机场关联 VOR/NDB 和空域通信分别保持 r194、来源作用域、来源作用域拒绝。
- r195 使用 r188 的冻结 `_work/china-navdata.xml`，仅保留 `ZPPP` 的物理跑道 `04/R` 及其两个来源 ILS，并在根级移除 `AiracCycle`、`Vor`、`Ndb`，机场内移除 `DeleteAirport`、航点、程序和等待航线。允许读取的唯一新增内容是 424 `RWY_DIRECTION.csv:65`：`04R`、`VAL_THR_DISPLACE=300m`；禁止读取 Fenix 和参考 BGL/记录。`04R` 与 XML 的 `number=04,primaryDesignator=R` 精确对应，因此变体只插入 `OffsetThreshold end=PRIMARY,length=984F,surface=CONCRETE`，并按 SDK XSD 位于 `Ils` 前。
- 对照输入 XML 为 `1377` 字节、SHA-256 `db6ccdec72d26146be4f86aaeefc6a9af5b1739bbb61434b8c3cfa949878e0e8`；变体为 `1443` 字节、SHA-256 `19385fa2b38e01421e4920c7b0cfdc8208eaf48733517a86d6dfe978de17d900`。Package Tool 两次均完成异步构建，读取器均完整登记一个 BGL 和两个 ILS。对照 BGL 为 `846` 字节、SHA-256 `208c3af833be1b7d3c3a78f8bf0bddcb0d0915d4bf1e4322af56000b4ce85fd1`；变体为 `878` 字节、SHA-256 `910951d81301925ed28cde0dd4efbeda7d6665c90e50ae69b9577846251d4d0b`。两者节表均为 `0x3/0x13/0x32/0x35`、各 `1`。
- 结论：Package Tool 会把来源阈值位移合法编码进既有跑道记录，但不生成候选缺失的 `0x17`/`0x33`，也没有改变读取器可见 ILS 计数。该结论仅闭合“来源字段 -> SDK 表达”的探针层，不能证明运行时加载或参考字节收敛，不能写入正式 adapter、不能触发模型重放或候选双构建。r196 必须从新的来源缺口或新的候选对象开始。

## 2026-08-19 r196 权威状态、进度与复用转换计划

本节优先于此前所有默认通用数据状态、百分比和后续计划。每次继续时，Codex 必须先核对本节、工作区根 `AGENTS.md`、`git status --short --branch`、冻结模型、最近两个有效候选的 `conversion-report.json`、最新诊断和本轮测试。文档与实际结果冲突时，以可复跑命令、标准 JSON 重读、候选产物和 Git 状态为准，并在同一轮同步更新两份 `AGENTS.md`。

### 当前事实与量化进度

- 仓库为 `fenix_to_default_navdata`，公开远端为 `https://github.com/JCH2333/defult_navdata_converter`。本轮 r196 盘点开始时本地 HEAD 为 `e7aaacc feat: audit source-backed runway SDK probes`，`main` 相对 `origin/main` 领先 `8` 个提交，工作树干净；每次继续必须重新执行 Git 状态检查，不得沿用该历史数字。普通 `git push` 因 `127.0.0.1:7897` 未监听而暂未完成；网络恢复后只允许普通推送，并以 `git ls-remote --heads origin main` 复核，禁止强推、重写历史或把本地提交误报为已推送。
- 冻结的可复用 424 内容快照为 `output/intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。模型规模为机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`、拒绝记录 `435`、拒绝 IAP `10`。
- 最新有效候选是 `output/candidate-2608-default-r188-doviv-replay` 与重复构建 `output/candidate-2608-default-r189-doviv-replay-repeat`。二者均已通过 `validate`，状态为 `candidate`、`local_contract_verified=true`、`deployable=false`；有效候选范围自重放为 `29/29` 文件 SHA-256 一致，参考中国覆盖包仍为 `0/29` 一致。前者证明构建确定性，后者表示字节级收敛尚未开始达标。
- 本轮全量自动化测试为 `409 passed`。这只覆盖代码回归；SDK 构建、本地读取器诊断、参考哈希、游戏加载、用户实机验证和正式发布必须分别报告，彼此不得替代。
- 当前工程能力可粗略估为约 `45%`：输入锁定、424 归一化、可序列化 `NavModel`、默认 BGL profile、CLI/GUI、Package Tool 构建、来源审计、候选自重放和部署门禁均已建立。最终上线验收仍为 `0%`，因为参考 `29/29`、Community 覆盖和实机验证均未完成。

| 阶段 | 当前状态 | 进入下一阶段的硬门禁 |
| --- | --- | --- |
| 输入与中间模型 | 已建立 | 输入/缓存/模型哈希可复现，来源引用完整 |
| 默认包构建与本地验证 | 已建立 | ASCII 暂存、Package Tool、`validate`、报告 JSON 重读和双构建均通过 |
| 来源缺口与目标表达 | 进行中 | 每项要么有直接来源规则、正反 fixture 与审计，要么有显式拒绝策略 |
| 逐文件二进制收敛 | 未达标 | 参考范围 `29/29` SHA-256 一致，且不读取参考导航记录回填 |
| 部署与实机验收 | 未开始 | 二进制一致、干净输入重建、游戏关闭、备份/恢复演练和用户清单全部通过 |

### r196 已确认经验与禁止回退项

- `unclassified-procedure-audit-v1` 已对 `13` 条 `kind` 为空或未验证枚举的程序段完成只读来源审计：`RNP-0` 共 `4` 条、`CC*-*` 共 `3` 条、`EO-*` 共 `6` 条。它们全部可回链当期 424 `terminal-database-coding` PDF，且 `target_mapping_allowed_total=0`；“数据库编码”页面只证明腿存在，不能证明 SID、STAR 或 IAP 类型。该 13 条必须继续以 `RejectedProcedure`/审计计数保留，禁止按标签名称、跑道、腿类型、参考差异或减少拒绝数猜测投影。
- OCR 只可作为可重跑、可校验页面 SHA-256、缓存版本、运行时画像和多次结果一致的受限证据；它只能消歧已经存在的 424 主记录，不得创建程序类型、主进近、航段、图页关联、坐标或一次性人工答案。
- 已否决且不得重复的方向：跑道表面、跑道阈值位移、机场关联 VOR/NDB、空域通信映射、`onlyAddIfReplace`、根节点重复终端航点、等待航线隔离、简单或整体反转 `CODE_DIR`、猜测 `routeType`。除非获得新的独立直接来源和新的最小反例，不得重开这些实验。
- SDK 节表、参考 BGL/SQLite、参考坐标和 Fenix 数据只能用于加载契约、只读结构诊断或最终差分；不得成为 `NavModel` 或目标 BGL 内容输入。参考范围看板只保存文件角色、大小、哈希和脱敏结构摘要。

### 下一阶段执行计划与关键节点

1. **维护 r196 拒绝基线。** 将未分类程序审计结论视为当前稳定降级策略；为每个标签族建立来源卡，包含原始 PDF、页面 SHA-256、直接类型字段、允许证据、拒绝原因和最小 fixture。只有同一 424 来源出现唯一类型字段或经审计 OCR 的直接标题证据，才可提出新的单标签族规则；否则不修改 `ProcedureSegment.kind`。
2. **先处理来源闭合，不追逐参考结构。** 对 `12` 条未投影航路段、`5` 个未决全局航点区域和 `10` 组 `no_unique_primary` IAP 分别建立可机读来源卡。固定顺序为：结构化 424 身份 -> PDF 直接文本 -> 受控 OCR 共识 -> 唯一保守规则 -> 正例/拒绝例 -> 来源审计 -> 模型重放 -> 目标投影。多地区、FIR 边界、身份冲突、`RTE_SEG` 独有标识和跨页不唯一情况继续拒绝。
3. **仅做来源完整的单变量 SDK 探针。** 机场探针只从 `airport-source-inventory` 的未否决直接字段中选择一个变量；每个 `rNNN` 必须保存源 XML、生成 XML、脚本、输入和工具 SHA-256、Package Tool 命令与日志、BGL 头/节表、读取器完整登记、产物树哈希和结论。探针未同时证明来源作用域、SDK 合法表达和预期 BGL 影响时，不得接入 adapter。
4. **模型门禁后才构建候选。** 任何来源或 adapter 规则变动后，先导出新的冻结 `NavModel`，运行 `model-replay-audit --fail-on-unexpected`。除本轮精确允许的字段路径外发现差异即否决本轮；通过后才可从同一模型独立构建两次，要求 `validate`、标准 JSON 重读和有效树自重放全部通过。
5. **以逐文件看板推进 `29/29`。** 每个有效候选都运行 `file-convergence-audit`，并与重复候选和参考范围比较。按 `00_enroute.bgl`、区域机场 BGL、机场补丁 BGL、索引/布局、清单/ContentHistory 分组，只接受“来源审计合规、变化范围符合单变量假设、重复候选一致且参考一致文件数增加”的改动。读取器不稳定的航路表只能用于 XML 合法性、来源完整性和结构诊断，不得作为强语义收敛指标。
6. **字节验收后的部署顺序。** 仅在 `29/29`、干净输入双构建、全量验证、报告 JSON 重读和来源审计均通过后，确认 `FlightSimulator2024.exe` 已退出；为两个 Community 覆盖包和全部元数据建立带时间戳备份并先做恢复演练；再覆盖 `F:\games\community\Community`。随后由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点，以及退出飞行和退出模拟器。全部通过前只能标为测试版，禁止正式 Release。

### 跨 AIRAC 与跨目标格式的可复用管线

所有未来 424 周期和其他目标格式必须复用：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs`：记录 CSV/PDF、官方模板、SDK、读取器、缓存、工具版本、AIRAC、文件树与 SHA-256。
- `ingest-424` 与 `evidence-audit`：只解析 424；PDF/OCR 证据必须带可回链 `SourceRef`、页面哈希、缓存版本和拒绝原因。
- `normalize-model` 与 `model-audit`：输出版本化 `NavModel`，保留原始精度、身份、单位、来源与显式降级，不允许任何机模专有规则进入来源层。
- `project-target`：每个目标新增独立 `profile/adapter/validator/deployer`，明确模板、加载路径、schema/文件契约、字段/单位、NULL/default、排序、元数据、容量、降级、fixture 和实机清单。
- `build-target`、`validate-target` 与 `diff-and-audit`：隔离输出、确定性构建、目标专用验证、报告 JSON 门禁和只读差分；参考成品只能做验收，不得反向提供内容。
- `stage-backup-deploy`：GUI、CLI 和自动更新入口共用 `deployable` 门禁，均不得绕过备份、游戏关闭、恢复演练和版本/校验记录。

### 每轮维护协议

每轮开始前记录实验编号、唯一假设、唯一变量、允许/禁止读取的数据、冻结输入/工具哈希、预期受影响文件角色、成功条件和否决条件。每轮结束后记录候选或诊断路径、测试、SDK 构建、读取器登记、标准 JSON 重读、文件树哈希、参考 `29` 文件统计、来源审计及保留/否决结论。代码或仓库文档改动后必须执行 `pytest -q`、`git diff --check`、审查暂存区、提交一个可解释变更并普通 `git push`；若代理 `http://127.0.0.1:7897` 不可用，则保留本地提交，待网络恢复后集中推送。

## 2026-08-19 r197 默认来源缺口卡审计

- 实验编号：`r197-default-gap-cards`。唯一假设是“冻结 `NavModel` 与本转换器自身的 candidate `conversion-report.json` 足以把现有默认通用数据缺口整理为逐项、可回链、不可反向填充的来源卡”。允许读取 r187 模型和 r188 候选报告的 `projection`；明确不读取参考 BGL/SQLite 导航记录、参考坐标、Fenix 数据或候选以外的外部目标产物。
- 新增可复用 CLI：`default-gap-cards-audit --model <NavModel> --candidate-report <conversion-report.json> --output <JSON>`。它验证候选报告为 `status=candidate`，并要求跳过航路段、跳过航点、IAP `unresolved_groups`、`RejectedProcedure` 与未分类程序审计之间计数和来源身份一致；不一致即失败，防止不同模型/候选报告混用。
- r188 实际报告：`diagnostics/r197-default-gap-cards-20260819.json`。共 `40` 张阻断卡，分为航路端点区域 `12`、航路点区域 `5`、IAP 主段选择 `10`、未分类程序 `13`。五个实际跳过航路点为 `P121`、`P127`、`P188`、`P225`、`P239`；`M771` 的 `****` 只作为无唯一 `DESIGNATED_POINT` 身份的航路端点卡保留，不得伪造全局航点。
- 报告固定声明 `read_only=true`、`reference_records_read=false`、`fenix_records_read=false`。每张卡都保存直接 `SourceRef`、当前拒绝/阻断状态和允许的下一类证据；允许证据仍仅限同周期 424 CSV/PDF、FIR/ACC、受控邻接和符合 OCR 运行时/缓存门禁的直接文本。卡片不是恢复规则、不是参考成品输入，也不能单独触发模型或 BGL 投影。
- 自动化结果：新增 `tests/test_default_gap_cards.py`，覆盖来源回链、四类计数、报告/模型不一致拒绝及 CLI 写出；全量 `pytest -q` 为 `412 passed`。本轮未构建新候选、未改变 `NavModel`、未改变 BGL adapter、未覆盖 Community。
- 后续顺序更新：以 r197 的卡为唯一工作队列，优先处理五个航路点及其 12 条关联航段的直接 FIR/ACC 冲突证据；无新证据时保持拒绝。IAP 和未分类程序各卡必须分别完成直接文本/OCR 共识、唯一规则、正反 fixture 与模型门禁后，才允许进入目标投影。不得以“卡片数量下降”为目标放宽来源条件。

## 2026-08-19 r198 航路端点拒绝理由绑定

- r198 只修改 `default-gap-cards-audit` 的航路卡审计字段：复用既有只读 `airway-endpoint-audit`，按端点类型、标识和精确坐标把来源端点分类、相邻地区和 ACC 名称绑定到候选实际跳过的航路段。未改动来源解析、`NavModel`、BGL adapter 或候选投影。
- 实际报告：`diagnostics/r198-default-gap-cards-endpoints-20260819.json`。12 条跳过航路段中 `11` 条的空端点为 `multiple_neighbor_regions`，邻接地区集合分别为 `ZH/ZL`、`ZG/ZP/ZU`、`ZH/ZP`、`ZG/ZS`、`ZH/ZS` 等跨地区组合；`M771:1` 的 `****` 为 `non_designated_endpoint_identity_unavailable`，不在 `DESIGNATED_POINT.csv` 的唯一身份集合中。
- 结论：当前五个可识别航路点和其关联的 11 条航段均已有直接来源拒绝理由，不得再次使用单一邻接地区、反转方向或参考结构推断恢复；`M771/****` 不得创建全局航点。除非新增同周期直接 FIR/ACC 证据且与全部现有邻接证据一致，否则这 12 张航路卡保持阻断。
- 自动化：缺口卡测试加入端点来源理由回归，全量 `pytest -q` 为 `412 passed`。报告仍为 `read_only=true`、`reference_records_read=false`、`fenix_records_read=false`。下一轮不再重复航路邻接方向，转入一个 IAP 或未分类程序卡的直接 PDF/OCR 证据核验。

## 2026-08-19 r199 ZBAD/R29R OCR 取证运行时门禁

- 实验编号：`r199-zbad-r29r-ocr-runtime`。对象为 r198 缺口卡 `ZBAD:R29R`，直接来源页为 `Terminal/ZBAD/ZBAD-0C-19.pdf`。唯一假设是本机 OCR 运行时可复跑，从而只将 OCR 用于消歧已有 IAP 主段；禁止读取参考包、Fenix、参考坐标或手工转录内容。
- 运行 `ocr-skill extract <ZBAD-0C-19.pdf> --json` 失败：`engine_unavailable`，`llama-server` 在 `http://127.0.0.1:8090` 返回 `WinError 10061`。随后 `ocr-skill doctor --json` 返回 `status=broken`、`ready=false`；Python/PDF 依赖和缓存目录正常，唯一警告为 `engine_llamacpp` 未监听。不得用 mock、单次人工答案或替代 OCR 引擎伪造该页内容。
- 结论：本轮未获得任何直接标题或角色证据，`ZBAD/R29R` 继续保持 `no_unique_primary` 和 `RejectedProcedure`。这不是对 IAP 内容的否定，也不是放宽投影规则的理由；OCR 服务恢复、页面哈希和多次结果满足缓存门禁前，禁止修改 `iap_coverage`、`ProcedureSegment` 或 BGL。
- 后续：先恢复可复跑的本地 OCR 服务，再以 r197/r198 IAP 卡逐项执行“数据库主段 -> PDF/OCR 直接证据 -> 唯一规则 -> 正反 fixture -> 模型门禁 -> 投影”。未恢复前可继续处理不依赖 OCR 的结构化 424 规则，但不得重复航路邻接实验。

## 2026-08-19 r200 权威项目状态、进度口径与字节收敛计划

本节优先于本文件此前默认通用数据的旧进度、旧 Git 领先数和旧“下一轮”描述。历史章节用于复核实验，不得直接作为当前决策依据。每次继续前，Codex 必须重读本节，并重新核对实际 Git 状态、冻结模型 SHA-256、两份有效候选的 `conversion-report.json`、最新诊断、标准 JSON 重读结果和本轮测试；任何冲突均以可复跑产物为准，并在同一轮更正本节及工作区根 `AGENTS.md`。

### 当前真实状态与进度看板

- 仓库：`fenix_to_default_navdata`；公开远端：`https://github.com/JCH2333/defult_navdata_converter`。截至本次盘点，HEAD 为 `eea2d2f docs: record r199 OCR runtime gate`，工作树干净，本地 `main` 相对 `origin/main` 领先 `12` 个提交。普通推送仍受 `http://127.0.0.1:7897` 未监听阻断；网络恢复后只允许执行普通 `git push`，再执行 `git ls-remote --heads origin main`，禁止强推或重写历史。
- 冻结的跨格式内容边界为 `output/intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。模型含机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、航路段 `4446`、终端航点 `12549`、程序段 `10409`、ILS `430`、等待航线 `1297`、拒绝记录 `435`、拒绝 IAP `10`。
- 有效候选为 r188 与 r189。二者使用同一冻结模型、官方双包和已验证设施索引独立构建，均为 `candidate`、`valid=true`、`local_contract_verified=true`、`deployable=false`，各含 `21` 个 BGL。`r190-r188-r189-file-convergence-audit.json` 证明候选自重放为 `29/29` 个文件 SHA-256 一致；与 `Default navdata 2608R1` 参考范围的字节一致仍为 `0/29`。
- 参考验收范围的 29 个文件由航路 BGL `1`、区域机场 BGL `10`、机场补丁 BGL `10`、包索引 `2`、布局 `2`、清单 `2` 和 ContentHistory `2` 组成。候选确定性不等于参考一致、游戏加载或可部署。
- r197/r198 已把已知内容阻断整理为 `40` 张来源缺口卡：航路端点区域 `12`、全局航点区域 `5`、IAP 主段 `10`、未分类程序 `13`。这是“卡片已覆盖和分类 `40/40`”，不是“内容已转换 `40/40`”：目前新增投影数为零，参考一致数仍为 `0/29`。
- 当前全量回归基线为 `412 passed`。工程基础能力可粗略估计为约 `45%`：输入锁定、424 归一化、版本化 `NavModel`、默认 BGL profile、CLI/GUI、Package Tool 构建、验证、模型重放审计、来源卡和文件收敛审计已建立。最终字节验收为 `0/29`，部署、用户实机验证和正式 Release 为 `0%`。
- 未覆盖 `F:\games\community\Community`，未为本候选创建部署备份，未进行实机验证，未创建正式 Release。即使 `FlightSimulator2024.exe` 未运行，也不满足部署条件。

| 里程碑 | 已完成证据 | 当前缺口 | 完成判据 |
| --- | --- | --- | --- |
| 输入与中间模型 | 424 输入边界、来源引用、r187 冻结模型和模型重放审计 | 每个新周期需重新锁定输入与证据 | 输入/缓存/工具/模型清单与 SHA-256 可复跑 |
| 目标构建确定性 | r188/r189 有效文件树 `29/29` 自重放一致 | 不能解释参考包二进制差异 | 同一冻结模型双构建、`validate`、JSON 重读均通过 |
| 内容来源闭合 | 40 张卡均已建立，航路与未分类程序已有保守拒绝结论 | 10 组 IAP 与任何新的直接来源规则仍待逐项取证 | 每项有来源、正反 fixture、审计和明确投影或拒绝 |
| SDK 表达契约 | 多项单变量探针已排除错误方向 | 机场/覆盖层缺失对象族和二进制布局尚无可证明来源表达 | 来源作用域、SDK 编码和预期 BGL 影响形成闭环 |
| 参考字节验收 | 只读 `file-convergence-audit` 已覆盖全部 29 文件 | 参考一致 `0/29` | 干净输入双构建后候选与参考 `29/29` SHA-256 一致 |
| 部署与实机验收 | 部署门禁、备份机制和测试清单已定义 | 尚未达到字节门禁 | 备份/恢复演练、覆盖、用户实机清单和退出稳定性均通过 |

### 已确认经验、来源边界与禁止回退项

1. `NavModel` 是唯一跨 AIRAC、跨格式的内容边界。默认 BGL、其他机模数据库、GUI、CLI 和自动更新均只能消费版本化模型；不得重解析已冻结 424，更不得读取 Fenix `nd.db3`、参考成品记录、参考坐标或参考 BGL 内容来补写模型。
2. 官方 `navigraph-nav-base` 与 `navigraph-nav-jepp` 只负责目标加载契约和全球基线；`Default navdata 2608R1` 只用于最终只读文件级差分。参考包的文件大小、哈希和脱敏结构摘要不能反向推导要伪造的导航记录。
3. OCR 是可复跑的来源证据提供器，不是人工补丁。可参与投影的缓存必须绑定 PDF SHA-256、页码、提取器/解析器版本、渲染与预处理、模型和命令、运行时画像及多次一致性；运行时不可用、缓存不完整或结论不唯一时，只能输出审计或拒绝。
4. 已否决且不得重复的方向包括：航路邻接或整体 `CODE_DIR` 反转、机场关联 VOR/NDB 伪投影、`onlyAddIfReplace`、根节点重复终端航点、空域通信映射、等待航线隔离、跑道表面、跑道阈值位移和无来源的 `routeType` 猜测。重开任何方向前必须有新的直接来源和新的最小正反例。
5. `12` 条航路端点卡中，`11` 条属于多地区邻接，`M771:1` 的 `****` 没有 `DESIGNATED_POINT.csv` 唯一身份；保持拒绝。`13` 条 `RNP-0`、`CC*-*`、`EO-*` 未分类程序只可回链到数据库编码页，未形成类型证据；继续作为显式降级，不得以标签名称猜测 SID/STAR/IAP。
6. 已存在可审计的 `ZBAD-0C-19.pdf` 缓存证据：文件 SHA-256 为 `7120b21074af83279e14196e54572714779e750365b9a451694ebcee34b5ec8e`，缓存版本 `43`。其 `R29R` 仅含 `进近过渡`（`IF AD521`、`TF AD790`）和 `复飞`（`CA 291`、`DF AD521`），没有主进近腿、进近图标题或直接角色。r200 必须将此写成可复用的“仅过渡/复飞、无主段”审计结论和正反 fixture；不得把 `R29R` 投影为进近，也不得借用其他跑道或图页主段。

### 后续执行计划与关键节点

1. **r200：固化 ZBAD/R29R 的直接来源拒绝规则。** 只读取当前 424 PDF 与受审计缓存，新增可复用审计/来源卡字段，证明“已存在同标签过渡和复飞，但无主进近”必须保持 `no_unique_primary`。加入一个正例和一个反例 fixture，验证不能从其他跑道、其他页或复飞腿借用主段。此轮不依赖 OCR 服务、不修改 BGL 投影、不构建候选。
2. **IAP 队列：按单卡而非按机场推进。** r200 后仅从其余 `9` 个 IAP 卡中选择一个。固定顺序为“数据库已有主段与标签 -> 424 PDF 直接文本 -> 满足门禁的 OCR 共识 -> 唯一保守归属规则 -> 正例/反例 -> 来源审计 -> 模型重放 -> BGL 投影”。任何条件不成立即写入明确拒绝，不得为减少未决数创建路径、坐标、图页归属或主段。
3. **OCR 运行时恢复：作为独立基础设施任务。** 先用 `ocr-skill doctor --json` 确认 `llama-server` 可访问 `127.0.0.1:8090`，记录二进制、模型、命令和版本；再对单一 PDF 执行至少两次相同配置提取，比较页面/文本/解析结果和 SHA-256。运行时恢复本身不允许修改模型或候选，只有缓存通过画像和一致性门禁后才可供第 2 项使用。
4. **航路与未分类程序：维持并扩展拒绝基线。** 现有 `12 + 5 + 13` 张卡不是盲目待办项。仅当同周期 424 出现与现有邻接、FIR/ACC 和精确身份不冲突的新直接证据时，才创建一条单变量恢复规则；否则只增强来源理由、fixture 和拒绝可读性，不修改模型。
5. **SDK 表达取证：只探测来源完整的对象族。** 机场/覆盖层存在明显的 BGL 节和体积差，但这些差异不是内容来源。每轮先从来源库存选择一个未否决的完整对象族，保留原始 XML、生成 XML、脚本、输入/工具哈希、Package Tool 轨迹、BGL 头/节表、读取器完整登记和产物树哈希。只有“424 来源 -> SDK 合法表达 -> 可解释 BGL 影响”三项同时成立，才可进入正式 adapter。
6. **规则接入后的模型门禁。** 任一来源或 adapter 变更先导出新的冻结模型，使用 `model-replay-audit --fail-on-unexpected` 对比 r187 或本轮基线。允许差异必须是精确对象身份、字段路径和两侧哈希；发生未允许差异时停止，不构建候选。
7. **候选收敛循环。** 模型门禁通过后，从同一模型独立构建两次，依次执行 `validate`、标准 JSON 重读、候选有效树自重放和只读 `file-convergence-audit`。按 7 类文件角色报告本轮影响。只有候选仍自重放一致、影响范围符合假设且参考一致数从 `0/29` 增加，才记录为字节收敛进展。
8. **字节门禁后的部署。** 仅在参考 `29/29`、干净输入双构建、完整来源/结构验证、报告 JSON 重读均通过后，检查 `FlightSimulator2024.exe` 已退出；为两个 Community 覆盖包及 `layout.json`、`manifest.json`、ContentHistory 建立带时间戳 SHA-256 备份，并先完成恢复演练。覆盖后由用户验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只能是测试版，禁止正式 Release。

### 可复用转换管线与状态维护协议

所有未来 AIRAC 和目标格式固定复用：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 必须保存 CSV/PDF、官方模板、SDK、读取器、缓存、工具版本、AIRAC、文件清单和 SHA-256。`ingest-424` 与 `evidence-audit` 只解析 424，所有补充证据均要可回链到 `SourceRef` 和拒绝/降级理由。
- `normalize-model` 与 `model-audit` 只产生版本化 `NavModel`，保留原始精度、单位、身份、来源、规则版本和不可表达项。新目标格式不得向来源层写入专有字段。
- `project-target` 为每个目标新增独立 `profile`、`adapter`、`validator`、`deployer`，明确真实加载路径、schema 或文件契约、单位、NULL/default、排序、容量、元数据、降级、最小 fixture、运行时模拟器和实机清单。
- `build-target`、`validate-target` 与 `diff-and-audit` 只在隔离输出运行，统一产出可机读报告。GUI、CLI、自动更新和部署入口必须共用同一 profile、候选清单和 `deployable` 决策，任何界面都不得绕过备份和游戏关闭门禁。
- 每轮开始时记录 r 编号、唯一假设、唯一变量、允许/禁止读取内容、冻结输入与工具哈希、预期影响文件角色、成功条件和否决条件。每轮结束时记录候选或诊断路径、测试、SDK/读取器轨迹、JSON 重读、文件树哈希、参考 `29` 文件统计、来源审计和保留/否决结论。
- 只有实际状态变化才更新本节中的候选编号、哈希、测试数、卡片数、参考一致数、Git 领先数和部署状态；不得沿用历史数字。代码或仓库文档改动后必须运行 `pytest -q`、`git diff --check`、审查精确暂存区、提交一个可解释变更并尝试普通 `git push`。代理不可用时保留本地提交，待网络恢复后集中推送。

## 2026-08-19 r200 ZBAD/R29R 无主进近来源审计

- 实验编号：`r200-zbad-r29r-primary-source-audit`。唯一假设是“当冻结模型和与其 `SourceRef` 精确匹配的 424 数据库编码页都只给出同标签进近过渡与复飞、没有主进近时，该 IAP 必须保持显式拒绝，不能借用其他跑道、图页或复飞腿”。允许读取 r187 `NavModel` 与受审计 PDF 直接证据缓存；禁止读取参考 BGL/SQLite/坐标、Fenix、OCR 一次性结果或人工转录。
- 新增可复用 CLI：`iap-primary-source-audit --model <NavModel> --pdf-evidence-cache <cache.json>... --output <JSON>`。它只读取缓存中 `terminal-database-coding` 图页，且要求机场、PDF 完整路径、页码和 PDF SHA-256 与 `RejectedProcedure` 的 `SourceRef` 同时精确匹配。输出固定声明 `read_only=true`、`reference_records_read=false`、`fenix_records_read=false`、`model_mutated=false`、`projection_changed=false`；缓存只是来源审计输入，绝不回写 `NavModel`。
- 实际输入缓存为 `C:\Users\Administrator\AppData\Local\default_navdata_converter\pdf-evidence-cache-2608r1-r43\36aa3108bbe5f9b5e32a80cf4bbb6f16c45fe40b56be71117196112e0a3b2dc3.json`，缓存文件 SHA-256 为 `027a78c2f7a51d6b1611df49daf36d138ed9c65db880fc0815602c483e2878dc`；其中 `ZBAD-0C-19.pdf` 的 PDF SHA-256 为 `7120b21074af83279e14196e54572714779e750365b9a451694ebcee34b5ec8e`。
- 实际报告为 `diagnostics/r200-zbad-r29r-primary-source-audit-20260819.json`。r187 的 `10` 个 IAP 未决组中，`9` 个因本轮只提供 ZBAD 单页缓存而保持 `not_evaluated_no_matching_direct_database_chart`；`ZBAD:R29R` 是唯一精确命中项，结论为 `rejected_transition_and_missed_without_primary`。模型段统计为主进近 `0`、进近过渡 `1`、复飞 `1`；缓存直接腿统计为主进近 `0`、进近过渡 `2`（`IF AD521`、`TF AD790`）、复飞 `2`（`CA 291`、`DF AD521`），逐腿身份与模型一致。
- 正反例测试覆盖“过渡和复飞均存在但无主段时明确拒绝”以及“直接缓存出现主段时保持证据不充分、不得拒绝性归纳”。CLI 输出和空缓存拒绝同样覆盖。全量 `pytest -q` 为 `416 passed`。
- 本轮未修改 424 解析、`iap_coverage` 决策、`ProcedureSegment`、BGL adapter、冻结模型或 r188/r189 候选。因此参考一致继续为 `0/29`、状态继续为 `candidate`、`deployable=false`。下一轮从其余 `9` 张 IAP 卡中只选择一张，并先取得同样精确、可审计的直接来源页或在 OCR 运行时门禁恢复后取得可复跑的限定证据。

## 2026-08-19 r201/r202 全量 IAP 直接证据盘点与缺口卡绑定

- r201 首先只读扫描本机 `pdf-evidence-cache-2608r1-r43`。r187 的 `10` 个 IAP 未决组对应 `9` 份唯一数据库编码 PDF（`ZYDD` 的 `R01` 与 `R01-Y` 共用一页）；r43 均有与其机场、完整 PDF 路径、页码和 PDF SHA-256 精确匹配的缓存，不使用 OCR、参考成品或 Fenix。
- `iap-primary-source-audit` 的实际报告为 `diagnostics/r201-all-unresolved-iap-primary-source-audit-20260819.json`。结果为 `rejected_transition_and_missed_without_primary=2`、`unresolved_direct_database_evidence_inconclusive=8`：`ZBAD:R29R` 与 `ZYTL:R10` 的模型和缓存都没有主进近，且同时有过渡与复飞；其余 `ZJSY:I08-X`、`ZSNJ:I25`、`ZSOF:R15`、`ZSOF:R33`、`ZSWY:I03`、`ZUAL:I15`、`ZYDD:R01`、`ZYDD:R01-Y` 至少缺少过渡/复飞其中之一，不能从“不完整”推出无主段，继续未决。
- r202 将 r201 只读报告绑定到 `default-gap-cards-audit --iap-primary-source-audit <r201.json>`，产物为 `diagnostics/r202-default-gap-cards-iap-primary-20260819.json`。40 张卡总数和四类计数不变；IAP 卡现精确分为 `rejected_transition_and_missed_without_primary=2` 与 `rejected_no_unique_primary=8`。绑定器强制检查报告格式、只读边界、`projection_allowed=false`、完整覆盖和每张卡的 `SourceRef`，任一来源不一致即失败。
- 新增正例、缓存含主段反例、空缓存拒绝、来源不一致拒绝和 CLI 绑定测试。全量 `pytest -q` 为 `419 passed`。本轮仅改变审计与卡片处置，不改变模型、BGL、候选或部署状态；参考字节一致仍为 `0/29`、`deployable=false`。
- 下一轮只从余下 `8` 张 IAP 未决卡中选取一个单一问题。先检查相同页面是否有可证明主段存在的直接 424 证据；若没有，保持拒绝/未决并转向另一张卡或 OCR 运行时恢复，禁止以“已有过渡或复飞”为由创造主进近。

## 2026-08-19 r203 ZJSY/I08-X 同页基础主段继承否决

- 实验编号：`r203-zjsy-i08-x-same-page-primary`。唯一假设是 `ZJSY:I08-X` 的同一数据库编码页是否存在可按已证实“同机场、同跑道、同页”条件继承的基础主进近。只读取 r187 与 r43 的精确来源缓存；禁止参考成品、Fenix、OCR 或跨页/跨跑道推断。
- `iap-primary-source-audit` 新增通用 `same_page_iap_labels` 输出：对每一份精确匹配数据库编码页列出全部 IAP 标签、跑道和主进近/过渡/复飞段计数。这是只读来源上下文，不参与投影选择。
- 实际报告为 `diagnostics/r203-all-unresolved-iap-primary-source-audit-20260819.json`。`ZJSY/I08-X` 在跑道 `08` 只有自身复飞 `4` 腿；同页 `R26` 在跑道 `26` 有过渡 `6` 腿，`R26-Y` 在跑道 `26` 有主进近 `3` 腿和复飞 `2` 腿。没有同跑道的基础主段，因此结论保持 `unresolved_direct_database_evidence_inconclusive`，不得将 `R26-Y` 或任何跑道 26 段继承给 `I08-X`。
- 回归覆盖同页标签摘要，完整 `pytest -q` 为 `419 passed`。本轮未改变模型、IAP 投影、候选或参考 `0/29` 字节状态；后续不得重试 `ZJSY:I08-X` 的跨跑道/跨标签继承，除非出现新的同周期直接来源页。

## 2026-08-19 r204 权威项目状态、进度统计与后续执行计划

本节是默认通用数据转换器的当前维护入口，优先于本文件更早的状态、进度估算和“下一步”描述。历史章节保留为实验和证据索引，不得直接替代当前判断。每次继续前，Codex 必须重新读取本节，并实际核对 Git、冻结模型、有效候选报告、收敛审计、来源缺口卡和本轮测试结果；若它们冲突，以本轮可复跑产物和标准 JSON 重读为准，并在同一轮同步修正本节及工作区根 `AGENTS.md`。

### 1. 当前真实状态

- 仓库为 `fenix_to_default_navdata`，公开远端为 `JCH2333/defult_navdata_converter`。截至 2026-08-19，`main` 比 `origin/main` 本地领先 `16` 个提交，工作树干净。普通推送此前因 `127.0.0.1:7897` 未监听而失败；网络恢复后只允许普通 `git push` 和 `git ls-remote --heads origin main`，禁止强推。
- 内容来源严格限定为 `424源数据\2608\2608` 的 CSV/PDF 与受审计的本地证据缓存。官方 `navigraph-nav-base`、`navigraph-nav-jepp` 仅提供全球基线与加载契约；`Default navdata 2608R1` 仅作最终只读文件级差分；Fenix、参考 BGL/SQLite、参考坐标或参考记录均不得成为内容输入。
- 冻结中间模型为 `output\intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。它是当前默认 BGL 适配器和未来其他目标格式适配器的唯一内容边界。
- 最近有效候选为 r188 与 r189。两者均为 `status=candidate`、`local_contract_verified=true`、`deployable=false`；r190 的只读收敛审计确认候选重复构建的最终范围为 `29/29` SHA-256 一致。
- 参考范围严格为两个中国覆盖包中的 `29` 个文件：`1` 个航路 BGL、`10` 个区域机场 BGL、`10` 个机场补丁 BGL、`2` 个索引、`2` 个布局、`2` 个清单、`2` 个 ContentHistory。文件集合没有缺失或额外项，但当前与 `Default navdata 2608R1` 的字节一致为 `0/29`。
- r202 已把阻断项整理为 `40/40` 张来源缺口卡：航路端点区域 `12`、全局航点区域 `5`、IAP 主进近选择 `10`、未分类程序 `13`。这表示工作队列完整，不表示问题已解决或内容已补齐。
- IAP 10 张卡中，`ZBAD:R29R` 与 `ZYTL:R10` 已由精确匹配的当前 424 数据库编码页证明“有过渡和复飞、无主进近”，必须保持显式拒绝；其余 `8` 张仍为来源不足的 `no_unique_primary`。`ZJSY:I08-X` 已否决跨跑道、跨标签继承。
- 最近全量回归为 `419 passed`。尚未覆盖 Community，尚未为当前候选创建部署备份，尚未实机验证，尚未创建正式 Release。

### 2. 进度口径与剩余工作

| 维度 | 当前进度 | 判定依据 | 剩余出口 |
| --- | --- | --- | --- |
| 输入锁定与 424 归一化 | 已建立 | 2608 CSV/PDF 来源边界、版本化 `NavModel`、r187 冻结模型 | 新 AIRAC 按同一清单重新锁定并重放 |
| 证据与拒绝管线 | 已建立 | PDF 缓存、来源审计、40 张缺口卡、IAP 直接页审计 | 每张可变更卡必须取得唯一直接来源或永久保守拒绝 |
| 默认目标构建链 | 已建立 | 官方双基线、ASCII 暂存、Package Tool、CLI、GUI、更新检查 | 补齐可解释的来源对象投影和目标表达契约 |
| 候选确定性 | 已通过当前基线 | r188/r189 最终范围自重放 `29/29` | 每次有效模型或适配器变更后重新双构建 |
| 参考字节收敛 | 未开始达标 | 参考一致 `0/29` | 干净输入双构建后参考一致 `29/29` |
| 部署与实机验收 | 未开始 | `deployable=false`，无备份、无覆盖、无飞行验证 | 通过全部字节、备份恢复和用户实机门禁 |

工程基础能力可估为约 `45%`：来源解析、中间模型、审计、构建、GUI、更新、验证和确定性收敛框架均已存在。这个数字不是上线完成度。字节验收必须单独报告为 `0/29`，部署、实机验证和正式发布均为 `0%`。剩余工作主要是高不确定性的来源闭合、SDK 表达契约取证和逐文件二进制收敛，不能按已完成代码行数线性估时。

### 3. 后续分阶段计划与关键门禁

1. **阶段 A：每轮状态基线。** 在任何新实验前记录 r 编号、唯一假设、唯一变量、允许/禁止读取的来源、输入/工具 SHA-256、预期影响的文件角色、成功条件和否决条件。先核对 `git status --short --branch`、r187 模型哈希、r188/r189 报告、最新收敛审计、来源卡和游戏进程状态。
2. **阶段 B：恢复可复跑 OCR 基础设施。** 先定位本机已有的 `llama-server.exe`，复用 `runtime-profile.json` 中已有模型、视觉投影、Vulkan、端口 `8090`、`seed=2608`、`temperature=0` 配置；不得安装替代依赖、使用 mock 或人工抄录。`ocr-skill doctor --json` 健康后，只选一页未决 IAP PDF 以完全相同配置运行两次，记录二进制/模型/视觉投影/页 SHA-256、命令、输出哈希和一致性。未通过门禁的 OCR 只可诊断，不能进入投影。
3. **阶段 C：按来源卡闭合内容缺口。** 每轮只处理一张卡，优先顺序为“已存在数据库主段和明确 424 直接文本”高于“需要 OCR 消歧”的卡。IAP 固定流程为：模型中的程序分段 -> 精确 `SourceRef` PDF 直接文本 -> 受限 OCR 共识（如需要）-> 唯一、保守的归属规则 -> 正反 fixture -> 来源审计 -> 模型重放 -> 目标投影。不能唯一证明时，把拒绝理由、证据范围和禁止继承路径写回卡片，不得伪造主段、航段、图页归属、坐标或类型。
4. **阶段 D：航路、全局航点与未分类程序保持来源优先。** 航路端点和航点区域仅接受与现有 FIR/ACC、精确身份和邻接证据不冲突的当前 424 直接规则；`****`、多区域边界和冲突身份保持拒绝。`RNP-0`、`CC*-*`、`EO-*` 标签不能单独证明 SID/STAR/IAP 类型。每个新增规则都必须有最小正反 fixture、拒绝路径和可读审计计数。
5. **阶段 E：SDK 目标表达契约。** 只从来源完整、尚未否决的一类机场对象中选择一个字段或对象族，使用隔离 Package Tool 探针确认“424 字段 -> 合法 XML -> 可解释的 BGL 影响”。探针必须保留输入 XML、生成 XML、脚本、编译器/工具哈希、进程轨迹、BGL 头与节表摘要、读取器完整登记和包树哈希；不能读取参考 BGL 记录，不能直接把探针发现写入正式适配器。
6. **阶段 F：模型与候选收敛循环。** 只有来源规则和目标表达同时闭合后才改变模型或适配器。先导出新模型并执行 `model-replay-audit --fail-on-unexpected`，差异必须精确到对象身份、字段路径和哈希；通过后从同一模型独立构建两次，依次执行 `validate`、报告 JSON 标准重读、候选有效树自重放和 `file-convergence-audit`。只有自重放仍全等、文件角色影响符合假设、参考一致数增加时，才记录为字节收敛进展。
7. **阶段 G：干净环境最终验收。** 达到 `29/29` 后，重新锁定输入和工具清单，在干净隔离输出中至少构建两次；复核 424 来源、模型、候选报告、包树、每个最终文件 SHA-256、布局/元数据和完整验证。任何单项失败都回到对应的来源卡或目标契约阶段，不得以复制或过滤参考产物通过验收。
8. **阶段 H：部署、恢复演练与实机测试。** 仅在阶段 G 全部通过后，确认 `FlightSimulator2024.exe` 完全退出；为两个 Community 覆盖包、`layout.json`、`manifest.json`、ContentHistory 和相关元数据创建带时间戳及 SHA-256 的备份，并先完成恢复演练。随后覆盖 `F:\games\community\Community`，由用户依次验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只能标为测试版，禁止正式 Release。

### 4. 可复用 424 转换管线

所有后续 AIRAC 和目标格式必须沿用以下边界，不得把当前默认 BGL 的专有规则回写到来源层：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 保存 AIRAC、CSV/PDF、官方目标模板、SDK/读取器、缓存、工具版本和 SHA-256 清单。
- `ingest-424` 与 `evidence-audit` 只处理当前 424 及可回链 `SourceRef` 的证据，所有降级和拒绝必须结构化输出。
- `normalize-model` 与 `model-audit` 产出版本化 `NavModel`，保留原始精度、单位、来源、规则版本与不可表达项；新适配器只能消费模型，不得重复解析已冻结输入。
- `project-target` 为每个格式建立独立 `profile`、`adapter`、`validator`、`deployer`，明确文件/数据库契约、字段映射、单位、默认值、排序、容量、元数据、降级、最小 fixture、运行时模拟器和实机清单。
- `build-target`、`validate-target` 与 `diff-and-audit` 必须在隔离输出执行。CLI、GUI、自动更新和部署入口共用同一 profile、候选清单和 `deployable` 判定，任何界面均不得绕过来源、游戏关闭或备份门禁。
- `stage-backup-deploy` 只能消费已验收候选；备份、恢复演练、部署、实机验证和 Release 是独立状态，不得由代码测试替代。

### 5. 每轮 Codex 状态维护协议

- 只有实际状态变化才更新本节中的候选编号、模型哈希、测试数、卡片计数、`29` 文件统计、Git 领先数、部署状态和下一步；不得复制旧数字。
- 每次代码或仓库文档变更后必须运行 `pytest -q`、`git diff --check`，审查精确暂存区，提交一个可解释变更，并尝试普通 `git push`。缓存、诊断、候选、日志、数据库、备份和外部测试包不得提交。
- 每个已确认经验必须记录适用 AIRAC/目标、证据来源、触发条件、解决或拒绝方式、自动化测试和对可复用模型/适配器边界的影响。实验假设必须标注为待验证，不能升级为规则。
- 本节下一项执行任务固定为：恢复既有本地 OCR 服务的运行时，并完成一页未决 IAP 的双次一致性取证；这一步不修改 `NavModel`、BGL 投影、候选或 Community。

## 2026-08-19 r205 OCR 运行时恢复与双次语义一致性门禁

- 实验编号：`r205-ocr-runtime-zsnj-i25-repeatability`。唯一目标是恢复现有、本机可复跑的 OCR 基础设施，并验证单一未决 IAP 来源页的推理输出可重复；不检索参考成品或 Fenix，不修改 `NavModel`、IAP 覆盖决策、BGL、候选或 Community。
- 已定位并通过 `scripts\start_local_ocr_server.ps1` 启动既有 `F:\AI项目\ocr\llama.cpp\llama-server.exe`。运行时固定为 llama `b10331`、模型 `deepseek-ocr-2-q8_0.gguf`、视觉投影 `mmproj-deepseek-ocr-2-q8_0.gguf`、`seed=2608`、`temperature=0`、`127.0.0.1:8090`；启动器生成并验证完整 `runtime-profile.json`。`ocr-skill doctor --json` 已确认 `OCR_BACKEND=llamacpp` 且 `/health` 正常。
- 新增只读 CLI：`ocr-runtime-probe --pdf <PDF> --runtime-profile-file <runtime-profile.json> --output <JSON>`。它固定 `OCR_BACKEND=llamacpp`，至少两次调用 `ocr-skill extract`，记录 PDF、OCR 程序和运行时画像 SHA-256，以及原始 stdout/stderr 与无文本语义摘要哈希；固定声明 `read_only=true`、`ocr_text_written=false`、`model_mutated=false`、`projection_changed=false`。报告永不保存 OCR Markdown 或包装 `content` 文本。
- Windows 上 `ocr-skill` 的管道 JSON 使用本机 `cp936` 编码，而不是 UTF-8；探针因此采用 UTF-8 优先、本机首选编码回退。随机 `content` nonce 和 `elapsed_ms` 会改变原始 stdout SHA-256，不能误判为识别不一致；语义比较只包含协议状态、后端、错误状态、文档分页字段和 Markdown SHA-256。自动化测试：`test_ocr_runtime_probe_compares_markdown_not_wrapped_content`、`test_ocr_runtime_probe_accepts_local_console_json_encoding`、`test_ocr_runtime_probe_writes_read_only_report`。
- 实际输入为 `Terminal/ZSNJ/ZSNJ-4P.pdf`，PDF SHA-256 为 `9dbc1378476911e587d4b8d5c1053e2e9ba46ded6d197acc1cdc9235db0c78ce`。报告 `diagnostics\r205-ocr-runtime-zsnj-i25-20260819\probe.json` 的两次运行均 `exit_code=0`、`backend=llamacpp`、`ok=true`，语义 SHA-256 均为 `ffbb28f40de0b500aaa2de0693897481d2aaa51dcc2433a5f5c78edde59eb708`，`repeatable=true`；两份原始 stdout 哈希不同，符合 nonce/耗时差异预期。
- 本轮全量 `pytest -q` 为 `422 passed`。它只恢复了 OCR 运行时和可复跑的门禁，不解除 `ZSNJ:I25` 的 `no_unique_primary`，不创建 OCR 缓存共识，不允许投影或构建新候选；参考字节状态仍为 `0/29`、`deployable=false`。
- 下一轮只可选择一张来源卡，优先检查该卡是否属于已有主进近的 `ambiguous_chart`/`no_matching_chart`，再按受限 OCR 缓存、至少三份独立一致缓存、角色审计、唯一规则、正反 fixture、模型门禁和双构建收敛推进。对 `no_unique_primary` 组，OCR 不得创造数据库中不存在的主进近。

## 2026-08-19 r206 IAP OCR 队列与 ZSNJ/I25 候选图页边界

- 实验编号：`r206-iap-ocr-eligibility-plan`。只读调用 `iap-ocr-cache --dry-run`，使用 r205 已验证运行时描述、`llamacpp-direct`、`ocr` 模式、3 倍 `autocontrast-grayscale`、`max_tokens=4096`；不运行 OCR、不创建缓存、不修改模型、投影、候选或 Community。
- 输出 `diagnostics\r206-iap-ocr-eligibility-plan-20260819\iap-ocr-cache-dry-run.json` 显示：在未加载既有 OCR 角色共识的来源模型中，可由 OCR 收集原始图页证据的任务仅有两份 PDF：`Terminal/ZWKN/ZWKN-5B.pdf` 与 `Terminal/ZWKN/ZWKN-9D.pdf`，均属于同一组 `ZWKN/R30-Y` 的 `ambiguous_chart`；没有新的 `no_matching_chart` 任务。
- `ZWKN/R30-Y` 已在 r65 由三份独立、受限 `llamacpp-direct` 缓存严格共识放行并投影。因此本轮不重复生成同一证据，不把“可执行 OCR”误作“需要新增内容”。这项审计只证明当前 OCR 队列没有遗漏新的可消歧来源卡。
- 对未决 `ZSNJ/I25`，只读结构化 `Terminal/ZSNJ/Charts.csv` 与受审计图页元数据确认同一跑道 25 存在两张 ILS 候选图：`ZSNJ-5G.pdf`（`RNAV ILS/DME z RWY25`，SHA-256 `5014e49ad1e51fdd59de14fb22341510f6862759feb7b160f1eca76946a9853c`）和 `ZSNJ-5H.pdf`（`ILS/DME y RWY25`，SHA-256 `78a5fdeaffab06ae6077bd1dd442d7f96abd7a7eb3724be40b9e108b016dd72b`）。数据库编码页 `ZSNJ-4P.pdf` 只给出复飞，模型没有主进近段。
- 候选图页存在不等于可映射。当前 424 结构化索引没有把 `I25` 唯一关联到 `5G` 或 `5H`，且没有模型主段可与图页角色相交；因此 `ZSNJ:I25` 必须继续保持 `no_unique_primary`。OCR 即使识别出图上固定点，也不得创造主进近或替代图页归属规则。下一步只有在当前 424 直接来源能够唯一证明数据库标签、主进近段与其中一张图的对应关系时，才可新增狭义规则和正反 fixture。

## 2026-08-19 r207 权威项目状态、进度统计与字节收敛计划

本节是默认通用数据转换器的唯一当前维护入口，优先于本文件及工作区根 `AGENTS.md` 中更早的默认通用数据状态、测试数、Git 领先数和“下一步”描述。历史章节只保留为可复核的实验索引。每次继续前，Codex 必须实际重查 Git、冻结模型 SHA-256、有效候选报告、收敛审计、来源缺口卡、OCR 运行时和游戏进程；发生冲突时，以本轮可复跑产物和标准 JSON 重读为准，并在同一轮同步更新两份 `AGENTS.md`。

### 1. 2026-08-19 已核验状态

- 仓库为 `fenix_to_default_navdata`，公开远端为 `https://github.com/JCH2333/defult_navdata_converter`。本轮盘点时工作树干净，`main` 比 `origin/main` 领先 `19` 个本地提交。`127.0.0.1:7897` 未监听，普通 `git ls-remote --heads origin main` 与 `git push` 均因代理连接失败；保留本地提交，网络恢复后只允许普通推送和远端 SHA 核对，禁止强推。
- 内容来源仍严格限定为 `424源数据\2608\2608` 的当期 CSV/PDF 和可回链、受审计的本地证据缓存。`navigraph-nav-base`、`navigraph-nav-jepp` 只提供全球基线和目标加载契约；`Default navdata 2608R1` 只用于只读的最终文件级比较；禁止 Fenix、参考 BGL/SQLite、参考坐标、参考记录或人工转录成为内容输入。
- 当前冻结的跨格式内容快照是 `output\intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。它是默认 BGL 适配器及未来其他目标格式适配器唯一可消费的内容边界；任何新适配器不得重新解析已冻结的 424，也不得读取 Fenix 或参考成品补值。
- 最近两个有效候选为 `r188` 与 `r189`。两者均为 `status=candidate`、`local_contract_verified=true`、`byte_equal_reference=false`、`deployable=false`。r190 只读收敛审计确认候选有效范围重复构建为 `29/29` 个文件 SHA-256 一致。
- 参考比较范围完整且固定：主覆盖包 `15` 个文件、机场补丁包 `14` 个文件，共 `29` 个文件；缺失和额外均为 `0`，与 `Default navdata 2608R1` 的 SHA-256 一致仍为 `0/29`。文件角色为航路 BGL `1`、区域机场 BGL `10`、机场补丁 BGL `10`、索引 `2`、布局 `2`、清单 `2`、ContentHistory `2`。
- 来源缺口工作队列已完成分类 `40/40`：航路端点区域 `12`、全局航点区域 `5`、IAP 主进近 `10`、未分类程序 `13`。其中 IAP 已有 `2` 张精确拒绝卡（`ZBAD:R29R`、`ZYTL:R10` 均是“有过渡和复飞、无主进近”），其余 `8` 张保持 `no_unique_primary`；`ZJSY:I08-X` 已否决跨跑道、跨标签继承。分类完成不等于内容闭合，更不等于参考字节收敛。
- OCR 运行时已经恢复并可复跑：`llama-server.exe` 在 `127.0.0.1:8090`，固定 llama `b10331`、DeepSeek-OCR-2、`seed=2608`、`temperature=0`。r205 对 `ZSNJ-4P.pdf` 两次识别的语义摘要 SHA-256 一致；r206 证明当前新增 OCR 队列只有已被 r65 三缓存共识处理过的 `ZWKN/R30-Y` 两页，不能为了“继续 OCR”而重复生成相同证据。
- 最近全量自动化回归为 `422 passed`。未覆盖 `F:\games\community\Community`，未创建当前候选的部署备份，未实机验证，未创建正式 Release。

### 2. 进度统计与正确口径

| 维度 | 当前状态 | 可量化证据 | 阶段出口 |
| --- | --- | --- | --- |
| 输入锁定与 424 归一化 | 已建立 | 当期 CSV/PDF 来源边界、`NavModel`、r187 SHA-256 | 新 AIRAC 可重新生成同类输入与模型清单 |
| 证据审计与保守拒绝 | 已建立 | PDF/OCR 审计、`40/40` 缺口卡、显式拒绝原因 | 每项变更都可回链到唯一 424 直接来源或明确拒绝 |
| 默认 BGL 构建管线 | 已建立 | profile、CLI/GUI、ASCII 暂存、Package Tool、验证器 | 每个来源对象都具有已证实的 SDK 投影契约 |
| 候选确定性 | 当前基线已通过 | r188/r189 有效范围 `29/29` 自重放一致 | 任一模型或适配器变更后仍需重新双构建 |
| 参考字节收敛 | 未达标 | 参考一致 `0/29` | 干净输入双构建后与参考 `29/29` SHA-256 一致 |
| 部署、实机与发布 | 未开始 | `deployable=false`、无备份、无实机结果 | 字节验收、恢复演练和用户实机清单全部通过 |

- 工程基础能力约为 `45%`：来源解析、统一模型、审计、构建、GUI、更新检查、验证和确定性框架已经具备。
- 参考字节验收进度必须单独表述为 `0/29`，而不是把候选自重放 `29/29`、测试 `422 passed` 或 SDK 冒烟视为已收敛。
- 最终上线验收进度为 `0%`。剩余部分包含高不确定性的来源闭合、目标 SDK 表达取证、二进制收敛、备份恢复演练和实机验证，不能按代码行数或已完成实验数线性估算。

### 3. 后续详细计划与关键门禁

1. **阶段 A：每轮建立不可变基线。** 分配连续 r 编号，只写一个假设和一个变量；记录允许/禁止来源、输入/缓存/工具 SHA-256、预期影响的文件角色、成功条件和否决条件。开始前核对 Git、r187、r188/r189、r190、缺口卡、OCR 健康状态和 `FlightSimulator2024.exe` 状态。
2. **阶段 B：按单张来源卡闭合，而非按机场或按 OCR 批量推进。** 优先选择可由当前 424 直接资料唯一证明的卡。IAP 顺序固定为：数据库主段和标签 -> 精确 `SourceRef` PDF 直接文本 -> 必要时的受限 OCR 三次独立一致 -> 唯一保守归属 -> 正反 fixture -> 来源审计。缺少任意环节即记录拒绝，不得创建程序、航段、坐标、类型、主段或图页归属。
3. **阶段 C：维持已否决路径。** `ZBAD:R29R`、`ZYTL:R10` 不得因其他图页或 OCR 推翻“无主段”结论；`ZJSY:I08-X` 不得继承跑道 26；`ZSNJ:I25` 不得在没有唯一标签、主段、图页三者关联时使用 `5G/5H`；多区域航路端点、`****`、冲突 FIR/ACC 和 `RNP-0`/`CC*-*`/`EO-*` 标签继续拒绝，除非出现新的同周期直接来源。
4. **阶段 D：仅做来源完整、未否决的单变量 SDK 探针。** 不重复已否决的跑道表面、阈值位移、机场关联 VOR/NDB、空域通信、`onlyAddIfReplace`、根节点终端航点、等待航线隔离、简单 `CODE_DIR` 反转或无来源 `routeType` 猜测。新探针必须保留源/生成 XML、脚本、输入与工具哈希、Package Tool 轨迹、BGL 头和节表、读取器完整登记、包树 SHA-256 与结论；探针结果不能直接写入正式适配器。
5. **阶段 E：规则接入前先封闭模型变化。** 每项来源规则先补充最小正反 fixture、拒绝路径和审计字段，再导出新的版本化模型。必须运行 `model-replay-audit --fail-on-unexpected`；允许差异只可列出精确对象身份、字段路径和两侧 SHA-256。出现未允许差异时停止，不构建候选。
6. **阶段 F：每次有效规则只走一次完整候选收敛循环。** 从同一冻结模型、同一官方双基线、同一工具版本独立构建两次，依次执行 `validate`、报告 JSON 标准重读、有效文件树自重放和只读 `file-convergence-audit`。报告本轮改变的文件角色及其是否符合假设；只有“候选仍自重放一致 + 影响范围正确 + 参考一致文件数增加”才记为字节收敛进展。若仍为 `0/29`，只记录否决或无效假设，不扩大规则。
7. **阶段 G：对编译器与参考生成契约设置可证伪检查点。** 在每轮文件级差分中区分“424 内容投影差异”“SDK XML/编译布局差异”“索引/布局/元数据差异”。若来源已闭合而同一 SDK 仍无法生成任何参考同字节文件，必须先通过合法、只读的 SDK 探针定位缺失的生成契约；不得以复制、筛选、拼接或反向读取参考文件获得 `29/29`。
8. **阶段 H：最终干净验收。** 只有达到参考 `29/29` 后，才重新锁定输入、缓存和工具清单，在全新隔离输出中至少双构建一次；复核模型、报告、布局、元数据、全部最终 SHA-256 和完整验证。任一失败均返回对应来源卡或 SDK 契约阶段。
9. **阶段 I：备份、部署、恢复演练与用户实机。** 阶段 H 通过后才确认 `FlightSimulator2024.exe` 已完全退出，为两个 Community 覆盖包及 `layout.json`、`manifest.json`、ContentHistory 创建带时间戳和 SHA-256 的完整备份，并完成一次恢复演练。随后才覆盖 `F:\games\community\Community`。用户实机依次验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。实机完成前只能标记为测试版，禁止正式 Release。

### 4. 可复用的 424 到任意目标格式管线

固定主链为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 必须产物 | 可复用边界 |
| --- | --- | --- |
| `lock-inputs` | AIRAC、CSV/PDF、模板、SDK/读取器、缓存和工具 SHA-256 清单 | 新周期先锁定再解析，不能混入旧周期 |
| `ingest-424` | 原始精度、单位、`SourceRef`、解析拒绝和结构化错误 | 只读当期 424；OCR 只作为受限消歧证据 |
| `evidence-audit` | 每条补充/拒绝规则的来源、条件、反例和审计报告 | 不读取参考导航记录或 Fenix 内容 |
| `normalize-model` | 版本化 `NavModel`、规则版本、不可表达项和来源字段 | 唯一跨 AIRAC、跨格式内容边界 |
| `model-audit` | 模型哈希、精确差异白名单、重放报告 | 变化必须可解释、可重复、可回退 |
| `project-target` | 独立 `profile`、`adapter`、字段/单位/默认值/排序/容量/降级规则 | 目标专有规则不得回写来源解析器 |
| `build-target` | 隔离构建目录、确定性输出、工具轨迹 | GUI、CLI 和更新入口共用同一实现 |
| `validate-target` | 结构、引用、运行时模拟器、目标专用 fixture 和元数据报告 | 通过不等于参考字节一致或实机通过 |
| `diff-and-audit` | 文件角色、SHA-256、语义计数和来源卡影响 | 参考仅为只读判据，不得反向补值 |
| `stage-backup-deploy` | 备份、恢复演练、部署记录、实机清单 | 仅消费 `deployable=true` 的最终候选 |

新目标格式必须新增独立 `profile/adapter/validator/deployer`，并在首次开发前记录官方可用基线、真实加载契约、schema 或文件格式、字段限制、NULL/default、排序、元数据、降级策略、最小 fixture、运行时模拟器和实机清单。Fenix 解析器只能保留为其自身目标的历史适配器，不得作为默认通用数据或其他 424 目标的内容来源。

### 5. 每轮 Codex 维护协议

- 每轮结束必须更新：r 编号、唯一假设和变量、输入/工具哈希、允许/禁止来源、变更的模型/适配器/测试、候选状态、候选自重放、参考 `x/29`、卡片状态、部署状态、Git 状态和下一项单一任务。
- 只有实际改变的指标才更新；不得复制旧 Git 领先数、测试数、模型哈希或进度百分比。没有参考一致数提升时，明确写“字节收敛未推进”。
- 每次代码或仓库文档变更后必须运行 `pytest -q`、`git diff --check`，审查精确暂存区，完成一个可解释的本地提交，并尝试普通 `git push`。诊断、缓存、候选、日志、数据库、备份和外部测试包必须保持忽略。
- 下一项工作固定为：不重跑既有 `ZWKN/R30-Y` OCR 组；从剩余 `8` 张 `no_unique_primary` IAP 卡、`12` 条航路端点、`5` 个航点区域或 `13` 条未分类程序中，选择一张有新的同周期直接来源可能性的单卡，先完成只读来源审计。若没有新直接来源，则记录拒绝理由并转到另一张卡，不修改模型或候选。

## 2026-08-19 r208 ZYDD/R01 同页关联标签无主进近审计

- 实验编号：`r208-zydd-r01-related-same-page-primary-source-audit`。唯一假设是：当同一机场、同一跑道、同一精确数据库编码页中的无后缀基础标签和单字母 `W/X/Y/Z` 变体合计只包含进近过渡和复飞，且冻结模型和该页均不存在主进近时，两条相关卡都可被明确拒绝；该结论不得把过渡或复飞拼接为主进近。
- 允许读取 r187 冻结模型及 r43 中与 `SourceRef` 精确匹配的数据库编码页缓存；禁止读取参考 BGL/SQLite/坐标、Fenix、IAP 图页 OCR 结果或人工转录。实现位于 `iap_primary_source_audit.py`：只接受严格形如 `R01-Y` 的“跑道身份加单个 W/X/Y/Z”标签族，要求相同跑道、至少两个相关标签、模型主段为零、直接页关联标签主段为零、并且关联页合计同时存在过渡和复飞。复合后缀、不相关标签、跨跑道、跨页或任一主段存在时不命中。
- 新处置为 `rejected_related_same_page_sections_without_primary`，只影响来源审计和缺口卡，不改变 `NavModel`、IAP 投影、BGL、候选或 Community。正反回归：`test_audit_rejects_related_same_page_base_and_variant_without_primary`、`test_audit_keeps_related_same_page_labels_unresolved_when_primary_exists`、`test_gap_cards_bind_related_same_page_primary_rejection`。
- 实际命令使用 r201 已记录的 9 个 r43 精确缓存重跑 `iap-primary-source-audit`，报告为 `diagnostics\r208-zydd-related-label-primary-source-audit-20260819.json`，并生成绑定卡片 `diagnostics\r208-default-gap-cards-20260819.json`。`ZYDD-0C-2.pdf`（SHA-256 `0f21ec38cd9cc0187f8722ad9b69ef1511cdf45b32c5d25867759da00fe4981e`）中 `R01` 有 `6` 条过渡、`R01-Y` 有 `3` 条复飞，当前页主进近为 `0`。但 r187 在另一页 `ZYDD-0C-4.pdf` 中含 `R01-Z` 主进近；它属于同一严格标签族，因此模型族主段计数为 `1`，r208 假设不成立。
- 结论是 `ZYDD:R01` 与 `ZYDD:R01-Y` 继续为 `unresolved_direct_database_evidence_inconclusive`，不得借用跨页、不同变体 `R01-Z` 的主段。审计总计仍为“明确拒绝 `2`、继续来源不足 `8`”，参考一致仍为 `0/29`、`deployable=false`。本轮只验证并固化了“任何关联标签族已有主段时不得误判为全族无主段”的防护边界，没有推进候选或字节收敛。

## 2026-08-19 r209 ZSOF/R15 图标题候选与缺失主段边界

- 实验编号：`r209-zsof-r15-chart-title-source-audit`。唯一假设是：当数据库标签对应的精确页没有主进近时，同机场同跑道的进近图标题是否能给出与该标签相同的直接身份；即使有标题命中，也不得由标题、IAF/IF 角色或坐标反向创造主进近。
- `iap-primary-source-audit` 新增只读字段 `instrument_chart_title_candidates`。它仅枚举同机场、同跑道 `instrument-approach-index` 图页、标题直接解析出的候选标签、来源页和是否精确命中数据库标签；不读取参考成品或 Fenix，不修改模型和投影。回归：`test_audit_reports_title_match_without_creating_missing_primary` 明确覆盖“标题可命中但无主段时仍不得放行”。
- 实际 r187 中 `ZSOF:R15` 只有 `4` 段进近过渡、无主进近和复飞；其精确数据库页 `ZSOF-4M.pdf`（SHA-256 `0f7bd7cb344f0738d51a6b537629ecf2ae53027112f0c1cdfd5f3ac7d8feb1fc`）有 `13` 条进近过渡、无主进近和复飞。图页候选为 `ZSOF-5A.pdf` 的 `I15/I15-Z`、`ZSOF-5B.pdf` 的 `I15/I15-Y`、`ZSOF-6A.pdf` 的 `D15`，精确 `R15` 标题命中数为 `0`。
- 报告为 `diagnostics\r209-zsof-r15-chart-title-source-audit-20260819.json`，绑定卡片为 `diagnostics\r209-default-gap-cards-20260819.json`。结论：`ZSOF:R15` 保持 `unresolved_direct_database_evidence_inconclusive`；不得根据相同跑道、候选 IAF/IF、RNAV ILS、ILS 或 VOR 图标题拼出 `R15` 主进近。模型、候选和 Community 均未改变；参考一致仍为 `0/29`、`deployable=false`。

## 2026-08-19 r210 包元数据是派生输出而非独立收敛目标

- r210 只读核对 r188 候选与 `Default navdata 2608R1` 的包级 `manifest.json`、`layout.json`、ContentHistory 和 r190 文件收敛看板；不读取参考 BGL/SQLite/坐标或任何导航记录，不修改模型、适配器、候选或 Community。
- 主覆盖包 `manifest.json` 的依赖、兼容版本、包名、标题、构建器和顺序提示字段已与参考一致；`total_package_size` 不一致（候选 `10916053`，参考 `47584567`），它是 Package Tool 对最终包树的派生大小，不能作为来源字段或独立修复目标。
- r190 已证明两个包的 `layout.json`、`bglIndex.bout`、ContentHistory 和 `manifest.json` 均属于同一 `29` 文件收敛范围；其中布局和大小字段依赖 BGL、索引及内容历史。手写总大小、布局日期、索引或 ContentHistory 既不能生成正确 BGL，也会使派生元数据与实际文件树不一致，禁止作为取得 SHA-256 的手段。
- 结论：后续先闭合 424 来源投影和 SDK BGL 表达契约，再由正常构建链重生成包元数据；不得把包元数据作为独立字节收敛任务。当前参考一致仍为 `0/29`、候选自重放 `29/29`、`deployable=false`。

## 2026-08-19 r211 权威项目状态、进度口径与后续计划

本节优先于本文件中更早的默认通用数据进度描述。每次继续工作前，Codex 必须重新核对本节、工作区根目录 `AGENTS.md`、`git status --short --branch`、冻结模型 SHA-256、最近两个有效候选的 `conversion-report.json`、最近的 `file-convergence-audit` 与本轮诊断。文档与可复跑产物冲突时，以可复跑命令、候选报告、测试和 Git 提交为准，并在同一轮同步修正两份 `AGENTS.md`。

### 1. 当前事实与独立进度

- 仓库为公开 `https://github.com/JCH2333/defult_navdata_converter`，当前分支 `main` 比 `origin/main` 领先 `23` 个本地提交。普通推送此前因 `127.0.0.1:7897` 未监听而失败；网络恢复后仅执行普通 `git push` 和 `git ls-remote --heads origin main`，禁止强推。
- 冻结内容模型为 `output\intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。内容只能来自当期 `424源数据\2608\2608` 的 CSV/PDF 及带来源哈希的受控证据缓存；`navigraph-nav-base`/`navigraph-nav-jepp` 只作全球基线与加载契约，`Default navdata 2608R1` 只作只读比较。Fenix、参考 BGL/SQLite、参考坐标和参考导航记录禁止作为内容输入。
- 有效候选是 r188/r189：`status=candidate`、`test_build=true`、`local_contract_verified=true`、`deployable=false`。同一冻结模型的两次独立构建在参考范围有效树内自重放一致 `29/29`；与参考中国覆盖包的 SHA-256 一致数仍为 `0/29`。这说明构建确定性已建立，不说明内容、BGL 契约、游戏加载或发布已完成。
- 当前工程能力可粗略估计为 `45%`：424 解析、`NavModel`、证据审计、CLI/GUI、Package Tool ASCII 暂存、目标验证、候选双构建和文件收敛看板已具备。字节级验收进度单独记为 `0/29`，上线验收进度为 `0%`；三项指标不得合并或相互替代。
- r211 全量 IAP 标题候选审计保持 10 张卡：明确拒绝 `2` 张（`ZBAD:R29R`、`ZYTL:R10`，均为“过渡/复飞存在但无主进近”），来源不足 `8` 张。10 张卡的冻结模型主进近和精确数据库编码页主进近均为 `0`。`ZJSY:I08-X` 只有一张直接标题命中图 `ZJSY-5L-3.pdf`，但标题命中不能创建缺失主段，当前仍不得投影。
- 尚未覆盖 `F:\games\community\Community`，未为当前候选创建部署备份，未进行实机验证，未创建正式 Release。

### 2. 已确认经验与硬边界

1. `NavModel` 是跨 AIRAC、跨目标格式的唯一内容边界。新目标只能消费版本化模型快照；不得重解析已冻结 424、读取 Fenix，或把 OCR 缓存和参考成品当作内容数据库。
2. OCR 是受控消歧证据，不是数据生成器。只有在已有数据库主进近、已有精确 PDF 归属、页面 SHA-256 和多次独立结果一致时，才可消歧既有角色；不得用 OCR 创建程序、主段、航段、坐标、类型或图页归属。
3. 参考包只用于只读验收。逐文件收敛看板只能保存路径、角色、大小、哈希和 BGL 摘要，且必须保持 `read_only=true`、`reference_records_exported=false`；禁止复制、筛选、拼接或反向填写参考内容。
4. `manifest.json`、`layout.json`、`bglIndex.bout`、ContentHistory 和包大小均是 BGL 与包树的派生输出，不得单独手写修复。任何此类差异必须回溯到来源投影或 SDK 编译契约。
5. 每个可接入正式适配器的规则都必须有直接来源、最小正例、最小反例、审计字段和明确拒绝路径。不能唯一证明时保留拒绝；减少未决数量不是成功指标。
6. 读取器日志只有完整登记所有请求 BGL 后才可用于语义判断。既有已否决方向（跑道表面、阈值位移、机场关联 VOR/NDB、空域通信、`onlyAddIfReplace`、根终端点重复、等待航线隔离和无来源 route type 猜测）不得重复作为正式适配器方向。

### 3. 接下来的执行顺序与阶段出口

1. **阶段 A：冻结基线与单卡队列。** 每轮分配连续 `rNNN`，记录唯一假设、唯一变量、允许/禁止来源、模型/工具哈希、预期受影响的文件角色、成功指标和否决条件。优先从 8 张来源不足 IAP 卡中选择一张；先处理 `ZJSY:I08-X` 的只读页面角色审计，验证其直接标题命中是否能在“不创建主段”的边界内产生新事实。不能唯一闭合即记录拒绝，转下一卡，不修改模型。
2. **阶段 B：关闭可证明的 424 缺口。** IAP 按“已有模型主段 -> 精确 SourceRef PDF -> 必要时受控 OCR -> 唯一保守规则 -> 来源审计 -> 正反 fixture -> BGL 投影”执行。并行工作队列仅限：12 条航路端点区域、5 个全局航点区域、13 条未分类程序。只允许使用当期 CSV/PDF、FIR/ACC、受控邻接和已审计 OCR；多地区、身份冲突、`****` 和无直接类型证据保持拒绝。
3. **阶段 C：SDK 表达契约取证。** 只对来源完整且尚未否决的一个 SDK 子对象做一次隔离探针。保留输入 XML、脚本、源/工具 SHA-256、Package Tool 轨迹、完整包树、BGL 头/节表和读取器完整登记。探针结论先进入诊断与 fixture，不直接写进正式适配器。
4. **阶段 D：规则接入与模型门禁。** 规则通过来源审计后，先补测试和审计字段，导出新的版本化模型，再执行 `model-replay-audit --fail-on-unexpected`。允许差异必须精确列出对象身份、字段路径和两侧 SHA-256；有任何未允许差异即停止，不构建候选。
5. **阶段 E：候选收敛循环。** 对通过模型门禁的规则，从同一冻结模型、同一官方双基线和同一工具版本独立构建两次；依次执行 `validate`、报告 JSON 标准重读、有效树自重放、`file-convergence-audit`。只有“自重放仍为 `29/29` + 受影响文件角色符合假设 + 参考一致文件数增加”同时成立，才记录为字节收敛进展。仍为 `0/29` 的实验只能记录为否决或未收敛，不扩大规则。
6. **阶段 F：按文件角色定位剩余差异。** 分别追踪 1 个航路 BGL、10 个区域机场 BGL、10 个机场补丁 BGL、2 个索引、2 个布局、2 个清单和 2 个 ContentHistory。先解决来源投影和 SDK BGL 契约，后让正常构建链重生派生包文件；禁止为了哈希单独改元数据。
7. **阶段 G：最终干净验收与部署。** 仅当参考 `29/29`、全新隔离输出双构建一致、完整验证和来源审计通过时，才检查 `FlightSimulator2024.exe` 已退出，为两个 Community 覆盖包及元数据创建带时间戳 SHA-256 备份并完成一次恢复演练。随后才覆盖 Community，交由用户验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。实机通过前仅可标记测试版，禁止正式 Release。

### 4. 可复用的 424 转换管线

固定主链为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

- `lock-inputs` 输出 AIRAC、源文件、模板、SDK、OCR/解析器和工具 SHA-256 清单；新周期必须重新锁定，禁止混用旧周期证据。
- `ingest-424` 保留原始精度、单位、`SourceRef`、解析失败和结构化拒绝；`evidence-audit` 单独保存 PDF/OCR 证据及其运行指纹，不直接产出导航内容。
- `normalize-model` 输出可序列化、可重放、可差分的 `NavModel`；`model-audit` 验证身份、引用、区域、程序、航路连通性和拒绝计数。
- 每个目标格式建立独立 `profile/adapter/validator/deployer`，负责目标 schema、单位、NULL/default、排序、容量、元数据、运行时契约、降级策略、最小 fixture 和实机清单；禁止把目标专有分支写回 `source.py`。
- GUI、CLI、自动更新和部署必须共用同一 profile、候选报告和 `deployable` 门禁。任何入口都不得绕过 `stage-backup-deploy` 直接写入 Community。

### 5. Codex 每轮维护协议

- 开始前记录：r 编号、唯一假设/变量、输入和工具哈希、允许/禁止来源、预期文件角色、成功和否决指标。
- 结束后更新：诊断或候选路径、模型 SHA-256、代码/文档提交、测试、SDK/读取器结果、JSON 重读、候选自重放、参考 `x/29`、缺口卡状态、部署状态和下一项唯一任务。没有提升参考一致数时必须明确写“字节收敛未推进”。
- 代码或仓库文档变更后必须运行 `pytest -q`、`git diff --check`、精确检查暂存区、创建单一主题提交并尝试普通 `git push`。数据库、备份、日志、诊断、候选、SDK 中间产物、外部测试包和生成导航包继续保持在 Git 之外。

## 2026-08-19 r212 ZJSY/I08-X 标题候选直接角色审计

- 实验编号：`r212-zjsy-title-direct-role-audit`。唯一假设是：当未决 IAP 的唯一同跑道标题命中图具有 424 PDF 直接角色时，审计应可复用地记录角色及其与已有模型主进近腿的身份交集；角色本身不得生成或补写主进近。
- 允许读取 r187 冻结 `NavModel`、图页已解析的 `ChartRouteFix` 和 r43 精确数据库编码页缓存；禁止读取参考 BGL/SQLite/坐标、Fenix、人工转录或新增 OCR。`iap_primary_source_audit.py` 的 `instrument_chart_title_candidates` 现输出稳定排序的 `direct_route_roles` 和 `primary_leg_role_overlap`。后者只报告已存在的同标签、同跑道 `approach` 腿标识交集，永远不创建航段或改变投影。
- 最小回归 `test_audit_reports_title_match_without_creating_missing_primary` 覆盖标题命中图含 `IAF`/`IF` 直接角色时，仍保持 `approach=0`、交集为空和 `projection_allowed=false`。定向回归：`3 passed, 52 deselected`。
- 真实命令用 r187 与 r211 的 9 份精确缓存重跑 `iap-primary-source-audit`，报告为 `diagnostics\r212-zjsy-title-direct-role-audit-20260819.json`。`ZJSY:I08-X` 的唯一标题命中 `ZJSY-5L-3.pdf`（SHA-256 `637310e313614e12dbcad7c8d87915cbde476677d1f769aa594b627b845bd1ec`）直接角色为 `SY461/IF`、`SY462/IAF`、`SY935/IAF`；冻结模型和精确数据库页主进近均为 `0`，`primary_leg_role_overlap=[]`，处置继续为 `unresolved_direct_database_evidence_inconclusive`。
- 结论：图页角色提供了可复用的来源审计信息，但缺失主进近的前提没有闭合，不得从 `SY462` 等既有复飞腿、图标题或同跑道图拼接主进近。模型、BGL、候选和 Community 未改变；参考一致仍为 `0/29`、`deployable=false`，字节收敛未推进。下一项工作从其余 7 张来源不足 IAP 卡、航路/航点区域或未分类程序中选择一张有新直接来源可能性的单卡。

## 2026-08-19 r213 权威状态、进度看板与可复用收敛计划

本节自 r213 起优先于本文件此前默认通用数据的“当前状态”“后续任务”和进度估算。历史章节保留为可复核的实验记录，不得替代当前决策。每次继续前，Codex 必须重新核对本节、工作区根 `AGENTS.md`、`git status --short --branch`、冻结模型哈希、r188/r189 候选报告、最近收敛审计、本轮诊断和本轮测试；文字与可复跑产物冲突时，以实际产物为准，并在同一轮同步两份 `AGENTS.md`。

### 1. 当前已核验状态

- 公开仓库为 `https://github.com/JCH2333/defult_navdata_converter`。截至本轮检查，`main` 比 `origin/main` 领先 `25` 个本地提交。此前普通推送因 `127.0.0.1:7897` 未监听失败；网络恢复后只允许执行普通 `git push` 与 `git ls-remote --heads origin main`，禁止强推、改写历史或为了同步而丢弃本地提交。
- 冻结内容模型仍为 `output\intermediate-2608-r187-navaid-label-replay.json.gz`，SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。任何影响内容的规则在接入前必须从此基线或新的显式版本化模型开始，先通过模型重放门禁。
- 最新有效候选仍为 r188/r189。它们在相同冻结模型、官方双基线和受控构建环境中有效树自重放 `29/29`，本地 `validate` 通过，状态为 `candidate`、`test_build=true`、`local_contract_verified=true`、`deployable=false`。与 `Default navdata 2608R1` 的两个中国覆盖包比较，SHA-256 一致仍为 `0/29`。
- 当前全量回归为 `428 passed`。这只证明代码回归通过，不证明 424 内容闭合、SDK 运行时加载、参考字节一致、部署或实机结果。
- 当前未覆盖 `F:\games\community\Community`，未为 r188/r189 创建部署备份，未进行用户实机验证，未创建正式 Release。任何候选均不得绕过 `deployable=false` 写入 Community。
- r213 正在进行“机场关联进近扇区频率”来源作用域审计。当前未提交实现和测试必须保留，但尚未完成：初版只读取 `AIRSPACE_RADIO.csv`，而当期该表只有表头；真实频率位于 `CONTROLLED_RADIO.csv`。因此现有 `diagnostics\r213-app-sector-radio-scope-audit-20260819.json` 的零记录结果无效，不能作为来源结论、不能提交为完成实验、不能影响模型或候选。

### 2. 分层进度统计

不得把工程能力、字节验收和上线验收合并为一个百分比。当前统计如下：

| 维度 | 当前状态 | 量化依据 | 进入下一阶段的硬门禁 |
| --- | --- | --- | --- |
| 输入与来源边界 | 已建立 | 2608 CSV/PDF、模板、参考比较和 Fenix 隔离边界已锁定 | 每个新增规则都要有同周期直接来源与哈希 |
| 规范化与可重放模型 | 已建立 | 版本化 `NavModel`、来源引用、模型 I/O 与 r187 冻结快照 | 模型变更通过精确 `model-replay-audit` |
| 默认目标适配器 | 已建立但未内容闭合 | BGL profile、CLI/GUI、Package Tool、验证器、ASCII 暂存 | 每个投影对象均有来源和 SDK 契约 |
| 来源缺口队列 | 已分类，持续处理 | 航路端点区域 `12`、全局航点区域 `5`、IAP 主进近 `10`、未分类程序 `13`，共 `40`；IAP 已明确拒绝 `2`、来源不足 `8` | 只处理可唯一证明的单卡；无法证明则永久保守拒绝 |
| 构建确定性 | 已建立 | r188/r189 候选有效树自重放 `29/29` | 每个有效模型变更后仍须双构建复核 |
| 参考字节验收 | 未达标 | 参考文件一致 `0/29` | 全新隔离双构建后达到 `29/29` SHA-256 一致 |
| 部署、实机和发布 | 未开始 | `deployable=false`，没有部署备份或飞行验证 | 字节验收、备份恢复演练和用户实机清单全部通过 |

工程基础能力可粗略估为约 `45%`，仅表示转换管线已具备可持续研究与验证的能力。剩余工作集中在来源闭合、SDK 表达契约与逐文件二进制收敛，具有高不确定性；不得据此推算上线日期，更不得把候选自重放 `29/29` 说成参考字节完成 `29/29`。

### 3. 已确认经验与禁止回退项

1. 内容来源严格限定为当期 `424源数据\2608\2608` 的 CSV/PDF 与带来源哈希、运行指纹的受控证据缓存。官方 `navigraph-nav-base`/`navigraph-nav-jepp` 只提供全球基线和加载契约；`Default navdata 2608R1` 只作只读比较；Fenix、参考 BGL/SQLite、参考坐标和参考导航记录不得作为内容输入。
2. `NavModel` 是唯一跨 AIRAC、跨目标格式的内容边界。目标 adapter 只能投影模型，不能重新解析冻结 424、读取 Fenix 或把 OCR 缓存当作导航数据。
3. OCR 只能在已有主进近、精确 `SourceRef` 页归属和可重放一致性均成立时消歧已有角色；不能创建程序、主段、航段、坐标、类型或图页归属。标题命中、同跑道、过渡或复飞都不能反向补造主进近。
4. `manifest.json`、`layout.json`、`bglIndex.bout`、ContentHistory 和包大小是 BGL 与包树的派生产物。禁止手写、复制或独立追逐这些文件的参考哈希；必须先解释来源投影和 SDK 编译契约。
5. 机场关联进近扇区频率属于空域/跑道方向关系，不等同于机场 `Com`/`Tower`。r213 必须先合并 `AIRSPACE_RADIO.csv`、`CONTROLLED_RADIO.csv`、`RESTRICTED_RADIO.csv`、`SPECIAL_AIRSPACE_RADIO.csv` 并以“来源文件 + RADIO_ID”建立唯一身份，才可形成可复用的拒绝审计；即使审计确认关联，也不得投影为默认机场通信对象。
6. 已否决方向不得重复包装为正式规则：跑道表面、阈值位移、机场关联 VOR/NDB、空域通信、`onlyAddIfReplace`、根终端点重复、等待航线隔离、无来源 `routeType` 猜测，以及任何未完整登记 BGL 的读取器结论。

### 4. 接下来的详细执行计划与关键节点

1. **P0：完成 r213 的结构化拒绝审计。** 修正未提交实现，使其读取全部四类无线电表、保留 `source_file`、以 `source_file + RADIO_ID` 去重，并记录每个示例的空域、机场、跑道方向、频率类型、频率、扇区和来源表。补充 `CONTROLLED_RADIO.csv` fixture。真实报告必须是 `read_only=true`、`reference_records_read=false`、非零关联数，并明确 `rejected_by_scope_and_cardinality`。该步骤只产生可复用来源库存，不修改 `NavModel`、BGL、候选或 Community。
2. **P1：以来源缺口卡为唯一内容工作队列。** 每轮只选择一张卡和一个假设，先产出直接来源、反例、唯一规则和拒绝理由。IAP 按“已有主段 -> 精确数据库页 -> 受控 OCR（仅必要时）-> 角色唯一性 -> 正反 fixture”推进；航路/航点区域按“直接 FIR/ACC/服务机场/受控邻接”推进；未分类程序必须取得明确类型证据。没有新直接证据即保留拒绝，不以减少卡片数为目标。
3. **P2：建立目标表达证据，而不是猜测 BGL。** 仅对来源完整、未被否决的一个 SDK 子对象做隔离单变量探针。每个探针必须保存源 XML、变体 XML、输入和工具哈希、命令、Package Tool 进程轨迹、包树 SHA-256、BGL 头/节表、读取器完整登记和可证伪结论。探针先变成 fixture 和诊断能力，不能直接接入 adapter。
4. **P3：规则接入与模型重放门禁。** 只有 P1 与 P2 同时闭合时，才修改来源解析、模型或 adapter。先新增最小正反测试和审计字段，导出新版本模型，运行 `model-replay-audit --fail-on-unexpected`。允许差异必须逐项列出对象身份、字段路径、来源、预期文件角色和两侧哈希；发现未预期差异即停止，不构建候选。
5. **P4：候选双构建与逐文件收敛。** 从同一模型、同一官方双基线、同一 SDK 和同一 ASCII 暂存策略独立构建两次，依次执行 `validate`、标准 JSON 重读、有效树自重放和只读 `file-convergence-audit`。将 29 个文件按航路 BGL、区域机场 BGL、机场补丁 BGL、索引、布局、清单和 ContentHistory 分组。只有“候选自重放仍为 `29/29` + 影响文件角色符合假设 + 参考一致数增加”同时成立，才可记录“字节收敛推进”。
6. **P5：编译器/参考契约检查点。** 若来源卡已无可接入规则，而参考一致持续为 `0/29`，暂停扩大内容规则，转为只读、合法的 SDK 契约探针，区分“424 内容未投影”“XML/SDK 表达差异”“包派生元数据差异”。此检查点的目的是真实定位阻塞条件，不允许读取或复制参考导航记录来伪造一致。
7. **P6：最终干净验收。** 仅在参考达到 `29/29` 后，从已锁定的 CSV/PDF、证据缓存、模型、profile 和工具清单在全新隔离目录至少双构建一次，复核全部报告 JSON、模型/包树哈希、验证结果与来源审计。任一失败返回对应 P1-P5，不进入部署。
8. **P7：备份、恢复、部署和实机。** P6 通过后检查 `FlightSimulator2024.exe` 已退出；为两个 Community 覆盖包及全部元数据建立带时间戳、SHA-256 的备份，先完成恢复演练，再覆盖 `F:\games\community\Community`。用户依次验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。全部通过前只能标记测试版，禁止正式 Release。

### 5. 面向未来 AIRAC 与目标格式的可复用工作管线

固定主链为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 强制产物 | 对未来工作的复用方式 |
| --- | --- | --- |
| `lock-inputs` | AIRAC、CSV/PDF、模板、SDK、证据运行时和工具哈希清单 | 新周期只替换输入清单，不混入旧周期文件 |
| `ingest-424` | 原始精度、单位、`SourceRef`、解析拒绝、结构化错误 | 所有目标复用相同来源事实 |
| `evidence-audit` | 来源卡、直接证据、反例、OCR 运行指纹、拒绝结论 | 把无法投影的事实保留为可审计降级，而非静默丢弃 |
| `normalize-model` | 版本化 `NavModel`、来源字段、引用、不可表达计数 | 是所有目标 adapter 的唯一输入 |
| `model-audit` | 模型哈希、重放差异白名单、完整性和覆盖统计 | 防止新格式反复修改来源解析而产生漂移 |
| `project-target` | 独立 `profile/adapter`、字段/单位/默认值/排序/容量/降级 | 新格式只增加目标层，不把规则回写 424 层 |
| `build-target` | 隔离输出、确定性构建、工具轨迹、输入 manifest | GUI、CLI、自动更新统一调用同一构建入口 |
| `validate-target` | 结构/引用/运行时模拟器/fixture/元数据报告 | 目标专用验证，不以通用 schema 代替加载契约 |
| `diff-and-audit` | 文件角色、哈希、语义计数、影响范围和来源卡关联 | 参考只作验收，不反向导入内容 |
| `stage-backup-deploy` | 备份、恢复演练、部署记录、实机清单 | 只允许消费 `deployable=true` 的最终候选 |

新目标格式开始前必须先在其 profile 文档登记官方可用基线、真实加载路径与契约、文件/schema、字段和单位限制、NULL/default、物理排序、元数据、不可表达项降级、最小 fixture、运行时模拟器和实机清单。未来应把 r213 这类“来源存在但目标无安全投影”的库存保留在通用证据层，供其他目标格式决定是否可表达，而不是为当前 BGL 适配器强行造字段。

### 6. Codex 状态维护与提交协议

- 每轮开始前写明连续 `rNNN`、唯一假设、唯一变量、允许/禁止来源、输入/工具哈希、预期影响文件角色、成功指标和否决条件。
- 每轮结束必须从实际命令输出更新：测试数、模型哈希、候选状态、候选自重放、参考 `x/29`、缺口卡计数、Git 领先数、部署状态、已确认经验和下一项唯一任务。没有参考一致数提升时必须写“字节收敛未推进”，不得复制历史数字。
- 对只读审计、SDK 探针、模型规则和候选构建分别提交，避免把诊断结论、内容变更和部署逻辑混入一个提交。数据库、备份、日志、诊断、候选、SDK 中间产物和外部测试包继续保持忽略。
- 每次代码或仓库文档变更后必须运行 `pytest -q`、`git diff --check`，检查精确暂存区，创建单一主题本地提交，并尝试普通 `git push`。网络失败时保留本地提交并记录失败原因；代理恢复后再普通推送，不得强推。
- r213 的下一项唯一任务固定为：修正无线电多表合并和跨表无线电身份，生成非零、只读的真实作用域审计；在该审计完成前，不启动模型变更、候选构建、部署或其他 SDK 探针。

## 2026-08-19 r213 进近扇区频率来源作用域审计

- 实验编号：`r213-app-sector-radio-scope-audit`。唯一假设是：当 424 的空域无线电可经 `APPSECTOR_RUNWAYDIRECTION` 和 `AD_HP` 关联到机场时，审计必须保留这一关系以供未来目标格式复用，同时依据其真实作用域明确拒绝默认 BGL 的 `Com`/`Tower` 投影。
- 实现将 `AIRSPACE_RADIO.csv`、`CONTROLLED_RADIO.csv`、`RESTRICTED_RADIO.csv`、`SPECIAL_AIRSPACE_RADIO.csv` 统一读取；每行携带 `source_file`，无线电身份严格为 `source_file + RADIO_ID`，避免不同表内同名 ID 被错误合并。报告样例同时记录空域、机场、跑道方向、频率、扇区和来源表。自动化回归 `test_inventory_rejects_airport_linked_approach_sector_radios` 覆盖实际使用的 `CONTROLLED_RADIO.csv` 以及跨表同名 `RADIO_ID` 的隔离。
- 真实命令使用 r187 冻结模型和 r188 的候选 XML 生成 `diagnostics\r213-app-sector-radio-scope-audit-20260819.json`。当期 `AIRSPACE_RADIO.csv`、`RESTRICTED_RADIO.csv`、`SPECIAL_AIRSPACE_RADIO.csv` 均只有表头；`CONTROLLED_RADIO.csv` 有 `1461` 条。审计得到 `854` 条扇区-机场跑道方向关联、`316` 个跨表隔离后的无线电记录、`24` 个机场、`264` 个关联多个跑道方向的无线电记录、`0` 个关联多个机场的无线电记录。
- 结论：这些记录的频率类型和扇区均属于进近空域语义；即使可间接关联一个机场，它们也不是机场台站设施，且大量记录服务多个跑道方向。因此处置为 `rejected_by_scope_and_cardinality`，仅作为通用证据层库存保留，不能投影为默认 BGL `Com`/`Tower`。本轮未修改 `NavModel`、BGL adapter、候选或 Community；参考字节一致仍为 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：从 `12` 条航路端点区域、`5` 个全局航点区域、`8` 张来源不足 IAP 卡或 `13` 条未分类程序中选择一张存在新同周期直接来源可能性的卡，先做只读来源审计；不得因 r213 的结构化库存启动机场通信投影或候选构建。

## 2026-08-19 r214 权威状态、字节收敛路线与可复用管线计划

本节自 r214 起优先于本文件全部更早的“当前状态”“下一步”和进度数字。历史 r213 初版“尚未完成”的描述已过期：提交 `8554280`、真实报告和 `428 passed` 已证明 r213 完成。每次继续前必须重查本节、工作区根 `AGENTS.md`、Git、冻结模型、候选报告、收敛审计、最新诊断、测试及游戏进程；文字与可复跑产物冲突时，以实际产物为准，并同步两份协作说明。

### 1. 实际状态与进度口径

| 轨道 | 当前状态 | 可量化证据 | 阶段出口 |
| --- | --- | --- | --- |
| 输入、来源与证据层 | 已建立 | 只允许 2608 CSV/PDF 与带来源哈希/运行指纹的受控缓存；r213 无线电库存已明确拒绝当前投影 | 每条规则有同周期直接来源、反例和拒绝路径 |
| 跨格式模型 | 已建立 | r187 `NavModel` SHA-256 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b` | 模型变更通过 `model-replay-audit --fail-on-unexpected` |
| 默认 BGL 适配器 | 已建立但未闭合 | CLI/GUI、ASCII 暂存、Package Tool、验证器和部署门禁已具备 | 每个投影对象同时有来源与 SDK 契约 |
| 候选确定性 | 已通过当前基线 | r188/r189 有效文件树自重放 `29/29` | 每个变更后重新双构建 |
| 参考字节验收 | 未达标 | 固定比较范围 `29` 文件，参考一致 `0/29` | 全新隔离双构建均为 `29/29` |
| 部署、实机、Release | 未开始 | `deployable=false`，无部署备份、实机或 Release | 字节验收、恢复演练和实机清单全通过 |

- 工程能力约 `45%`，只代表可复用的解析、模型、证据、GUI/CLI、构建、验证与确定性框架；字节验收为 `0/29`，部署/实机/正式发布均为 `0%`，三者不得与测试或候选自重放混用。
- r213 已完成：`CONTROLLED_RADIO.csv` 的 `1461` 条记录得到 `854` 条扇区-机场跑道方向关联、`316` 个 `source_file + RADIO_ID` 隔离身份、`24` 个机场、`264` 个多跑道方向关联；处置为 `rejected_by_scope_and_cardinality`，不得投影为 BGL `Com`/`Tower`，只保留为未来目标格式的通用证据库存。

### 2. 已确认阻塞与禁止路径

1. r190 已证明候选包树稳定但参考一致仍 `0/29`。候选机场 BGL 通常只有 `0x3/0x13/0x22/0x32/0x34/0x35`，参考普遍另有大型 `0x17`、`0x33` 节；航路 BGL 仍少约 `43,820` 字节。节表差异仅是定位线索，不是对象类型映射证据。
2. 禁止根据参考 BGL/SQLite/坐标/记录/BGL payload/哈希反填模型、XML 或包元数据。`Default navdata 2608R1` 只读比较；官方 `nav-base`/`nav-jepp` 只提供全球基线和加载契约；Fenix 绝不进入内容链。
3. `layout.json`、`manifest.json`、`bglIndex.bout`、ContentHistory 和包大小均是 BGL/包树派生产物，禁止单独手写或复制。
4. OCR 仅能消歧已有主进近及精确 `SourceRef` 图页归属，不能创建主进近、程序、航段、坐标、类型或归属。标题命中、同跑道、过渡和复飞不能补造主段。
5. 已否决的跑道表面、阈值位移、机场关联 VOR/NDB、空域通信、`onlyAddIfReplace`、根终端点重复、等待航线隔离及无来源 `routeType` 猜测不得重复包装为规则，除非存在新的独立同周期来源和单变量 SDK 证据。

### 3. 接下来的工作计划与门禁

1. **r214：机场 BGL 节表基数审计。** 实现可复用 `airport-bgl-cardinality-audit`，只读 r187 模型区域来源计数、候选/参考 BGL 头及节表。逐文件输出节类型、计数、大小、存在性差异，以及模型的机场、跑道方向、终端点、ILS、程序段、等待航线计数；标记 `read_only=true`、`reference_records_exported=false`，不读取 BGL payload，不把 `0x17/0x33` 命名为任何对象。以最小伪 BGL fixture 覆盖参考有/候选无的汇总和来源计数关联。此轮不改模型或候选。
2. **单卡来源闭合。** 在 `12` 条航路端点区域、`5` 个全局航点区域、`8` 张来源不足 IAP、`13` 条未分类程序中，每轮只选一张有新同周期直接来源可能性的卡。先形成直接来源、反例、唯一规则和拒绝理由；没有唯一证据则保持拒绝。
3. **单变量 SDK 契约探针。** 只对来源完整、未被否决的对象建立隔离探针，保留 XML/变体、源与工具 SHA-256、命令、Package Tool 轨迹、包树 SHA-256、BGL 头/节表、读取器完整登记和可证伪结论。探针先成为诊断和 fixture，不能直接写入 adapter。
4. **规则接入与模型门禁。** 来源规则和 SDK 表达同时闭合后才可改解析、模型或 adapter。先补最小正反测试与审计字段，导出版本化模型，再运行重放门禁；允许差异必须列出对象身份、字段路径、来源、预期文件角色及两侧哈希，出现未预期差异即停止构建。
5. **双构建收敛循环。** 同一模型、官方双基线、SDK 和 ASCII 暂存策略独立构建两次，再执行 `validate`、JSON 重读、有效树自重放、`file-convergence-audit` 与节表审计。只有自重放 `29/29`、影响范围正确、参考一致数增加三项同时满足，才称“字节收敛推进”；否则明确写“字节收敛未推进”。
6. **编译契约检查点。** 若来源卡无可接入规则且参考仍为 `0/29`，暂停扩大内容投影，利用 r214 看板和合法 SDK 探针区分 424 内容缺口、XML/SDK 表达差异与派生元数据差异；不得以参考内容填补。
7. **最终部署与实机。** 仅在参考 `29/29` 后重新锁定输入/工具清单、全新隔离双构建并完整验证；确认 `FlightSimulator2024.exe` 已退出，为两个 Community 覆盖包及元数据创建带 SHA-256 的时间戳备份并完成恢复演练，才可覆盖 Community。用户按 `ZBCF`、`ZUNZ`、`ZUUU` 验证机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器；实机前只能测试版。

### 4. 未来 AIRAC 和目标格式的可复用管线

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 强制产物 | 复用边界 |
| --- | --- | --- |
| `lock-inputs` | AIRAC、CSV/PDF、模板、SDK、运行时、缓存 SHA-256 清单 | 新周期重新锁定，禁止混用 |
| `ingest-424` | 原始精度、单位、`SourceRef`、错误与拒绝 | 只读 424，证据层不直接产出内容 |
| `evidence-audit` | 来源卡、反例、OCR/探针指纹、拒绝结论 | 参考只作验收，不反向取数 |
| `normalize-model` | 版本化 `NavModel`、来源、引用、不可表达计数 | 唯一跨 AIRAC、跨目标内容边界 |
| `model-audit` | 模型哈希、重放和精确差异白名单 | 防止目标规则污染来源层 |
| `project-target` | 独立 profile/adapter、字段、单位、默认值、排序、容量、降级 | 目标专有规则不得回写 `source.py` |
| `build-target` | 隔离输出、确定性构建、工具轨迹、输入 manifest | GUI、CLI、更新和部署共用入口 |
| `validate-target` | 结构、引用、运行时模拟器、fixture、元数据报告 | 通过不等于字节或实机通过 |
| `diff-and-audit` | 文件角色、SHA-256、节表、语义计数、卡片影响 | 允许定位，不允许反向补值 |
| `stage-backup-deploy` | 备份、恢复演练、部署记录、实机清单 | 只消费 `deployable=true` |

新目标格式开始前必须独立建立 `profile/adapter/validator/deployer` 文档，记录官方基线、真实加载路径/契约、文件或 schema、字段/单位/NULL/default、物理排序、元数据、不可表达项降级、最小 fixture、运行时模拟器和实机清单。未来目标只消费 `NavModel` 和通用证据库存，不得重新解析冻结 424 或读取 Fenix/参考成品补值。

### 5. Codex 状态维护与 Git 协议

- 每轮开始记录连续 `rNNN`、唯一假设和变量、允许/禁止来源、输入/工具哈希、预期影响文件角色、成功与否决条件。
- 每轮结束按实际命令输出同步两份 `AGENTS.md`：测试数、模型哈希、候选状态、自重放、参考 `x/29`、缺口卡、节表看板、部署状态、Git 领先数、经验和下一项唯一任务。历史文字冲突时追加纠正，不改写事实。
- 代码或仓库文档变更后必须运行 `pytest -q`、`git diff --check`，精确审查暂存区，提交一个可解释主题，并尝试普通 `git push`；诊断、缓存、候选、日志、数据库、备份、SDK 中间产物和外部测试包不得提交。
- 当前实际 Git：工作树干净，`main` 比 `origin/main` 领先 `27` 个提交，远端为 `JCH2333/defult_navdata_converter`。网络恢复后仅普通 `git push` 与 `git ls-remote --heads origin main`，禁止强推、重写历史或丢弃本地提交。
- r214 的唯一下一项工作是机场 BGL 节表基数审计；在完成前不得修改 `NavModel`、正式 BGL 投影、候选、Community 或部署逻辑。

## 2026-08-19 r214 机场 BGL 节表基数审计结果

- 实验编号：`r214-airport-bgl-cardinality-audit`。唯一变量是新增只读诊断 `airport-bgl-cardinality-audit`；它读取 r187 `NavModel` 的区域来源计数、候选/参考最终机场 BGL 的固定头和节表，不读取 BGL payload、参考导航记录、参考坐标或 Fenix，也不修改模型、XML、候选、Community 或部署逻辑。
- 新模块 `airport_bgl_cardinality_audit.py` 按最终参考包顶层根目录过滤候选支持包和 `_work`，按 `ZB` 至 `ZY` 区域 BGL 输出节类型、单节记录数和大小、候选/参考存在性差异，以及该区域的机场、跑道方向、终端点、ILS、程序段和等待航线来源计数。报告固定声明 `read_only=true`、`reference_records_exported=false`、`reference_payload_read=false`、`section_type_semantics_inferred=false`；节类型只能作为基数差异，不得被命名为任何对象类型。
- 真实命令使用 r187、r188 和 `Default navdata 2608R1`，输出为 `diagnostics\r214-airport-bgl-cardinality-audit-20260819.json`。范围为候选/参考各 `20` 个机场 BGL，公共文件 `20` 个；参考 `20/20` 含 `0x17`、候选 `20/20` 缺失 `0x17`；参考 `18/20` 含 `0x33`、候选 `20/20` 缺失 `0x33`；候选 `20/20` 独有 `0x35`，参考 `0/20` 含 `0x35`。例如 ZB 的来源计数为机场 `37`、跑道方向 `88`、终端点 `1402`、ILS `58`、程序段 `1254`、等待航线 `166`，但这些计数不证明任何节的语义归属。
- 自动化新增最小伪 BGL/模型 fixture，覆盖参考有 `0x17/0x33`、候选缺失、候选支持包排除、模型区域来源计数和禁止 payload/语义推断的报告门禁。全量回归为 `429 passed`。r188/r189 自重放仍为 `29/29`，参考一致仍为 `0/29`，`deployable=false`；字节收敛未推进。
- 已确认经验：当节表差异与来源对象计数同时存在时，二者只能构成下一步 SDK 探针的量化输入，不能证明映射关系。后续探针必须从单个、来源完整且未否决的 SDK 对象出发，验证其是否同时解释节类型、作用域和记录数量；无法满足三者时不得接入 adapter。
- 下一项唯一任务：基于 r214 看板选择一个尚未否决、具备同周期直接来源的机场 SDK 子对象，先设计单变量隔离探针，要求结果能同时报告对象作用域、节表变化和记录基数。不得重试已否决的跑道表面、阈值位移、机场关联 VOR/NDB、空域通信、根终端点重复或等待航线隔离；在探针结论前不得修改正式投影。

## 2026-08-19 r215 ZUAL DeleteAirport 覆盖表达探针

- 实验编号：`r215-zual-deleteairport-overlay-contract`。唯一变量是保留或移除 `ZUAL` 的 `<DeleteAirport deleteAllApproaches="TRUE" deleteAllDepartures="TRUE" deleteAllArrivals="TRUE"/>`。两组均从 r188 冻结 `china-navdata.xml` 选择同一 ZUAL，均移除根级 `AiracCycle`、`Vor`、`Ndb` 以避免根对象污染，均保留同一份 424 来源机场、跑道、ILS、终端点、SID、STAR、IAP 和等待航线；不读取参考 BGL/SQLite/坐标/Fenix，不改模型或正式候选。
- 生成 XML 的结构核对证明变量唯一：控制组输入为 `45,795` 字节、SHA-256 `a9bb052587ea1884ff6749ec01baba224be0ef1a13f3cff13b8145c6cdb7ee82`，变体为 `45,693` 字节、SHA-256 `630c5999a37bfc8e9b5a7248509f132062dfff0451b5749ffa4fc3cb4efa2bfb`；除 `DeleteAirport` 外，两组均为 1 条跑道、81 个终端点、1 个 ILS、2 条离场、2 条进场、3 条进近和 4 条等待航线。
- Package Tool 两次均按已确认异步契约启动并等待新的 `FlightSimulator2024.exe` 退出后产出完整包；工具前台返回 `1`，但两组都有成功包产物、无新增 BuilderLog 错误、完整 BGL 和读取器登记，因此以产物判定构建成功。控制组 BGL 为 `23,559` 字节、SHA-256 `c0a7fb20f89abc85fc32369dc5cf51ac8daac3d55560519050732cbaddc11fa9`；移除组为 `23,547` 字节、SHA-256 `3e68ac9d013583e2de7bca312e7f5a638be91a37c745eb76ed7e2dcbb694ff7a`。
- 两组节表均为 `0x3/0x13/0x22/0x32/0x34/0x35`，记录基数均为 `1/1/10/1/1/1`；读取器均完整登记 1 个 BGL，并读取 81 个航点、1 个 ILS，其他目标表为零。删除语义仅改变二进制负载 12 字节，未改变节类型、节表基数或读取器可见对象，不能解释 r214 中参考机场 BGL 缺失的 `0x17/0x33`。
- 结论：`DeleteAirport` 是正式覆盖加载策略所需的目标表达，不是机场节表基数缺口的来源；保持现有适配器的程序删除行为，不得为了追逐哈希移除它。r188/r189 自重放仍 `29/29`，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。诊断目录为 `diagnostics\r215-zual-deleteairport-retained-20260819` 与 `diagnostics\r215-zual-deleteairport-removed-20260819`，不得提交。
- 下一项唯一任务：机场来源完整且尚未单独验证的对象已被 r177/r194/r195/r213/r215 逐项排除或证伪；停止扩大机场子对象探针，转入航路 `00_enroute.bgl` 的来源闭合与 SDK 表达差异，先从 `12` 条航路端点区域和 `5` 个全局航点区域的拒绝卡中选择一项能够取得新同周期直接来源的对象。无新来源时保留拒绝，禁止从 r214 节表、参考内容或 Fenix 推断补值。

## 2026-08-19 r216 航路 BGL 节表基数审计

- 实验编号：`r216-enroute-bgl-cardinality-audit`。新增只读 `enroute-bgl-cardinality-audit`，只读取 r187 模型的 VOR/NDB、全局航点、航路段、区域未决、航路证据和拒绝记录计数，以及候选/参考最终 `00_enroute.bgl` 的固定头和节表；不读取 reference payload、导航记录、坐标或 Fenix，不修改模型、XML、候选或 Community。
- 真实报告 `diagnostics\r216-enroute-bgl-cardinality-audit-20260819.json` 覆盖候选/参考各 1 个最终航路 BGL。节类型、版本、QMID、`0x20` magvar 网格及 `0x32/0x33/0x34` 均一致；候选相对参考的节表差异只有 `0x13` 记录数 `119/131`（`-12`，大小 `-192`）、`0x17` `92/96`（`-4`，`-64`）、`0x22` `875/1294`（`-419`，`-6,704`）。BGL 总大小仍为 `2,867,006/2,910,826`，差 `-43,820` 字节。
- 同轮模型来源规模为 VOR `361`、NDB `77`、全局航点 `2741`、航路段 `4446`，其中端点区域完整 `4394`、仍未决 `52`；另有 `138` 条航路导航台证据、0 条可投影的最低高度证据，以及 `434` 条 GeneralDoc 航点拒绝和 1 条 VOR 拒绝。上述计数只用于来源卡优先级，不证明任何节类型与对象类型的映射。
- 自动化新增最小航路 BGL fixture，覆盖同节类型而记录数/大小不同、模型来源规模、模型哈希和严格只读报告边界。定向回归通过；完整回归、提交前检查仍需在本轮结束前执行。r188/r189 自重放仍 `29/29`，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：以 r216 中仍未决的 `52` 条航路端点区域为入口，先对一张来源卡执行只读直接来源复核，优先验证是否存在此前未使用的同周期 FIR/ACC/服务机场或邻接证据；若仍为多地区、身份冲突或 `****`，必须记录拒绝并转到下一张卡，不得依据 `0x13/0x17/0x22` 差值、参考内容或 Fenix 补值。

## 2026-08-19 r217 权威项目状态、进度统计与字节收敛执行计划

本节优先于本文件中更早的默认通用数据状态、百分比、测试数和下一步描述。每次继续前必须核对本节、工作区根 `AGENTS.md`、`git status --short --branch`、冻结模型 SHA-256、r188/r189 的 `conversion-report.json`、最新 `file-convergence-audit`、最新节表审计、当前诊断及游戏进程。历史文字与可复跑产物冲突时，以实际命令、报告、测试和 Git 提交为准，并在同一轮同步两份 `AGENTS.md`。

### 1. 截至 r217 的已核验状态

| 轨道 | 状态 | 量化证据 | 完成出口 |
| --- | --- | --- | --- |
| 输入锁定与来源边界 | 已建立 | 只读 `2608` 424 CSV/PDF；官方 `nav-base`/`nav-jepp` 仅为基线和加载契约；参考成品仅比较 | 每次新 AIRAC 重新锁定文件、工具和证据哈希 |
| 规范化模型与可复用管线 | 已建立，内容缺口未闭合 | r187 `NavModel` SHA-256 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b` | 每条新规则通过来源审计和模型重放门禁 |
| 默认通用数据适配器 | 已建立，SDK 表达契约未闭合 | CLI/GUI、ASCII 暂存、Package Tool、验证器、部署门禁和 BGL/包审计可运行 | 每个正式投影对象同时具备来源证明和单变量 SDK 证据 |
| 候选确定性 | 已通过当前冻结模型 | r188/r189 有效树独立自重放 `29/29`，`local_contract_verified=true` | 后续任何模型或适配器改动均须重新双构建 |
| 参考字节验收 | 未推进 | 固定范围 `29` 个文件，参考 SHA-256 一致 `0/29` | 全新隔离的两次构建均达到 `29/29` |
| 部署、实机与 Release | 未开始 | `deployable=false`；未覆盖 Community、未创建当前候选部署备份、未实机、未 Release | 字节验收、恢复演练和实机清单全部通过 |

- 当前全量自动化回归为 `430 passed`。这只证明代码和已知约束的回归，不证明字节一致、游戏加载或可部署。
- 工程能力估算为约 `45%`：解析、证据层、模型、GUI/CLI、构建、验证、候选确定性与审计基础设施已具备。字节级验收为 `0/29`，部署/实机/正式发布均为 `0%`；三类数字必须分开报告。
- r216 已将航路 BGL 的未闭合部分量化：候选/参考 `00_enroute.bgl` 的 `0x13` 差 `-12`、`0x17` 差 `-4`、`0x22` 差 `-419`，总大小差 `-43,820` 字节；这些只是定位指标，绝不构成对象映射或补值依据。
- 已分类的内容来源缺口为 `40` 张卡：航路端点区域 `12`、全局航点区域 `5`、IAP 主段 `10`、未分类程序 `13`。航路端点 `12` 张卡在模型中对应 `52` 条未决端点区域；IAP 已有 `2` 张由同页直接来源明确拒绝，其余 `8` 张仍为来源不足。分类完成不等于可以投影。
- 当前本地提交包含 `052e1f2`（r216）；远端同步情况必须以本轮实际 `git status --short --branch` 和普通 `git push` 的结果为准。代理未监听时保留本地提交，提示用户检查 `http://127.0.0.1:7897`，禁止强推或重写历史。

### 2. 已确认经验和禁止路径

1. `NavModel` 是唯一跨 AIRAC、跨目标格式的内容边界。其他目标只消费版本化模型和通用证据库存；不得重新解析冻结模型，也不得读取 Fenix、参考 BGL、参考 SQLite、参考坐标或参考导航记录补写内容。
2. 424 CSV/PDF 是内容来源；OCR 仅是带页面 SHA-256、渲染参数、模型指纹和重复运行一致性的消歧证据。OCR、标题、同跑道、过渡或复飞均不能创造缺失的程序主段、航段、坐标、类型或图页归属。
3. 节表、文件大小、SHA-256、`layout.json`、`manifest.json`、`bglIndex.bout` 和 ContentHistory 是诊断或派生产物。它们可以定位差异，不能反向解释目标对象或作为单独手写修复目标。
4. 已否决的跑道表面、阈值位移、机场关联 VOR/NDB、空域通信投影、`onlyAddIfReplace`、根终端点重复、等待航线隔离、`DeleteAirport` 删除和无来源 `routeType` 猜测不得重复尝试；只有新的独立同周期来源加单变量 SDK 证据才能重新立项。
5. 任何候选仅在同时满足“模型重放无未允许差异、双构建自重放 `29/29`、影响文件角色符合假设、参考一致数增加”时，才可称为字节收敛推进。其余结果必须明确写“字节收敛未推进”。

### 3. 后续工作分阶段计划

1. **阶段 A：每轮基线和单卡选择。**
   每个 `rNNN` 仅定义一个假设和一个变量，记录输入/工具哈希、允许/禁止来源、预期对象和文件角色、成功指标、拒绝条件。优先从 40 张缺口卡中选择一张；航路端点卡必须进一步锁定到一条精确端点身份，不能把 52 条记录合并为一项实验。

2. **阶段 B：只读来源闭合。**
   对单卡按“当期 CSV -> 同期 PDF -> 显式 FIR/ACC -> 有服务机场的身份 -> 已验证邻接”顺序复核。每个可接入规则必须同时拥有直接来源、最小正例、最小反例、审计字段和拒绝路径。多地区、身份冲突、`****`、缺坐标或无唯一类型证据保持拒绝；只读审计不改模型、不构建候选。

3. **阶段 C：单变量 SDK 契约取证。**
   仅在来源完整、未被既有实验否决的对象上建立隔离 Package Tool 探针。每个探针保存输入 XML、脚本、源和工具 SHA-256、命令、模拟器进程轨迹、完整包树、BGL 头/节表和读取器完整登记。探针只先生成诊断和 fixture；不能直接变为适配器规则，也不能从参考 payload 推断表达。

4. **阶段 D：规则接入和模型门禁。**
   只有同一规则同时通过来源闭合与 SDK 契约取证时，才可修改解析、模型或目标适配器。先增加正反测试和审计字段，导出新的版本化模型，运行 `model-replay-audit --fail-on-unexpected`。白名单必须逐项列出对象身份、字段路径、来源、预期文件角色和两侧模型哈希；存在任何未允许差异即停止，不进入构建。

5. **阶段 E：候选构建和字节收敛。**
   用同一模型、同一官方双基线、同一 SDK 和同一 ASCII 暂存策略独立构建两次。依次执行 `validate`、报告 JSON 标准重读、有效树自重放、`file-convergence-audit`、机场/航路节表审计。只有参考一致文件数实际增加时才保留新的收敛候选；没有增加则保留诊断、回退到规则假设，不扩大投影。

6. **阶段 F：按文件角色收敛。**
   分别追踪 `00_enroute.bgl`、20 个区域机场 BGL、机场补丁 BGL、索引、布局、清单和 ContentHistory。BGL 与来源投影/SDK 契约先闭合，索引和包元数据必须由正常构建链派生。禁止按哈希逐字节修补、复制参考文件或单独修改派生元数据。

7. **阶段 G：最终验收、备份和部署。**
   仅在参考 `29/29`、全新隔离输出双构建一致、完整验证与来源审计通过后，检查 `FlightSimulator2024.exe` 已退出。为两个 Community 覆盖包及元数据创建带 SHA-256 的时间戳备份，完成恢复演练，才允许覆盖 `F:\games\community\Community`。随后由用户验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。实机通过前只能是测试版，禁止正式 Release。

### 4. 面向未来 AIRAC 和目标格式的可复用工作管线

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 必需产物 | 复用约束 |
| --- | --- | --- |
| `lock-inputs` | AIRAC、CSV/PDF、官方模板、SDK、运行时、解析/OCR 工具和哈希清单 | 新周期必须重新锁定，禁止混用历史证据 |
| `ingest-424` | 原始精度、单位、`SourceRef`、结构化错误和拒绝 | 只读来源，不因目标格式修改原始语义 |
| `evidence-audit` | 单卡证据、正反例、OCR/SDK 运行指纹和拒绝结论 | 参考只用于验收，不反向取值 |
| `normalize-model` | 版本化、可序列化、可重放和可差分的 `NavModel` | 唯一跨格式内容边界 |
| `model-audit` | 模型哈希、引用/区域/程序检查和差异白名单 | 阻止目标特有规则污染来源层 |
| `project-target` | 独立 `profile/adapter/validator/deployer` | 明确字段、单位、NULL/default、排序、容量、元数据和降级 |
| `build-target` | 隔离输出、输入清单、工具轨迹和双构建结果 | GUI、CLI、自动更新和部署复用同一 profile 与门禁 |
| `validate-target` | 结构、引用、运行时模拟器、fixture、元数据与降级报告 | 通过不等于字节一致或实机通过 |
| `diff-and-audit` | 文件角色、哈希、节表、语义计数、影响卡 | 只能定位，禁止反向补值 |
| `stage-backup-deploy` | 时间戳备份、恢复演练、部署记录和实机清单 | 只能消费 `deployable=true` 的完整候选 |

新目标格式启动前必须创建单独的 `profile/adapter/validator/deployer` 说明，登记官方基线、实际加载路径和契约、文件/schema、字段/单位/NULL/default、物理排序、元数据、不可表达项降级、最小 fixture、运行时模拟器、GUI/CLI 接入和实机验证清单。默认通用数据适配器的任何未闭合 SDK 规则不得直接迁移给其他目标。

### 5. Codex 状态维护协议和下一项唯一任务

- 开始每轮前：检查两份 `AGENTS.md`、Git、冻结模型、有效候选、最新收敛/节表审计和游戏进程；登记连续 r 编号与单一假设。
- 结束每轮后：基于实际命令更新测试数、模型哈希、候选状态、自重放、参考 `x/29`、缺口卡、节表看板、部署状态、Git 领先数、已确认经验和下一项单一任务。没有参考增加时必须写“字节收敛未推进”。
- 代码或仓库文档变更后：运行 `pytest -q`、`git diff --check`，精确审查暂存区，提交一个主题并尝试普通 `git push`。诊断、缓存、候选、日志、数据库、备份、SDK 中间产物和外部测试包不得提交。
- r218 的唯一任务：从 r216 的 12 张航路端点区域卡中按诊断稳定排序选择一条精确端点身份，执行一次只读的同周期 FIR/ACC/服务机场/邻接证据复核。该轮只允许新增审计、fixture 或明确拒绝记录；除非取得唯一的新直接来源并通过阶段 C 证据，不得修改 `NavModel`、BGL 投影、候选、Community 或部署逻辑。

## 2026-08-19 r218 P225 航路端点直接来源复核

- 实验编号：`r218-p225-airway-endpoint-card-source-audit`。唯一假设是：稳定排序首张端点卡 `H34:3` 的精确身份 `DESIGNATED_POINT/P225` 是否能通过此前未显式复核的同周期指定点 FIR、服务机场、关联 `RTE_SEG` 端点 FIR、ACC 或邻接证据唯一恢复区域。唯一变量是新增只读 CLI `airway-endpoint-card-audit`；不修改 `NavModel`、BGL XML、候选、Community 或部署逻辑。
- 新模块按 `DESIGNATED_POINT.csv.SIGNIFICANT_POINT_ID` UUID（非仅按名称）关联 `RTE_SEG.csv.POINT_START_ID/POINT_END_ID`，输出直接指定点字段、关联航段端点 FIR、ACC 名称、能由 `AIRSPACE.csv` 明确映射的 ACC 地区，以及模型中已由 424 规则恢复的相邻地区。它固定声明 `read_only=true`、`model_changed=false`、`projection_changed=false`、`reference_records_read=false`、`fenix_records_read=false`，并记录三个输入 CSV 的 SHA-256。任何重复指定点身份、缺少 UUID 或没有精确关联航段都必须失败，不能选择性取一行。
- 真实命令以 r187 冻结模型和当前 2608 原始目录生成 `diagnostics\r218-p225-airway-endpoint-card-source-audit-20260819.json`。`P225` 的唯一指定点行为 `58`、UUID 为 `3dab1bcf-b242-415d-a649-7d70e9ec4e11`；其 `CODE_FIR`、`SERVICED_AIRPORT` 均为空。H34 的精确关联段为 `RTE_SEG.csv` 第 `4132`、`4133` 行，P225 端点 FIR 均为空；两段只给出“西安 ACC”备注，而 `AIRSPACE.csv` 不提供可直接把该 ACC 名称映射为区域键的 FIR 证据。
- 模型侧的同一精确身份仍有两个已来源化相邻地区：`P612 -> ZH` 和 `SHX -> ZL`。因此处置为 `rejected_multiple_neighbor_regions_with_blank_direct_region`，`projection_allowed=false`：不能从一个 ACC 名称、任一相邻地区或 BGL 节表选择 `ZH` 或 `ZL`。这是对 r198 “多地区邻接”拒绝的直接原始行复核，不是新模型规则。
- 自动化新增精确 UUID 关联、空直接地区加多相邻地区拒绝、重复 `CODE_ID` 身份失败和 CLI 路径回归；全量回归为 `433 passed`。r188/r189 自重放仍 `29/29`，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按剩余端点卡稳定排序复核 `H35:2` 的精确身份 `DESIGNATED_POINT/P127`。该轮仍只允许对指定点 FIR/服务机场、精确 UUID 关联航段 FIR、ACC 映射及邻接证据做只读审计；多地区或缺乏唯一直接来源时保持拒绝，不得修改模型、候选或部署状态。

## 2026-08-19 r219 P127 部分 ACC 映射拒绝

- 实验编号：`r219-p127-airway-endpoint-card-source-audit`。唯一假设是：P127 的 ACC 备注中若有部分名称可由 `AIRSPACE.csv` FIR 标题映射，是否能够在多地区邻接时唯一恢复区域。变量仅为把 `airway-endpoint-card-audit` 的 ACC 结果细化为“已映射”和“未映射”；审计规则与既有 `_restore_waypoint_countries_from_airway_acc` 门禁一致：任一 ACC 名称无法映射时，禁止恢复。
- 真实报告为 `diagnostics\r219-p127-airway-endpoint-card-source-audit-20260819.json`。`P127` 的唯一指定点行为 `505`、UUID `754c8ef2-dab0-444a-a16e-fc306b7d96b8`，自身 `CODE_FIR` 和 `SERVICED_AIRPORT` 为空。其精确关联航段是 H35 第 `60`、`61` 行和 J75 第 `342` 行，端点 FIR 均为空。
- 原始 ACC 名称为“广州、长沙、成都”；只有“广州”可由 `AIRSPACE.csv` FIR 标题映射到 `ZG`，“长沙、成都”均无可用映射。模型侧相邻地区同时为 `ZG`、`ZP`、`ZU`。因此处置为 `rejected_multiple_neighbor_regions_with_incomplete_acc_evidence`、`projection_allowed=false`；不得用部分 `ZG` 映射覆盖或选择任一邻接地区。
- 自动化新增“部分 ACC 映射加多地区边界必须拒绝”反例，并将 P225 同类未知 ACC 防护对齐该门禁；定向回归 `18 passed`，完整回归、提交前检查待本轮完成。模型、BGL、候选和 Community 未变，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序复核 `H38:2` 的精确身份 `DESIGNATED_POINT/P239`。仅复用 UUID 精确关联、FIR/服务机场、ACC 映射和邻接来源审计；无唯一直接来源不得修改 `NavModel`、BGL 投影、候选或部署状态。

## 2026-08-19 r220 P239 冲突 ACC 映射拒绝

- 实验编号：`r220-p239-airway-endpoint-card-source-audit`。唯一假设是：当所有 ACC 名称都可由 FIR 标题映射、但映射到多个地区时，是否能够结合邻接地区选择区域。变量仅为 `airway-endpoint-card-audit` 新增已映射 ACC 地区集合及冲突处置；它不改变来源恢复算法，只把已有“多 ACC 地区保持未决”门禁变为可审计输出。
- 真实报告为 `diagnostics\r220-p239-airway-endpoint-card-source-audit-20260819.json`。P239 的唯一指定点行为 `350`、UUID `3c15573d-8400-41f6-b61d-49135bfc3bc5`，自身 FIR/服务机场为空；H38 第 `2056`、`2057` 行的 P239 端点 FIR 同样为空。
- 两个 ACC 名称均可映射，但“广州 -> ZG”、“武汉 -> ZH”，映射地区集合为 `ZG/ZH`；模型侧相邻地区为 `ZH/ZP`。处置为 `rejected_multiple_neighbor_regions_with_conflicting_acc_regions`、`projection_allowed=false`。不得根据共同出现的 `ZH`、任一 ACC 或相邻地区发明唯一区域。
- 自动化新增“全部 ACC 已映射但映射地区冲突必须拒绝”反例；定向回归 `19 passed`，完整回归、提交前检查待本轮完成。模型、BGL、候选、Community 和部署状态均未变，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序复核 `J35:1` 的精确身份 `DESIGNATED_POINT/P121`。继续仅做 UUID 精确关联、FIR/服务机场、ACC 映射和邻接来源审计；未获得唯一直接来源时保持拒绝。

## 2026-08-19 r221 P121 部分 ACC 映射复核

- 实验编号：`r221-p121-airway-endpoint-card-source-audit`。P121 使用已由 r219 建立的“部分 ACC 映射”审计路径；本轮唯一变量是精确 UUID 卡 `P121`，不修改审计器、模型、BGL、候选或部署逻辑。
- 真实报告为 `diagnostics\r221-p121-airway-endpoint-card-source-audit-20260819.json`。P121 的唯一指定点行为 `1651`、UUID `7de5f462-998e-4a0d-bdc1-638e95a9f241`，自身 `CODE_FIR`、`SERVICED_AIRPORT` 和 J35 第 `2215`、`2216` 行的端点 FIR 均为空。
- ACC 名称为“广州、长沙”；“广州”唯一映射 `ZG`，“长沙”无映射。模型侧相邻地区为 `ZG/ZS`。处置保持 `rejected_multiple_neighbor_regions_with_incomplete_acc_evidence`、`projection_allowed=false`；部分 `ZG` 映射不能覆盖或替代另一侧 `ZS` 邻接。
- 本轮只复用 r219 的已通过回归，不增加投影规则；模型、BGL、候选、Community 和部署均未变，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。完整回归、提交前检查待本轮完成。
- 下一项唯一任务：按稳定排序复核 `X62:1` 的精确身份 `DESIGNATED_POINT/P188`。仅做同一只读来源卡审计；没有唯一直接来源时继续拒绝。

## 2026-08-19 r222 P188 部分 ACC 映射复核

- 实验编号：`r222-p188-airway-endpoint-card-source-audit`。P188 是最后一个存在于 `DESIGNATED_POINT.csv` 的未决端点身份；本轮复用 r219 的部分 ACC 映射门禁，只读取原始 CSV 和 r187 冻结模型，不修改代码、模型、BGL、候选或部署。
- 真实报告为 `diagnostics\r222-p188-airway-endpoint-card-source-audit-20260819.json`。P188 的唯一指定点行为 `1615`、UUID `af9bc75e-95a0-4dfc-bf78-b5c4afd3d757`，自身 FIR/服务机场为空；X62 第 `2292`、`2293` 行端点 FIR 也为空。
- ACC 名称为“北京、济南、郑州”；仅“北京”可映射到 `ZB`，“济南、郑州”无映射。模型侧相邻地区为 `ZH/ZS`。处置为 `rejected_multiple_neighbor_regions_with_incomplete_acc_evidence`、`projection_allowed=false`；不得以不相关的部分 `ZB` 映射或任一邻接地区补写 P188。
- 至此，来源缺口中的五个 `DESIGNATED_POINT` 区域身份 `P121/P127/P188/P225/P239` 均已通过 UUID 精确卡审计并保持拒绝。它们覆盖了所有 `DESIGNATED_POINT` 类型的 11 张航路端点卡和 5 张全局航点卡；没有任何卡获得新的唯一地区。M771 的 `****` 是唯一剩余航路端点卡，但它不是指定点，不能强行套用 UUID 审计。
- 本轮不增加投影规则，完整回归、提交前检查待本轮完成。模型、BGL、候选、Community 和部署状态均未变，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：为 M771 的非指定点 `****` 建立可复用的只读端点身份审计，验证其无法回链 `DESIGNATED_POINT.csv` 且不能仅凭单侧 `ZJ` 邻接恢复；该任务不得将 `****` 伪装为指定点或修改模型。

## 2026-08-19 r223 M771 非指定点身份审计

- 实验编号：`r223-m771-non-designated-endpoint-card-source-audit`。唯一假设是：M771 的 `****` 虽有 `RTE_SEG` 内部 UUID，是否能从允许的命名导航身份目录得到可投影的指定点、VOR 或 NDB 身份。变量是新增 `non-designated-airway-endpoint-card-audit`；它只处理非 `DESIGNATED_POINT` 类型，强制单一内部 UUID、单一坐标和单一模型未决身份，禁止跨类型调用指定点审计。
- 真实报告为 `diagnostics\r223-m771-non-designated-endpoint-card-source-audit-20260819.json`。M771 第 `4421` 行的 `****` 类型为“地名点”、内部 UUID `1dcf91d7-66b2-4b88-b1af-287f4615fef8`、坐标 `N143400/E1115530`、端点 FIR 为空；该 UUID 在 `DESIGNATED_POINT.csv`、`VOR.csv`、`NDB.csv` 中出现次数均为 `0`。它仅与 `DONDA/ZJ` 单侧相邻，备注为“三亚 ACC”。
- 处置为 `rejected_non_designated_endpoint_identity_unavailable`、`projection_allowed=false`。路由内部 UUID 不是可投影的命名导航身份；不得把“地名点”伪装成 `DESIGNATED_POINT`、跨表借用同坐标实体，或凭单侧 `ZJ` 邻接补写地区。
- 自动化新增非指定点 UUID 目录缺失拒绝和 CLI 回归；定向回归 `21 passed`，完整回归、提交前检查待本轮完成。至此 12 张航路端点卡和 5 张由其派生的全局航点地区卡均已获得直接来源闭合结论：五个指定点均因多地区/不完整或冲突 ACC 拒绝，M771 因非指定点身份不可用拒绝。没有新增可投影记录。
- 模型、BGL、候选、Community 和部署状态均未变；r188/r189 自重放仍 `29/29`，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：停止重复航路端点地区审计，转到稳定排序首张未分类程序卡 `ZGBS:RNP-0:12:0`。先建立只读的同周期 PDF/终端数据库编码程序类别审计，验证是否存在明确类别字段或可重放直接标题；不能唯一确认时保持 `rejected_for_target_mapping`，不得修改程序投影。

## 2026-08-19 r224 权威状态、进度统计与后续收敛计划

本节优先于本文件中更早的默认通用数据进度、测试数、Git 领先数和下一项任务描述。每次续做时，Codex 必须先执行实际核对；不得用本节文字替代可复跑证据。核对顺序固定为：两份 `AGENTS.md`、`git status --short --branch`、冻结模型 SHA-256、r188/r189 候选 `conversion-report.json`、`validate`、最近收敛/节表/来源卡诊断、测试结果和 `FlightSimulator2024.exe` 进程。

### 1. 当前实测状态

| 轨道 | 当前指标 | 状态与结论 |
| --- | --- | --- |
| 仓库与远端 | `main` 比 `origin/main` 领先 `38` 个提交；HEAD `81437bd`；工作树干净 | 代理 `127.0.0.1:7897` 未监听，普通推送暂不可用；保留本地提交，禁止强推或重写历史 |
| 跨格式模型 | `output\intermediate-2608-r187-navaid-label-replay.json.gz` | SHA-256 为 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`；是当前唯一可供其他格式消费的冻结内容边界 |
| 模型规模 | 机场 `275`、跑道方向 `640`、导航台 `438`、ILS `430`、全局航点 `2741`、终端航点 `12549`、航路段 `4446`、程序段 `10409`、等待航线 `1297` | 这些是来源模型规模，不是目标包加载或字节一致证明 |
| 候选确定性 | r188/r189 | 同模型有效树独立自重放 `29/29`；`valid=true`、`local_contract_verified=true`、`test_build=true` |
| 参考字节验收 | 两个中国覆盖包共 `29` 个受控文件 | 候选/参考目录均无缺失或额外文件，但 SHA-256 一致 `0/29`；所有 BGL、索引和派生包元数据仍不同 |
| 来源缺口卡 | 初始 `40` 张 | 已关闭 `17` 张航路端点/全局航点地区卡，结论均为有证据的拒绝；剩余 `23` 张：IAP 主段 `10`、未分类程序 `13` |
| 自动化与部署 | 最新完整回归 `437 passed`；本轮另行执行 `validate` | `deployable=false`；未覆盖 Community、未为当前候选创建部署备份、未实机验证、未创建正式 Release |

工程基础能力仍可估为约 `45%`，仅指 424 解析、来源证据、可重放 `NavModel`、CLI/GUI、SDK 构建、验证、更新与审计框架已建立。字节级验收是 `0/29`，部署、实机与正式 Release 均为 `0%`；这四类指标必须分开报告，不能用测试通过或候选自重放替代。

### 2. 已完成且可复用的经验

1. `NavModel` 是唯一跨 AIRAC、跨目标格式的内容边界。目标适配器只能消费已版本化的模型和通用证据；不得重新解析冻结 424、读取 Fenix，或把参考 BGL/SQLite/坐标/记录作为内容输入。
2. 424 CSV/PDF 是内容来源。OCR 仅能在“已存在模型对象 + 精确页面 + 可重放运行指纹”的范围内消歧；它不能创造程序、主段、腿、坐标、类别或归属。来源不足时必须留下拒绝卡。
3. `bglIndex.bout`、`layout.json`、`manifest.json`、ContentHistory、节表、文件大小与哈希都是构建产物或诊断指标。它们可以定位差异，不能反向推导对象语义或手工修补为参考值。
4. r218-r223 已完整复核全部 `12` 张航路端点地区卡及其 `5` 张全局航点地区卡。`P121/P127/P188/P225/P239` 因多地区或 ACC 证据不完整/冲突而拒绝；M771 的 `****` 因没有可投影命名身份而拒绝。不得重新尝试，除非获得新的、独立的同周期直接来源。
5. 已否决的机场子对象方向包括跑道表面、阈值位移、机场关联 VOR/NDB、进近扇区无线电投影、根终端点重复、等待航线隔离和 `DeleteAirport` 去除。没有新来源和单变量 SDK 证据，不得把这些方向重新包装为字节修复。
6. 包构建必须使用纯 ASCII 暂存路径，并以新的 `FlightSimulator2024.exe` 构建进程退出与完整产物为成功判据；前台 `fspackagetool.exe` 返回非零本身不能直接判定失败。

### 3. 收敛门禁和阶段计划

每轮固定为一个 `rNNN`、一个可证伪假设、一个变量。仅当“模型重放无未允许差异 + 同模型双构建自重放 `29/29` + 影响范围符合假设 + 参考一致文件数实际增加”四项同时成立，才记录为“字节收敛推进”。其他结果一律记录为“字节收敛未推进”，但可保留可复用诊断、fixture 或拒绝结论。

1. **阶段 A：r224 未分类程序卡审计。** 先处理稳定排序首卡 `ZGBS:RNP-0:12:0`。新增或扩展只读 `unclassified-procedure-card-audit`，精确输出模型段和腿、PDF SHA-256/页/行、终端数据库编码页类型、标签直接出现次数、明确类别标题的直接文本事实，以及 `target_mapping_allowed`。邻近标题、顺序、标签形态和 OCR 猜测都不能将 `kind=""` 写成进近、复飞、离场或进场。至少建立一个“无精确标签锚点而邻近有类别标题，必须拒绝”的反例 fixture；未来唯一直接关联正例才可建立允许 fixture。本阶段默认预期是拒绝，不改模型、候选或 Community。
2. **阶段 B：剩余来源卡闭合。** r224 后按诊断稳定顺序处理剩余 `12` 张未分类程序卡，再处理 `10` 张 IAP 主段卡；每张卡必须独立结束，不得把同机场、同跑道、相同标题或相邻图页合并为同一证据。每张卡的输出必须包含来源哈希、正/反例、结论、拒绝原因和潜在影响文件角色。无唯一同周期直接来源时，保持拒绝并前进到下一张卡。
3. **阶段 C：来源充分对象的单变量 SDK 契约探针。** 只有阶段 B 得到可投影的新规则，才建立隔离 Package Tool 探针。探针必须保存输入 XML、脚本、输入/工具 SHA-256、命令、模拟器进程轨迹、完整产物树、BGL 头/节表和读取器完整登记，并证明对象作用域、节表变化和记录基数三者一致。探针只生成诊断和最小 fixture，不直接修改正式适配器。
4. **阶段 D：模型和适配器规则接入。** 规则同时通过来源卡和 SDK 探针后，先加最小正反测试与审计字段，再修改来源解析、模型或默认数据 adapter。导出新模型，执行 `model-replay-audit --fail-on-unexpected`；差异白名单必须逐项列出对象、字段、来源、预期文件角色和双侧模型 SHA-256。未允许差异存在时停止，不进入构建。
5. **阶段 E：确定性构建与文件角色收敛。** 使用同一新模型、官方双基线、SDK、ASCII 暂存策略独立构建两次。依次运行 `validate`、报告 JSON 重读、有效树自重放、`file-convergence-audit`、机场/航路 BGL 节表审计。优先按 `00_enroute.bgl`、20 个区域机场 BGL、机场补丁 BGL、索引和包元数据分角色记录变化；包元数据只能由正常构建链派生。
6. **阶段 F：来源卡耗尽后的结构性阻塞处理。** 若 23 张剩余卡全部以有证据拒绝且参考仍为 `0/29`，不得为了继续推进而扩大 424 投影或读取参考 payload。应冻结“来源侧无新增规则”的结论，转为建立可复用的 SDK 表达能力清单：逐个已来源充分的对象类别做单变量探针，记录可表达性、覆盖语义、BGL 影响和读取器结果。只有该清单产生新的、可独立验证的目标契约，才另立新轮。
7. **阶段 G：最终验收、部署和实机。** 仅在参考 `29/29`、全新隔离双构建一致、完整验证和来源审计通过后，才检查游戏关闭，为两个 Community 覆盖包及相关元数据创建带 SHA-256 的时间戳备份并完成恢复演练。随后覆盖 `F:\games\community\Community`，由用户实机验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。实机通过前只能标记为测试版，禁止正式 Release。

### 4. 面向后续 AIRAC 与目标格式的通用管线

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 强制产物 | 未来复用要求 |
| --- | --- | --- |
| `lock-inputs` | 周期、CSV/PDF、官方模板、SDK、运行时、解析/OCR工具及 SHA-256 清单 | 每个 AIRAC 与每个目标重新锁定，不混用周期 |
| `ingest-424` | 原始精度、单位、`SourceRef`、结构化错误和拒绝 | 只读 424；目标格式不得污染来源语义 |
| `evidence-audit` | 单卡证据、正反例、OCR/SDK 指纹、允许或拒绝结论 | 参考仅验收，不回填内容 |
| `normalize-model` | 版本化、序列化、重放、差分均可用的 `NavModel` | 唯一跨格式内容边界 |
| `project-target` | 独立 `profile/adapter/validator/deployer` | 登记字段、单位、NULL/default、排序、容量、元数据和降级 |
| `build-target` | 隔离输出、输入清单、工具轨迹、双构建 | GUI、CLI、自动更新和部署复用同一 profile 与门禁 |
| `validate-target` | 结构、引用、运行时模拟器、fixture、元数据与降级报告 | 通过不等于字节一致或实机通过 |
| `diff-and-audit` | 文件角色、哈希、节表、语义计数、影响卡 | 仅定位，禁止反向补值 |
| `stage-backup-deploy` | 备份、恢复演练、部署记录、实机清单 | 只消费 `deployable=true` 的完整候选 |

任何新目标格式开始前，必须在本文件先新增目标小节，至少记录：官方基线、真实加载路径/SQL 或读取流程、文件/schema、字段映射与单位、NULL/default、物理排序、周期元数据、不可表达降级、最小 fixture、运行时模拟器、GUI/CLI 接入、备份恢复和实机清单。默认通用数据未闭合的 SDK 规则不得直接移植到其他目标。

### 5. Codex 状态维护与 Git 协议

- 每轮开始：核对上述基线，登记 `rNNN`、假设、变量、允许/禁止来源、输入/工具哈希、预期影响范围、成功/拒绝条件。
- 每轮结束：依据实际命令同步两份 `AGENTS.md` 的模型哈希、测试数、候选状态、自重放、参考 `x/29`、来源卡剩余数、节表差异、部署状态、Git 领先数、经验与下一项唯一任务。历史事实不得改写；若此前文字与实际产物冲突，应追加纠正说明。
- 每次代码或仓库文档改动：运行 `pytest -q`、`git diff --check`，精确审查暂存区，提交一个可解释主题，并尝试普通 `git push`。候选、诊断、缓存、数据库、备份、日志、SDK 中间产物和外部测试包不得提交。
- 推送失败时只记录失败原因；当前应提示检查代理 `http://127.0.0.1:7897`。网络恢复后按 `git push` 和 `git ls-remote --heads origin main` 核对，不得强推。
- 当前下一项唯一任务为阶段 A 的 `ZGBS:RNP-0:12:0` 只读未分类程序卡审计。在它完成、测试、提交和状态同步前，不启动下一张卡，不修改 `NavModel`、正式投影、候选、Community 或部署逻辑。

## 2026-08-19 r224 ZGBS RNP-0 未分类程序卡直接来源审计

- 实验编号：`r224-zgbs-rnp-0-12-unclassified-procedure-card-audit`。唯一假设是：`ZGBS:RNP-0:12:0` 能否由同一来源页中标签与程序类别标题的直接、唯一文本关联确认 `kind`。唯一变量是新增只读 CLI `unclassified-procedure-card-audit`；它按缺口卡精确键选择模型段，不读取参考 BGL/SQLite、Fenix 或 OCR，不修改模型、XML、候选、Community 或部署。
- 新审计验证 `SourceRef` PDF SHA-256，读取指定页的直接文本，输出精确程序段/腿、terminal-database-coding 图页、标签直接命中、类别标题事实和同文本行的标签-类别链接。只有标签恰好命中一次、链接恰好一条且类别唯一时，才报告 `source_proven_kind` 和 `target_mapping_allowed=true`。相邻标题、页面顺序、标签形态和 OCR 均不能成为关联规则。
- 真实输出为 `diagnostics\r224-zgbs-rnp-0-12-unclassified-procedure-card-audit-20260819.json`。来源 `Terminal\ZGBS\ZGBS-0C-2.pdf` 第 1 页的实际 SHA-256 为 `16a443504222d3732bac6b9ea1023c56c6a6b6727f6b8bf91ac93b643f2e52b0`，与冻结模型一致；`RNP-0` 直接命中 `0` 次。页面确有 8 条程序类别标题事实，包括 `RWY12 进近及复飞` 和多个 `RWY12/RWY30 进近过渡`，但它们不含该数据库标签，不能按腿在标题之后、下一标题之前的顺序推断类别。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署状态均未改变；r188/r189 自重放继续为 `29/29`，参考一致继续为 `0/29`，`deployable=false`，字节收敛未推进。
- 新增最小正反 fixture：无标签直接锚点但存在相邻“进近及复飞”标题时必须拒绝；仅为未来来源规则验证的正例要求 `RNP-0` 与单一类别在同一文本行。CLI 参数和输出写入路径亦有独立回归。完整回归为 `440 passed`。
- 下一项唯一任务：按稳定排序处理 `ZGBS:RNP-0:15:1`。复用 r224 审计器，仅替换精确卡键；无新的唯一标签-类别直接关联时保持拒绝，不得修改模型或投影。

## 2026-08-19 r225 ZGBS RNP-0 跑道 15 程序卡直接来源审计

- 实验编号：`r225-zgbs-rnp-0-15-unclassified-procedure-card-audit`。唯一变量是将 r224 的精确卡键替换为 `ZGBS:RNP-0:15:1`；复用同一只读审计器、r187 冻结模型和同周期 424 PDF，不修改代码、模型、候选、Community 或部署。
- 真实输出为 `diagnostics\r225-zgbs-rnp-0-15-unclassified-procedure-card-audit-20260819.json`。卡片源仍为 `ZGBS-0C-2.pdf` 第 1 页，SHA-256 `16a443504222d3732bac6b9ea1023c56c6a6b6727f6b8bf91ac93b643f2e52b0` 与模型一致；`RNP-0` 直接命中仍为 `0`，类别标题事实仍为 8 条，且不存在同文本行的标签-类别链接。
- 该模型段的跑道字段为 `15`，而同页 terminal-database-coding 图页仅列 `12/30`。这不是类别映射证据，也不能用于否定、修正或按相邻数据库记录推断该段；只记录为来源页与模型字段的审计事实。
- 处置继续为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署状态不变；自重放保持 `29/29`、参考一致保持 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZGBS:RNP-0:15:2`。该卡指向不同的 `ZGBS-0C-3.pdf`，可复用 r224 审计器，但必须作为独立来源卡处理，不得把本页拒绝结论跨页套用。

## 2026-08-19 r226 ZGBS RNP-0 跑道 15 跨页程序卡直接来源审计

- 实验编号：`r226-zgbs-rnp-0-15-source-page-2-unclassified-procedure-card-audit`。唯一变量是将 r225 卡键替换为 `ZGBS:RNP-0:15:2`；该卡改为读取不同来源页 `ZGBS-0C-3.pdf` 第 1 页，继续不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r226-zgbs-rnp-0-15-source-page-2-unclassified-procedure-card-audit-20260819.json`。源 PDF SHA-256 `40d1ec47b7641d2a1680918d005a6392aca983206ffd8873bb552090d7cc5955` 与模型一致；程序腿为 `CF BS509`、`DF BS508`、`TF BS506`。页面存在 2 条类别标题事实，但 `RNP-0` 直接命中为 `0`，无同文本行的标签-类别链接。
- 处置继续为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。不同 PDF 页的独立审计未提供新来源规则；模型、投影、候选、Community 和部署不变，自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZGBS:RNP-0:30:3`。该卡与 r226 使用同一来源页，但跑道和模型段不同，仍必须按精确卡单独审计；除非该段自身得到唯一直接标签-类别关联，不得复用 r226 的页面顺序或标题推断。

## 2026-08-19 r227 ZGBS RNP-0 跑道 30 程序卡直接来源审计

- 实验编号：`r227-zgbs-rnp-0-30-unclassified-procedure-card-audit`。唯一变量是将 r226 卡键替换为 `ZGBS:RNP-0:30:3`；继续只读 `ZGBS-0C-3.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r227-zgbs-rnp-0-30-unclassified-procedure-card-audit-20260819.json`。PDF SHA-256 `40d1ec47b7641d2a1680918d005a6392aca983206ffd8873bb552090d7cc5955` 与模型一致；程序腿为 `CF BS509`、`DF BS508`、`TF BS506`。该页类别标题事实为 2 条，`RNP-0` 直接命中 `0`，没有直接标签-类别链接。
- 本卡跑道 `30` 与 terminal-database-coding 页列出的 `30` 一致，但跑道一致性不是程序类别证明，不能替代缺失的标签锚点或允许按标题顺序归类。处置保持 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。
- 模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：从稳定排序的下一张未分类程序卡 `ZHCC:CC3-09:12R:4` 开始独立审计。其来源文件和标签族均不同，必须先重新核对 PDF/模型哈希和直接标签锚点，不能把 ZGBS RNP 结论泛化为规则。

## 2026-08-19 r228 ZHCC CC3-09 程序卡直接来源审计

- 实验编号：`r228-zhcc-cc3-09-12r-unclassified-procedure-card-audit`。唯一变量是切换到不同机场、不同来源文件和 `cc_numeric` 标签族的精确卡 `ZHCC:CC3-09:12R:4`；仍只执行 `unclassified-procedure-card-audit`，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r228-zhcc-cc3-09-12r-unclassified-procedure-card-audit-20260819.json`。来源 `ZHCC-4Z12.pdf` 第 1 页的 SHA-256 为 `d69025ea3321a275918d57571daba12c315d4f7aca747b90bb918693770be8b2`，与模型一致；程序腿为 `IF CC304`、`TF CC406`、`IF CC608`。同页 terminal-database-coding 图页列出跑道 `12R/30L/30R`，并有 13 条类别标题事实。
- `CC3-09` 在直接文本中命中 `0`，没有同文本行标签-类别链接。即使若干类别标题和部分腿标识共同出现，也不能将标识重合、跑道一致、图面顺序或等待航线位置转换为标签类别证据。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。这证明 r224 的拒绝门禁在不同机场/标签族上仍成立，但不构成修改任何程序投影的正向规则；模型、候选、Community 和部署不变，自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZHCC:CC5-17:30L:5`。该卡与 r228 共用来源页但标签、跑道和腿不同，必须按精确卡独立审计，不能从 `CC3-09` 的标签缺失外推其直接文本结果。

## 2026-08-19 r229 ZHCC CC5-17 程序卡直接来源审计

- 实验编号：`r229-zhcc-cc5-17-30l-unclassified-procedure-card-audit`。唯一变量是从 r228 切换精确卡键到 `ZHCC:CC5-17:30L:5`；继续只读同一 `ZHCC-4Z12.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r229-zhcc-cc5-17-30l-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 仍为 `d69025ea3321a275918d57571daba12c315d4f7aca747b90bb918693770be8b2` 并与模型一致；程序段有 16 条腿，从 `IF DWS` 经 `CC518/CC517/...` 到 `TF CC312`。页面类别标题事实仍为 13 条。
- `CC5-17` 直接命中 `0`，没有同文本行标签-类别链接。页面的 `RWY30L` 标题、`DWS` 或 `CC` 前缀腿标识均不能取代缺失标签锚点；它们只表明同页存在相邻的航图内容，不能证明这段未分类数据库编码属于哪一类程序。
- 处置保持 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计不同来源页的 `ZHCC:CC5-32:30R:6`。不得将本页的腿/标题相邻事实跨页使用。

## 2026-08-19 r230 ZHCC CC5-32 跨页程序卡直接来源审计

- 实验编号：`r230-zhcc-cc5-32-30r-unclassified-procedure-card-audit`。唯一变量是将 r229 的精确卡键切换为跨页卡 `ZHCC:CC5-32:30R:6`，只读 `ZHCC-4Z13.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r230-zhcc-cc5-32-30r-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `82b48a2d7c87a2086495fd78a85a9034214cceac2c5d99b072c5dc370d35bce0` 与模型一致；程序腿为 `IF CC608`、`TF CC533`、`TF CC312`、`TF CC534`。页面有 9 条类别标题事实，terminal-database-coding 图页列出 `12L/30R`。
- `CC5-32` 直接命中 `0`，无同文本行标签-类别链接。`CC608` 腿标识、`RWY30R` 类别标题和跑道一致性均不能构成程序类别映射；它们只能用于说明同页存在相关航图内容。
- 处置继续为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZPDQ:EO-16:16:7`。该卡切换到 `eo_numeric` 标签族和新的机场来源，必须从 PDF 哈希和直接标签锚点重新开始，不得泛化 ZHCC 结论。

## 2026-08-19 r231 ZPDQ EO-16 程序卡直接来源审计

- 实验编号：`r231-zpdq-eo-16-16-unclassified-procedure-card-audit`。唯一变量是切换到 `eo_numeric` 标签族和新机场的精确卡 `ZPDQ:EO-16:16:7`；只读 `ZPDQ-4J.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r231-zpdq-eo-16-16-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `928990a1d84556c6cfd005f179fb43b6fc2c5715c48ca3c59367f928ce7111e8` 与模型一致；程序腿为 `IF DER16`、`TF DQ510`、`RF DQ514`、`RF DQ517`。页面有 7 条类别标题事实，均为 `RWY16` 离场标题及其命名变体。
- `EO-16` 直接命中 `0`，无同文本行标签-类别链接。离场标题、`DER16`、RF 腿或跑道 `16` 都不能将该数据库标签归类为离场；它们不满足直接来源关联门禁。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZPDQ:EO-34:34:8`。该卡来源页和跑道均不同，必须按精确卡重新审计，禁止由 EO-16 或 RF 腿形态推断类别。

## 2026-08-19 r232 ZPDQ EO-34 跨页程序卡直接来源审计

- 实验编号：`r232-zpdq-eo-34-34-unclassified-procedure-card-audit`。唯一变量是将 r231 的精确卡切换为 `ZPDQ:EO-34:34:8`，只读 `ZPDQ-4L.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r232-zpdq-eo-34-34-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `7cad7386be31f0d7e4d35674eed2323a2f93c51e20480c15e9568f3ce7262233` 与模型一致；程序段包含 `IF DQ610`、多个 `TF/RF`、`HM DQ560` 等 11 条腿。页面有 4 条类别标题事实，编码页列出跑道 `16/34`。
- `EO-34` 直接命中 `0`，无同文本行标签-类别链接。RF/HM 腿形态、`DQ560`、`RWY34` 离场标题和跑道匹配都不是程序类别映射证据，不能解除未分类拒绝。
- 处置继续为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZUKD:EO-15:15:9`。该卡切换机场和来源页，必须重新核对 PDF 哈希与直接文本，不能将 EO-34 的 RF/HM 观察外推。

## 2026-08-19 r233 ZUKD EO-15 程序卡直接来源审计

- 实验编号：`r233-zukd-eo-15-15-unclassified-procedure-card-audit`。唯一变量是切换为精确卡 `ZUKD:EO-15:15:9`，只读 `ZUKD-4J.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r233-zukd-eo-15-15-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `a0334bccdd794d60aa2da38ddd654531f536bb95f2b12fa552463b1f2af05eb4` 与模型一致；程序腿为 `IF RW15C`、`TF KD601`、多个 `RF KD602...KD613`、`TF KD614`。页面有 5 条类别标题事实，terminal-database-coding 图页列出 `BIG-81A/KAM-81A/MYD-81A` 与跑道 `15/33`。
- `EO-15` 直接命中 `0`，无同文本行标签-类别链接。其他离场标签、`RW15C`、`KD614`、RF 腿、跑道 `15` 和进近过渡标题均不能替代标签锚点，也不得用它们把此段分类为离场或进近过渡。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计同页不同卡 `ZUKD:EO-33:33:10`。必须单独验证其标签在直接文本中的出现和类别链接，不能从 EO-15 的缺失结论替代该卡审计。

## 2026-08-19 r234 ZUKD EO-33 程序卡直接来源审计

- 实验编号：`r234-zukd-eo-33-33-unclassified-procedure-card-audit`。唯一变量是将 r233 的精确卡键替换为同页不同跑道卡 `ZUKD:EO-33:33:10`；继续只读 `ZUKD-4J.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r234-zukd-eo-33-33-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `a0334bccdd794d60aa2da38ddd654531f536bb95f2b12fa552463b1f2af05eb4` 与模型一致；程序腿为 `IF RW33C`、`TF KD702`、`RF KD701`、`RF KD700`、`TF KD654`。页面有 5 条类别标题事实，编码页列出跑道 `15/33`。
- `EO-33` 直接命中 `0`，无同文本行标签-类别链接。页面的类别标题只显式涉及其他 `RWY15` 标签；`RW33C`、RF 腿和跑道 `33` 不能将该段归类，也不能将未出现的 `RWY33` 标题视为来源事实。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计 `ZUSH:EO-10:10:11`。该卡切换至不同机场和 PDF，不得从 ZUKD 同页缺失结果推断。

## 2026-08-19 r235 ZUSH EO-10 程序卡直接来源审计

- 实验编号：`r235-zush-eo-10-10-unclassified-procedure-card-audit`。唯一变量是切换到精确卡 `ZUSH:EO-10:10:11`，只读 `ZUSH-4Z01.pdf` 第 1 页，不修改代码、模型、候选、Community 或部署。
- 真实报告为 `diagnostics\r235-zush-eo-10-10-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `feb8f58de95e0f1934e47da4b11a8ca4db0f85c1f8ab6c748a6042ba6a18f478` 与模型一致；程序腿为 `IF RW10`、`TF DE10/NS600/NS610` 与多个 RF 腿。页面有 2 条类别标题事实，直接列出 `RWY10 UGOVA-09D` 和 `RWY28 UGOVA-19D` 离场，编码页列出跑道 `10/28`。
- `EO-10` 直接命中 `0`，无同文本行标签-类别链接。`UGOVA` 离场标题、`RW10`、RF 腿和跑道 `10` 不能替代缺失标签锚点，也不能将此段归类为离场。
- 处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。模型、投影、候选、Community 和部署不变；自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 下一项唯一任务：按稳定排序审计最后一张未分类程序卡 `ZUSH:EO-28:28:12`。它使用不同 PDF 页，必须独立核对；完成后需汇总 13 张未分类程序卡的来源闭合结果，再决定下一阶段的来源卡或 SDK 表达审计。

## 2026-08-19 r236 ZUSH EO-28 程序卡审计与未分类程序卡覆盖闭合

- 实验编号：`r236-zush-eo-28-28-unclassified-procedure-card-audit`。唯一程序卡变量是最后一张 `ZUSH:EO-28:28:12`，只读 `ZUSH-4Z02.pdf` 第 1 页；随后以当前 `default-gap-cards-audit` 清单做诊断覆盖核对，不修改代码、模型、候选、Community 或部署。
- 真实卡报告为 `diagnostics\r236-zush-eo-28-28-unclassified-procedure-card-audit-20260819.json`。来源 SHA-256 `e9b91d3fd932037c0447d4f7ca15eaad3c63e610ff648416f92c0885f34d7b10` 与模型一致；程序段包含 `IF RW28`、`TF/RF NS500...NS999` 等 15 条腿。页面有 3 条类别标题事实（`UGOVA-8A/9A` 进场及 `RWY10` 进近过渡），`EO-28` 直接命中 `0`，没有标签-类别直接关联。
- 本卡处置为 `rejected_missing_direct_label_anchor`、`source_proven_kind=null`、`target_mapping_allowed=false`。标题、`RW28`、RF 腿、`NS988` 和跑道都不能替代标签锚点；模型、投影、候选、Community 和部署不变，自重放 `29/29`、参考一致 `0/29`、`deployable=false`，字节收敛未推进。
- 覆盖核对使用 r187、r188 `conversion-report.json` 与 `diagnostics\r236-default-gap-cards-unclassified-coverage-20260819.json`：当前缺口清单恰有 `13` 张未分类程序卡，r224-r236 恰有 `13` 份唯一精确卡诊断，缺失 `0`、额外 `0`、哈希/标签命中/处置门禁异常 `0`。全部卡均为 `rejected_missing_direct_label_anchor`；未分类程序类别来源卡已完整闭合，不能继续以标签/标题/腿形态扩大投影。
- 下一项唯一任务：先对剩余 `10` 张 IAP 主段缺口卡做只读来源审计覆盖盘点，区分已有精确拒绝结论与仍缺精确来源卡的对象；不得重做已闭合 IAP 卡，也不得直接处理 `ZBAD:R29R` 等历史卡而跳过覆盖核对。盘点后按稳定排序选择第一张真正未闭合 IAP 卡。

## 2026-08-19 r237 IAP 主段来源审计覆盖盘点

- 实验编号：`r237-iap-primary-source-audit-coverage-inventory`。本轮只读取当前 r187、r188 `conversion-report.json`、最新缺口卡清单和既有 `r200/r203/r208/r209/r212` IAP 来源审计；不读取参考/Fenix，不修改代码、模型、候选、Community 或部署。
- 当前缺口清单共有 `10` 张 IAP 主段卡：`ZBAD:R29R`、`ZJSY:I08-X`、`ZSNJ:I25`、`ZSOF:R15/R33`、`ZSWY:I03`、`ZUAL:I15`、`ZYDD:R01/R01-Y`、`ZYTL:R10`。`r203-all-unresolved-iap-primary-source-audit` 对全部 10 张均有直接数据库来源审计覆盖：`ZBAD:R29R` 与 `ZYTL:R10` 为 `rejected_transition_and_missed_without_primary`，其余 8 张为 `unresolved_direct_database_evidence_inconclusive`。
- 已存在的精确补充审计不能重复：`ZBAD:R29R` 已由 r200 直接确认拒绝；`ZJSY:I08-X` 已由 r212 标题/直接角色审计保持未决；`ZYDD` 相关标题已由 r208 审计；`ZSOF:R15` 已由 r209 审计。它们均没有形成可投影主进近规则。
- 结论：IAP 类别的 10 张卡都已有来源审计覆盖，但只有 2 张可作为明确拒绝闭合；剩余 8 张仍须逐张取得新的、精确且可重放的同周期 PDF/数据库证据，不能以全局审计的“inconclusive”把它们视为已闭合，也不得重做已有精确审计。
- 下一项唯一任务：按稳定排序审计首张真正未闭合且无精确补充卡的 `ZSNJ:I25`。必须先限定其数据库主段、候选 PDF 标题和直接角色/固定点来源；无唯一主段或页面关联时保持 `unresolved_direct_database_evidence_inconclusive`，不得修改 IAP 投影。

## 2026-08-19 r237 后权威状态、进度面板与长期执行计划

本节是 r237 后默认通用数据转换器的唯一状态入口，优先于本文件此前所有默认通用数据的进度估算、下一项任务和历史候选描述。历史章节保留为可复核证据，不能代替当前决策。每次继续前必须实际核对两份 `AGENTS.md`、Git、冻结模型、有效候选报告、最近诊断、完整测试和游戏进程；文字与可复跑产物冲突时，以产物为准，并在同一轮修正本节和工作区根 `AGENTS.md`。

### 1. 实际基线

| 项目 | 已核验状态 | 说明 |
| --- | --- | --- |
| 内容来源 | 仅 `424源数据\2608\2608` 的 CSV/PDF | 官方 `navigraph-nav-base`/`navigraph-nav-jepp` 仅作全球基线和加载契约；`Default navdata 2608R1` 仅作只读验收；禁止读取 Fenix 或参考成品来补值 |
| 冻结跨格式模型 | `output\intermediate-2608-r187-navaid-label-replay.json.gz` | SHA-256 `7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`；任何内容规则变更必须导出新版本模型并通过重放审计 |
| 最新有效候选 | r188/r189 | 同一冻结模型的独立构建有效树自重放 `29/29`；`test_build=true`、`local_contract_verified=true`、`deployable=false` |
| 参考字节验收 | 未开始收敛 | 两个中国覆盖包的受控文件集合完整，但 SHA-256 一致仍为 `0/29`；不得将候选自重放误报为参考一致 |
| 自动化回归 | 已通过 | 最近完整回归为 `440 passed`；它只覆盖已编码的约束，不证明 BGL 加载、字节一致或实机可用 |
| Community 与发布 | 未开始 | 未覆盖 Community、未为候选建立部署备份、未实机、未正式 Release；本机当前不应以游戏关闭状态替代部署门禁 |
| Git | 本地待同步 | 工作树干净，`main` 比 `origin/main` 领先 `53` 个提交；远端为 `JCH2333/defult_navdata_converter`；此前普通推送因 `127.0.0.1:7897` 未监听失败 |

### 2. 分层进度统计

不得把基础能力、来源审计、字节验收和上线验收合成单一百分比。

| 轨道 | 当前进度 | 量化依据 | 阶段出口 |
| --- | --- | --- | --- |
| 工程基础能力 | 约 45% | 输入锁定、424 解析、证据层、可重放 `NavModel`、默认 BGL adapter、CLI/GUI、Package Tool、验证器、更新和部署门禁已经存在 | 每个后续目标格式都能消费相同模型并具备独立 profile/adapter/validator/deployer |
| 来源缺口卡审计覆盖 | 32/40，80% | 12 张航路端点区域卡、5 张派生全局航点区域卡、13 张未分类程序卡和 2 张 IAP 明确拒绝卡已有精确来源闭合结论 | 剩余 8 张 IAP 卡逐张得到可投影的唯一来源规则，或得到精确、可重放的拒绝结论 |
| 可安全投影的内容闭合 | 未完成 | 32 张卡中的多数结论是保守拒绝，不等同于新增内容；8 张 IAP 仍为 `unresolved_direct_database_evidence_inconclusive` | 任何新增投影均通过来源、目标表达和最小正反例三重门禁 |
| 候选构建确定性 | 29/29 | r188/r189 有效树自重放一致 | 每次模型、adapter、SDK、模板或构建策略变化后均重新双构建 |
| 参考字节验收 | 0/29，0% | 29 个受控文件均存在且无额外文件，但没有一个 SHA-256 相同 | 新鲜隔离双构建均为 29/29，并保留完整树哈希与差异报告 |
| 部署、实机、正式发布 | 0% | `deployable=false`，未备份恢复演练、未覆盖 Community、未实机 | 字节验收、完整验证、恢复演练和用户实机清单全部通过 |

当前剩余工作不能据 45% 推导交付日期。字节一致仍是高不确定性阶段；只有参考一致数实际增加，才称为“字节收敛推进”。

### 3. 已确认经验与禁止回退项

1. `NavModel` 是唯一跨 AIRAC、跨格式的内容边界。其他格式只能新增目标 profile/adapter，不能重新解析冻结 424、读取 Fenix，或把 OCR 缓存当作内容来源。
2. 来源审计“闭合”有两种不同结果：`projection_allowed=true` 的唯一规则，或带证据的保守拒绝。拒绝结论同样是管线资产，但不应被计入内容投影完成率。
3. OCR 只能在已有对象、精确 `SourceRef`、来源页归属和可重放一致性都成立时，为已存在角色消歧；不能创造主进近、程序段、坐标、类型、图页归属或地区。
4. 未分类程序的 13 张卡均缺少标签到类别的直接锚点，已全部以 `rejected_missing_direct_label_anchor` 闭合；不得以跑道、腿标识、标题邻近、页面顺序、RF/HM 或 OCR 反推类别。
5. 航路端点和派生全局航点的 17 张卡均已按精确身份审计后保守拒绝；多地区邻接、ACC 映射不完整/冲突及非指定点身份缺失不能生成唯一地区。
6. 已否决的方向继续有效：机场关联 VOR/NDB 伪投影、机场扇区无线电投影、跑道表面/阈值位移猜测、根终端点重复、等待航线隔离、`CODE_DIR` 简单反转、无来源 `routeType`、为节表差异移除 `DeleteAirport`。重启任何方向必须有新的直接 424 来源或真实 SDK/运行时证据和最小反例。
7. `manifest.json`、`layout.json`、`bglIndex.bout`、ContentHistory 和包大小均为构建链派生产物。禁止复制参考文件、手工修补哈希或用参考内容驱动 XML。

### 4. 接下来工作的阶段计划

#### 阶段 A：闭合 8 张 IAP 主段来源卡

下一项唯一任务固定为 `ZSNJ:I25`。已知直接数据库来源为 `Terminal\ZSNJ\ZSNJ-4P.pdf` 第 1 页，SHA-256 `9dbc1378476911e587d4b8d5c1053e2e9ba46ded6d197acc1cdc9235db0c78ce`；当前只确认 3 条复飞腿 `NJ602/CF`、`CA`、`NJ216/DF`，没有主进近或过渡腿，因此仍为 `unresolved_direct_database_evidence_inconclusive`。

每张未闭合 IAP 卡都必须按以下顺序推进：

1. 用冻结模型和精确数据库编码页建立只读卡片，输出主进近、过渡、复飞的独立腿集、页 SHA-256、候选图标题、直接角色、固定点和拒绝原因。
2. 只有当数据库主段和同周期 PDF 的图页归属可唯一对应时，才允许调用受控 OCR；OCR 只能验证已有角色，不能补出缺失主段。
3. 有唯一、可重复的来源规则时，先写最小正反 fixture 和审计字段，再做单变量 SDK 探针；无唯一规则时写精确拒绝结论并从队列移除。
4. 不得重做 r200、r208、r209、r212 已有精确审计；新卡按稳定排序选择，并在开始前说明为何尚未被精确审计覆盖。

阶段 A 的出口不是“8 张都被强行投影”，而是 8 张均有可审计的唯一投影规则或精确拒绝结论。

#### 阶段 B：规则接入与模型重放

仅当阶段 A 得到 `projection_allowed=true` 的来源规则，且目标表达已由阶段 C 证实时，才允许修改解析、模型或 BGL adapter。接入顺序固定为：

`最小正反 fixture -> 来源审计字段 -> 规则实现 -> 新版本模型 -> model-replay-audit --fail-on-unexpected -> 新旧模型语义差异白名单 -> 候选构建`

白名单必须逐项记录对象身份、字段路径、来源、预期 BGL 文件角色和两侧哈希。出现任何未允许模型差异时立即停止，不能继续构建候选。

#### 阶段 C：SDK/目标表达契约探针

当来源卡已无可接入规则或规则尚缺目标表达证据时，转入只读或隔离 SDK 探针，而不是扩大 424 猜测。每个探针只能改变一个 XML 变量，并保存：

- 控制组和变量组 XML、输入/工具 SHA-256、Package Tool 命令与进程轨迹；
- 完整包树哈希、BGL 节表、读取器完整登记和对象计数；
- 可证伪结论，以及该结论是否允许接入 adapter。

探针按受控文件角色排序：`00_enroute.bgl` 的来源对象/SDK 表达，区域机场 BGL，机场补丁 BGL，最后才是索引和派生元数据。节表计数只能定位差异，不能反向推断或补写参考对象。

#### 阶段 D：候选双构建与字节收敛

每个有效模型变化必须从相同的冻结模型、官方双基线、SDK、ASCII 暂存策略和输入 manifest 独立构建两次，并依次执行：

`validate -> 标准 JSON 重读 -> 29 文件自重放 -> source-gap audit -> BGL/layout audit -> file-convergence-audit`

文件比较必须按角色分组：航路 BGL、区域机场 BGL、机场补丁 BGL、索引、布局、清单、ContentHistory。仅当模型重放无未允许差异、自重放保持 29/29、受影响文件符合该轮假设且参考一致文件数增加时，才记录“字节收敛推进”；否则明确记录“字节收敛未推进”。

#### 阶段 E：干净验收、备份、部署与实机

只有参考 `29/29`、从全新隔离目录双构建一致、完整 `validate` 与来源审计通过后，才进入部署准备：

1. 再次确认 `FlightSimulator2024.exe` 已退出。
2. 为两个 Community 覆盖包、`layout.json`、`manifest.json`、`bglIndex.bout` 和 ContentHistory 创建带时间戳、SHA-256 清单的完整备份。
3. 先完成恢复演练并验证备份树哈希，再覆盖 `F:\games\community\Community`。
4. 用户依次验证 `ZBCF`、`ZUNZ`、`ZUUU` 的机场输入、跑道、SID、STAR、IAP、航路/航点、退出飞行和退出模拟器。

实机通过前仅能标记测试版；正式 GitHub Release 必须在全部实机清单通过后创建。

### 5. 面向未来 AIRAC 与目标格式的可复用管线

统一管线固定为：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

| 阶段 | 必须保留的可复用产物 | 新 AIRAC/新格式的用法 |
| --- | --- | --- |
| `lock-inputs` | CSV/PDF/模板/SDK/缓存运行指纹和 SHA-256 manifest | 只替换当期输入，不混用旧周期内容 |
| `ingest-424` | 原始精度、单位、`SourceRef`、拒绝记录 | 所有适配器共享同一来源事实 |
| `evidence-audit` | 精确卡、正反例、OCR 指纹、允许/拒绝理由 | 把无法表达的事实保留为可审计降级，不静默丢弃 |
| `normalize-model` | 版本化 `NavModel`、来源字段、引用和降级计数 | 所有目标格式只消费模型，不重复解析 |
| `project-target` | 独立 profile/adapter 的字段、单位、NULL/default、排序、容量和降级规则 | 新格式不得污染默认 BGL 或其他 adapter |
| `build-target` | 隔离输出、确定性 manifest、工具轨迹、GUI/CLI 共用入口 | 自动更新、GUI 和 CLI 走同一构建门禁 |
| `validate-target` | 格式/引用/运行时模拟器/fixture/元数据报告 | 每个机模保留自己的加载契约 |
| `diff-and-audit` | 文件角色、哈希、脱敏语义计数和来源卡关联 | 参考只作验收，不作为内容输入 |
| `stage-backup-deploy` | 备份、恢复演练、部署记录和实机清单 | 仅消费 `deployable=true` 的最终候选 |

新目标格式启动前，必须在其 profile 文档登记官方基线、真实加载路径和契约、文件/schema、字段单位、NULL/default、物理顺序、元数据、不可表达项降级、最小 fixture、运行时模拟器、GUI/CLI 接入及实机清单。默认 BGL 的未闭合规则不得直接迁移。

### 6. Codex 进度维护与提交协议

1. 每轮开始前分配连续 `rNNN`，写明唯一假设、唯一变量、允许/禁止来源、输入/工具哈希、预期影响文件角色、成功条件和否决条件。
2. 每轮结束后必须从实际命令输出更新两份 `AGENTS.md`：测试数、模型哈希、候选状态、自重放、参考 `x/29`、来源卡 `已闭合/可投影/未决` 三类数量、节表看板、部署状态、Git 领先数、确认经验、否决项和下一项唯一任务。
3. 只读审计、SDK 探针、模型/adapter 变更、候选构建和部署逻辑必须分主题提交；不得将诊断结论和内容投影混在同一次规则变更中。
4. 每次仓库代码或文档修改后必须运行 `pytest -q`、`git diff --check`、精确审查暂存区、创建单一主题提交，并尝试普通 `git push`。代理不可用时记录失败并保留本地提交；网络恢复后只允许 `git push` 和 `git ls-remote --heads origin main`，禁止强推或改写历史。
5. `diagnostics`、`output`、数据库、备份、缓存、SDK 中间产物、日志和外部测试包继续留在 Git 之外。工作区根 `AGENTS.md` 不在仓库中，但仓库内说明发生变化时必须同步更新它。

## 2026-08-19 r238 ZSNJ I25 精确 IAP 主段来源审计

- 实验编号：`r238-zsnj-i25-exact-iap-primary-source-audit`。唯一变量是将既有全局 `iap-primary-source-audit` 扩展为可重复指定 `--card AIRPORT:LABEL` 的精确只读审计，并只在精确卡模式下要求仪表进近图缓存与冻结 `NavModel` 的 `SourceRef`、直接角色完全一致。允许读取 r187、四份带哈希的 424 PDF 直接证据缓存及其同源模型记录；禁止读取参考成品、Fenix、OCR、候选 BGL/SQLite 或修改模型/投影。
- 新增可复用 CLI 参数 `iap-primary-source-audit --card`。它只输出所选的未决卡，拒绝不在未决队列的键，并额外报告 `cache_verified_instrument_chart_title_candidates`。缓存候选必须与模型的原始 PDF 路径、页码、SHA-256 和直接 `route_fixes` 完全一致；此字段只提供标题/角色来源库存，固定 `projection_allowed=false`，永远不能从缺失主段生成程序。
- 真实报告为 `diagnostics\r238-zsnj-i25-exact-iap-primary-source-audit-20260819.json`。数据库编码页 `Terminal\ZSNJ\ZSNJ-4P.pdf` 第 1 页 SHA-256 `9dbc1378476911e587d4b8d5c1053e2e9ba46ded6d197acc1cdc9235db0c78ce` 只有 `NJ602/CF`、`CA`、`NJ216/DF` 三条复飞腿；模型和缓存的主进近、进近过渡均为零。
- 缓存验证的同跑道仪表图有三张：`ZSNJ-5G.pdf`（SHA-256 `5014e49ad1e51fdd59de14fb22341510f6862759feb7b160f1eca76946a9853c`）标题候选 `I25/I25-Z`，直接角色为 `NJ206/IF`、`NJ209/IAF`、`NJ210/IAF`；`ZSNJ-5H.pdf`（SHA-256 `78a5fdeaffab06ae6077bd1dd442d7f96abd7a7eb3724be40b9e108b016dd72b`）标题候选 `I25/I25-Y`，无直接角色；`ZSNJ-9D.pdf` 为 `R25`，不匹配 `I25`。两张 `I25` 标题兼容图不能唯一归属同一个缺失主段，且既无数据库主段也无主段角色交集。
- 处置为 `unresolved_direct_database_evidence_inconclusive`、`projection_allowed=false`。不得把 `ZSNJ-5G` 的 IAF/IF、`ZSNJ-5H` 的空角色、同跑道、图题或任一复飞腿拼接成 `I25` 主进近；模型、BGL、候选、Community 和部署均未改变，自重放仍以 r188/r189 的 `29/29` 为基线，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 自动化新增精确卡筛选、未知卡拒绝、缓存 `SourceRef`/直接角色绑定和 CLI 参数回归；定向回归 `10 passed`。完整回归、提交前检查和 Git 提交必须在本轮结束前完成。
- 下一项唯一任务：按剩余 IAP 未决卡稳定排序，对尚无精确补充审计的 `ZSOF:R33` 建立同样的数据库主段、候选标题、直接角色和缓存哈希只读卡。不得重做 `ZSOF:R15`、`ZJSY:I08-X`、`ZYDD` 或 `ZSNJ:I25`，无唯一来源时继续保守拒绝。

## 2026-08-19 r239 ZSOF R33 精确 IAP 主段来源审计

- 实验编号：`r239-zsof-r33-exact-iap-primary-source-audit`。本轮只复用 r238 的精确 `--card` 只读审计，不修改代码、模型、投影、候选、Community 或部署。允许读取 r187、`ZSOF-4P.pdf` 的数据库编码缓存及同跑道 `ZSOF-5C/5D/6B.pdf` 仪表图缓存；禁止读取参考、Fenix、OCR 或候选内容。
- 真实报告为 `diagnostics\r239-zsof-r33-exact-iap-primary-source-audit-20260819.json`。直接数据库页 `Terminal\ZSOF\ZSOF-4P.pdf` 第 1 页 SHA-256 `14eb661a95735d30075faa643834229de102193f0dd7bea4d31e65cfb325835e` 有 5 条 `R33` 进近过渡腿（`OF105/OF106 -> OF104 -> OF103`），主进近和复飞均为零；模型还有来自另一页的 `OF108` 过渡，但不属于本精确来源页。
- 三张缓存验证的同跑道仪表图均不匹配 `R33`：`ZSOF-5C.pdf`（SHA-256 `3ecbe812d33568de83cc6abd52dc55f4b33bd4c23e3e91789d9bc714c5e08f29`）标题候选仅为 `I33/I33-Z`，直接角色 `OF103/IF`、`OF105/OF106/OF108 IAF`；`ZSOF-5D.pdf` 仅为 `I33/I33-Y`；`ZSOF-6B.pdf` 仅为 `D33`。因此不存在匹配 `R33` 的标题候选，更不存在可关联的数据库主段或主段角色交集。
- 处置为 `unresolved_direct_database_evidence_inconclusive`、`projection_allowed=false`。不得根据同跑道、`OF103`/`OF105` 等过渡腿与图页角色、RNAV ILS 图题或参考差分发明 `R33` 主进近。模型、BGL、候选、Community 和部署不变；r188/r189 自重放仍 `29/29`，参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 本轮无代码变化；完整回归、提交前检查和文档提交必须在结束前完成。
- 下一项唯一任务：按稳定排序对尚无精确补充审计的 `ZSWY:I03` 建立同样的精确来源卡。必须分别核对数据库主段、候选图标题、缓存直接角色和固定点；无唯一来源时保持拒绝。

## 2026-08-19 r240 ZSWY I03 精确 IAP 主段来源审计

- 实验编号：`r240-zswy-i03-exact-iap-primary-source-audit`。本轮只复用 r238 的精确 `--card` 审计，读取 r187、`ZSWY-4Z03.pdf` 数据库编码缓存及同跑道 `ZSWY-5A/5B/6/9A/9C.pdf` 仪表图缓存；不读取参考、Fenix、OCR 或候选内容，不修改代码、模型、投影、Community 或部署。
- 真实报告为 `diagnostics\r240-zswy-i03-exact-iap-primary-source-audit-20260819.json`。`Terminal\ZSWY\ZSWY-4Z03.pdf` 第 1 页 SHA-256 `f8f8fe6c50e78eb0d46e9b1a10e31ba27fd0f1ade180cebaae65bbda2f60820c` 有 `I03` 的 17 条进近过渡腿，主段与复飞均为零；该页另有 `R03` 的 15 条过渡腿，不能跨标签混用。
- 缓存验证的 `I03` 标题兼容图恰有两张且角色不一致：`ZSWY-5A.pdf`（SHA-256 `7c91fd121ce3681727687b58942e4ee3a6c503bcd8e6b07936d941f431f933bd`）为 `I03/R03/I03-Z/R03-Z`，直接角色 `WY503/IF`、`WY644/WY805/WY814 IAF`；`ZSWY-5B.pdf`（SHA-256 `1b226e1d07d44dce5439cff8d1bf2ddbb3e9415715823220f9d716b127782e05`）为 `I03/I03-Y`，直接角色 `WY805/WY814/WY820 IAF`。`ZSWY-6/9A/9C.pdf` 不匹配 `I03`。两张兼容图既不能唯一归属，也没有可与数据库主段相交的角色。
- 处置为 `unresolved_direct_database_evidence_inconclusive`、`projection_allowed=false`。不得把任一图题、同跑道、`WY805/WY814` 等重叠 IAF、`WY503/IF`、同页 `R03` 过渡或缺失的复飞拼接为 `I03` 主进近。模型、BGL、候选、Community 和部署不变；自重放仍 `29/29`、参考一致仍 `0/29`、`deployable=false`，字节收敛未推进。
- 本轮无代码变化；完整回归、提交前检查和文档提交必须在结束前完成。
- 下一项唯一任务：按稳定排序对尚无精确补充审计的 `ZUAL:I15` 建立同样的精确来源卡。必须分别核对主段、过渡、复飞、标题、缓存角色和固定点；无唯一来源时继续拒绝。
