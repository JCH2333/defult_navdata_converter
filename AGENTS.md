# 默认通用数据转换器协作规则

## 目标与边界

- 唯一内容来源：`424源数据\2608\2608` 的 424 CSV/PDF 与匹配 `RTE_SEG.csv`。
- 默认包、Fenix、参考 BGL/SQLite 只用于 schema、加载契约和只读差分；禁止回填参考 payload、坐标或记录。
- `NavModel` 是跨 AIRAC/格式的内容边界；默认 BGL 使用独立 adapter、validator、deployer。
- 目标是逐文件 SHA-256 与 `Default navdata 2608R1` 一致；未完成前不得部署或 Release。

## 可复用管线

```text
lock-inputs -> ingest-424 -> evidence-audit -> normalize-model
-> model-audit -> project-target -> build-target -> validate-target
-> diff-and-audit -> stage-backup-deploy
```

适配器不得重新解析 424，也不得把机模专有规则写入 `NavModel`。无法无损表达的字段必须计数并阻断关键航段，禁止静默丢弃。

## 当前权威状态（2026-08-21）

- 冻结模型：`output/intermediate-2608-r187-navaid-label-replay.json.gz`
- 模型 SHA-256：`7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`
- 历史候选：`output/candidate-2608-default-r366-terminal-global-identity`、`output/candidate-2608-default-r377-navaid-fir-priority-full-evidence`
- 当前候选：`output/candidate-2608-default-r385-frozen-rebuild`
- 参考范围 29 个文件，字节一致 `0/29`，`deployable=false`；未部署、未实机验证、未 Release。
- 最近全量测试：`519 passed`；最新阶段 r392 缺口卡与未决项来源审计。

## 验证门禁

1. 锁定输入、模型哈希、来源和拒绝原因。
2. 检查 SQLite/BGL 完整性、schema、Header、元数据、引用、排序和容量。
3. 模拟真实 SQL/游标及 NULL、长度、枚举、距离约束。
4. 点查 `ZBCF`、`ZUNZ`、`ZUUU` 和边界航段。
5. 双构建、独立 `validate`、逐文件 SHA-256 差分。
6. 备份恢复演练；实机验证机场、出发/到达、SID/STAR/IAP、退出飞行和退出模拟器。

## 已确认契约

- 机场 XML 不写 `AiracCycle`；航路 XML 保留它。
- 无 `ORDER BY` 时固定写入顺序并验证物理行顺序。
- BGL Section 数量/类型只能说明布局，不能反推对象语义或授权复制参考内容。
- `RTE_SEG.CODE_TYPE_START/END` 可提供 VOR/NDB 航路端点类型；终端 `NAMED` 不得占用同一 `(region, ident)`。
- `RWY_DIRECTION.VAL_THR_DISPLACE` 的 33 条记录仅用于隔离探针，尚未授权接入 adapter。
- OCR 只能提供固定配置下的受限证据，不得创造主进近或绕过 `blocked/no_unique_primary`。

## 阶段日志（压缩）

- r204-r368：完成来源、模型、IAP/OCR、SDK、BGL、元数据和缺口卡体系；40 张缺口卡均为 `rejected/blocked`。
- r369-r372：参考独有全局航点可安全提升 0 条；SDK/跑道偏移隔离未找到可授权单变量。
- r373-r378：参考 BGL/SDK 未找到可复用生成模板；完成 navaid 区域规则与证据重放，候选本地契约通过但参考仍 `0/29`。
- r379-r385：完成机场作用域、参考构建来源、BGL 基数、SDK 表达式、来源完整性和主流程审计；参考额外 7 个机场无 424 直接证据，未授权回填。r385 冻结模型重建与既有候选 `29/29` 一致，证明差异可复现而非构建漂移。证据：`diagnostics/r379-*` 至 `r385-*`。
- r386-r389：完成等待航线、航路字段、SDK Section 和机场 PDF 来源审计。等待记录缺少足够作用域；2,263 条同源航路差异中 2,241 条为几何差异、12 条端点无唯一来源；NDB `0x17/0x33` 不能解释参考 Section；7 个额外机场未被 424 PDF 命中。均为 `projection_authorized=false`，未改模型/适配器。证据：`diagnostics/r386-*` 至 `r389-*`。
- r390-r392：新增 package-derived-metadata-audit、airway-endpoint-audit 与 default-gap-cards-audit。layout/bglIndex/尺寸等元数据差异依赖编译过程，未授权手工修改；航路 10 个未决端点（APOGO 等）关联 21 条未投影航段，7 个为多邻接地区跨 FIR 边界点，2 个非指定点，1 个 ACC 冲突；40 张缺口卡（航路端点 12、航点区域 5、IAP 10、未分类程序 13）全量审计确认全部处于 rejected/blocked 状态，均缺少唯一 424 来源依据，保持严格拒绝。模型/适配器不变。证据：diagnostics/r390-* 至 r392-*。

详细日志、差分和运行输出只保存在 `diagnostics/` 与 `output/`，不复制到本文件。

## 后续

- 保持 r187 冻结模型、adapter 和 r385 候选不变。
- 继续审计参考生成输入范围、SDK/Package Tool 与真实加载契约；优先寻找标准 XML 对象与节类型的独立契约证据。只有取得 424 直接证据或明确契约后才修改 adapter。
- 新目标格式可复用 `reference-build-source-audit`，先确认生成输入和工具边界，再决定是否进入目标 adapter 实现。
- 新目标格式复用同一 `NavModel` 和管线，另建独立 profile/adapter/validator/deployer。
