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
- 最近全量测试：`519 passed`；最新完成 R403 航路投影矩阵与连接完整性审计。
- 40 张缺口卡和 r390-r394 审计均未产生可授权的新投影；模型/adapter 保持不变。

## 验收门禁

1. 锁定 AIRAC、输入、模型哈希、来源文件/行号和拒绝原因。
2. 检查 SQLite/BGL 完整性、schema、Header、元数据、引用、排序和容量。
3. 模拟真实 SQL/游标及 NULL、长度、枚举、距离约束。
4. 点查 `ZBCF`、`ZUNZ`、`ZUUU` 和边界航段。
5. 双构建、独立 `validate`、逐文件 SHA-256 差分。
6. 完成备份恢复演练，再进行机场、出发/到达、SID/STAR/IAP、退出飞行和退出模拟器实机验证。

## 计划

- **R395 基线治理（已完成）：** 建立 29 文件差异-来源-加载契约决策矩阵（diagnostics/r395-convergence-decision-matrix.json），明确 8 个元数据文件由编译派生、1 个航路 BGL 受几何/端点阻塞、20 个机场 BGL 受 Section 基数与 IAP 来源阻塞；当前未授权修改 adapter。
- **R396 目标契约（已完成）：** 聚合 4 类核心 SDK 目标契约（XML 作用域/Route Previous-Next 排序/Section 基数与来源/元数据编译派生，diagnostics/r396-sdk-target-contract-audit.json），确认 3 项已在代码中强制实施，禁止逆向修改；当前未授权修改 adapter。
- **R397 授权增量（已完成）：** 评估 6 类主要候选项（航路几何/未决端点/机场 Section/IAP 主进近/未分类程序/元数据派生，diagnostics/r397-adapter-increment-authorization-audit.json），确认 0 项满足双重授权，全部处于 blocked 状态；保持 adapter 与模型不变。
- **R398 端到端看板（已完成）：** 聚合 29 文件全量收敛状态（diagnostics/r398-file-convergence-master.json），验证同输入自重放 29/29 一致，参考 0/29；确认 8 元数据、1 航路、20 机场 BGL 均有明确阻断归因；保持模型与 adapter 不变。
- **R399 状态快照（已完成）：** 锁定 33 个原始 CSV 哈希、r187 模型、40 张缺口卡及 29 文件重放基线（diagnostics/r399-status-snapshot.json），四级门禁明确 candidate_replay_equal=true、reference_byte_equal=false、deployable=false；保持模型与 adapter 不变。
- **R400 BGL 布局门禁（已完成）：** 审计 21 个目标 BGL 布局头结构（diagnostics/r400-bgl-layout-audit.json），确认 21 个 BGL 的头部版本一致（0x8051803），Section 差异仅反映编译组织，未授权逆向修改；四级门禁严格保持 deployable=false。
- **R401 管线主控（已完成）：** 运行端到端管线主控审计（diagnostics/r401-pipeline-master-audit.json），确认 33 CSV 来源、275 机场/640 跑道/438 导航台/2741 航点/4446 航段中间模型与 10 区域 BGL 投影架构全量闭环（pipeline_master_verified=true）；保持模型与 adapter 不变。
- **R402 模型重放（已完成）：** 审计 r187 冻结中间模型自重放与基准对比（diagnostics/r402-model-replay-audit.json），确认 11 类核心实体 0 差异（difference_count=0, consistent=true）；保持模型与 adapter 不变。
- **R403 航路矩阵（已完成）：** 审计 00_enroute.xml 航路投影矩阵（diagnostics/r403-airway-projection-matrix.json），确认 8,868 条双向连接全部具有 424 来源归属（candidate_connections_without_source_owner=0），4,394 段直接投影、40 段目标身份解析投影、12 段源端点缺失拒绝；保持模型与 adapter 不变。
- **R404+ 收敛：** 按差异矩阵处理剩余文件；达到 `29/29` 后才进入备份、部署和实机验证。

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