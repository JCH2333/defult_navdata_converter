# OCR 缓存构建

`ocr-cache` 将 424 原始 PDF 制作成可复用、可断点续跑的本地 OCR 证据缓存。

流程固定为：

1. 校验 PDF 位于 `--source-root` 指向的 424 原始数据目录内。
2. 记录 PDF 相对路径、SHA-256 和物理页数到 `manifest.json`。
3. 使用 PDFium 将每个物理页渲染到缓存目录的 `.images`。
4. 对每个页面调用 `ocr-skill extract --backend llamacpp --json`。
5. 原样保存每页 OCR JSON，下一次运行只补缺失或无效页面。

OCR 缓存必须位于 424 原始数据目录之外。源 PDF 指纹、相对路径或页数变化时，命令会拒绝复用旧缓存；不能把上一 AIRAC 的 OCR 结果混入新周期。

本机 DeepSeek-OCR-2 llama.cpp 服务健康后，先验证单页：

```powershell
python -m fenix_default_navdata.cli ocr-cache `
  --pdf "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608\GeneralDoc\航路_4.1无线电导航设施——航路.pdf" `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache "$env:LOCALAPPDATA\default_navdata_converter\general-doc-ocr-cache-2608r1\enr-4.1-navaids" `
  --first-page 1 --last-page 1
```

首张页检查通过后，移除 `--first-page` 和 `--last-page` 即可继续整册。默认单页 OCR 超时为 180 秒，可通过 `--timeout` 调整。`--force` 仅用于明确要求重新识别已有有效页面。通用 `ocr-cache` 默认不重试；`iap-ocr-cache` 默认对每页重试 2 次，可通过 `--retries` 调整。子进程固定以 UTF-8 输出，避免 Windows 控制台代码页把有效 OCR JSON 误判为失败。

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
