# 默认通用数据 2608R1 契约

## 输入职责

- 主内容来源：`424源数据\2608\2608` 中的结构化 CSV/PDF，负责机场、跑道、ILS、终端航点、SID、STAR、IAP、航路与等待航线。
- Fenix `nd.db3` 不参与默认通用数据转换；Fenix 适配器代码仅保留为历史回归材料。
- 目标基线：Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`。
- 只读参考：`424源数据\2608\Default navdata 2608R1`。

内容来源、目标基线和参考成品不得互相替代。

官方索引是“官方基线可证明查询”的只读派生产物，不是内容来源。用于导航台差分或
航路端点区域恢复前，必须验证 VOR、NDB、WAYPOINT 三类读取器记录都能通过
`file_id -> bgl_file.filepath -> 中性镜像 -> 当前官方 BGL` 回溯。索引侧车还必须记录
三类行数、来源统计和官方双包树指纹；旧版或不完整的侧车不得复用。

对于 `RTE_SEG.csv` 或 `DESIGNATED_POINT.csv` 中未给出区域码的记录，默认适配器可以
查询该可信索引，但查询结果仅能填入区域键，不能把官方记录复制进模型。恢复必须同时
满足端点类型、标识一致，坐标在 `0.01 NM` 内，且命中的官方区域唯一；VOR、NDB、
指定点分别只匹配相应表。歧义、无匹配、无坐标或未知端点类型一律保留为空并进入
转换报告，随后由 BGL 投影器跳过无法满足 SDK region 契约的航路段。

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

截至 2026-08-12，转换器只读加载 `424源数据\2608\2608` 的 CSV/PDF，并使用
版本 `33` 的本地 PDF 证据缓存复核，得到：

- 10,302 个按程序类型、跑道和过渡分组的终端程序段。
- 1,297 条机场等待航线。
- 0 条因等待固定点无法从 424 数据唯一定位而被拒绝的记录。
- 424 结构化来源当前包含 2,158 个航点和 4,446 条航路段。

默认通用 BGL 的 VOR/NDB 显示名以 424 原始中文 `TXT_NAME` 为内容来源，并在
目标适配器中投影为无分隔的大写拼音；这不是对源模型的改写。2608R1 参考 BGL
逐条对照确认 `霍林郭勒`、`库尔勒`、`阿拉尔`、`克拉玛依`、`吐鲁番`、`长武`、
`长治`、`昌都` 需要使用既定航空拼写而非逐字拼音库默认读音。对应回归测试为
`test_enroute_projection_uses_verified_default_navaid_name_exceptions`。不属于名称
转写的特殊导航台记录继续按设施集合差分处理，不能借此规则反向固化参考 BGL 内容。

等待航线的唯一内容来源是终端数据库编码页中明确印刷的 `HM`、`HF` 或 `HA`
行及其 `RWY...等待` 标题。解析器保留固定点、入航向、左右转、最低高度、速度
限制、适用跑道和标题中的出航时间；只有当固定点可由机场终端坐标页、
`DESIGNATED_POINT.csv`、`VOR.csv` 或 `NDB.csv` 唯一定位时，才生成
`HoldingPattern`。不明确的固定点必须记入拒绝记录，不能猜测坐标，也不能从
Fenix 或参考 BGL 回填。

等待表与 SID/STAR/IAP 的程序编码表是不同的语义表面。解析器进入等待标题后会
停止普通程序腿归属，直到观察到下一条程序标题；这避免把跑道编号误当作程序名称。
对应回归测试为 `test_database_holding_titles_keep_time_and_do_not_become_procedure_legs`
和 `test_airport_projection_emits_source_backed_holding_pattern`。

PDF 缓存载荷带有提取器版本。修改可影响证据解释的规则时，必须递增
`_EVIDENCE_CACHE_VERSION`，并以新缓存进行冷读与热读一致性复核；不得依据旧缓存
中的统计或程序分类作出发布、部署或数据覆盖决定。

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

## 当前限制

- 当前候选已经可以生成两个具有 BGL、`bglIndex.bout`、`layout.json`、
  `manifest.json` 和 ContentInfo 的测试覆盖包，但与参考成品同名文件尚未逐字节
  收敛。
- 程序标题分类仍有少量复杂双栏版式和无分隔程序名需要继续以 424 PDF 原文处理。
- 在 `byte_equal_reference=true` 且完成实机验证前，任何候选都不得覆盖
  `F:\games\community\Community`，不得创建正式 Release。
