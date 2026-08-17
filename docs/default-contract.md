# 默认通用数据 2608R1 契约

## 输入职责

- 主内容来源：`424源数据\2608\2608` 中的结构化 CSV/PDF，负责机场、跑道、ILS、终端航点、SID、STAR、IAP、航路与等待航线。
- Fenix `nd.db3` 不参与默认通用数据转换；Fenix 适配器代码仅保留为历史回归材料。
- 目标基线：Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`。
- 只读参考：`424源数据\2608\Default navdata 2608R1`。

内容来源、目标基线和参考成品不得互相替代。

官方索引是“官方基线可证明查询”的只读派生产物，不是内容来源。用于导航台差分或
航路端点区域恢复前，必须验证 VOR、NDB、WAYPOINT 三类读取器记录都能通过
`file_id -> bgl_file.filepath -> 中性镜像 -> 当前官方 BGL` 回溯。索引侧车还必须记录
三类行数、来源统计和官方双包树指纹；旧版或不完整的侧车不得复用。

对于 2608 `DESIGNATED_POINT.csv` 的指定点，源加载器优先使用严格匹配
`Z[A-Z]{3}` 的四位中国 ICAO `SERVICED_AIRPORT` 前两位作为区域键；这是源表
中最具体的归属字段。无有效服务机场时才使用首个 `CODE_FIR`、既有空 FIR 覆盖或
FIR 多边形恢复。该规则只生成区域键，不复制官方航点记录。2026-08-14 对 r54
“指定点区域不同”的 335 项审计中，12 条带严格有效服务机场：9 条的只读参考
逻辑区域与服务机场前缀一致，3 条与原区域一致，没有第三方区域反例。此前空 FIR
且带服务机场的 12 条中，10 条可被已验证官方航点索引唯一匹配，且区域均与服务
机场前缀一致；`P216 -> ZUHY` 与 `P394 -> ZYJM` 没有官方索引匹配，但仍可由
严格源规则确定为 `ZU` 与 `ZY`。不符合严格格式的服务机场值不参与该优先规则。
自动化覆盖：`test_waypoint_country_prefers_valid_serviced_airport_over_fir`、
`test_load_naip_uses_strict_serviced_airport_prefix_for_blank_waypoint_fir`。

对于严格服务机场、显式 FIR 和既有边界覆盖均不能恢复的空区域指定点，加载器可只读
使用当期 424 `AIRSPACE.csv` 中 `CODE_TYPE=FIR` 的 FIR `CODE_ID` 与
`AIRSPACE_BORDER_VERTEX.csv` 中按 `NO_SEQ` 排序的边界顶点。仅当点唯一位于一个
中国 FIR 多边形内，且到该 FIR 边界的最短大圆距离至少为 `5 NM` 时，才可使用
`CODE_ID` 前两位作为区域键；重叠、边界 `5 NM` 内、多边形外、顶点不足或坐标异常
的 FIR 都必须保留为空。该规则只恢复区域键，不能复制任何官方记录或参考 BGL 内容，
且恢复计数必须写入 `model.source_fir_region_resolution` 和候选报告，随后才能通过
同源 `DESIGNATED_POINT.csv` 身份恢复匹配的 `RTE_SEG.csv` 航路端点。2608R1 的
真实只读加载得到 9 个 FIR、多边形顶点 150 个；175 个剩余空区域指定点中恢复 124，
13 个边界附近、38 个多边形外、0 个歧义。自动化覆盖：
`test_load_naip_recovers_blank_waypoint_fir_only_when_source_geometry_is_unambiguous`。

对于上述来源规则仍为空、且连接到航路的指定点，可继续从同周期
`RTE_SEG.csv.Airspace_Remark` 恢复区域，但仅限可直接回链到
`AIRSPACE.csv` FIR 标题的 ACC 名称。解析仅标准化 ACC 名称前的精确边界词
`以上` 或 `以下`，例如 `以下广州ACC` 归一为 `广州`；归一后的名称必须唯一匹配
`TXT_NAME` 去除 `飞行情报区` 后的 FIR 名称。一个指定点关联到的全部非空 ACC 名称
都必须可映射且落到同一地区，才可恢复该点和同源精确身份的航路端点；未知 ACC、
多个地区、无 ACC 或未连接航路一律保持为空。该规则只读取 424
`AIRSPACE.csv`/`RTE_SEG.csv`，不读取官方索引、参考成品或 Fenix。2026-08-17 的
2608 全量复核得到 9 个可映射 FIR/ACC 名称；FIR 几何后的 51 个空区域点中，18 个
由该规则恢复，30 个因未知 ACC、2 个因多地区、1 个未连接航路而继续拒绝。r96
完整构建与 r95 的 2,258 个 BGL SHA-256 全部一致，说明该“以下”前缀修正是当前周期
的无内容变化解析防护，不能据此宣称字节差分收敛。自动化覆盖：
`test_load_naip_recovers_blank_waypoint_region_from_unambiguous_source_acc`。

### Navdatareader 语义差分

候选和参考覆盖包可以分别由 Navdatareader 解析为 SQLite 后，使用
`semantic-diff` 进行只读诊断。首批固定比较 `vor`、`ndb`、`waypoint`、`airway`
四张表，并按稳定逻辑身份统计严格相同、候选新增、候选缺失、字段差异和无法唯一
配对的逻辑身份。浮点读取值按六位小数归一，避免 SQLite/读取器的微小二进制误差
遮蔽真实内容差异。

该诊断报告只能输出逻辑身份、差异字段名、行数和不可逆摘要；参考 SQLite 的坐标、
频率、磁差、高程、名称、航路端点等值不得写入报告，更不得被用作候选投影输入。
它用于定位需要回到 424 CSV/PDF 继续取证的缺口，不构成参考成品的反向内容来源。

读取器的 `bgl_file` 登记数必须与本次请求的 BGL 数精确相等。2608R1 的 r67 主导航
包实测对 `*.bgl` 仅登记 3/11；单 BGL 只有 `00_enroute.bgl`、`ZG_airports.bgl`、
`ZJ_airports.bgl` 在候选和参考侧都达到 1/1。它们可用于局部、只读诊断，不能合并
为完整主包或双覆盖包结论；其余八个机场分区在获得完整登记前不得参与语义比较。
对于 `00_enroute.bgl`，不得向 `read-package` 传入 `--objects AIRWAY`：2608R1 的
r67/r69/参考受控读取表明，这个外部读取器过滤会产生 `bgl_file=0`，而不带对象过滤
时同一文件稳定登记为 1/1。航路诊断应先读取完整单 BGL SQLite，再使用
`semantic-diff --tables airway` 限定比较表。

对于 `RTE_SEG.csv` 或 `DESIGNATED_POINT.csv` 中未给出区域码的记录，默认适配器可以
查询该可信索引，但查询结果仅能填入区域键，不能把官方记录复制进模型。恢复必须同时
满足端点类型、标识一致，坐标在 `0.01 NM` 内，且命中的官方区域唯一；VOR、NDB、
指定点分别只匹配相应表。歧义、无匹配、无坐标或未知端点类型一律保留为空并进入
转换报告，随后由 BGL 投影器跳过无法满足 SDK region 契约的航路段。

### 导航台物理身份防重

424 导航台的 `CODE_FIR` 或由服务机场推导出的区域键不是默认覆盖层的唯一物理身份。
为保留诊断能力，适配器先按区域执行严格官方差分；仅对这个差分判定为缺失的记录，
再在经来源校验的官方索引中按以下条件查询物理同一性：类型、标识、目标频率一致，
坐标距离不超过 `0.25 NM`。若得到唯一官方实体，即使区域键不同也必须抑制覆盖输出；
若得到多个不同实体，整个导航台选择即为未验证，不能投影任何导航台。

424 `VOR.csv`、`NDB.csv` 的 `CODE_IN_AIRWAY`、`PURPOSE`、`IS_REP_ATC`、
`ROUTE_RESTRICT`、`IS_TRANS_POINT`、`IS_BORDER_POINT`、`SERVICED_AIRPORT` 与
`CODE_FIR` 必须随中间模型保留，并在候选报告中记录选择理由。它们是后续从原始
424/PDF 补充默认覆盖层选择规则的证据，不允许使用参考 BGL 的设施名单反向填充。

### 导航台区域冲突

当导航台的 `SERVICED_AIRPORT` 前缀与非空 `CODE_FIR` 映射不同，不能假定任一字段
总是目标覆盖层的区域键。2608R1 的 54 条 VOR 和 4 条 NDB 冲突审计中，VOR 参考
逻辑身份有 23 条使用服务机场前缀、5 条使用 FIR、26 条两者均未出现；4 条 NDB 都
使用服务机场前缀。它们的 `CODE_IN_AIRWAY`、`PURPOSE`、`IS_REP_ATC`、
`ROUTE_RESTRICT`、`IS_TRANS_POINT`、`IS_BORDER_POINT` 组合没有可用区分力。

因此适配器保持 `r39` 的服务机场优先保守基线。不得把“所有显式 FIR 优先”或从
参考身份导出的单条例外写入转换逻辑。未决记录只能作为来源取证缺口报告，等待能从
当期 424/PDF 独立复现的规则。

### NDB 原始修订

当一条直接来自 424 `NDB.csv` 的记录已经在经来源校验的官方索引中唯一匹配到同区域、
同标识、同频率且坐标不超过 `0.25 NM` 的实体时，官方存在并不代表无需写出覆盖。若
424 原始记录与官方实体在可投影字段存在差异（坐标、磁差、高程或可表达名称），默认
适配器必须把该 424 NDB 作为“原始修订”写入覆盖 BGL。官方记录仅用于证明同一物理
实体和审计字段差异，输出字段始终来自 424；无差异记录不重复输出。

该规则目前仅适用于 NDB。VOR 的属性差异继续在报告中保留，直到有独立的 424/PDF
来源规则证明应覆盖，不能从参考 BGL 的结果反推。严格匹配或跨区域物理匹配存在多
实体歧义时，整个导航台选择仍不通过验证且不得投影任何导航台。

## AIRAC

- 周期：2608。
- Revision：1。
- 开始日期：`20260806`。
- 结束日期：`20260903`。
- SDK `AiracCycle.cycleNumber`：`08`。

## 覆盖包

参考成品包含：

- `zzz-pmdg-china-navdata`
  - `scenery/pmdg-china-navdata/00_enroute.bgl`
  - `ZB/ZG/ZH/ZJ/ZL/ZP/ZS/ZU/ZW/ZY_airports.bgl`
- `zzz-pmdg-china-navdata-airport-patch`
  - `scenery/pmdg-china-airport-patch/`
  - 十个对应分区机场 BGL

每个包都必须包含：

- `bglIndex.bout`
- `layout.json`
- `manifest.json`
- `ContentInfo/<包名>/ContentHistory.json`
- 至少一个可读取的 BGL

## SDK 编译契约

2026-08-11 的本机验证环境：

- MSFS 2024：`1.7.35.0`
- SDK：`1.5.7`
- 编译入口：`C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`
- 平台：Steam

已确认：

1. `fspackagetool.exe <项目.xml> -nopause -rebuild -forcesteam` 会启动游戏的 `BuildAssetPackages` 模式。
2. Package Tool 会生成 BGL、`bglIndex.bout`、布局、清单和 ContentInfo。
3. 项目 XML、PackageDefinitions 和 PackageSources 必须先镜像到纯 ASCII 路径。
4. 包装器可能因附着竞态先返回代码 1，但后台游戏仍会完成构建；应等待新启动的模拟器进程退出，再检查实际产物。
5. 构建前若已有 `FlightSimulator2024.exe`，必须拒绝运行。

对应自动化测试：

- `test_package_tool_project_is_deterministic`
- `test_package_tool_stages_project_in_ascii_path`

## 当前数据模型

### 导航台区域键

424 的 VOR/NDB 如有有效中国 `SERVICED_AIRPORT`，默认通用数据适配器必须以该 ICAO 前缀作为区域键。这是 FIR 边界导航台唯一可证明的机场侧物理归属。没有服务机场时，才可使用单一 `CODE_FIR` 的映射；跨区域的多 FIR 不得取第一个字符串，必须拒绝。该规则只使用当期 424 字段。

截至 2026-08-15，转换器只读加载 `424源数据\2608\2608` 的 CSV/PDF，并使用
版本 `34` 的本地 PDF 证据缓存复核，得到：

- 10,302 个按程序类型、跑道和过渡分组的终端程序段。
- 743 个 IAP 程序分组中，665 个具有唯一且非空的主进近数据库编码腿；其中 642 个
  分组的仪表进近图角色已由唯一图页、唯一 MAP/MAPT 终点、唯一多角色证据，或严格
  占优的多角色证据安全消歧，1 个分组有唯一图页但没有可用角色标记，20 个分组仍有
  多图歧义，2 个分组
  没有匹配图页，50 个分组没有唯一主进近编码段；另有 28 个无主段分组是同页后缀
  进近已消费的共享过渡/复飞段，不列为未决。未决分组合计 72。报告将角色证据、
  完整数据库腿和未决分组分开统计，
  不再把 2,186 个图页全部计为“未解析程序”。
- 1,297 条机场等待航线。
- 0 条因等待固定点无法从 424 数据唯一定位而被拒绝的记录。
- 424 结构化来源当前包含 2,158 个航点和 4,446 条航路段。

默认通用 BGL 的 VOR/NDB 显示名以 424 原始中文 `TXT_NAME` 为内容来源，并在
目标适配器中投影为无分隔的大写拼音；这不是对源模型的改写。2608R1 参考 BGL
逐条对照确认 `霍林郭勒`、`库尔勒`、`阿拉尔`、`克拉玛依`、`吐鲁番`、`长武`、
`长治`、`昌都` 需要使用既定航空拼写而非逐字拼音库默认读音。对应回归测试为
`test_enroute_projection_uses_verified_default_navaid_name_exceptions`。不属于名称
转写的特殊导航台记录继续按设施集合差分处理，不能借此规则反向固化参考 BGL 内容。

等待航线的唯一内容来源是终端数据库编码页中明确印刷的 `HM`、`HF` 或 `HA`
行及其 `RWY...等待` 标题。解析器保留固定点、入航向、左右转、最低高度、速度
限制、适用跑道和标题中的出航时间；只有当固定点可由机场终端坐标页、
`DESIGNATED_POINT.csv`、`VOR.csv` 或 `NDB.csv` 唯一定位时，才生成
`HoldingPattern`。不明确的固定点必须记入拒绝记录，不能猜测坐标，也不能从
Fenix 或参考 BGL 回填。

等待表与 SID/STAR/IAP 的程序编码表是不同的语义表面。解析器进入等待标题后会
停止普通程序腿归属，直到观察到下一条程序标题；这避免把跑道编号误当作程序名称。
对应回归测试为 `test_database_holding_titles_keep_time_and_do_not_become_procedure_legs`
和 `test_airport_projection_emits_source_backed_holding_pattern`。

PDF 缓存载荷带有提取器版本。修改可影响证据解释的规则时，必须递增
`_EVIDENCE_CACHE_VERSION`，并以新缓存进行冷读与热读一致性复核；不得依据旧缓存
中的统计或程序分类作出发布、部署或数据覆盖决定。

IAP 覆盖报告由 `iap_coverage.version=14` 标记。所有角色投影必须满足：数据库编码页
提供有序腿，仪表进近图页提供明确角色，且同一机场、跑道、程序标签的图页唯一；多图
时优先要求主进近最后定位点在恰好一张图上明确为 `MAP/MAPT`。若该定位点不能消歧，
仅当恰好一张候选图页对至少两个不同数据库腿给出 `IAF`、`IF`、`FAF`、`MAP` 或
`MAPT` 的明确角色，至少一个角色为 `FAF`、`MAP` 或 `MAPT`，且其他候选图页没有
任何同腿角色证据时，才允许消歧。若其他候选存在同腿角色证据，则只有该候选图页的
不同数据库腿角色数量严格高于每一张其他候选图页时才允许消歧；相同数量一律拒绝。
其余分组仍可保留已解析的来源腿，但必须在
`unresolved_groups` 中列出，不能猜测图页或从参考成品回填程序语义。经 OCR 共识实际
放行的图页必须另列入 `ocr_role_selections`，记录程序键、选择方法、候选页数、图页来源
及参与选择的数据库腿角色；该审计字段不构成新增程序、航段或图页匹配的依据。

对仅由 OCR 发现的图页角色，必须先对至少三份独立、完整缓存重新审计：源 PDF 路径和
SHA-256、OCR 运行时标识、命令、后端、模式、图像预处理、渲染比例、角色-航点对和相邻
关系必须完全一致。通过后仅可用于已有 `ambiguous_chart` 分组内、同一 424 主进近腿与
同一源 PDF 哈希绑定的候选页唯一消歧；不得新增主进近、航段或图页匹配，也不得解除
`no_unique_primary`、`empty_primary` 或 `no_matching_chart` 拒绝。自动化测试：
`test_iap_ocr_consensus_loads_only_unanimous_roles_for_matching_chart_pages`、
`test_iap_coverage_uses_consensus_ocr_mapt_only_for_one_matching_chart`、
`test_iap_coverage_keeps_two_consensus_ocr_mapt_candidates_ambiguous` 和
`test_bgl_iap_chart_roles_reuses_consensus_ocr_selection`。

上述 OCR 限制不排除由同一 424 PDF 直接文本完整证明的窄例外：当直接 PDF 角色仍不能唯一
选择图页，且已有两个以上标题候选，或通常图题匹配为空且同机场同跑道的图题为未标变体
`RNP ... (AR)`、主进近数据库标签为 `R<跑道>-...` 时，若恰好一张候选图页直接抽取的
`waypoints` 包含该主段所有至少两个不同的非空数据库固定点，可关联该图页。该规则在 OCR
之前执行，不使用 OCR、参考成品或 Fenix 数据；固定点缺失、少于两个、图题已有变体的无
匹配情形或多个完整候选仍为未决。覆盖报告将此类
选择写入 `source_fixed_point_selections`，供构建和差分审计。图页关联本身不能制造角色
证据：只有图页的直接 `IAF`、`IF`、`FAF`、`MAP` 或 `MAPT` 标识与主进近腿实际相交时，
才可计入角色覆盖或投影到 BGL。

另一项更窄的 424 直接文本规则只适用于彼此标题兼容的多张 RNP AR 图页：每一张候选
图题都必须在 `(AR)` 后印刷至少一个非跑道限定固定点，且恰好一张图题中的限定点与该
有序主进近数据库腿相同，才可选择该图页。候选中任一图不是这种带限定点的 RNP AR 图、
没有命中或有多张命中时一律继续拒绝。该规则不使用 OCR、参考成品或 Fenix，选择必须
写入 `source_title_qualifier_selections`，并且同样只有与数据库腿实际相交的图页角色
可以写入 BGL。自动化测试：
`test_iap_coverage_selects_unique_rnp_ar_title_qualifier_matching_primary_leg`、
`test_iap_coverage_rejects_nonunique_or_mixed_rnp_ar_title_qualifier_matches` 和
`test_bgl_iap_chart_roles_reuse_rnp_ar_title_qualifier_selection`。

另一项同样受限的直接文本规则仅适用于图题没有非跑道固定点限定的 RNP AR 候选：所有候选
都必须为 RNP AR 图，且只有一张图明确把数据库主进近腿标为 `IAF`、`IF`、`FAF`、`MAP`
或 `MAPT`，才可选择该图页。多个候选命中、没有命中、混入非 RNP AR 图或图题含固定点
限定时一律拒绝。选择写入 `source_unqualified_rnp_ar_direct_role_selections`，只投影
与数据库腿相交的直接图页角色；该规则不使用 OCR、参考成品或 Fenix。自动化测试：
`test_iap_coverage_selects_unqualified_rnp_ar_chart_by_unique_direct_role`、
`test_iap_coverage_rejects_qualified_or_nonunique_rnp_ar_direct_role_matches` 和
`test_bgl_iap_chart_roles_reuse_unqualified_rnp_ar_direct_role_selection`。

另一项直接文本规则适用于存在多个标题兼容候选、但恰好一张图的明确 `IAF`、`IF`、`FAF`、
`MAP` 或 `MAPT` 标记与来源主进近腿相交的情形。它不使用 OCR、参考成品或 Fenix，并将
选择写入 `source_unique_direct_role_selections`。RNP AR 候选不得与非 AR 图题混用；
RNP AR 图题中的固定点限定状态也必须在所有候选中一致，且候选标题标准化后必须彼此
不同。多个候选命中、没有候选命中、重复标题或混合 AR 类别一律继续拒绝。自动化测试：
`test_iap_coverage_selects_unique_direct_source_role_without_ar_title_mixing` 和
`test_iap_coverage_selects_uniform_qualified_rnp_ar_by_unique_direct_role`。

若候选图的直接“固定点、角色”集合中恰好一张严格包含每一张其他候选的集合，且仍满足
标题不同、RNP AR 分类一致与限定状态一致的条件，可选择该图并记录为
`source_dominant_direct_role_selections`。相同集合、不可比较集合、重复标题或混合类别
一律拒绝。该规则不使用 OCR、参考成品或 Fenix。自动化测试：
`test_iap_coverage_selects_strict_direct_role_superset` 和
`test_iap_coverage_rejects_incomparable_direct_role_sets`。

当此前所有直接角色、固定点和 RNP AR 消歧均无法选择时，数据库主标签以 `R` 开头、
候选恰有一张非 AR 且不含 `ILS` 的 `RNP` 图和一张非 AR 的 `RNP ILS` 图时，可选择
前者并记录为 `source_plain_rnp_title_selections`。含 AR、额外候选或非 `R` 标签一律
拒绝；两图与来源腿相交的直接角色-固定点集合还必须相同且非空。该规则仅使用数据库
标签和图页直接角色，不读取 OCR、参考成品或 Fenix。自动化测试：
`test_iap_coverage_prefers_plain_rnp_title_after_stronger_rules_fail` 与
`test_bgl_iap_chart_roles_reuse_plain_rnp_title_selection`。

覆盖报告的 `role_evidence_used`、`role_evidence_counts` 和角色类状态同样只统计上述交集。
同页的共享过渡、复飞或其他路径角色不能因图页已经选中而计入当前主进近，更不能生成
BGL 标记。

不带后缀的 IAP 基础标签可能只包含共享过渡或复飞段，而 `-X/-Y/-Z` 等唯一主进近段会
在 BGL 投影中消费它们。映射只接受两类直接 424 数据库编码证据：同一源页恰有一个同
机场、同跑道的后缀主段，或基础段在连续的数据库表顺序中紧邻同跑道后缀主段，且过渡
只能向后、复飞只能向前归属。遇到不同机场、跑道、基础标签族、非 IAP 段或多个候选时
立即拒绝，不能依据 OCR、参考成品或图形推断继续搜索。只有基础标签组的每个来源段均
获得唯一映射时，覆盖报告才计入 `shared_section_groups` 而非未决；每条映射必须写入
`shared_section_assignments`，供 BGL 投影和审计共同复用。

## 验证与发布

候选至少通过：

1. 官方双包基线 SHA-256 树保持不变。
2. SDK XML 校验和 Package Tool 构建。
3. 两个覆盖包结构与索引完整性。
4. BGL 分区、内容结构与参考成品差分。
5. 参考目录逐文件字节比较。
6. ZBCF、ZUNZ、ZUUU 的机场、跑道、SID、STAR、IAP 实机验证。
7. 退出飞行和退出模拟器稳定性验证。

实机验证完成前只允许测试版，不创建正式 Release。

### Community 覆盖门禁

`build` 生成的候选固定为 `test_build=true`，即使官方索引、导航台选择、区域恢复和
两个覆盖包的本地结构都已通过，也只能用于隔离分析，不能通过任何命令行或 GUI 开关
覆盖 Community。验证器分别报告以下状态：

1. `local_contract_verified`：官方索引、导航台选择、区域恢复和双覆盖包结构通过。
2. `byte_equal_reference`：两个中国覆盖包均与只读参考成品逐文件 SHA-256 一致。
3. `flight_validation_verified`：ZBCF、ZUNZ、ZUUU 的机场输入、跑道、SID/STAR/IAP，及退出飞行、退出模拟器均已完成并登记。

只有 `status=release`、`test_build=false` 且以上三项均通过时，验证器才会给出
`deployable=true`。部署器不再提供 `--allow-test-build` 或 GUI 旁路；缺少其中任何一项
都会在创建备份前拒绝覆盖 Community。

## 当前限制

- 当前候选已经可以生成两个具有 BGL、`bglIndex.bout`、`layout.json`、
  `manifest.json` 和 ContentInfo 的测试覆盖包，但与参考成品同名文件尚未逐字节
  收敛。
- 2026-08-17 的 r69 已完成 GeneralDoc ENR 3.2 A/B/G/H/J/R/V/W/X 九册、455 页的
  可复用本地 OCR 审计：4,069 条发布最低高度中，3,827 条唯一回链到直接
  `RTE_SEG.csv` 并投影，242 条没有直接 424 航段，歧义和冲突均为 0。该规则仅写入
  已回链航段的 `minimum_altitude`，不得由 OCR 新增航路、端点或区域键。r69 的
  `00_enroute.bgl` 受控读取为 VOR `121/135`、NDB `133/143`、航点 `3132/3266`、
  航路 `4401/4614`（候选/参考）；候选仍为测试版。
- 2026-08-14 的当前 `r45` 航路 BGL 只读语义差分为：VOR `121/135`、NDB
  `133/143`、航点 `2519/3266`、航路 `4300/4614`（候选/参考）。14 个参考
  VOR 逻辑身份和 18 个参考 NDB 逻辑身份不在当期 424 的直接 VOR/NDB 表中，
  也没有作为 `RTE_SEG.csv` 的同周期航路端点出现；这些缺口不能由参考成品、
  Fenix 或名称猜测反向补写。另有 6 个 VOR 与 3 个 NDB 仅以不同的 424
  区域键出现，继续按区域冲突契约保守处理。
- 2026-08-14 对 `FLIGHT_AIRLINE_POINT.csv` 和完整终端资料的补充审计表明：
  前者还包含起止点磁差；以唯一标识和频率与已有直接 VOR 交叉时，267 条磁差
  全部一致、没有冲突。但它没有设施类型、坐标或区域，当前 14 个参考缺失 VOR
  也没有可用的唯一磁差匹配，因此不能作为缺失 VOR/NDB 的独立投影依据。后者中
  少数同标识只作为裸程序固定点出现，未同时给出类型、区域和坐标。
- 2026-08-17 的 GeneralDoc 导航台来源复核使用带运行时指纹、页码和 SHA-256
  的本地 OCR 缓存完成。`航路_4.1无线电导航设施——航路.pdf` 的 33 页共解析
  138 条记录，132 条可直接回链到当期 `VOR.csv`/`NDB.csv`，其余 6 条仅为
  可唯一纠正的 OCR 标识误读；不存在未能回链的设施身份。`总则_2.5无线电导航设施表.pdf`
  的唯一页面仅指向 AD 2.19 与 ENR 4.1，未给出设施明细。两份文档都不能作为
  当前 VOR/NDB 缺口的新增投影来源；OCR 只能继续保留为审计证据。
- 2026-08-17 对 `Terminal/ZJHK/海口美兰.pdf` 与
  `Terminal/ZJSY/三亚凤凰.pdf` 建立了同一 `markdown`、3 倍
  `autocontrast-grayscale` 配置的完整 AD 2.19 OCR 缓存，共 66 页，源文件
  SHA-256 分别为 `3ba4d8f7da01ebe56636559708cfadfda23612e9a5dc3347dd0ee6d75161102b`
  与 `89447787350793f90f36c4359f54c080c33e53de5ea5883c51d121ca6eb53e1c`。
  `ad219-ndb-ocr-audit` 仅解析出三亚 `WL/426 kHz`，可唯一回链至
  `NDB.csv` 第 51 行，但该直接记录缺少 `VAL_ELEV`；海口没有可回链 NDB。
  因此参考 `ZJ_airports.bgl` 中的机场作用域 `K/ZJSY` 与 `P/ZJHK`
  不能由允许的 424 CSV/PDF 来源填足名称、磁差、高程与区域，必须保持
  `projection_allowed=false`，不得按参考身份或机场名称硬编码新增。
- 2026-08-17 对 `Terminal/ZGDY/湛江机场.pdf` 以同一可复用设置完成 19 页
  AD 2.19 OCR。审计只解析到 `JX`，当期 `NDB.csv` 没有可直接回链记录，
  因而名称、磁差、高程和区域均未被来源证明。参考 `ZG_airports.bgl` 中的
  `D/P@ZGDY` 也没有由该 CSV/PDF 链支持的身份；不得按参考差分或服务机场
  推断、硬编码这些机场作用域 NDB，继续保持 `projection_allowed=false`。
- AD 2.19 机场无线电导航设施表可提供直接打印的 VOR/DME 标识、频率、坐标和
  明确打印的 DME 天线高程，并作为带页码与 SHA-256 的审计证据保留。它没有可验证的设施
  磁差；2026-08-14 对 346 条可按服务机场关联的直接 `VOR.csv` 记录与
  `AD_HP.csv.VAL_MAG_VAR` 的交叉校验中，3 条相同、343 条不同。机场磁差不得
  代填 VOR 磁差，所以该证据目前不能增加、修订或重区域化任何投影 VOR。完整
  2608 源加载获得 386 条此类证据，53 个唯一物理身份不在直接 VOR 记录中；
  CZW 的 `013°MAG/2000m` 与 HOK 的 `337°MAG/122982m` 是天线相对位置，不是
  磁差或高程，不能误用。
- 本机 WMM-2020/WMM-2025 只可用于诊断，不是 424 磁差的替代来源。2026-08-14
  对 362 条直接 VOR 的扫描中，最佳 WMM-2020/2024 仍只有 37 条在 `0.01°` 内，
  中位绝对误差 `0.0497°`、最大 `2.1818°`；WMM-2025 在 2026-08-06 的中位绝对
  误差约 `0.1191°`。任何 WMM 推导值都不得进入候选 BGL。
- 2026-08-14 的 `r54` 完整只读差分已由 `source-gap-audit-v3` 重新分类。
  它只接受 `read_only=true`、`reference_values_redacted=true` 且所有参考缺失样本
  未截断的 `semantic-diff`，只输出来源类别计数，不能保存或输出参考逻辑身份。
  以 2,158 个 424 结构化指定点与 4,446 条航路段审计，1,032 个参考缺失航点中：
  667 个不在结构化指定点或航路端点中，335 个仅有不同区域的指定点，15 个指定点
  区域未决，15 个仅以不同区域出现在航路端点中。1,214 个参考缺失航路中，607 个
  有同名同序号源段，123 个只有同名不同序号，484 个不在 `RTE_SEG.csv`。全部
  1,354 个 424 `EN_ROUTE_RTE_ID` 与航路名一一对应，且每条源航路的序号与端点均
  连续；默认 BGL 的 `airway_fragment_no` 由投影后连通图生成，不能从参考身份反推
  或硬编码。`FLIGHT_AIRLINE_POINT.csv` 的 390,659 条记录均以端点 ID 回链到直接
  424 点，且全部对应现有 `RTE_SEG` 的正向 263,184 条或反向 127,475 条；对 54 个
  RTE 缺席参考航路名零命中，故该表只能审计既有航路引用，不能作为新增航路来源。
  测试覆盖：`tests/test_source_gap.py`。
- 同次指定点区域审计中，335 个与参考逻辑区域不同的结构化指定点里仅 12 个有
  严格有效的中国服务机场。将服务机场置于 FIR 之前后，9 个与只读参考逻辑区域
  一致、3 个保持原区域，未出现第三方区域反例。因此 `SERVICED_AIRPORT` 是唯一
  可以提高该源侧区域判定优先级的字段；此结论不允许按参考差分反推其他点的区域。
  自动化覆盖：`test_waypoint_country_prefers_valid_serviced_airport_over_fir`。
- 终端坐标页全局航点提升（2608R1，证据：全部 `Terminal/*/Charts.csv` 索引的源
  PDF 坐标页、r70 完整只读加载、`conversion-report.json`、受控 Navdatareader 与
  `tests/test_source.py`，2026-08-17）：加载器在坐标页解析之后、数据库编码腿筛选
  之前执行 `_promote_shared_terminal_coordinate_waypoints()`。全量来源共有 12,991
  个坐标点、12,417 个“区域 + 标识”身份组；只有同一区域、原始标识完全一致且不超过
  8 字符、坐标六位小数一致、至少两个不同机场独立发布、且未被既有规范化全局航点或
  导航台身份占用的组，才可作为全局 `Waypoint` 提升。r70 提升 96 个；明确拒绝
  11,967 个单机场组、79 个多坐标组和 275 个既有全局身份冲突组，标识为空、变体和
  超长均为 0。终端点本身继续保留给机场程序和等待航线；已有 BGL 的动态共享选择会
  因新全局身份存在而避免重复写入。自动化覆盖：
  `test_promotes_shared_terminal_coordinate_waypoint_to_global_model`、
  `test_shared_terminal_coordinate_waypoint_requires_two_airports`、
  `test_shared_terminal_coordinate_waypoint_rejects_coordinate_conflicts`、
  `test_shared_terminal_coordinate_waypoint_keeps_existing_global_identity` 和
  `test_candidate_reports_terminal_coordinate_waypoint_promotion`。
- r70 `00_enroute.bgl` 的单 BGL 受控读取为 VOR `121/135`、NDB `133/143`、航点
  `3139/3266`、航路 `4401/4614`（候选/参考）。完整脱敏差分的来源审计把 1,019 个
  参考缺失航点分为：663 个不在结构化指定点或航路端点中、326 个直接指定点区域不同、
  15 个直接指定点区域未决、15 个仅以不同区域出现的航路端点；1,186 个参考缺失航路
  分为：538 个同名同序号源段已在候选连通图表达、41 个因端点区域为空未投影、123 个
  同名不同序号、484 个不在 `RTE_SEG.csv`。这些分类只用于下一步来源追溯，不能从
  参考 BGL/SQLite 反向补写内容。r70 仍是测试候选，尚未达到字节一致或实机验证门槛。
- `terminal-coordinate-audit`（2026-08-17，证据：完整 r70 脱敏差分、相同的 r35
  PDF 缓存、`terminal-coordinate-r70-reference-coverage-20260817.json` 与
  `test_terminal_coordinate_audit_keeps_source_categories_redacted`）进一步只读审计了
  1,019 个参考缺失全局航点。862 个根本未出现在终端坐标页；146 个只由一个机场
  发布；11 个同一“区域 + 标识”拥有多个源坐标；没有现成全局冲突或额外可提升的
  `terminal_source_promotable` 组。因此跨机场坐标页提升规则在当前 2608 来源上已无
  其他安全扩展空间，不能为了缩小参考差分而放宽单机场或多坐标拒绝条件。
- `general-doc-keypoint-audit`（2026-08-17，证据：完整 r70 脱敏差分、已校验的
  ENR 4.4 OCR 缓存与 `test_general_doc_keypoint_audit_keeps_source_categories_redacted`）
  使用构建同一套 FIR 几何规则复核了 1,019 个参考缺失全局航点。816 个不在关键点
  表中，154 个同名但恢复出的区域不同，39 个在 FIR 边界 5 海里内，9 个在 FIR 外，
  1 个位于重叠区域；没有 `general_doc_source_promotable` 组。因此不得放宽 FIR
  边界、区域或身份冲突规则追随参考差分。
- 对当前剩余 47 个无区域航路端点，`RTE_SEG.POINT_START_ID/POINT_END_ID` 的
  只读回链没有提供新增可投影区域：40 个 ID 指向的当期 424 源点本身仍为空区域，
  6 个端点类型与同 ID 源表类型矛盾，1 个 ID 没有对应源点。端点类型不得跨表放宽，
  该 ID 链只能作为审计证据，不能覆盖既有的类型和区域恢复契约。
- 程序标题分类仍有少量复杂双栏版式和无分隔程序名需要继续以 424 PDF 原文处理。
- 在 `byte_equal_reference=true` 且完成实机验证前，任何候选都不得覆盖
  `F:\games\community\Community`，不得创建正式 Release。
- 2026-08-17 的 r67 单 `ZG_airports.bgl` 完整脱敏差分和来源审计确认：候选/参考航点行数为 `2697/2839`，其中全局航点为 `1320/1384`、机场作用域航点为 `1377/1455`。789 个参考缺失逻辑身份经带 `--check-retention` 的终端坐标页审计后，31 个机场作用域项在同机场 424 坐标页中存在但未被当前程序引用保留规则保留，392 个机场作用域项不在同机场坐标页，335 个全局项不在终端坐标页，31 个全局项只由单一机场发布；经同源 ENR 4.4 关键点 OCR 审计后，423 个仍为机场作用域、366 个根本不在关键点表中。两类审计均没有可自动提升的来源类别。31 个未保留来源点只是下一步来源侧保留规则调查信号，不能据此把全部未引用坐标页条目写入候选。候选侧 647 个额外逻辑身份中，有 290 个同时具有全局与机场作用域版本；但参考 BGL 同样具有两种作用域，不能据此关闭 `duplicate_terminal_waypoints` 或按参考身份删除任何已由 424 证实的记录。字段差异与来源缺口只可继续用于追溯 424 CSV/PDF 的通用规则，不能作为反向收紧投影范围的依据。

- 标准 SID/STAR 航迹表坐标保留（默认通用数据、2608R1，证据：`ProcedureChart.standard_routes` 与 `table_standard_routes` 的完整只读统计、`test_standard_route_table_retains_matching_terminal_coordinate_waypoint`、r78 Package Tool 构建及单 BGL 读取，2026-08-17）：坐标页不是完整航迹来源，但同机场标准程序图中由“航迹简述”表完整列出的顺序标识可与数据库编码腿、等待固定点同等作为保留依据。当前 341 张有完整路线表的标准图中，只有 13 个坐标页标识不在既有数据库腿或等待固定点集合内；标准图角色文本没有额外可保留点，IAP 角色文本虽有 60 个额外点但已由 r75/r77 证明不得单独保留。r78 因此将终端坐标点从 12,523 增至 12,536，保持 21 个 BGL 的本地契约有效；受影响的 `ZG_airports.bgl` 受控读取从 2,697 增至 2,699 个航点且 ILS 保持 51。`ZB/ZH/ZP/ZU/ZW` 单 BGL 读取在 r77 与 r78 中均未登记来源，属于既有离线读取器限制，不能作为成功或失败证据。该规则不得放宽至 IAP 角色、矢量图形或未形成完整航迹表的图页文本。

## AD 2.19 VOR/DME 高程投影结论

AD 2.19 的 VOR/DME 表继续保存为带页码和 SHA-256 的审计证据，但不得新增、重区域化或修改任何 VOR 本体字段，也不得写入默认 BGL 的 `Vor/Dme.alt`。2026-08-14 的 r52 真实 SDK 构建与受控 Navdatareader 差分表明，投影 108 条已匹配 VOR 的 PDF DME 高程后，VOR 严格一致行从 40 降至 36、字段差异从 75 增至 79、含 `dme_altitude` 的差异样本从 27 增至 44。因此该高程不是默认 BGL `Vor/Dme.alt` 的可证明来源。
