# 本地 OCR 服务

`iap-ocr-cache` 使用 `ocr-skill` 调用本机 DeepSeek-OCR-2/llama.cpp 服务。服务未启动时，
先使用仓库脚本启动；脚本不会下载模型、修改 424 原始数据或写入候选包。

```powershell
$runtime = .\scripts\start_local_ocr_server.ps1 `
  -ServerPath "F:\AI项目\ocr\llama.cpp\llama-server.exe" `
  -ModelPath "F:\AI项目\ocr\models\DeepSeek-OCR-2\deepseek-ocr-2-q8_0.gguf" `
  -MmprojPath "F:\AI项目\ocr\models\DeepSeek-OCR-2\mmproj-deepseek-ocr-2-q8_0.gguf" |
  ConvertFrom-Json
```

默认配置为 `http://127.0.0.1:8090`、8192 上下文、单槽和全部 GPU 层。脚本会：

1. 验证服务程序、模型与视觉投影文件存在。
2. 仅允许绑定本机回环地址，避免意外开放 OCR 服务。
3. 若健康服务已经存在，直接返回 `already_ready`，不会启动第二个进程。
4. 若端口已被未知进程占用，拒绝覆盖。
5. 将标准输出和错误日志写入 `%LOCALAPPDATA%\default_navdata_converter\ocr-server`。
6. 等待 `/health` 成功后返回进程 ID、日志路径和完整运行时标识。
7. 原子写入 `%LOCALAPPDATA%\default_navdata_converter\ocr-server\runtime-profile.json`，
   其中包含 llama 构建号、模型与视觉投影 SHA-256、种子和温度。

服务可用后，使用可复现的缓存入口，而不是直接对图页做一次性识别：

```powershell
python -m fenix_default_navdata.cli iap-ocr-cache `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r35" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x" `
  --backend llamacpp `
  --mode ocr `
  --render-scale 3 `
  --runtime-profile-file $runtime.runtime_profile_file
```

缓存按原始 PDF 相对路径、SHA-256、渲染比例、图像预处理和识别配置隔离。识别输出只用于
来源审计；在建立独立的图页角色解析规则和回归测试前，不能解除 IAP 拒绝或用于 BGL 投影。

可以用相同的原始数据和缓存生成只读审计。审计会记录与当前数据库进近腿同一 OCR 文本项、
同一行或垂直相邻的明确 `IAF`、`IF`、`FAF`、`MAP`、`MAPT` 标签，并按页码、航点和角色
去重，保留最强的关系；不会由标识命中数量或 OCR 角色证据选择图页，更不会解除 IAP 拒绝。

```powershell
python -m fenix_default_navdata.cli iap-ocr-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --pdf-cache "$env:LOCALAPPDATA\default_navdata_converter\pdf-evidence-cache-2608r1-r35" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\iap-ocr-cache-2608r1\ocr-3x-rerun-20260815" `
  --output "diagnostics\iap-ocr-evidence-audit-ocr-3x-rerun-20260815.json"
```
