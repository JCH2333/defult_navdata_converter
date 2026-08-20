# 默认通用数据转换器协作规则

## 目标与边界

- 输入内容只来自 `424源数据\2608\2608` 的 424 CSV/PDF 及匹配 `RTE_SEG.csv`。
- 官方 `navigraph-nav-base`、`navigraph-nav-jepp` 和 `Default navdata 2608R1` 只用于模板、加载契约和只读验收。
- Fenix `nd.db3`、参考 BGL/SQLite、参考坐标、参考记录和派生哈希不得作为内容来源。
- `NavModel` 是跨周期、跨格式的唯一内容边界；默认 BGL 只是独立 adapter。
- 所有诊断只输出脱敏结构、计数、哈希和边界，不复制参考导航记录。

## 安全与提交

- 覆盖 Community 或 WASM 前，确认 `FlightSimulator2024.exe` 已退出，并备份数据库、元数据和布局文件。
- 未完成参考字节验收、完整本地验证、备份恢复演练和实机验证时，只能标记测试版，不得部署或创建 Release。
- `output/`、`diagnostics/`、数据库、备份、日志、反编译结果和外部测试包不得提交。
- 每次代码或文档改动都要运行相称测试，提交并普通推送；禁止强推。

## 可复用转换管线

固定流程：

`lock-inputs -> ingest-424 -> evidence-audit -> normalize-model -> model-audit -> project-target -> build-target -> validate-target -> diff-and-audit -> stage-backup-deploy`

每个目标格式独立实现：

1. profile/schema/version 识别；
2. 字段、单位、枚举、NULL/default 和长度映射；
3. 排序、索引、元数据和部署契约；
4. 目标专用验证器、报告和部署器。

适配器不得重新解析 424，不得把其他机模规则写入通用模型。无法无损表达的字段必须显式计数并阻断关键航段静默丢失。转换必须确定性、可重复、尽量幂等。

## 当前权威状态

以本节、当前 Git、可复跑产物和标准 JSON 重读结果为准；旧日志只作索引。

- 冻结模型：`output/intermediate-2608-r187-navaid-label-replay.json.gz`
- 模型 SHA-256：`7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`
- 当前有效参考候选：`output/candidate-2608-default-r188-doviv-replay`，自重放 `29/29`
- 最新实验候选：`output/candidate-2608-default-r347-airport-terminal-waypoints`
- r338 模型计数与冻结模型一致；V111/V162 四条端点区域恢复
- 与参考默认数据字节一致：`0/29`
- `deployable=false`
- 当前完整回归：`506 passed`（2026-08-20）
- 当前未部署 Community、未实机验证、未创建 Release。

### r338-r343 阶段结论

- r338 修复 GeneralDoc 航点污染直接 `RTE_SEG.csv` 端点区域证据；V111/V162 四条端点恢复，模型计数未变。
- r341 全量 BGL 结构审计：29/29 文件不一致；机场候选缺少参考中的 `0x17`，且 `0x13/0x22` 规模明显更小。
- r342 SDK 作用域探针触发 `DUPLICATE WAYPOINT`，未获得可授权的 `Waypoint` 结构映射；禁止据参考 Section 反推对象或修改正式 adapter。
- r343 将终端航点移到 `FSData` 根级，并按区域/标识/坐标确定性去重；48 个 BGL 测试、500 个全量测试通过。收敛审计仍为参考 `0/29`，21 个目标 BGL 全部不同；该实验不能授权复制参考 Section 或 payload。
- 证据：`diagnostics/r338-*`、`diagnostics/r341-*`、`diagnostics/r342-probe-zjhk-*`、`diagnostics/r343-file-convergence.json`、`diagnostics/r343-bgl-binary-diff.json`。原始运行日志不入本文档。

### r344 当前结论

- r343 后复核确认：参考 BGL 的 `0x13/0x17/0x22` Section 数量是 SDK 空间分桶/布局统计，不能当作机场或导航记录数量；不得据此复制参考记录或扩大模型范围。
- r339 的 40 张默认缺口卡仍全部为 `blocked/rejected`：航路端点区域 12、航点区域 5、IAP 主进近 10、未分类程序 13；本轮没有新的 424 直接证据授权投影。
- 当前冻结模型与候选仍保持 `0/29` 字节一致、`deployable=false`。下一阶段只接受新增的同周期 424 直接证据，并继续使用“来源缺口审计 -> 最小测试 -> 双构建 -> 差分”的复用管线。
- 证据：`diagnostics/r339-default-gap-cards-20260820.json`、`diagnostics/r340-source-model-completeness-20260820.json`、`diagnostics/r343-bgl-binary-diff.json`。本结论不改变模型、adapter 或候选。

### r346 阶段结论（2026-08-20）

- r343 的根级终端航点实验被同一 Navdatareader 反证：参考 ZB 机场 BGL 为 2710 个 waypoint，旧 r77 为 2739 个，r343 仅 1346 个；r346 恢复机场内 `Waypoint`，仅导航包按 `duplicate_terminal_waypoints` 增加根级副本。
- r346 使用冻结 r187 模型重建，500 个测试通过；ZB 读取为 2741 waypoint、58 ILS，候选可读取。文件收敛仍为参考 `0/29`，因此未部署、未实机验证。
- 参考机场 BGL 仍有 `0x17/0x33` 等额外 Section，且 Section 数量不能直接解释为记录数；本阶段只确认作用域错误，不授权复制参考记录或 payload。
- 证据：`diagnostics/r346-r77-navreader.sqlite`、`diagnostics/r346-r343-navreader.sqlite`、`diagnostics/r346-r346-zb-navreader.sqlite`、`diagnostics/r346-file-convergence.json`、`diagnostics/r346-bgl-binary-diff.json`。

### r347 阶段结论（2026-08-20）

- 使用本机已验证官方设施索引重新构建，`local_contract_verified=true`、`selected_navaids=254`；r346 因错误诊断索引导致 `selected_navaids=0`，其全包语义差分不作依据。
- r347 全包读取结果：VOR `121/135`、NDB `133/174`、waypoint `27705/27887`、airway `5044/4620`（候选/参考）；语义差分仍存在，文件收敛仍为 `0/29`。
- 结论：机场终端航点作用域已恢复，但设施字段、航路投影和来源缺口仍需按 `r347-semantic-diff.json` 分层调查；禁止复制参考记录或 payload。候选未部署、未实机验证、不得 Release。
- 证据：`diagnostics/r347-candidate-navreader.sqlite`、`diagnostics/r347-semantic-diff.json`、`output/candidate-2608-default-r347-airport-terminal-waypoints/conversion-report.json`。

### r348 航路类型来源审计（2026-08-20）

- 424 `RTE_SEG.csv`、`SEGMENT.csv`、`EN_ROUTE_RTE.csv` 共读取 `4446/4311/1354` 行；`CODE_TYPE` 是 RNAV/RNP 来源语义，`TXT_LOC_TYPE` 是来源分类，未发现直接提供 SDK `VICTOR/JET/BOTH` 的字段。
- 最小 SDK 探针已证实 `Route.routeType` 会生成读取器的 `airway_type=B/J/V`；参考数据同名航路可混合多种类型，不能用名称前缀或参考类别反推源字段。
- 因无 424 直接映射证据，本轮不修改 `NavModel`、`_route_type` 或 BGL adapter；当前候选 `airway=5044`、参考 `4620`，字节一致仍为 `0/29`。
- 证据：`diagnostics/r348-airway-type-source-audit-20260820.json`、`diagnostics/route-type-hint-probe-r71-20260817/probe-report.json`、`diagnostics/route-type-name-fixed-probe-r71-20260817/probe-report.json`。状态：`blocked`，等待同周期 424 直接类别字段或官方转换规则。

### r349 设施区域冲突审计（2026-08-20）

- 回查 r347 的 6 个 VOR 区域差异（ALS/BDA/ETL/MSN/PAN/WUH）及 4 个 NDB 字段差异（DM/DS/SB/RG）的 424 坐标、频率、`SERVICED_AIRPORT` 和 `CODE_FIR`。
- 4 个 NDB 与官方读取索引的 `ZU` 记录在坐标/频率上对应；6 个 VOR 无法在已验证索引中建立同坐标同频的一一身份映射，不能把参考区域倒推成来源规则。
- 不修改 `navaid_country()`，保留有效服务机场优先、单一 FIR 回退、多 FIR 拒绝；状态 `blocked`。下一步须取得同周期官方转换规则或可复核的目标记录身份映射。
- 证据：`diagnostics/r347-semantic-diff.json`、官方设施索引元数据及本轮只读审计；模型、候选和部署状态不变。

### r350 NDB 作用域来源审计（2026-08-20）

- 目标读取器的 `ndb` schema 支持 `airport_ident`；官方索引含 33 条中国机场作用域 NDB。
- 424 `NDB.csv` 有 77 行，其中 41 行、43 个机场关联（含多机场标记）；与上述目标记录按 `ident/region/airport` 零匹配，不能用官方频率、坐标、名称或作用域回填。
- 结论：机场 NDB 作用域契约已确认，但当前 424 没有授权对应目标内容；不扩展 `Navaid`、不接入机场 XML、不改变候选。状态 `blocked`，等待同周期直接来源或官方转换规则。该审计同时确认现有 `airport-source-inventory` 的来源边界仍有效。
- 全量状态不变：测试 `500 passed`，参考字节一致 `0/29`，`deployable=false`，未部署、未实机验证、不得 Release。

### r351 未分类程序直接 PDF 审计（2026-08-20）

- 使用冻结 r187 模型和逐卡直接文本审计管线复核全部 13 张未分类程序卡（ZGBS/RNP-0、ZHCC/CC、ZPDQ/ZUKD/ZUSH/EO）。
- 13/13 均未在同页 424 数据库编码 PDF 中找到程序标签与唯一类别标题的直接锚点，全部保持 `rejected_missing_direct_label_anchor`；未读取参考记录、Fenix 数据或 OCR，模型与候选不变。
- 结论：不能把 `RNP-0`、`CC*`、`EO-*` 等标签按名称或邻近标题映射为 SID/STAR/IAP；等待同周期直接类别字段或可复核的官方转换规则。全量测试 `500 passed`，参考字节 `0/29`，状态 `blocked`。
- 证据：本轮首张卡 `diagnostics/r351-unclassified-zgbs-rnp0-12.json`；其余卡使用同一 `unclassified-procedure-card-audit-v1` 管线批量复核，输出仅保留脱敏汇总。

### r352 VOR 身份来源审计（2026-08-20）

- r347 参考独有 VOR 样本 20 条中，14 个标识不在 424 `VOR.csv`；其余 6 个（ALS/BDA/ETL/MSN/PAN/WUH）虽在 424 中存在，但来源区域与参考区域不同，不能用参考区域改写来源映射。
- 424 中另有 11 条同坐标/同频但跨区域的物理重复 VOR 被确定性抑制；只有 SNF 的跨区域添加有独立可复核授权。该规则不扩大到参考独有 VOR。
- 结论：缺少参考独有 VOR 的完整 424 身份证据，不修改 `navaid_country()`、设施选择或候选；状态 `blocked`。证据：`diagnostics/r352-vor-source-identity-audit.json`、`diagnostics/r347-semantic-diff.json`。

### r353 未分类程序批量审计管线（2026-08-20）

- 新增 `unclassified-procedure-cards-audit` CLI，复用单卡 PDF SHA-256、页码、标签锚点和类别标题门禁，支持全量或指定卡集合，输出确定性汇总与逐卡证据。
- 冻结 r187 模型实际运行：13 张卡、`target_mapping_allowed_total=0`、13 条均为 `rejected_missing_direct_label_anchor`；未读取参考记录/Fenix，未修改模型或投影。
- 新增回归后全量测试为 `502 passed`。该管线只改善来源审计复用性，不授权 `RNP/CC/EO` 标签映射，不改变候选或 `0/29` 字节状态。
- 证据：`diagnostics/r353-unclassified-procedure-cards.json`；代码：`src/fenix_default_navdata/unclassified_procedure_card_audit.py`、`src/fenix_default_navdata/cli.py`。

### r354-r356 原始数据重导出与模型重放（2026-08-20）

- 使用 `424源数据\2608\2608` 重导出；首次未传通用文档缓存导致模型少 489 个航点、138 条航路设施证据和 434 条拒绝记录，已通过正确的 `general-doc-ocr-cache-2608r1` 根目录重跑纠正。
- r356 模型计数与冻结 r187 完全一致；模型重放仅有 33 个 `RTE_SEG.csv` 端点区域字段差异，均为当前来源侧恢复的 `ZB/ZH/ZU`，不修改投影逻辑。证据：`diagnostics/r354-model-replay-audit.json`、`diagnostics/r356-model-replay-audit.json`。
- r356 候选通过本地验证；与 r347 候选相比参考范围 `29` 个文件中 `28` 个字节相同，仅 `00_enroute.bgl` 受上述 33 条区域差异影响。对 `Default navdata 2608R1` 仍为 `0/29`，`deployable=false`，未部署、未实机验证、不得 Release。证据：`diagnostics/r356-vs-r347-file-convergence.json`。
- 可复用重放命令：`export-model --raw ... --general-doc-cache ...`，随后 `build --model ... --baseline-db ...`、`validate`、`file-convergence-audit`。中间模型仍是跨目标格式唯一内容边界，缓存和参考包只作证据输入。

### r357 00_enroute 读取器语义差异审计（2026-08-20）

- 对 r356 候选与官方同路径 `00_enroute.bgl` 建立的 Navdatareader SQLite 完成完整脱敏差分；候选/参考为：waypoint `3150/3266`、airway `4434/4614`。读取器两侧均返回 `1` 并标记 `broken`，但 SQLite、来源和设施检查仍可继续作为只读审计输入。
- `source-gap-audit-v5`：参考独有 waypoint `1014`，其中 `662` 个不在结构化指定点或航路端点、`332` 个仅有不同区域、`5` 个区域未解析、`15` 个仅有航路端点区域冲突；参考独有 airway `1182`，其中 `484` 个不在 `RTE_SEG.csv`、`575` 个同名同序号、`123` 个同名不同序号。
- `airway-diff-audit-v1`：`2020` 条同逻辑键字段差异全部能唯一回链到 424 航路和序号，端点坐标完整；`1990` 条为纯几何差异，`30` 条为几何加最低高度差异。该证据不能授权复制官方坐标、字段或 payload，也没有形成安全的 adapter 修复。
- 本阶段只读阻断，不修改 `NavModel`、BGL adapter 或候选；候选仍为 `0/29` 字节一致、`deployable=false`、未部署、未实机验证。证据：`diagnostics/r356-00-enroute-semantic-diff-full.json`、`diagnostics/r356-source-gap-audit-full.json`、`diagnostics/r356-airway-diff-audit.json`。

### r358 候选航段关联与航路类型来源审计（2026-08-20）

- 将候选 `china-navdata.xml` 纳入 `source-gap-audit-v5` 后，候选含 `8868` 个 Route link、`4434` 个唯一端点对；参考独有 airway `1182` 条中 `562` 条已确认对应候选已投影的 424 航段，`13` 条因端点区域缺失未投影，`123` 条为同名不同序号，`484` 条不在 `RTE_SEG.csv`。字段差异 `2020` 条中 `2013` 条已投影，`7` 条受端点区域缺失影响。
- 对 `APOGO、P121、P127、P188、P225、P239、LELIM、****` 八个未解析端点完成来源卡审计；直接 FIR/ACC、唯一邻接区域或 DESIGNATED_POINT 身份均不足，全部保持拒绝，不修改区域恢复规则。`APOGO` 的四条邻接航段同时指向 `ZB/ZL`，且 ACC 名称没有 `AIRSPACE.csv` 唯一映射。
- 目标读取器额外出现 `airway_type=J` `432` 条、`V` `56` 条，而候选全部为 `B`。对可按航路名/序号关联的目标 J/V 样本，来源 `TXT_LOC_TYPE`、`CODE_TYPE`、`CODE_DIR` 均呈多种组合，且 `488` 条样本中 `250` 条不能用 `VAL_SORT` 唯一对应，未形成可复核的 `B/J/V` 映射。不得按航路前缀、PBN 或参考类型猜测 `routeType`。
- 本阶段仍为只读阻断；未修改模型、adapter 或候选。证据：`diagnostics/r357-source-gap-with-candidate.xml.json`、`diagnostics/r357-airway-endpoint-card-APOGO.json`、既有端点卡片 `r218-r223/r336`、`diagnostics/r357-route-type-source-association-v2.json`。

### r359 routeType 来源审计管线（2026-08-20）

- 新增可复用 CLI `route-type-source-audit`，只消费 `NavModel` 与完整、只读、脱敏的 `semantic-diff`；输出目标 J/V 计数、来源字段组合唯一匹配率和冲突数，不读取参考坐标/payload，不修改模型或候选。
- r356 实际运行：目标额外 `J=432`、`V=56`；按航路名/序号唯一匹配 `238` 条，`250` 条无法匹配；`23` 个来源字段组合中 `3` 个同时对应多个目标类型，状态 `insufficient_for_adapter_rule`。因此仍不得猜测 `routeType`。
- 代码与回归：`src/fenix_default_navdata/route_type_source_audit.py`、`tests/test_route_type_source_audit.py`；真实证据：`diagnostics/r359-route-type-source-audit.json`。针对性测试 `42 passed`，候选仍 `0/29`、`deployable=false`。

### r361 机场范围来源审计（2026-08-20）

- 新增只读、可复用 CLI `airport-scope-source-audit`，只读取 424 `AD_HP.csv`、`Terminal` 目录、顶层 CSV、候选 XML，以及可选的参考 `ContentHistory.json` 元数据；不读取参考 BGL 记录，不修改模型、adapter 或候选。
- r356 实际结果：424、NavModel、候选 XML 均为 `275` 个机场；参考 `ContentHistory` 为 `279` 个。参考独有 `ZBSH/ZGFS/ZL02/ZL03/ZSLT/ZW01/ZW02` 均无 424 直接机场来源；候选独有 `ZBAR/ZGUH/ZGYJ` 均有 `AD_HP.csv`、`Terminal` 和 CSV 证据。
- 结论：参考范围超出当前 424 输入边界，不能复制参考记录回填；候选独有机场也不能仅因参考范围缺少而删除。当前仍为 `0/29`、`deployable=false`，未部署、未实机验证。
- 代码、测试和证据：`src/fenix_default_navdata/airport_scope_source_audit.py`、`tests/test_airport_scope_source_audit.py`、`diagnostics/r361-airport-scope-source-audit.json`。

### r362-r363 SDK 工具链对照构建（2026-08-20）

- 使用同一份 r356 冻结模型、同一官方设施索引和同一输入，分别调用 SDK 1.5.3 与 1.6.9；输出仅用于诊断，不部署。
- r362（SDK 1.5.3）：`local_contract_verified=true`，本地 `validate` 通过；参考包仍为 `0/29`。与 r356 候选的 15 个主包文件和 14 个机场补丁文件全部字节相同，证明完整模型下 SDK 1.5.3 不改变既有差异。
- r363（SDK 1.6.9）：Package Tool 返回码 `1`，两个包均未生成 `manifest.json`、`layout.json`、`bglIndex.bout` 或 BGL，`local_contract_verified=false`；隔离诊断未发现新的 BuilderLog 内容。该版本不能用于收敛判断。
- 结论：SDK 1.5.3 已排除为当前完整 BGL 差异的原因；SDK 1.6.9 是失败工具链，不修改 adapter 迎合其失败。继续按来源缺口和 BGL 投影契约审计。
- 证据：`diagnostics/r362-validate-sdk153.json`、`diagnostics/r363-validate-sdk169.json`、`diagnostics/r362-file-convergence-sdk153.json`、`diagnostics/r363-file-convergence-sdk169.json`、本地 `sdk-builds` 隔离诊断。

## 已确认的通用契约

- 官方包必须保留全球基线，区域覆盖独立生成。
- Package Tool 需要 ASCII 暂存路径，并必须等待 `FlightSimulator2024.exe` 完全退出后再清理构建目录。
- 机场 XML 不写 `AiracCycle`；航路 XML 保留它。当前 SDK 机场 BGL 可能自动生成 `0x20` magvar 网格，不能据体积猜测内容。
- SID/STAR 名称按 SDK 限制唯一化：`Departure/Arrival` 最长 6 字符，transition 最长 5 字符；只在 BGL adapter 中处理。
- `Airport.onlyAddIfReplace` 的受控探针可移除 `0x35`，但没有 424 来源授权，不得写入正式 adapter。
- BGL Header/Section 审计只能证明布局、数量和序列差异，不能反推记录语义或复制参考 payload。
- 无 `ORDER BY` 的真实加载 SQL 必须配合物理行顺序模拟；固定内存加载器还要检查 NULL、长度、枚举、距离和容量。

## 来源与 IAP 门禁

- 机场、跑道、导航台、航路点、航路、ILS、SID/STAR/IAP、等待航线和拒绝项必须保留来源引用。
- 424 区域恢复只能使用同周期直接来源、服务机场、FIR/ACC、合法多边形或唯一邻接；跨表猜测和参考数据回填禁止。
- OCR 只作受限证据：必须固定运行时、模型、seed、temperature、渲染配置和源文件哈希，并通过至少三份独立完整缓存共识。
- OCR 不得创造主进近、图页归属或绕过 `no_unique_primary`、`empty_primary`、`no_matching_chart`。
- 多图 IAP 只有在直接角色、页面所有权或严格交集规则闭合时才可投影；否则保持拒绝。

## 验证顺序

1. 输入锁定、模型哈希和来源审计；
2. SQLite/BGL 完整性、schema、Header、元数据和引用完整性；
3. 目标真实 SQL、排序、游标和容量模拟；
4. `ZBCF`、`ZUNZ`、`ZUUU` 等关键机场点查；
5. 候选双构建哈希与参考字节比较；
6. 备份恢复演练；
7. 用户实机验证：机场输入、出发/抵达、SID/STAR/IAP、退出飞行和退出模拟器。

## 历史阶段索引

详细旧日志已压缩；按阶段只保留主题和结论，证据以 `diagnostics/` 中可复跑产物为准：

- r204-r259：来源审计、IAP/OCR 门禁、NavModel、BGL/Package Tool 基础契约。
- r260-r304：根 CSV 分类、来源缺口、模型投影、包元数据和 BGL 差分管线。
- r305-r314：参考模板、SDK 工具链、读取器重复性、运行时契约和包依赖。
- r315-r324：日期纠偏、来源缺口复核、BGL 结构、XML 排序、统一模型和安全体系。
- r325：权威状态归一；冻结模型、候选 `29/29` 自重放、参考 `0/29`。
- r326：权威快照和 `ZJ_airports.bgl` 记录布局基线。
- r327：脱敏 Section 记录序列审计，确认数量/序列未收敛。
- r328：`onlyAddIfReplace` 隔离探针和相同输入重放门禁；不改变 adapter。
- r329-r335：贡献度、ZJ Section、运行时触发和来源缺口只读审计；参考差异未授权投影，waypoint/airway 缺口 `1013/1186` 保持拒绝。
- r338-r343：GeneralDoc 边界修复、全量 BGL 结构审计、SDK 作用域探针和根级终端航点实验；候选仍 `0/29` 字节一致、未部署。
- r347-r353：设施索引修复、机场终端航点作用域恢复、航路类型/设施区域/NDB 作用域、未分类程序/VOR 来源审计及批量审计管线；候选仍 `0/29`，未授权修改映射或部署。
- r354-r361：424 重导出、`00_enroute`/来源缺口/航路类型/机场范围只读审计；候选仍 `0/29`。
- r362-r363：SDK 1.5.3/1.6.9 完整模型对照；1.5.3 与 r356 完全一致，1.6.9 构建失败；未修改 adapter、未部署。

## 维护协议

- 新经验只记录已由代码、官方模板、真实运行时或实机验证证实的事实。
- 每条新增规则注明适用周期/目标、证据、触发条件、处理方式和测试。
- 实验性推测标记“待验证”，不得写成通用规则。
- 后续更新本文件时，同时更新工作区根目录镜像 `..\AGENTS.md`。
