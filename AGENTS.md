# 默认通用数据转换器协作规则

## 输入与边界

- 唯一内容来源：`424源数据\2608\2608` 的 424 CSV/PDF 与匹配 `RTE_SEG.csv`。
- 官方默认包、Fenix、参考 BGL/SQLite 只用于 schema、加载契约和只读差分；禁止回填参考 payload、坐标或记录。
- `NavModel` 是内容边界；默认 BGL 使用独立 adapter、validator、deployer，适配器不得重新解析 424。
- 目标是与 `Default navdata 2608R1` 逐文件 SHA-256 一致；完成前不得部署或 Release。

## 可复用管线

```text
lock-inputs -> ingest-424 -> evidence-audit -> normalize-model
-> model-audit -> project-target -> build-target -> validate-target
-> diff-and-audit -> stage-backup-deploy
```

## 当前状态（2026-08-22）

- 冻结模型：`output/intermediate-2608-r187-navaid-label-replay.json.gz`。
- 模型 SHA-256：`7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。
- 当前候选：`output/candidate-2608-default-r385-frozen-rebuild`。
- 参考 29 文件，字节一致 `0/29`，`deployable=false`；未部署、未实机验证、未 Release。
- 最近全量测试：`519 passed`；最新完成 r394 IAP 未决项来源审计。
- 40 张缺口卡和 r390-r394 审计均未产生可授权的新投影；模型/adapter 保持不变。

## 验收门禁

1. 锁定 AIRAC、输入、模型哈希、来源文件/行号和拒绝原因。
2. 检查 SQLite/BGL 完整性、schema、Header、元数据、引用、排序和容量。
3. 模拟真实 SQL/游标及 NULL、长度、枚举、距离约束。
4. 点查 `ZBCF`、`ZUNZ`、`ZUUU` 和边界航段。
5. 双构建、独立 `validate`、逐文件 SHA-256 差分。
6. 完成备份恢复演练，再进行机场、出发/到达、SID/STAR/IAP、退出飞行和退出模拟器实机验证。

## 计划

- **R395 基线治理：** 修复根目录摘要编码；建立 29 文件差异-来源-加载契约决策矩阵，冻结当前 r385 重放基线。
- **R396 目标契约：** 使用来源完整 fixture 验证 SDK/Package Tool 的 XML 作用域、排序、Section、索引和元数据影响，形成独立 profile 证据。
- **R397 授权增量：** 仅实现同时具备 424 直接来源、目标契约和最小测试的一个最小变更；执行双构建、validate、差分和点查。
- **R398+ 收敛：** 按差异矩阵处理剩余文件；达到 `29/29` 后才进入备份、部署和实机验证。

每个 R 是完整里程碑包（归因/实验或实现/回归/归档），原则上持续 1 至 3 个连续工作日；不为单个命令、缺口卡或重复测试拆分 R。`AGENTS.md` 仅记录里程碑摘要，详细证据放在 `diagnostics/` 和 `output/`。

## 已确认的通用边界

- 机场 XML 不写 `AiracCycle`；航路 XML 保留它。
- 无 `ORDER BY` 时必须固定写入顺序并验证物理行顺序。
- BGL Section 数量/类型只能说明布局，不能反推对象语义或授权复制参考内容。
- `RTE_SEG.CODE_TYPE_START/END` 可提供 VOR/NDB 航路端点类型；终端 `NAMED` 不得占用同一 `(region, ident)`。
- OCR 只能提供受限来源证据，不得创造主进近或绕过 `blocked/no_unique_primary`。

## 详细文档入口

- 默认契约：`docs/default-contract.md`。
- SDK/Package Tool：`docs/sdk-compile-contracts.md`。
- AS346/ToLiss 专用加载规则：`docs/aircraft-contracts/as346-toliss.md`。
- 阶段证据：`diagnostics/`；可复用审计实现：`src/fenix_default_navdata/*_audit.py`。