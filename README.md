# Default NavData Converter

把 424/2608 原始导航数据投影为 Microsoft Flight Simulator 2024 默认通用导航数据覆盖包。

> 当前为测试版。转换结果尚未完成参考成品字节级收敛与实机验证，不发布正式 Release。

## 当前能力

- 只读解析 424 2608 原始 CSV/PDF，以机场、跑道、ILS、终端程序和主要导航内容建立统一中间模型。
- 可将该中间模型导出为 `default-navdata-intermediate-model` 快照；默认 BGL 适配器和其他机模适配器都应消费这份快照，不必再次解析 424。
- 使用 `RTE_SEG.csv` 航路、端点和终端文档作为内容来源。
- 只读复制官方 `navigraph-nav-base` 与 `navigraph-nav-jepp` 全球基线。
- 在中国 NDB 覆盖层中明确区分 424 新增、直接 `NDB.csv` 修订与官方基线保留；官方字段仅用于保留原有基线，绝不由参考成品反向补写。
- 对 2608R1 已验证的 `GJ/ZG/245 kHz` SDK 身份冲突保留官方实体；未登记的同类冲突会阻止候选输出，避免生成 Package Tool 无法加载的重复导航台。
- 生成符合 SDK `bglcomp.xsd` 的确定性设施 XML。
- 自动探测 MSFS 2024 SDK `fspackagetool.exe`。
- 通过纯 ASCII 暂存项目调用 Package Tool，生成 BGL、`bglIndex.bout`、包元数据与 ContentInfo。
- 提供 `route-fragment-probe`：用最小合成航路复现实测 SDK 的片段、序号和 `routeType` 编码，不修改任何转换候选。
- 将 PDF 解析证据缓存到本机可复用目录，长时间转换中断后可以断点续跑。
- OCR 缓存绑定渲染比例、固定图像预处理和本地识别配置；可将完整 OCR 缓存与重跑缓存逐页比对，并独立审计每条记录是否可唯一回链到直接 424。仅 IAP 多图页消歧可在至少三份缓存完全一致后受限使用，不能新增程序或航段。
- 本地 llama.cpp OCR 启动器固定记录随机种子和温度，并生成可验证的运行时描述文件；OCR 缓存通过 `--runtime-profile-file` 绑定 llama 构建号、模型哈希、视觉投影哈希、种子与温度，避免手工简写混用不同推理配置。
- 对 GeneralDoc 4.1 中 OCR 识别码与直接 424 记录不一致的情形，只在类型、频率和坐标均唯一匹配时登记为 OCR 转录差异；直接 CSV 仍是唯一的导航台投影来源。
- 比较参考成品目录的逐文件大小和 SHA-256。
- 对候选与参考的 Navdatareader SQLite 执行只读语义差分；报告只保留逻辑身份、差异字段名和数量，不导出参考字段值。
- 在转换报告中分开记录 IAP 数据库腿、图页角色证据和未决分组；唯一 MAP/MAPT 终点只用于来源消歧，不代表完整图形语义已经解码。
- 转换报告的 `rejection_audit` 按直接 424/PDF 来源汇总记录和程序拒绝原因，并列出程序的来源位置；它只用于定位后续可证明的修复，不能自动放行、补齐或回填目标数据。
- 提供命令行、Tk GUI、备份、恢复、正式部署门禁和 GitHub 预发布更新检查。

## 本机已验证编译链

2026-08-11 使用 MSFS 2024 SDK 1.5.7 完成最小导航包真实构建：

- 输入：一个机场和一条跑道的设施 XML。
- 输出：`smoke.bgl`、`bglIndex.bout`、`layout.json`、`manifest.json` 与 ContentInfo。
- Package Tool 会通过 Steam 启动 `FlightSimulator2024.exe` 的 `BuildAssetPackages` 模式。
- SDK 项目路径必须为纯 ASCII；中文项目路径会在游戏命令行中损坏并导致启动崩溃。
- `fspackagetool.exe` 可能先返回非零代码，而后台构建进程仍在运行；转换器会等待该进程结束并以实际产物为判据。

## OCR 限制

- `llamacpp-direct` 是默认 OCR 后端。转换器直接调用本机 llama.cpp 的 OpenAI 兼容接口，并固定 `temperature=0`、`seed=2608`、`top_k=1` 和 `max_tokens=4096`。
- 每份新 OCR 缓存都记录内置适配器版本、输出 token 上限、图像渲染设置和可验证的运行时模型指纹。IAP 候选构建只接受至少三份这些设置完全一致的完整缓存。
- 旧 `ocr-skill/llamacpp` 缓存继续保留为只读审计证据，但缺少显式输出上限，不能与新的受限缓存混合参与 IAP 共识或候选构建。

## 使用

```powershell
python -m pip install -e .
python -m fenix_default_navdata.cli detect
python -m fenix_default_navdata.cli export-model --output output/nav-model-2608.json.gz
python -m fenix_default_navdata.cli build --output output/candidate-2608-default
python -m fenix_default_navdata.cli build --model output/nav-model-2608.json.gz --output output/candidate-2608-default
python -m fenix_default_navdata.cli validate `
  --candidate output/candidate-2608-default `
  --reference "F:\我的世界动画\AI项目\导航数据\424源数据\2608\Default navdata 2608R1"
python -m fenix_default_navdata.cli semantic-diff `
  --candidate-db "C:\诊断目录\candidate.sqlite" `
  --reference-db "C:\诊断目录\reference.sqlite" `
  --candidate-bgl-count 21 `
  --reference-bgl-count 21 `
  --output diagnostics\navdatareader\semantic-diff.json
python -m fenix_default_navdata.cli bgl-layout-audit `
  --candidate output\candidate-2608-default `
  --reference "F:\我的世界动画\AI项目\导航数据\424源数据\2608\Default navdata 2608R1" `
  --output diagnostics\bgl-layout-audit.json
python -m fenix_default_navdata.cli read-package `
  --package output\candidate-2608-default\zzz-pmdg-china-navdata `
  --output diagnostics\navdatareader\candidate.sqlite `
  --filenames *.bgl
python -m fenix_default_navdata.cli route-fragment-probe `
  --output diagnostics\route-fragment-probe `
  --bglcomp "C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe"
python -m fenix_default_navdata.cli source-gap-audit `
  --raw "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --semantic-diff diagnostics\navdatareader\semantic-diff.json `
  --output diagnostics\source-gap-audit.json
python -m fenix_default_navdata.cli terminal-coordinate-audit `
  --raw "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --semantic-diff diagnostics\navdatareader\semantic-diff.json `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r38" `
  --output diagnostics\terminal-coordinate-audit.json
python -m fenix_default_navdata.cli general-doc-keypoint-audit `
  --raw "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --semantic-diff diagnostics\navdatareader\semantic-diff.json `
  --general-doc-cache "$env:LOCALAPPDATA\default_navdata_converter\general-doc-ocr-cache-2608r1" `
  --output diagnostics\general-doc-keypoint-audit.json
python -m fenix_default_navdata.cli ocr-cache `
  --pdf "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608\GeneralDoc\航路_4.1无线电导航设施——航路.pdf" `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache "C:\Users\Administrator\AppData\Local\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids-rerun" `
  --render-scale 3 `
  --image-profile autocontrast-grayscale `
  --first-page 19 `
  --last-page 26
python -m fenix_default_navdata.cli ocr-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --canonical-cache "C:\Users\Administrator\AppData\Local\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids" `
  --rerun-cache "C:\Users\Administrator\AppData\Local\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids-rerun" `
  --require-agreement `
  --output diagnostics\ocr-rerun-audit.json
python -m fenix_default_navdata.cli ocr-source-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache "C:\Users\Administrator\AppData\Local\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids-rerun" `
  --output diagnostics\ocr-source-audit.json
python -m fenix_default_navdata.cli ad219-ndb-ocr-cache `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\ad219-ndb-ocr-cache-2608r1" `
  --airports ZBCZ
python -m fenix_default_navdata.cli ad219-ndb-ocr-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\ad219-ndb-ocr-cache-2608r1" `
  --airports ZBCZ `
  --output diagnostics\ad219-ndb-ocr-zbcz.json
python -m fenix_default_navdata.cli iap-ocr-cache `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r38" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\markdown-3x" `
  --mode ocr `
  --runtime-profile "deepseek-ocr-2-q8_0-seed2608-temp0" `
  --statuses ambiguous_chart no_matching_chart `
  --dry-run
python -m fenix_default_navdata.cli iap-ocr-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r38" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\markdown-3x" `
  --output diagnostics\iap-ocr-evidence-audit.json
python -m fenix_default_navdata.gui
```

也可以双击 `run_gui.bat`。

`read-package` 默认最多运行 120 秒，并在外部读取器日志超过 16 MiB 时停止本次诊断，避免异常 BGL 读取消耗无限磁盘空间。

`ocr-audit` 的主缓存必须完整，并且两份缓存必须绑定同一份原始 PDF SHA-256。它只比较重跑所含的物理页；`--require-agreement` 适合用于自动化任务，发现任何主缓存独有或重跑独有记录时返回退出代码 `1`。

`ocr-source-audit` 只审计 OCR 证据是否能按类型、频率和坐标唯一回链到直接 424 导航台；它会报告完全匹配、唯一 OCR 标识纠正和未决页码，但不会新增、修改或投影导航台。

`ad219-ndb-ocr-cache` 只缓存各机场未列入 `Charts.csv` 的原始 PDF；`ad219-ndb-ocr-audit` 只在 OCR 文本中定位 AD 2.19 到 AD 2.20 之间的 NDB 条目，并与直接 `NDB.csv` 对账。它会显式记录 OCR 自身缺失的显示名、磁差、高程和区域，以及直接 CSV 是否仍有空字段；任何结果均固定为 `projection_allowed=false`，不能作为默认 BGL NDB 的新增或修订来源。

`iap-ocr-cache` 会从现有 IAP 覆盖审计中自动筛出仅可能受图页识别影响的 `ambiguous_chart` 与 `no_matching_chart`，把对应的原始仪表进近 PDF 按相对路径和源 SHA-256 缓存到本机。它不会处理“没有唯一数据库主进近段”的分组，也不会因识别完成就解除任何 IAP 拒绝；必须另行新增可验证的图页解析规则和回归测试。

当本地 `ocr-skill` 在其默认 300 秒引擎等待内提前失败时，可显式传入 `--engine-timeout`，并将外层 `--timeout` 设得更长。该参数只覆盖单页等待，不改变模型、提示模式或图像预处理；IAP 缓存报告会记录本次执行设置。

`iap-ocr-audit` 逐项验证 IAP OCR 缓存的源相对路径、SHA-256、页数与页面 JSON，再报告 OCR 文本中能与主进近源腿精确匹配的标识，以及同一文本项、同一行或垂直相邻的明确角色标签。即使某一候选图页有至少两个标识的唯一命中或出现角色标签，报告仍会保持 `projection_allowed=false`；OCR 证据不能单独解除 IAP 拒绝。

`iap-ocr-recheck` 比较两份完整、独立重跑的 IAP OCR 缓存，仅报告角色证据的交集和差异；`--require-agreement` 会同时要求所有候选页记录且匹配完整识别设置：命令、后端、模式、图像预处理、渲染比例与非空 `runtime_profile`。即使两份缓存完全一致，它也不会选择图页或解除 IAP 拒绝。`iap-ocr-consensus` 将这一门禁扩展为至少三份缓存，逐份校验候选页、识别设置、角色-航点对和相邻关系；其输出同样不可投影。

`build --iap-ocr-cache-roots` 会重新审计至少三份缓存。仅当全部候选页、运行时标识、
识别设置、角色-航点对及其相邻关系完全一致时，构建才把这些角色用于已有
`ambiguous_chart` 分组的唯一图页选择。它不处理 `no_unique_primary` 或
`no_matching_chart`，不生成新程序腿，也不改变测试版、字节比对和实机验证门禁。与 OCR
无关的窄例外是未标变体的同机场同跑道 RNP AR 图题：当唯一图页的直接文本航点集合完整
包含数据库主进近至少两个不同固定点时，转换器会记录
`source_fixed_point_selections` 并关联该图页；缺点、同分或显式图题变体仍拒绝。
对于同样没有固定点限定的 RNP AR 图题，若只有一张图明确把数据库主进近腿标为
`IAF`、`IF`、`FAF`、`MAP` 或 `MAPT`，转换器会记录
`source_unqualified_rnp_ar_direct_role_selections`；多个候选命中、没有命中或图题带固定点
限定时仍拒绝。

当多个标题兼容候选中只有一张图的直接 `IAF`、`IF`、`FAF`、`MAP` 或 `MAPT` 标记与
来源主进近腿相交时，转换器会记录 `source_unique_direct_role_selections`。该规则不使用
OCR、参考成品或 Fenix；RNP AR 不能与非 AR 图题混用，带固定点限定与不带限定的 RNP AR
候选也不能混用，候选标题标准化后必须彼此不同；其余多个命中或零命中继续拒绝。

若多张候选图的直接角色-固定点集合中，只有一张严格包含每一张其他候选的集合，转换器会
记录 `source_dominant_direct_role_selections`。这同样只使用直接 424 文本；集合相同、
不可比较、重复标题或混合 AR 类别仍拒绝。

当此前所有直接角色、固定点和 RNP AR 规则均无法选择时，数据库主标签为 `Rxx`、候选
恰为一张非 AR 的 `RNP` 图和一张非 AR 的 `RNP ILS` 图时，转换器只选择前者，并记录
`source_plain_rnp_title_selections`。两图与来源腿相交的直接角色-固定点集合还必须相同且
非空；含 AR、额外候选、角色集合不一致或非 `R` 标签一律继续拒绝。

当其余直接角色规则仍不能选择，但来源主进近的第一条腿明确为 `IF`，且恰好一张候选图
将该固定点直接标为 `IF` 时，转换器选择该图并记录 `source_unique_first_if_selections`。
首腿不是 `IF`、首腿固定点为空或多张图同样命中时一律继续拒绝。

当前候选构建使用 `bounded-max4096-ocr-r80-a/b/c-20260817` 三份独立缓存。三者都记录了
内置 `llamacpp-direct` 适配器、`max_tokens=4096`、完整运行时描述、角色-航点对和相邻
关系，并通过严格共识。旧 `ocr-3x-deterministic-a/b/d/f-20260815` 即使角色证据相同，
也因缺少完整识别设置元数据被严格门禁拒绝，只能保留为只读审计证据。

显式指定 SDK Package Tool：

```powershell
python -m fenix_default_navdata.cli build `
  --raw "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --bglcomp "C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r38" `
  --iap-ocr-cache-roots `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\bounded-max4096-ocr-r80-a-20260817" `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\bounded-max4096-ocr-r80-b-20260817" `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\bounded-max4096-ocr-r80-c-20260817" `
  --output output/candidate-2608-default
```

`detect` 与 GUI 会自动查找当前工作区的 424 2608 原始目录和官方双基线。
需要手动指定可复用缓存时，使用 `--pdf-cache`。

## 安全边界

- 原始 CSV/PDF、官方 Community 包、参考 BGL、备份、日志和生成包均不进入仓库。
- 中间模型快照只保存已规范化的 424 `NavModel`，不含 PDF 缓存目录或 Fenix `nd.db3`。
- Fenix `nd.db3` 不参与本工具转换；Fenix 相关代码仅保留为历史适配器回归材料。
- 参考成品只用于只读差分，绝不复制参考 BGL 冒充转换结果。
- `semantic-diff` 不返回参考 SQLite 的坐标、频率、磁差、高程、名称或航路端点字段值，不能作为候选内容的反向来源。调用时必须显式提供候选和参考各自的预期 BGL 数；`bgl_file` 登记数不精确相等即拒绝生成报告。
- `bgl-layout-audit` 以参考包的顶层包名确定比较范围，只读取候选和参考最终包内 BGL 的文件路径、文件大小、SHA-256 相等性、头部版本、QMID 和节表类型/计数/尺寸；候选根目录下的 SDK `_work` 中间产物和不在参考范围内的官方依赖副本始终排除，数量会记录在 `scope`。它不读取或导出任何参考导航记录，输出仅用于定位 SDK 编译布局与内容覆盖差异。
- `scripts/airport_subset_probe.py` 的隔离构建会在本次诊断目录写入 `probe-report.json`，记录完整输入选择、每个探针 BGL 的文件大小、头部版本、QMID、节表类型/计数/尺寸和读取器状态。它只用于验证 SDK 输入对象如何影响编译布局，不读取参考 BGL 的内容。
- 该探针的 `--set-airport-attribute name=value` 仅为隔离编译实验设置 XML 属性，绝不写入 `NavModel` 或正式候选。
- `--append-airport-child "TAG;NAME=VALUE;..."` 可在每个被选机场末尾追加属性型 SDK 子对象，用于可复现的单变量布局实验；它同样永远不写入 `NavModel` 或正式候选。
- `--append-root-child "TAG;NAME=VALUE;..."` 以同样约束在 `FSData` 根节点追加对象，用于区分根节点和机场作用域的 SDK 编译布局。
- `--delete-airport-procedures` 用于隔离编译实验，验证正式适配器同样使用的 `DeleteAirport` 进近、离场和进场删除语义。
- `source-gap-audit` 只接受完整、只读且已脱敏、并已证明 BGL 登记数完整的 `semantic-diff` 报告；它只输出 424 来源分类计数，不导出或保存参考逻辑身份。航路字段差异会额外汇总同源 424 航段的连接状态、端点完整性和已携带元数据，不输出参考值或原始身份。它还会核验 `ROUTE_HOLDING.csv` 是否只回链既有点；无区域键或复用位置标签的记录不得当作新 enroute 航点。
- `terminal-coordinate-audit` 使用同一类完整脱敏差分，只读核验参考缺失航点是否可由 424 终端坐标页独立证明；输出只含来源类别计数。全局航点只有在 `terminal_source_promotable` 非零时，才可进入通用跨机场提升规则；机场作用域的 `airport_terminal_coordinate_source_present` 仅表示同机场坐标页存在来源，不构成新增或补写依据。传入 `--check-retention` 后，审计会再区分现有规则是否保留此类来源点；`airport_terminal_coordinate_not_retained` 仍只是一项调查信号，必须另行证明通用保留与投影规则，不能按审计结果列表补点。
- `general-doc-keypoint-audit` 仅使用带 SHA-256 校验的 ENR 4.4 OCR 缓存与同源 FIR 几何，分类参考缺失全局航点是否能由关键点页独立证明；输出只含类别计数。`general_doc_source_promotable` 非零时，必须先把来源规则、最小 fixture 和候选报告接入构建，不能按审计列表补点。
- Package Tool 构建和 Community 覆盖前都要求 `FlightSimulator2024.exe` 已完全退出。
- 覆盖前自动备份四个相关包；测试候选、不完整候选、未完成字节比对或实机验证的候选都会拒绝部署。
- 只有 `status=release`、参考覆盖包逐文件字节一致，并已登记 ZBCF、ZUNZ、ZUUU 与退出稳定性实机验证的候选才可覆盖 Community。

## 尚未完成

- 参考成品采用 `00_enroute.bgl` 加十个机场分区 BGL，并另有十个机场补丁 BGL；当前完整转换仍需按相同边界拆分。
- SID、STAR、IAP、航路与导航设施的 BGL 投影仍需补齐和逐项验证。
- 必须完成 BGL 结构差分、逐文件 SHA-256 收敛，以及 ZBCF、ZUNZ、ZUUU 实机回归。
