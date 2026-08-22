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
- 最近全量测试：`519 passed`；最新完成 R421 APOGO 航路端点来源卡片审计。
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
- **R404 表达矩阵（已完成）：** 审计 SDK 编译表达矩阵（diagnostics/r404-sdk-bgl-expression-matrix.json），聚合航路序列化与机场表达候选项，确认无来源完整且未测试的新单变量（blocked_on_machine_readable_target_evidence）；保持模型与 adapter 不变。
- **R405 工具链审计（已完成）：** 审计 MSFS 2024 SDK 1.6.9 与 1.5.3 Package Tool 二进制指纹及历史探针证据（diagnostics/r405-sdk-toolchain-audit.json），明确工具链差异不构成目标表达契约改变的授权（toolchain_difference_without_target_expression_evidence）；保持模型与 adapter 不变。
- **R406 核心映射（已完成）：** 审计 424 核心实体到 NavModel 的通用映射（diagnostics/r406-core-model-mapping-audit.json），确认 275 机场、640 跑道、438 导航台、2,741 航点、4,446 航路段 100% 来源溯源且坐标有效（all_core_groups_verified=true）；保持模型与 adapter 不变。
- **R407 航路限制与类型（已完成）：** 审计 ROUTE_RESTRICT（309 条）与 J/V 航路类型映射（diagnostics/r407-route-*.json），确认限制描述属文本证据保留（projection_allowed=false），J/V 映射因元数据冲突不足以建立独立适配器规则（insufficient_for_adapter_rule）；保持模型与 adapter 不变。
- **R408 航路差异（已完成）：** 审计 2,263 条同源航路字段差异（diagnostics/r408-airway-diff-audit.json），确认 2,241 条为纯几何包围盒/坐标量化差异、22 条带最低高度差异，全部为 same_source_airway_and_sequence 同源记录，受编译器量化阻断；保持模型与 adapter 不变。
- **R409 空域与非指定端点（已完成）：** 审计 424 四类空域（744 主表/6,492 顶点，diagnostics/r409-airspace-source-audit.json）与地名点 **** 航路端点缺口卡（diagnostics/r409-non-designated-*.json），确认空域属证据保留，非指定点禁止跨类型补写区域（projection_allowed=false）；保持模型与 adapter 不变。
- **R410 航司与通用文档（已完成）：** 审计 424 FLIGHT_AIRLINE（390,659 航线点，100% 匹配 13,907 航线，diagnostics/r410-airline-*.json）与 GENERAL_DOC（132 PDF 100% 匹配，diagnostics/r410-general-*.json），确认航司网络与总览目录属来源证据保留（projection_allowed=false）；保持模型与 adapter 不变。
- **R411 关键点来源（已完成）：** 审计 ENR 4.4 关键点（2,108 条解析记录）对 6,342 个参考独有航点的来源覆盖（diagnostics/r411-general-doc-keypoint-audit.json），确认 3,007 机场独有、3,216 文本缺失、119 区域不符/越界，可安全提升航点数为 0；保持模型与 adapter 不变。
- **R412 终端坐标覆盖（已完成）：** 审计 424 终端坐标图页（12,991 终端点，保留 12,549 点）对 6,342 个参考独有航点的来源覆盖（diagnostics/r412-terminal-coordinate-audit.json），确认 5,649 点未在坐标页出现、347 单机场点、346 未保留点，无新可全局提升航点；保持模型与 adapter 不变。
- **R413 程序图表覆盖（已完成）：** 审计 424 终端程序（10,409 程序段/53,268 航段，diagnostics/r413-procedure-*.json）与 6 机场 42 个未缓存原始 PDF 直接文本（diagnostics/r413-uncached-*.json），确认全部为 not_directly_relevant，无未读直接证据（no_unread_direct_424_evidence=true）；保持模型与 adapter 不变。
- **R414 坐标增量比对（已完成）：** 审计 1,604 个同源航点字段差异在终端坐标页的覆盖分布（diagnostics/r414-terminal-coordinate-delta-audit.json），确认 487 机场独有点、612 根节点点有图页支持，10 个多坐标点，495 个完全未出现，属作用域与坐标量化差异；保持模型与 adapter 不变。
- **R415 关键端点卡片（已完成）：** 深度审计跨 FIR 边界点 P225 来源链条（diagnostics/r415-airway-endpoint-card-P225.json），确认其连接 ZH/ZL 多邻接地区且 ACC 无法唯一映射（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R416 P127 端点卡片（已完成）：** 深度审计跨 FIR 边界点 P127 来源链条（diagnostics/r416-airway-endpoint-card-P127.json），确认其连接 ZG/ZP/ZU 三邻接地区且 ACC 包含武汉/成都/长沙等跨区管制（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R417 P188 端点卡片（已完成）：** 深度审计跨 FIR 边界点 P188 来源链条（diagnostics/r417-airway-endpoint-card-P188.json），确认其连接 ZH/ZS 两邻接地区且 ACC 包含北京/济南/郑州等跨区管制（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R418 P121 端点卡片（已完成）：** 深度审计跨 FIR 边界点 P121 来源链条（diagnostics/r418-airway-endpoint-card-P121.json），确认其连接 ZG/ZS 两邻接地区且 ACC 包含广州/长沙等不同管制区（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R419 P239 端点卡片（已完成）：** 深度审计跨 FIR 边界点 P239 来源链条（diagnostics/r419-airway-endpoint-card-P239.json），确认其连接 ZH/ZP 两邻接地区且 ACC 映射指向冲突地区 ZG/ZH（rejected_multiple_neighbor_regions_with_conflicting_acc_regions），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R420 OTBUG 端点卡片（已完成）：** 深度审计跨 FIR 边界点 OTBUG 来源链条（diagnostics/r420-airway-endpoint-card-OTBUG.json），确认其连接 ZH/ZS 两邻接地区且 ACC 跨越上海/广州/武汉/合肥等三区管制（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R421 APOGO 端点卡片（已完成）：** 深度审计跨 FIR 边界点 APOGO 来源链条（diagnostics/r421-airway-endpoint-card-APOGO.json），确认其连接 ZB/ZL 两邻接地区且 ACC 太原无法唯一映射（rejected_multiple_neighbor_regions_with_incomplete_acc_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R422+ 收敛：** 按差异矩阵处理剩余文件；达到 `29/29` 后才进入备份、部署和实机验证。

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