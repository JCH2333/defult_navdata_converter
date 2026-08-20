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
- 有效候选：`output/candidate-2608-default-r188-doviv-replay`
- 候选自重放：`29/29`
- 与参考默认数据字节一致：`0/29`
- `deployable=false`
- 当前完整回归：`499 passed`
- 当前未部署 Community、未实机验证、未创建 Release。

### r329 贡献度矩阵

命令入口：`projection-contribution-audit`

功能：从冻结 `NavModel` 生成一份航路 XML 和十份地区机场 XML，统计模型实体、`SourceRef`、XML 标签和候选 BGL Header/Section。报告固定标记：

- `reference_payload_read=false`
- `section_type_semantics_inferred=false`
- `candidate_modified=false`

真实报告：

`diagnostics/r329-projection-contribution-audit-20260820.json`

SHA-256：

`2d9409a949453290493583953d144c4f4bc369eb56215237c509e9cc35845b0e`

规模基线：机场 `275`、跑道方向 `640`、导航台 `438`、全局航点 `2741`、终端航点 `12549`、航路段 `4446`、程序段 `10409`、拒绝记录 `435`、拒绝程序 `10`。这些数字只用于审计排序，不表示 Section 语义，也不授权修改 adapter。

下一步：以 `ZJ_airports.bgl` 为单一目标，取得可复跑 XML 触发或记录边界证据后，才允许改变投影规则。

### r330 ZJ 记录边界审计

- 主包候选与参考均可解析，所有 Section 均为固定步长；候选/参考文件大小分别为 `130146/813572` 字节。
- 参考 `0x13/0x17/0x22` 各有 `2003` 个记录，候选分别为 `3/缺失/17`；参考还存在候选缺失的 `0x33`，候选独有 `0x35`。
- 所有共同 Section 的首个记录摘要均不同，`equal_ordered_sections=0`。该结果证明边界和规模差异可复跑，但不能证明 Section 语义或对应的 424 对象，禁止据此修改正式投影。
- 报告：`diagnostics/r330-zj-airports-record-boundary-audit-v2-a.json`；重放报告：`diagnostics/r330-zj-airports-record-boundary-audit-v2-b.json`；两者 SHA-256：`b2e67d36819606c6195b9ec1093a87ed397dd88b95c15b76dba66720c2180426`。
- 修复 `bgl-record-layout-audit` 的确定性：持久化 JSON 不再写入输出绝对路径，报告可跨输出目录字节一致；专项回归 `30 passed`。
- r330 未改变 `NavModel`、BGL adapter 或候选；当前仍无足够来源证据进入最小投影探针。

### r331 ZJ 根导航台 Section 触发隔离

- 来源清单确认 `ZJ` 机场为 `ZJHK/ZJQH/ZJSY/ZJYX`；机场 XML 的直接来源对象为机场、跑道、终端航点、ILS、程序、等待航线和删除标记。机场通信未进入 `NavModel`，机场关联 VOR/NDB 仍限定为 enroute 作用域。
- 同一份 424-derived XML 只保留四个 ZJ 机场时，保留根 `Vor/Ndb` 的 SDK BGL 为 `0x13=122`、`0x17=92`、`0x22=17`；移除根 `Ndb` 后 `0x17/0x33` 消失且 `0x13=122` 保持；移除根 `Vor` 后 `0x13=3` 且 `0x17=92` 保持。
- 结论：该隔离实验只证明根 `Vor`/`Ndb` 对 SDK Section 的触发关系，并支持 Section 计数是空间桶/索引布局而非直接实体数量；不能解释参考机场 BGL 的 `2003` 计数，也不能授权把根导航台复制到机场 adapter。
- 三份报告：`diagnostics/r331-zj-source-baseline-probe-20260820.json`、`diagnostics/r331-zj-drop-root-ndb-probe-20260820.json`、`diagnostics/r331-zj-drop-root-vor-probe-20260820.json`；SHA-256 依次为 `02607b0f6617eb2dbbf760d48fa6ffa8258f4733cd1cd6d49d8dfe3d01f87a54`、`ea57f0a17cbb17cc2bb7b0ef2dc69ec7308a0de8a0a9351eb3e1df81f69bf98e`、`b7f0795df45abbdbb2f1f06b9fe7a8959491b675cc420ea3aa24488e48870631`。
- Package Tool 三次均生成 BGL；探针 Navdatareader 均未登记 BGL 来源，因此运行时语义仍为“未验证”。未修改 `NavModel`、正式 adapter 或候选。

### r333 ZJ 来源缺口单表审计

- 新增 `source-gap-audit --table waypoint|airway` 只读探针；默认全量行为不变，允许对完整的单表语义差分进行区域/目标隔离审计，避免用不完整历史差分绕过完整性门禁。
- 使用完整的 `r74-vs-reference-single-ZJ-semantic-diff.json` 仅审计 `waypoint`：203 个参考缺失身份中，当前 424 `NavModel` 可证明机场作用域来源 102 个，另 101 个不在 `DESIGNATED_POINT.csv` 或 `RTE_SEG.csv` 端点集合；未取得直接来源前不得补写。
- `r333-zj-source-inventory-20260820.json` 仅保存 424 源文件哈希、计数、模型集合哈希和授权结论；无参考导航 payload。ZJ 四机场终端航点为 `193`（ZJHK 85、ZJQH 33、ZJSY 61、ZJYX 14），全局 ZJ 航点为 `51`。
- r136 全量差分和 r77 ZJ 差分因 waypoint 样本截断被门禁拒绝；r74 因缺少 airway 表仅可用于 waypoint 单表探针。模型/adapter 仍未授权修改。

### r334 ZJ 终端坐标与 GeneralDoc 来源复核

- 使用完整 r74 ZJ waypoint 差分和同周期 GeneralDoc ENR 4.4 缓存复核 203 条缺口：`general_doc_ident_absent=101`，`airport_scoped=102`，没有可直接投影的 GeneralDoc 关键点来源。报告：`r334-general-doc-keypoint-r74-zj-20260820.json`。
- 使用同周期终端坐标页缓存复核：3 条机场作用域身份在坐标页出现，但均为 `terminal_single_airport`；99 条机场作用域身份不在坐标页；98 条全局身份不在坐标页。带 `--check-retention` 后 3 条均为 `airport_terminal_coordinate_not_retained`，仍只是调查信号，不授权提升或补写。报告：`r334-terminal-coordinate-r74-zj-20260820.json`、`r334-terminal-coordinate-r74-zj-retention-20260820.json`。
- r334 未修改 `NavModel`、BGL adapter、候选或部署；ZJ 来源侧当前没有可安全提升的新增记录。

### r335 全量来源缺口审计

- 使用完整 `r162-00-enroute-semantic-diff-all-full.json` 审计 waypoint/airway；输入完整性通过：waypoint `1013` 条、airway `1186` 条，未截断。
- waypoint 缺口分类：`662` 条不在结构化指定点或航路端点集合，`331` 条虽有直接指定点但区域不同，`5` 条直接指定点区域未解析，`15` 条航路端点区域不同。没有独立 424 来源契约前，均不得按参考身份或区域猜测补写。
- airway 缺口分类：`484` 条不在 `RTE_SEG.csv`，`579` 条可回链同源航路和序号，`123` 条同源航路但序号不同；字段差异 `2045` 条全部可回链到同源 `RTE_SEG.csv`，主要是坐标格式/包围盒差异，不能据参考值回填。
- 旁证：`FLIGHT_AIRLINE_POINT.csv` 的 `390659` 条均回链到直接 424 点；参考独有航路名对应的 54 个航路没有该表行。`ROUTE_HOLDING` 的 116 条中 52 条点 ID 未解析，当前没有可安全构造独立全局航点的区域/身份契约。
- 报告：`diagnostics/r335-source-gap-r162-full-20260820.json`。r335 为只读审计，未修改 `NavModel`、BGL adapter、候选、部署或 Release；下一步仍是寻找可独立证明的 424 来源，不得用参考包反向补全。

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
- r330：`ZJ_airports.bgl` 脱敏记录边界审计和诊断报告确定性修复；确认 Section 差异不足以授权投影变更。
- r331：ZJ 仅来源投影的根 `Vor/Ndb` 单变量 SDK 探针；确认 Section 触发关系，未授权正式投影。
- r333：来源缺口审计增加单表探针；ZJ waypoint 203 条缺口中仅 102 条有当前 424 机场作用域来源，未授权模型或 adapter 修改。
- r334：ZJ GeneralDoc 与终端坐标页复核未发现可安全提升的来源；3 条坐标页命中均为单机场且当前未保留，未授权模型或 adapter 修改。
- r335：全量 waypoint/airway 来源缺口审计完成；`1013/1186` 条参考缺口均未获得足够独立来源授权，未修改模型或 adapter。

## 维护协议

- 新经验只记录已由代码、官方模板、真实运行时或实机验证证实的事实。
- 每条新增规则注明适用周期/目标、证据、触发条件、处理方式和测试。
- 实验性推测标记“待验证”，不得写成通用规则。
- 后续更新本文件时，同时更新工作区根目录镜像 `..\AGENTS.md`。
