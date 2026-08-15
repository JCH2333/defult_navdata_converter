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
