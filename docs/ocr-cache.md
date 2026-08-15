# OCR 缓存构建

`ocr-cache` 将 424 原始 PDF 制作成可复用、可断点续跑的本地 OCR 证据缓存。

流程固定为：

1. 校验 PDF 位于 `--source-root` 指向的 424 原始数据目录内。
2. 记录 PDF 相对路径、SHA-256 和物理页数到 `manifest.json`。
3. 使用 PDFium 将每个物理页渲染到缓存目录的 `.images`。
4. 对每个页面调用 `ocr-skill extract --backend llamacpp --json`。
5. 原样保存每页 OCR JSON，下一次运行只补缺失或无效页面。

OCR 缓存必须位于 424 原始数据目录之外。源 PDF 指纹、相对路径或页数变化时，命令会拒绝复用旧缓存；不能把上一 AIRAC 的 OCR 结果混入新周期。

本机 DeepSeek-OCR-2 llama.cpp 服务应使用仓库中的启动脚本，并固定种子与温度。例如：

```powershell
$runtime = .\scripts\start_local_ocr_server.ps1 `
  -ServerPath "F:\AI项目\ocr\llama.cpp\llama-server.exe" `
  -ModelPath "F:\AI项目\ocr\models\DeepSeek-OCR-2\deepseek-ocr-2-q8_0.gguf" `
  -MmprojPath "F:\AI项目\ocr\models\DeepSeek-OCR-2\mmproj-deepseek-ocr-2-q8_0.gguf" `
  -Seed 2608 `
  -Temperature 0 `
  -Restart |
  ConvertFrom-Json
```

脚本会拒绝复用模型、种子或温度不一致的本地服务，并原子写入包含 llama 构建号、模型与
`mmproj` SHA-256、种子和温度的运行时描述文件。新建缓存和重跑应传入
`--runtime-profile-file $runtime.runtime_profile_file`；CLI 会验证描述中的完整标识，避免人工
拼写的简写标识混入严格共识。

服务健康后，先验证单页：

```powershell
python -m fenix_default_navdata.cli ocr-cache `
  --pdf "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608\GeneralDoc\航路_4.1无线电导航设施——航路.pdf" `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache "$env:LOCALAPPDATA\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids" `
  --runtime-profile-file $runtime.runtime_profile_file `
  --first-page 1 --last-page 1
```

首张页检查通过后，移除 `--first-page` 和 `--last-page` 即可继续整册。默认单页 OCR 超时为 180 秒，可通过 `--timeout` 调整。`--force` 仅用于明确要求重新识别已有有效页面。通用 `ocr-cache` 默认不重试；`iap-ocr-cache` 默认对每页重试 2 次，可通过 `--retries` 调整。子进程固定以 UTF-8 输出，避免 Windows 控制台代码页把有效 OCR JSON 误判为失败。

本地 `ocr-skill` 的 llama.cpp 后端还具有独立的内部 HTTP 等待。可用 `--engine-timeout`
显式传入秒数，转换器仅对该子进程设置 `OCR_LLAMA_TIMEOUT_S`，并在 IAP 缓存报告中记录；
外层 `--timeout` 应大于该值。内部等待只决定何时放弃无响应页面，不改变模型输入、模式、
渲染比例或图像预处理。

仅完整页集可提供给后续解析器。缓存本身是本地数据资产，不得提交到 Git 仓库。

## IAP 图页批量缓存

`iap-ocr-cache` 不接受人工挑选的参考图页。它先读取 424 的现有 IAP 覆盖报告，再只针对
`ambiguous_chart` 与 `no_matching_chart` 分组选择源侧仪表进近图：

- 多图歧义：缓存该主进近段按机场、跑道和程序标签匹配到的全部源图页。
- 无匹配图页：缓存同机场、同跑道的全部仪表进近索引图页，供后续修复图页名称或角色解析。
- 没有唯一数据库主进近段：不进入 OCR 队列，因为图像识别不能补造数据库编码主段。

先使用 `--dry-run` 固定任务清单，再移除该开关执行。每个 PDF 缓存目录包含相对路径和
源 SHA-256，页面级 JSON、图像渲染参数和 OCR 配置均可断点复用。该命令的输出始终是
来源证据，不会写入候选包、解除 IAP 拒绝或修改参考比较结果。

2608R1 已用本机 DeepSeek-OCR-2/llama.cpp 完成 113 份源侧 IAP PDF 的 113 页缓存；
服务以 3 倍渲染处理图页时如出现 `Context size has been exceeded`，应将 llama-server
上下文提升至 `8192` 后重试既有缓存页。该缓存只用于后续可验证的图页解析规则，不是
候选导航数据来源。

## IAP OCR 证据审计

`iap-ocr-audit` 读取已完整的 IAP OCR 缓存，对每个源图页再次核对相对路径、源
SHA-256、页数与页面 JSON。它只从 OCR 文本中匹配已经存在于同一 424 主进近段的完整
标识，并输出 `unique_identifier_only` 或 `not_discriminating` 等证据状态。

该命令永久输出 `evidence_only=true` 与 `projection_allowed=false`。即使 OCR 中出现
两个以上主段标识且比其他候选更多，也不能直接选择图页、改变 BGL 投影或解除 IAP
拒绝；任何可投影规则仍须由可复现的源侧结构化图页角色与独立回归测试证明。

## IAP OCR 独立重跑比较

`iap-ocr-recheck` 对同一 424 原始数据重新审计两份完整 IAP OCR 缓存。它要求每个候选
图页的源文件、SHA-256、物理页和完整识别设置均可验证：命令、后端、模式、图像预处理、
渲染比例与非空 `runtime_profile`。它比较“候选图页、页码、当前数据库腿、角色”的交集、
各自独有项和同一配对的相邻关系变化。`--require-agreement` 会拒绝未记录、候选间混用或
两份缓存不一致的识别设置；任何差异都会返回非零，且即使完全一致仍保持不可投影。

```powershell
python -m fenix_default_navdata.cli iap-ocr-recheck `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r35" `
  --canonical-cache "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-rerun-20260815" `
  --rerun-cache "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-role-recheck-20260815" `
  --require-agreement `
  --output diagnostics\iap-ocr-role-recheck-20260815.json
```

## IAP OCR 三次共识门禁

`iap-ocr-consensus` 接受至少三份不同的完整缓存，以第一份为基线逐份核对候选源图页、
源 SHA-256、完整识别设置、角色-航点配对及其渲染邻接关系。任一项不一致时，
`--require-agreement` 返回非零。该命令只汇总可复查的 OCR 共识，始终输出
`evidence_only=true` 和 `projection_allowed=false`，不会选择图页、修改候选包或解除 IAP 拒绝。

```powershell
python -m fenix_default_navdata.cli iap-ocr-consensus `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r35" `
  --cache-roots `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-deterministic-a-20260815" `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-deterministic-b-20260815" `
    "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-deterministic-d-20260815" `
  --require-agreement `
  --output diagnostics\iap-ocr-role-consensus-a-b-d-strict-20260815.json
```

2608R1 的 A/B/D 三份独立缓存通过了严格共识：22 个分组、50 个候选页和 17 条
角色-航点证据及其相邻关系完全一致。历史 C 缓存虽然角色证据相同，但其识别设置将
命令记录为 `E:\python\3.12\Scripts\ocr-skill.exe`，而 A/B 使用 `ocr-skill`，
因此被完整识别设置门禁排除。D 在 `ZWHJ-5B` 页遇到本地引擎默认 300 秒内部等待后，
以 `--engine-timeout 900 --timeout 960` 断点完成；内部等待参数会写入缓存报告，但
不属于模型、模式或图像预处理的替代证明。
