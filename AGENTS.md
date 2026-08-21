# 默认通用数据转换器协作规则

## 目标与边界

- 输入内容只来自 `424源数据\2608\2608` 的 424 CSV/PDF 和匹配的 `RTE_SEG.csv`。
- `Default navdata 2608R1`、Fenix、参考 BGL/SQLite 只用于 schema、加载契约和只读差分，不得作为内容、坐标、payload 或记录回填来源。
- `NavModel` 是跨 AIRAC、跨目标格式的唯一内容边界；默认 BGL 是独立 adapter。
- 当前目标：从 424 原始数据生成默认导航数据，并逐文件与目标默认包字节一致。未完成前不得部署或 Release。

## 可复用管线

```text
lock-inputs -> ingest-424 -> evidence-audit -> normalize-model
-> model-audit -> project-target -> build-target -> validate-target
-> diff-and-audit -> stage-backup-deploy
```

每个目标格式独立实现 profile/schema/version、字段和单位映射、NULL/default、排序/索引、元数据、验证器和部署器。适配器不得重新解析 424，也不得把其他机模规则写入 `NavModel`。

## 输入与安全

- 官方基线只定义目标 schema、全球基线和加载契约；来源模型必须保留来源文件、行号、周期和拒绝原因。
- 无法无损表达的字段必须计数并阻断关键航段，禁止静默丢弃。
- 数据库、BGL、备份、日志、诊断输出、SDK 构建目录和外部测试包不得提交。
- 覆盖游戏文件前确认 `FlightSimulator2024.exe` 已退出，并备份数据库、元数据和布局文件。
- 参考字节、完整本地验证、备份恢复演练和实机验证未全部通过时，只能标记测试版。

## 当前权威状态（2026-08-21）

- 冻结模型：`output/intermediate-2608-r187-navaid-label-replay.json.gz`
- 模型 SHA-256：`7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`
- 当前实验候选：`output/candidate-2608-default-r366-terminal-global-identity`
- 参考范围 29 个文件，字节一致 `0/29`，`deployable=false`。
- 最近全量测试基线：`513 passed`。
- 当前未部署 Community、未实机验证、未创建 Release。
- 工作区 Git 提交和推送由根目录协作规则约束；提交前确认不含数据库、诊断和构建产物。

## 验证门禁

1. 锁定输入、模型哈希和来源审计。
2. SQLite/BGL 完整性、schema、Header、元数据和引用检查。
3. 真实 SQL、物理顺序、游标、NULL、长度、枚举、距离和容量模拟。
4. 点查 `ZBCF`、`ZUNZ`、`ZUUU` 等机场及边界航段。
5. 双构建、独立 validate、逐文件 SHA-256 与参考包差分。
6. 备份恢复演练。
7. 实机验证机场输入、出发/到达、SID/STAR/IAP、退出飞行和退出模拟器。

## 已确认的目标契约

- 机场 XML 不写 `AiracCycle`；航路 XML 保留它。
- XML 无 `ORDER BY` 保障时，必须固定写入顺序并检查物理行顺序。
- SDK 生成的 BGL Section 数量/类型只能说明布局，不得反推对象语义或复制参考 payload。
- `RTE_SEG.CODE_TYPE_START/END` 可作为 VOR/NDB 航路端点类型来源；终端 `NAMED` 航点不得与 424 VOR/NDB 占用同一 `(region, ident)` 身份。
- `RWY_DIRECTION.VAL_THR_DISPLACE` 的 33 条记录仅允许做独立隔离探针；未取得可复核结果前不得接入正式 adapter。
- `scripts/airport_subset_probe.py` 支持 `--runway-ident`/`--keep-runway-ident` 精确选择含 L/R/C 的跑道方向，并按 XML `primaryDesignator/secondaryDesignator` 区分 PRIMARY/SECONDARY 端。
- OCR 只能作为固定运行配置下的受限证据，不能创造主进近、图页归属或绕过 `blocked/no_unique_primary`。

## 阶段索引

- r204-r259：来源审计、IAP/OCR 门禁、NavModel、BGL/Package Tool 基础。
- r260-r324：CSV 分类、来源缺口、模型投影、元数据、SDK、统一模型和安全体系。
- r325-r343：权威状态、ZJ/来源缺口、GeneralDoc 边界、BGL 结构与 SDK 探针。
- r347-r353：设施索引、终端/全局航点、航路类型、设施区域、NDB/VOR 来源和批量审计。
- r354-r361：424 重导出、`00_enroute`、来源缺口、航路类型和机场范围只读审计。
- r362-r364：SDK 1.5.3/1.6.9 对照、`VAL_MTCA` 高度来源审计；未授权修改 adapter。
- r365-r366：航路端点类型投影与全局身份门禁；本地契约通过但参考仍 `0/29`。
- r367-r368：航路/航点/IAP/未分类程序缺口卡共 `40` 张，全部 `rejected/blocked`；无新 424 直接证据。
- r369：参考独有全局航点 `1014` 条，分类 `811/154/39/9/1`，可安全提升 `0` 条。
- r370：机场 `20/20` 缺参考 `0x17`、`18/20` 参考含 `0x33`；航路差异 `0x13=-12`、`0x17=-4`、`0x22=-419`；SDK 矩阵无授权单变量。
- r371：只读审计 NavModel -> XML -> 候选 BGL；模型计数 `275/640/438/430/2741/12549/4446/10409/1297`（机场/跑道/导航台/ILS/全局航点/终端航点/航路段/程序段/等待航线），拒绝记录/程序 `435/10`。机场 XML 消费模型来源计数一致；`00_enroute.xml` 为 `Waypoint=3145`、`VOR=361`、`NDB=77`、`Next/Previous=4394/4394`、`Route=5744`，跳过航路段/航点 `52/9`。候选未修改、未读取参考 payload。
- r372：对全部 33 条正值 `RWY_DIRECTION.VAL_THR_DISPLACE` 做精确跑道方向隔离构建，`33/33` 成功；所有输出仅含 `0x3/0x13/0x32/0x35`，`0x17/0x33` 均未出现。该字段不能解释参考 Section 差异，不修改正式 adapter。证据：`diagnostics/r372-offset-threshold-matrix.json`、`diagnostics/r372-offset-threshold-matrix-summary.json`。

## 当前后续

- 保持 r366 模型、adapter 和候选不变。
- 继续保持 `VAL_THR_DISPLACE` 为已否决的诊断方向，不接入正式 adapter；下一步回到 SDK/目标加载契约或参考输入范围审计。
- 每阶段只记录短摘要；详细证据放在 `diagnostics/`，不复制到本文件。
- 新目标格式必须复用同一 `NavModel` 和管线，另建独立 adapter/validator/deployer。
### r373：baseline 与参考包范围审计

- `--baseline-db` 只用于官方 VOR/NDB/航点索引校验、区域恢复和默认导航台选择，不合并参考 BGL payload。
- 参考两个目标包约 90.6 MB，当前候选约 17.0 MB；参考 20/20 个机场 BGL 含 `0x17`，候选全部缺少；`00_enroute` 的 `0x20` 完全一致，但仍少 `0x13=12`、`0x17=4`、`0x22=419` 个节。
- `r312-reference-template-source-audit-20260820.json` 未发现可复用的参考导航 BGL 模板。未取得 424 直接来源或目标加载契约前，不得按参考节表反推对象或修改 adapter；本方向保持 blocked。
- r374：参考来源追踪。参考包元数据的 BGL/索引时间为 2026-08-06，`manifest.json` 标识 `PMDG DFD v2 converter`；工作区未找到对应 XML、BglComp 输入或专用生成器。旧 `navdata_converter` 仅为 2607 -> PMDG DFDv2 SQLite 的简化转换器，不能复用于默认 BGL。无新来源证据，模型、adapter、候选保持不变，继续 blocked。
- r375：对 r366 候选运行包级派生元数据、全量 BGL 节表和 3 个样本 BGL 二进制只读审计。候选与参考 BGL 版本字段相同，但机场结构仍普遍缺 `0x17/0x33`、多出 `0x35`；参考 `layout/index/content history` 的差异也不能由时间正规化单独解释。证据：`diagnostics/r375-package-derived-metadata.json`、`diagnostics/r375-bgl-layout.json`、`diagnostics/r375-bgl-binary-diff-samples.json`。无新来源或加载契约证据，禁止按节表反推对象，模型、adapter、候选保持不变，继续 blocked。
- r376：发现本地 `NavigraphDFDv2-2604.1.0` 仅含 DFDv2 SQLite 样本，无 BGL 生成器。使用 Navdatareader 1.2.4 对 r366 与参考的 `00_enroute.bgl` 做同配置只读读取：候选/参考行数为 `121/135 VOR`、`133/143 NDB`、`3150/3266 Waypoint`、`4223/4614 Airway`；语义差分严格一致 `2994` 行，仍有 `1560/2091` 逻辑键差异。候选 `ZB_airports.bgl` 触发读取器空扫描，参考同文件可读出 `2710` 终端航点和 `59` ILS。证据：`diagnostics/navdatareader/r376-*.sqlite`、`diagnostics/navdatareader/r376-enroute-semantic-diff.json`。这是结构/来源缺口证据，不授权参考记录回填或修改 adapter；继续 blocked。
- r377：完成 424 navaid 区域源侧审计并加入可复用 `navaid_region_source_audit`。2608 `VOR.csv` 为 `13` 条服务机场/FIR 冲突，其中 FIR 多边形明确支持 FIR `5` 条、位于多边形外 `7` 条、近边界 `1` 条；`NDB.csv` 实际为 `0` 条同类冲突。`navaid_country` 改为单一可映射 `CODE_FIR` 优先、无 FIR 才回退服务机场；聚焦与全量测试 `513 passed`。重导出模型计数变为全局航点 `2265`、拒绝记录 `1`，说明该规则会触发大范围身份重算；r377 候选本地契约通过但参考仍 `0/29`、`deployable=false`。候选机场 BGL 的 Navdatareader 探针在边界记录偏移 `2787278` 重复告警并被停止，不能作为通过证据。实验模型/候选未晋级为冻结状态，未部署。证据：`diagnostics/r377-navaid-region-source-audit.json`、`output/intermediate-2608-r377-navaid-fir-priority.json.gz`、`output/candidate-2608-default-r377-navaid-fir-priority/conversion-report.json`。
