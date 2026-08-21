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
- 冻结候选：`output/candidate-2608-default-r366-terminal-global-identity`
- 实验候选：`output/candidate-2608-default-r377-navaid-fir-priority-full-evidence`
- 参考范围 29 个文件，字节一致 `0/29`，`deployable=false`；未部署、未实机验证、未 Release。
- 最近全量测试：`517 passed`。

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
- r373-r376：参考 BGL 无可复用模板，未找到对应生成器；差异继续保持来源/加载契约 blocked。
- r377-r378：完成 navaid 区域规则与完整证据重放；r377 候选本地契约通过，但参考仍 `0/29`。
- r379：完成机场作用域来源审计。424、模型和候选均为 275 个机场，全部有 `AD_HP.csv`、`Terminal` 和 CSV 文本证据；参考额外 7 个机场（`ZBSH,ZGFS,ZL02,ZL03,ZSLT,ZW01,ZW02`）无 424 直接证据，禁止回填。证据：`diagnostics/r379-airport-scope-source-audit.json`。
- r380：新增可复用 `reference-build-source-audit`，只读记录参考生成输入、候选 XML 和 SDK 工具边界。真实审计发现参考包有 `21` 个 BGL、无 XML/生成器；候选有 `47` 个 XML；两个 SDK 均有 Package Tool 和 XSD、无 `bglcomp.exe`。参考 manifest 的 creator 为 `PMDG DFD v2 converter`，仍不能授权修改 adapter。证据：`diagnostics/r380-reference-build-source-audit.json`。
- r381：机场参考 BGL 普遍含 `0x17`、多数含 `0x33`，候选对应缺失且多出 `0x35`；机场/航路节计数也大幅不同。该审计只确认结构差异，不能据此推断对象语义或授权复制参考记录。证据：`diagnostics/r381-airport-bgl-cardinality.json`、`diagnostics/r381-enroute-bgl-cardinality.json`。
- r382：表达式矩阵接入 r372 `OffsetThreshold` 探针摘要，兼容历史文本型缺失节字段；33/33 构建成功、未改模型/候选、未收敛参考缺口，故标记 `rejected_after_probe`。航路序列化仍无新的单变量。证据：`diagnostics/r382-sdk-bgl-expression-matrix.json`；定向测试 `7 passed`，全量测试 `517 passed`。
- r383：来源完整性审计确认 33 个根 CSV 全部归类、16/16 来源组完整，`source_complete_sdk_probe_candidates=[]`。剩余来源组均为已投影、证据保留或目标结构拒绝；未发现可安全新增到默认 adapter 的 424 字段。证据：`diagnostics/r383-source-model-completeness.json`。

详细日志、差分和运行输出只保存在 `diagnostics/` 与 `output/`，不复制到本文件。

## 后续

- 保持 r366 冻结模型、adapter 和候选不变。
- 继续审计参考生成输入范围、SDK/Package Tool 与真实加载契约；优先寻找标准 XML 对象与节类型的独立契约证据。只有取得 424 直接证据或明确契约后才修改 adapter。
- 新目标格式可复用 `reference-build-source-audit`，先确认生成输入和工具边界，再决定是否进入目标 adapter 实现。
- 新目标格式复用同一 `NavModel` 和管线，另建独立 profile/adapter/validator/deployer。
