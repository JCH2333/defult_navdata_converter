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
- 最近全量测试基线：`509 passed`。
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
