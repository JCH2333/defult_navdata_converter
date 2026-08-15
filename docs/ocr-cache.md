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

首张页检查通过后，移除 `--first-page` 和 `--last-page` 即可继续整册。默认单页 OCR 超时为 180 秒，可通过 `--timeout` 调整。`--force` 仅用于明确要求重新识别已有有效页面。

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
