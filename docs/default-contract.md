# 默认通用数据 2608R1 契约

## 输入职责

- 主内容来源：`424源数据\2608\Navdata（fnx2608N）\Navdata\nd.db3`，负责机场、跑道、ILS、终端航点、SID、STAR、IAP 与主要导航设施。
- 航路补充：`424源数据\2608\2608` 中的结构化 CSV，重点使用匹配的 `RTE_SEG.csv` 与航路端点。
- 目标基线：Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`。
- 只读参考：`424源数据\2608\Default navdata 2608R1`。

内容来源、目标基线和参考成品不得互相替代。

## AIRAC

- 周期：2608。
- Revision：1。
- 开始日期：`20260806`。
- 结束日期：`20260903`。
- SDK `AiracCycle.cycleNumber`：`08`。

## 覆盖包

参考成品包含：

- `zzz-pmdg-china-navdata`
  - `scenery/pmdg-china-navdata/00_enroute.bgl`
  - `ZB/ZG/ZH/ZJ/ZL/ZP/ZS/ZU/ZW/ZY_airports.bgl`
- `zzz-pmdg-china-navdata-airport-patch`
  - `scenery/pmdg-china-airport-patch/`
  - 十个对应分区机场 BGL

每个包都必须包含：

- `bglIndex.bout`
- `layout.json`
- `manifest.json`
- `ContentInfo/<包名>/ContentHistory.json`
- 至少一个可读取的 BGL

## SDK 编译契约

2026-08-11 的本机验证环境：

- MSFS 2024：`1.7.35.0`
- SDK：`1.5.7`
- 编译入口：`C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`
- 平台：Steam

已确认：

1. `fspackagetool.exe <项目.xml> -nopause -rebuild -forcesteam` 会启动游戏的 `BuildAssetPackages` 模式。
2. Package Tool 会生成 BGL、`bglIndex.bout`、布局、清单和 ContentInfo。
3. 项目 XML、PackageDefinitions 和 PackageSources 必须先镜像到纯 ASCII 路径。
4. 包装器可能因附着竞态先返回代码 1，但后台游戏仍会完成构建；应等待新启动的模拟器进程退出，再检查实际产物。
5. 构建前若已有 `FlightSimulator2024.exe`，必须拒绝运行。

对应自动化测试：

- `test_package_tool_project_is_deterministic`
- `test_package_tool_stages_project_in_ascii_path`

## 当前数据模型

2026-08-11 的 Fenix 2608R1 只读加载结果：

- 279 个中国机场
- 641 条跑道
- 456 套 ILS
- 8861 个 Terminal
- 69795 条 TerminalLeg
- 17140 个规范化终端航点
- 20032 个按 route type/transition 分组的程序段
- 673 条中国等待航线
- 424 来源中的 2158 个结构化航点与 4446 条航路段

Fenix `WaypointLookup` 可能为同一 waypoint ID 保存多条国家码记录。程序加载
必须先按 ID 归一后再关联，否则 69795 条中国程序腿会被错误展开为 70642 条。
对应回归测试为 `test_fenix_loader_uses_fenix_content_and_raw_route_model`。

参考 `00_enroute.bgl` 含 135 条 VOR 和 143 条 NDB。Fenix
`Navaids.ID=11396..11515` 是连续的 120 条中国 VOR 增量块，已全部按标识和
坐标匹配参考 BGL；剩余 15 条 VOR 与 NDB 的精确来源规则仍在差分确认中，
当前不得将参考 BGL 记录反向固化为转换输入。

## 验证与发布

候选至少通过：

1. 官方双包基线 SHA-256 树保持不变。
2. SDK XML 校验和 Package Tool 构建。
3. 两个覆盖包结构与索引完整性。
4. BGL 分区、内容结构与参考成品差分。
5. 参考目录逐文件字节比较。
6. ZBCF、ZUNZ、ZUUU 的机场、跑道、SID、STAR、IAP 实机验证。
7. 退出飞行和退出模拟器稳定性验证。

实机验证完成前只允许测试版，不创建正式 Release。
