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
- 最新实验候选：`output/candidate-2608-default-r338-general-doc-boundary`
- r338 模型计数与冻结模型一致；V111/V162 四条端点区域恢复
- 与参考默认数据字节一致：`0/29`
- `deployable=false`
- 当前完整回归：`500 passed`
- 当前未部署 Community、未实机验证、未创建 Release。

### r329-r335 阶段审计索引（已压缩）

- 贡献度、ZJ Section 边界、根导航台触发和来源缺口均完成只读审计；均未使用参考 payload，也未授权复制 Section 或修改正式 adapter。
- 关键结论：参考 Section 数量/边界不能反推语义；完整来源缺口为 waypoint `1013`、airway `1186`，无来源授权的记录保持拒绝。
- 证据文件：`diagnostics/r329-*`、`r330-*`、`r331-*`、`r333-*`、`r334-*`、`r335-source-gap-r162-full-20260820.json`。

### r338 GeneralDoc 来源边界修复

- 根因：GeneralDoc 新增航点被加入 `airway_endpoint_countries`，同标识同坐标的不同区域会污染直接 `DESIGNATED_POINT.csv` 端点证据。
- 修复：GeneralDoc 航点仍可保留并计入审计，但不再参与 `RTE_SEG.csv` 端点区域恢复。
- 回归：新增 `test_load_naip_general_document_waypoint_does_not_ambiguate_direct_airway_endpoint`；完整测试 `500 passed`。
- 模型：`output/intermediate-2608-r338-general-doc-boundary.json.gz`；计数与冻结模型一致，V111/V162 四条端点恢复。
- 候选：`output/candidate-2608-default-r338-general-doc-boundary`；`validate` 通过，来源审计 `diagnostics/r338-source-gap-r162-with-candidate-20260820.json`。
- 字节验收：两个包共 `29` 个文件均不一致，仍为 `deployable=false`；未部署、未实机验证、未 Release。

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
- r329：424 到投影贡献度矩阵；当前最新阶段。
- r330-r335：ZJ Section/运行时触发与全量来源缺口只读审计；参考 Section 差异不足以授权投影，waypoint/airway 缺口 `1013/1186` 均未获独立来源授权。详细报告保留在 `diagnostics/`。
- r338：GeneralDoc 航点不再污染直接航路端点区域证据；新增回归后完整测试 `500 passed`，V111/V162 四条端点恢复。候选仍 `0/29` 字节一致、未部署。

## 维护协议

- 新经验只记录已由代码、官方模板、真实运行时或实机验证证实的事实。
- 每条新增规则注明适用周期/目标、证据、触发条件、处理方式和测试。
- 实验性推测标记“待验证”，不得写成通用规则。
- 后续更新本文件时，同时更新工作区根目录镜像 `..\AGENTS.md`。
