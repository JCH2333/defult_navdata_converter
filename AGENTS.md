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
- 默认通用数据导航台防重（2608R1，证据：424 `VOR.csv` 与经来源校验的官方 VOR/NDB 索引，2026-08-12）：424 与官方记录的 `region` 不可单独作为物理身份键。默认覆盖层先保留区域严格差分报告，再对其“缺失”项按类型、标识、频率和不超过 `0.25 NM` 的坐标作全索引物理匹配；不同区域但唯一物理匹配时必须抑制输出，多个不同实体命中时必须使选择验证失败。该规则只消除已存在的官方实体，绝不从参考成品补写内容。回归：`test_default_navaids.py`、`test_candidate_suppresses_cross_region_official_navaid_duplicate`。
- 默认通用数据导航台区域码（2608R1，证据：424 `VOR.csv`/`NDB.csv` 的 `CODE_FIR` 与服务机场字段全量审计、r39 只读逻辑身份差分，2026-08-14）：当导航台带有非空且可映射的 `CODE_FIR` 时，必须以该 FIR 映射 MSFS `region`；服务机场 ICAO 前缀只能在 `CODE_FIR` 为空时回退使用。当前全量审计发现 63 条 VOR 和 4 条 NDB 的两个字段映射不同，例如 `ALS/ZBES/沈阳情报区` 必须为 `ZY`。未知的非空 FIR 必须拒绝，不能悄悄回退到机场前缀。回归：`test_navaid_country_prefers_explicit_fir_over_serviced_airport`、`test_load_naip_recovers_blank_route_endpoint_firs_from_matching_424_records`。
- 默认通用数据 NDB 修订投影（2608R1，证据：424 `NDB.csv` 与经来源校验的官方 NDB 索引，2026-08-12）：仅当直接来自 424 `NDB.csv` 的记录以相同区域、标识、频率和不超过 `0.25 NM` 的坐标唯一匹配官方实体，且坐标、磁差、高程或可表达名称存在差异时，才必须把该 424 原始 NDB 作为覆盖修订投影；官方索引只用于确认物理身份和记录差异，不能反向提供字段。无差异的实体不重复写出，VOR 属性差异仍仅报告、不得借此规则输出；任何严格或物理身份歧义仍会使导航台选择不通过验证。回归：`test_default_selection_projects_source_backed_ndb_property_correction`、`test_default_selection_requires_direct_ndb_csv_provenance_for_correction`、`test_candidate_projects_source_backed_ndb_property_correction`。
- 默认通用数据官方 NDB 保留投影（2608R1，证据：经来源校验的官方 `nav-base`/`nav-jepp` NDB 索引、424 `NDB.csv` 全量物理匹配审计与最小 fixture，2026-08-13）：中国区域官方 NDB 必须在覆盖层中恰好表达一次。直接 `NDB.csv` 的唯一、同区域物理匹配且带可表达属性变化时由 424 修订替换；所有其余中国区域官方 NDB 以原官方字段重新投影为 `official_baseline_preservation`，424 无匹配、跨区域匹配、无变化或来源不满足修订条件时都不得臆造 424 覆盖。424 新增设施仍标记 `raw_424_addition`。单条 424 NDB 对多条官方实体、或多条不同 424 物理身份对同一官方实体时，必须清空本批导航台输出并标记不通过验证；磁差/高程缺失等不能无损投影的官方 NDB 同样拒绝。回归：`test_default_navaids.py` 官方保留、同标识不同实体、跨区域和歧义 fixture，以及 `test_candidate_projects_verified_official_baseline_ndb_preservation`。
- 默认通用数据 SDK 导航台身份冲突（2608R1，证据：Package Tool 实际错误、参考覆盖包 `00_enroute.bgl` 的只读 XML 读取和 424 `NDB.csv` 行 57，2026-08-13）：`NDB/GJ/ZG/245 kHz` 的 424 坐标（`N280426 E1121241`）与官方基线坐标相距约 `0.63 NM`，但 SDK 仍将二者视为同一输出身份并拒绝重复写入；参考覆盖层保留官方基线实体。适配器对该完整 2608R1 来源键使用 `official_baseline_precedence`，抑制 424 新增并在报告中记录冲突；任何未登记的同类冲突必须保持 `unresolved`、清空导航台输出并使验证失败。回归：`test_default_selection_uses_verified_official_precedence_for_2608_gj_conflict`、`test_default_selection_rejects_unlisted_sdk_identity_conflict`。
- IAP 来源审计（2608R1，证据：424 CSV/PDF、版本 34 PDF 证据缓存的冷读与热读、`tests/test_iap_coverage.py` 及既有 IAP 角色测试，2026-08-13）：743 个 IAP 程序分组中 665 个具有唯一且非空的主进近数据库编码段；606 个分组的图页角色已安全利用，其中 373 个由唯一图页确定、233 个由唯一 `MAP/MAPT` 终点完成多图消歧，1 个只有唯一图页但没有可用角色标记。56 个分组存在多图歧义，2 个没有匹配图页，78 个没有唯一主进近编码段，未决分组合计 136。角色证据计数为 `IAF=1238`、`IF=604`、`FAF=557`、`MAP=1`、`MAPT=547`；未决分组必须拒绝写入不完整进近语义并保留报告计数。
- Navdatareader 语义差分（2608R1，证据：读取器 SQLite 实际 `vor`、`ndb`、`waypoint`、`airway` schema 与最小 SQLite fixture，2026-08-12）：诊断器必须以 SQLite `mode=ro` 打开候选和参考，执行完整性检查，并按稳定逻辑身份报告严格行数、候选新增、候选缺失、字段差异和逻辑身份歧义。报告只能含逻辑身份、字段名、数量和不可逆摘要，不得输出参考坐标、频率、名称或其他可反向写入的字段值；空值与文本混合的身份键也必须确定性排序。回归：`test_semantic_diff.py`。
- `WaypointLookup` 的主键不是单独的 `ID`；直接连接会把中国程序腿从 69795 条错误展开到 70642 条。加载器必须先按 waypoint ID 归一国家码，对应回归测试为 `test_fenix_loader_uses_fenix_content_and_raw_route_model`。
- 全量 `china-navdata.xml` 为 544433 字节，并通过 SDK `bglcomp.xsd`。没有 BGL、`bglIndex.bout` 和两包元数据时，验证器必须返回 `valid=false`，即使显式允许测试版也不得部署。
- 最小回归覆盖 AIRAC 周期、确定性 XML、SDK 字段格式、候选包完整性、更新版本排序和不完整测试候选的部署拒绝。
- 来源覆盖率限制（2608R1，证据：2026-08-14 r38 真实构建与只读 Navdatareader 语义差分）：候选覆盖层读取为 VOR 120、NDB 133、航路点 2519、航路 4300；参考覆盖层为 VOR 135、NDB 143、航路点 3266、航路 4614。参考侧存在一批逻辑设施标识未能以当前 VOR/NDB 424 加载记录或官方索引的同一物理身份证明。它们必须继续追溯到允许的 424 结构化来源；不得从参考 BGL/SQLite 反向回填。未完成来源证明前，字节级参考一致性与部署均不成立。
- 实机验证仍须检查 ZBCF、ZUNZ、ZUUU 的机场、跑道、SID/STAR/IAP，以及退出飞行和退出模拟器。完成前不得创建正式 Release。
