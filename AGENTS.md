# Fenix 默认通用数据转换器协作规则

- 所有用户信息使用中文。
- 424 原始 CSV/PDF 与官方 Community 包只作为本地输入，不提交任何导航数据或生成包；Fenix `nd.db3` 不参与本工具转换。
- 默认包必须保留官方 `nav-base`/`nav-jepp` 全球基线，区域覆盖层独立生成。
- 参考成品只读比较，禁止复制参考 BGL 冒充转换结果。
- 没有版本匹配的 Package Tool、没有本地验证或未完成实机测试时，输出只能标记测试版。
- 覆盖 Community 前必须确认 `FlightSimulator2024.exe` 已退出，并备份目标包与元数据。
- 每次代码/文档改动都要提交并推送 Git；未经实机验证不得创建正式 Release。

## 2608R1 已确认契约

- 官方全球基线为 Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`，候选复制后分别有 475 和 1752 个文件，2026-08-11 全量 SHA-256 树比较均字节一致。
- 参考成品不是完整全球包，而是 `zzz-pmdg-china-navdata` 与 `zzz-pmdg-china-navdata-airport-patch` 两个中国覆盖包。
- MSFS 2024 SDK 1.5.7 的正式设施编译入口为 `fspackagetool.exe`。2026-08-11 已用一个机场和一条跑道完成真实构建，生成 BGL、`bglIndex.bout`、布局、清单与 ContentInfo。
- Package Tool 项目必须先镜像到纯 ASCII 暂存路径；中文路径会在游戏命令行中损坏并导致 `Main_Z ProgramInit` 启动崩溃。
- `fspackagetool.exe` 可能因 Steam 进程附着竞态先返回非零代码，但后台 `FlightSimulator2024.exe` 仍在构建；必须等待新进程退出，以实际包产物判定成功后再清理暂存目录。
- Package Tool 启动恢复（2608R1，证据：2026-08-14 的 r35/r37 项目输入逐文件 SHA-256 一致；r37 两次调用均退出代码 1、没有新模拟器进程、没有新 Builder 日志或产物）：仅当首次非零退出、完整启动等待期内未发现新的 `FlightSimulator2024.exe` 时，允许以同一纯 ASCII 暂存项目重试一次。发现新进程时仍只能等待其退出并以完整包产物判定；第二次失败不得继续重试。自动化测试：`test_package_tool_retries_one_startup_failure_without_simulator_process`。
- 内容来源为当期 424 `2608` 原始 CSV/PDF，负责机场、跑道、ILS、终端航点、SID/STAR/IAP、航路和等待航线；官方包只负责全球基线和加载契约。
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
- `WaypointLookup` 的主键不是单独的 `ID`；直接连接会把中国程序腿从 69795 条错误展开到 70642 条。加载器必须先按 waypoint ID 归一国家码，对应回归测试为 `test_fenix_loader_uses_fenix_content_and_raw_route_model`。
- 全量 `china-navdata.xml` 为 544433 字节，并通过 SDK `bglcomp.xsd`。没有 BGL、`bglIndex.bout` 和两包元数据时，验证器必须返回 `valid=false`，即使显式允许测试版也不得部署。
- 最小回归覆盖 AIRAC 周期、确定性 XML、SDK 字段格式、候选包完整性、更新版本排序和不完整测试候选的部署拒绝。
- 来源覆盖率限制（2608R1，证据：2026-08-14 r38 真实构建与只读 Navdatareader 语义差分）：候选覆盖层读取为 VOR 120、NDB 133、航路点 2519、航路 4300；参考覆盖层为 VOR 135、NDB 143、航路点 3266、航路 4614。参考侧存在一批逻辑设施标识未能以当前 VOR/NDB 424 加载记录或官方索引的同一物理身份证明。它们必须继续追溯到允许的 424 结构化来源；不得从参考 BGL/SQLite 反向回填。未完成来源证明前，字节级参考一致性与部署均不成立。
- 实机验证仍须检查 ZBCF、ZUNZ、ZUUU 的机场、跑道、SID/STAR/IAP，以及退出飞行和退出模拟器。完成前不得创建正式 Release。
- 来源缺口复核（默认通用数据、2608R1，证据：2026-08-14 `r45` 当前候选与当前参考 `00_enroute.bgl` 的 Navdatareader 只读语义差分，以及对当期 `VOR.csv`、`NDB.csv`、`RTE_SEG.csv` 的逐身份回查）：候选/参考分别解析为 VOR `121/135`、NDB `133/143`、航点 `2519/3266`、航路 `4300/4614`。其中 14 个参考 VOR 逻辑身份和 18 个参考 NDB 逻辑身份既不出现在当期 424 的直接 VOR/NDB 记录中，也不作为同周期航路端点出现；另有 6 个 VOR 和 3 个 NDB 仅以不同的 424 区域键出现。前一类必须继续追溯到允许的当期 424 结构化来源；后一类仍受已记录的区域冲突规则约束。不得用参考 BGL/SQLite 字段值、Fenix 数据或“按名称猜测”补写这些缺口。自动化保护：`test_default_navaids.py`、`test_semantic_diff.py`；此结论未改变候选内容，继续禁止部署。
- 补充来源审计（默认通用数据、2608R1，证据：2026-08-14 对 `FLIGHT_AIRLINE_POINT.csv` 的全量索引及完整 `load_naip(..., include_terminal_documents=True)` 重建）：航路点表包含名称、标识、频道/频率、起止点磁差和 UUID，但没有可投影导航台所需的类型、坐标和区域；它可对 267 条已有直接 VOR 的唯一标识/频率磁差交叉匹配做到 267 条完全一致、0 条冲突，却不能独立构成设施投影。当前 14 个参考缺失 VOR 均没有该表中可用的唯一磁差记录，不能借此补齐。终端程序腿对少数同标识仅保留裸固定点文本，未同时提供类型、区域和坐标。两类资料均不得独立新增或重区域化 VOR/NDB。
- AD 2.19 VOR/DME 证据边界（默认通用数据、2608R1，证据：2026-08-14 对直接 `VOR.csv` 与同服务机场 `AD_HP.csv.VAL_MAG_VAR` 的全量交叉校验，以及 275 机场真实 `load_naip(..., include_terminal_documents=True)` 加载）：346 条可按服务机场关联的 VOR 中仅 3 条磁差相同、343 条不同；因此机场磁差不能代替设施磁差。真实加载从 AD 2.19 取得 386 条 VOR/DME 证据，其中 53 个唯一物理身份不在当前模型的直接 VOR 记录中。表头中的 `VAR` 不表示每行均给出磁差；CZW 的 `013°MAG/2000m` 和 HOK 的 `337°MAG/122982m` 等字段是天线相对位置，不得误作磁差或高程。AD 2.19 表中直接读取到的 VOR/DME 频率、坐标和明确打印的 DME 高程必须以页码和 SHA-256 保存为审计证据，但在取得当期 424 对设施磁差的独立证明前，不得写入 `model.navaids`、导航台选择或 BGL。自动化保护：`test_ad219_vor_evidence_keeps_direct_facts_without_a_magnetic_variation`、`test_ad219_vor_evidence_does_not_treat_position_distance_as_elevation`、`test_ad219_vor_evidence_is_not_promoted_to_a_navaid`。
- WMM 推导禁止项（默认通用数据、2608R1，证据：2026-08-14 以全部 362 条直接 `VOR.csv.VAL_MAG_VAR` 对本机 `pygeomag` WMM-2020/WMM-2025 扫描）：最佳组合为 WMM-2020、2024 年，仍只有 37 条在 `0.01°` 内，中位绝对误差 `0.0497°`、90 分位 `0.1739°`、最大 `2.1818°`。WMM-2025 在 2026-08-06 时中位绝对误差约 `0.1191°`。两者都不能复现 424 设施磁差，不得用于补写 AD 2.19 缺失 VOR。
## AD 2.19 VOR/DME 高程投影结论（2608R1）

- AD 2.19 继续保留为带页码和 SHA-256 的独立审计证据；不得新增、重区域化或修改任何 VOR 本体字段，也不得写入 `Vor/Dme.alt`。
- 证据：2026-08-14 的 r52 真实 SDK 构建和受控 Navdatareader 差分中，投影 108 条已匹配 VOR 的 PDF DME 高程后，VOR 严格一致行从 40 降至 36、字段差异从 75 增至 79、含 `dme_altitude` 的差异样本从 27 增至 44。故该高程不是默认 BGL `Vor/Dme.alt` 的可证明来源。
- 回归：`test_load_naip_keeps_ad219_vor_evidence_separate_from_direct_vor`、`test_ad219_vor_evidence_is_not_promoted_to_a_navaid`。
