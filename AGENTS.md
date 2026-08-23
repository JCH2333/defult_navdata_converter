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

## 当前状态（2026-08-23）

- 基线模型：`output/intermediate-2608-r187-navaid-label-replay.json.gz`；当前修复模型：`output/intermediate-2608-r394-global-procedure-ils-fix.json.gz`。
- 模型 SHA-256：`7cec24bd4a57545d39aab037abe4125c763ad12f364bd5f8f0073b0e050fdb4b`。
- 当前候选：`output/candidate-2608-default-r403-official-overlay-connection-fix`。
- 参考 29 文件，字节一致 `0/29`，`deployable=false`；已进入受控功能测试暂存，未实机验证、未 Release。
- 暂存备份：`F:\games\community\backups\default_navdata_20260822_174608`；官方两个 2608 包原样保留，中国区域两个候选包按哈希核验一致。
- 最近部署备份：`F:\games\community\backups\default_navdata_20260823_224104`；官方两个 2608 包原样保留，中国区域 r403 两个候选包已部署。
- 最近全量测试：`532 passed`；候选 `validate` 通过，仍为 `deployable=false`，等待实机验证。
- 已生成可转发功能测试包：`output/functional-test-navdata-2608-r385.zip`；仅含两个中国区域包、安装/恢复脚本、SHA-256 清单和游戏内清单，打包后隔离安装/恢复演练通过。
- 40 张缺口卡和 r390-r394 审计均未产生可授权的新投影；模型/adapter 保持不变。
- 官方覆盖冲突修复（2026-08-23）：参考成品与官方包均证明 `P396`/中国 `H14` 是官方缺失增量，而 `HO/YHD/WHA`、`W214/W215`、`B213->WHA` 已由官方包提供。r402 使用可复用 `official_overlay` 过滤同身份且 0.25 NM 内的官方重复导航台/航路边，保留 `HO->P396->P339`；过滤 113 个导航台和 1,399 条航路边。证据：`diagnostics/r402-official-overlay-audit.json`、`diagnostics/r402-custom-enroute-reader.sqlite`、`diagnostics/r175-reference-00-enroute-reader.sqlite`。
- r402 实机回归：过度删除官方重叠边导致 `W215->SADBU`、`SADBU->W214`、`HO->H14` 无法输入；官方包不能替代自定义包中的连接声明。

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
- **R422 LELIM 端点卡片（已完成）：** 深度审计单邻接带 ACC 冲突点 LELIM 来源链条（diagnostics/r422-airway-endpoint-card-LELIM.json），确认其邻接 ZG 但 ACC 指向上海（ZS），属未决冲突（unresolved_requires_new_direct_evidence），保持拒绝（projection_allowed=false）；保持模型与 adapter 不变。
- **R423 缺口闭环复核（已完成）：** 结合最新 r394-r422 细粒度审计复核全量 40 张来源缺口卡（diagnostics/r423-default-gap-cards-closure.json），确认 12 端点、5 航点、10 IAP、13 未分类程序仍 100% 保持 blocked/rejected 状态（all_cards_rejected_or_blocked=true）；保持模型与 adapter 不变。
- **R424 航路二进制差分（已完成）：** 审计 00_enroute.bgl 头结构与 Section 二进制差异（diagnostics/r424-bgl-binary-diff-enroute.json），确认 7 个 Section 类型与 QMID 瓦片一致，差异集中于 Section 34 航路与 Section 19/23 航点数量（数量差由未决边界端点引起）；保持模型与 adapter 不变。
- **R425 机场二进制差分（已完成）：** 审计 10 区域机场 BGL 二进制与 Section 结构（diagnostics/r425-bgl-binary-diff-airports.json），确认 10 个 BGL Section 3（机场）基数一致，Section 19/23/34 差异源于 SDK 项目级与 QMID 瓦片级编译组织；保持模型与 adapter 不变。
- **R426 补丁 BGL 差分（已完成）：** 审计 10 区域机场补丁 BGL 二进制与 Section 结构（diagnostics/r426-bgl-binary-diff-airport-patches.json），确认 10 个补丁 BGL Section 3（机场）基数与主区完全对称（275 个），Section 19/23/34 差异源于编译器瓦片索引分配；保持模型与 adapter 不变。
- **R427 记录步长审计（已完成）：** 审计 00_enroute.bgl 7 类 Section 内部记录步长与闭合边界（diagnostics/r427-bgl-record-layout-enroute.json），确认 7 个 Section 均为 fixed_stride 闭合结构（candidate_all_sections_closed=true），Section 20 Magvar 前 65,536 项位置精确一致；保持模型与 adapter 不变。
- **R428 模板来源审计（已完成）：** 审计 29 个参考文件与官方 navigraph-nav-base/jepp 双模板关系（diagnostics/r428-reference-template-source-audit.json），确认 21 个 BGL 无模板匹配（100% 专有生成）、8 个元数据文件仅为同名派生（direct_copy_path_proven=false），禁止直接复制参考数据；保持模型与 adapter 不变。
- **R429 BGL 投影主控（已完成）：** 审计 10 区域机场与航路 BGL 投影 schema 架构（diagnostics/r429-bgl-projection-master-audit.json），确认 10 个区域 275 机场/640 跑道/10,409 程序段/430 ILS 与 00_enroute 4,446 航段全量通过架构闭环校验（bgl_projection_master_pipeline_verified=true）；保持模型与 adapter 不变。
- **R430 来源主控（已完成）：** 运行 424 到中间模型全量主控审计（diagnostics/r430-source-model-master-audit.json），确认 16 类来源数据组全量完整闭环，5 大核心实体与终端程序证据链严格溯源（master_pipeline_verified=true）；保持模型与 adapter 不变。
- **R431 功能测试暂存（已完成）：** 新增 `stage-functional-test`，仅接受 `candidate/functional-test` 测试候选；先备份四个 Community 包，原样保留官方 `navigraph-nav-base`/`navigraph-nav-jepp`，只替换中国区域 `zzz-pmdg-china-navdata`/`zzz-pmdg-china-navdata-airport-patch`，并写入 `backup-manifest.json`、`functional-test-stage.json`；部署失败自动恢复。正式 `deploy` 门禁未放宽。备份路径见当前状态。
- **R391 ZBCF 程序名称修复（已完成）：** `_DATABASE_PROCEDURE` 修正为禁止在 `P528-9ZA/P528-9ZD` 处提前截断，PDF 证据缓存版本升至 44；真实 PDF 验证 `ZA=进场`、`ZD=离场`。r390 模型程序段 `10,466`，r391 候选 XML/BGL 已生成并部署；ZBCF 旧乱码名称消失。
- **R392 全局程序/ILS/参考对照（已完成）：** 全局 SID/STAR 名称去除错误连字符；参考和候选读取器均含 `SADBU(ZL/WN)`、`YHD(ZL/V)`、`W215`、`H14`。依据 4 张 `RNAV ILS/DME z` 直接图和唯一 RNP 主程序，新增 ZSHC `I06/I24/I07-Z/I25-Z` ILS Approach；r394 模型程序段 `10,624`，r395 候选已部署。
- **R397 航路点/航路身份修复（已完成）：** 关闭主导航包根级终端航点复制；程序腿优先绑定同区域全局 NDB/VOR；过滤与全局导航台同物理位置的机场局部重复点。r397 XML 中 `SADBU/HO/YHD/DWZ` 各单一身份，`SADBU` 挂载 `W214/W215`，`HO` 挂载 `H14/W214`，已部署。
- **R399 航路端点官方坐标修复（已完成）：** 使用已验证官方设施索引坐标投影所有 VOR/NDB 航路端点；r399 编译读取结果与参考一致，`P396/WHA/YHD/HO` 身份和坐标对齐，`H14/B213/W215` 连接保留，已部署。
- **R400 游戏内航路/进近复测（待用户执行）：** 复测 `HO H14 P396`、`B213 WHA`、`YHD W215 SADBU W214` 与 `ZUUU AKDK7U/I02R`；`I02R` 的直接来源主段目前只有 `UU615`，`BHS` 属复飞段。
- **R400 NAIP 航路类别修复（已完成）：** 目标投影使用 `H/J -> JET`、`V/W -> VICTOR`、其他 RNAV/区域航路保持 `BOTH`；r400 已验证 `H14=JET`、`W214/W215=VICTOR`、`B213=BOTH` 并部署。
- **官方覆盖连接修复（已完成构建/部署，待 R432 实机）：** r403 保留参考成品所需的自定义导航台和航路连接，同时把 52 条同官方导航台规范化为官方字段；自定义读取确认 `HO` 挂载 `H14/W214`、`SADBU` 挂载 `W214/W215`。部署备份：`F:\games\community\backups\default_navdata_20260823_224104`。
- **功能测试交付（已完成）：** `tools/create-functional-test-package.ps1` 可从候选生成可转发 ZIP，`tools/verify-functional-test-package.ps1` 在隔离 Community 演练安装、官方包保留和恢复；模板位于 `packaging/functional-test-2608/`。ZIP 仅携带两个中国区域包，不携带或覆盖官方 2608 包。
- **R432 游戏内验证（待用户执行）：** 使用当前暂存包测试 ZBCF、ZUNZ、ZUUU 的机场/跑道/出发到达/SID/STAR/IAP、普通航路、VOR/NDB/航点搜索、重启加载和退出稳定性；边界端点仅作负面稳定性测试。完成前保持 `deployable=false`。
- **R433+ 字节收敛（长期）：** 只有新的直接来源、目标生成器或加载契约证据才继续推进 `29/29`；不得用功能通过替代字节一致。

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
