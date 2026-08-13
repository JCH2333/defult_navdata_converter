# Default NavData Converter

把 424/2608 原始导航数据投影为 Microsoft Flight Simulator 2024 默认通用导航数据覆盖包。

> 当前为测试版。转换结果尚未完成参考成品字节级收敛与实机验证，不发布正式 Release。

## 当前能力

- 只读解析 424 2608 原始 CSV/PDF，以机场、跑道、ILS、终端程序和主要导航内容建立统一中间模型。
- 使用 `RTE_SEG.csv` 航路、端点和终端文档作为内容来源。
- 只读复制官方 `navigraph-nav-base` 与 `navigraph-nav-jepp` 全球基线。
- 在中国 NDB 覆盖层中明确区分 424 新增、直接 `NDB.csv` 修订与官方基线保留；官方字段仅用于保留原有基线，绝不由参考成品反向补写。
- 对 2608R1 已验证的 `GJ/ZG/245 kHz` SDK 身份冲突保留官方实体；未登记的同类冲突会阻止候选输出，避免生成 Package Tool 无法加载的重复导航台。
- 生成符合 SDK `bglcomp.xsd` 的确定性设施 XML。
- 自动探测 MSFS 2024 SDK `fspackagetool.exe`。
- 通过纯 ASCII 暂存项目调用 Package Tool，生成 BGL、`bglIndex.bout`、包元数据与 ContentInfo。
- 将 PDF 解析证据缓存到本机可复用目录，长时间转换中断后可以断点续跑。
- 比较参考成品目录的逐文件大小和 SHA-256。
- 对候选与参考的 Navdatareader SQLite 执行只读语义差分；报告只保留逻辑身份、差异字段名和数量，不导出参考字段值。
- 在转换报告中分开记录 IAP 数据库腿、图页角色证据和未决分组；唯一 MAP/MAPT 终点只用于来源消歧，不代表完整图形语义已经解码。
- 提供命令行、Tk GUI、备份、恢复、正式部署门禁和 GitHub 预发布更新检查。

## 本机已验证编译链

2026-08-11 使用 MSFS 2024 SDK 1.5.7 完成最小导航包真实构建：

- 输入：一个机场和一条跑道的设施 XML。
- 输出：`smoke.bgl`、`bglIndex.bout`、`layout.json`、`manifest.json` 与 ContentInfo。
- Package Tool 会通过 Steam 启动 `FlightSimulator2024.exe` 的 `BuildAssetPackages` 模式。
- SDK 项目路径必须为纯 ASCII；中文项目路径会在游戏命令行中损坏并导致启动崩溃。
- `fspackagetool.exe` 可能先返回非零代码，而后台构建进程仍在运行；转换器会等待该进程结束并以实际产物为判据。

## 使用

```powershell
python -m pip install -e .
python -m fenix_default_navdata.cli detect
python -m fenix_default_navdata.cli build --output output/candidate-2608-default
python -m fenix_default_navdata.cli validate `
  --candidate output/candidate-2608-default `
  --reference "F:\我的世界动画\AI项目\导航数据\424源数据\2608\Default navdata 2608R1"
python -m fenix_default_navdata.cli semantic-diff `
  --candidate-db "C:\诊断目录\candidate.sqlite" `
  --reference-db "C:\诊断目录\reference.sqlite" `
  --output diagnostics\navdatareader\semantic-diff.json
python -m fenix_default_navdata.gui
```

也可以双击 `run_gui.bat`。

显式指定 SDK Package Tool：

```powershell
python -m fenix_default_navdata.cli build `
  --raw "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --bglcomp "C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe" `
  --output output/candidate-2608-default
```

`detect` 与 GUI 会自动查找当前工作区的 424 2608 原始目录和官方双基线。
需要手动指定可复用缓存时，使用 `--pdf-cache`。

## 安全边界

- 原始 CSV/PDF、官方 Community 包、参考 BGL、备份、日志和生成包均不进入仓库。
- Fenix `nd.db3` 不参与本工具转换；Fenix 相关代码仅保留为历史适配器回归材料。
- 参考成品只用于只读差分，绝不复制参考 BGL 冒充转换结果。
- `semantic-diff` 不返回参考 SQLite 的坐标、频率、磁差、高程、名称或航路端点字段值，不能作为候选内容的反向来源。
- Package Tool 构建和 Community 覆盖前都要求 `FlightSimulator2024.exe` 已完全退出。
- 覆盖前自动备份四个相关包；测试候选、不完整候选、未完成字节比对或实机验证的候选都会拒绝部署。
- 只有 `status=release`、参考覆盖包逐文件字节一致，并已登记 ZBCF、ZUNZ、ZUUU 与退出稳定性实机验证的候选才可覆盖 Community。

## 尚未完成

- 参考成品采用 `00_enroute.bgl` 加十个机场分区 BGL，并另有十个机场补丁 BGL；当前完整转换仍需按相同边界拆分。
- SID、STAR、IAP、航路与导航设施的 BGL 投影仍需补齐和逐项验证。
- 必须完成 BGL 结构差分、逐文件 SHA-256 收敛，以及 ZBCF、ZUNZ、ZUUU 实机回归。
