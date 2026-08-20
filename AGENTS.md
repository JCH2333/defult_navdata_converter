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
- 当前完整回归：`500 passed`
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

### r349 设施区域冲突审计（2026-08-21）

- 回查 r347 的 6 个 VOR 区域差异（ALS/BDA/ETL/MSN/PAN/WUH）及 4 个 NDB 字段差异（DM/DS/SB/RG）的 424 坐标、频率、`SERVICED_AIRPORT` 和 `CODE_FIR`。
- 4 个 NDB 与官方读取索引的 `ZU` 记录在坐标/频率上对应；6 个 VOR 无法在已验证索引中建立同坐标同频的一一身份映射，不能把参考区域倒推成来源规则。
- 不修改 `navaid_country()`，保留有效服务机场优先、单一 FIR 回退、多 FIR 拒绝；状态 `blocked`。下一步须取得同周期官方转换规则或可复核的目标记录身份映射。
- 证据：`diagnostics/r347-semantic-diff.json`、官方设施索引元数据及本轮只读审计；模型、候选和部署状态不变。

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
- r347-r349：设施索引修复、机场终端航点作用域恢复、航路类型与设施区域来源审计；候选仍 `0/29`，未授权修改映射或部署。

## 维护协议

- 新经验只记录已由代码、官方模板、真实运行时或实机验证证实的事实。
- 每条新增规则注明适用周期/目标、证据、触发条件、处理方式和测试。
- 实验性推测标记“待验证”，不得写成通用规则。
- 后续更新本文件时，同时更新工作区根目录镜像 `..\AGENTS.md`。
