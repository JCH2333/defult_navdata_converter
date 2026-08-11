# Fenix 默认通用数据转换器协作规则

- 所有用户信息使用中文。
- Fenix `nd.db3`、源 CSV/PDF 与官方 Community 包只作为本地输入，不提交任何导航数据或生成包。
- 默认包必须保留官方 `nav-base`/`nav-jepp` 全球基线，区域覆盖层独立生成。
- 参考成品只读比较，禁止复制参考 BGL 冒充转换结果。
- 没有版本匹配的 Package Tool、没有本地验证或未完成实机测试时，输出只能标记测试版。
- 覆盖 Community 前必须确认 `FlightSimulator2024.exe` 已退出，并备份目标包与元数据。
- 每次代码/文档改动都要提交并推送 Git；未经实机验证不得创建正式 Release。

## 2608R1 已确认契约

- 官方全球基线为 Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`，候选复制后分别有 475 和 1752 个文件，2026-08-11 全量 SHA-256 树比较均字节一致。
- 参考成品不是完整全球包，而是 `zzz-pmdg-china-navdata` 与 `zzz-pmdg-china-navdata-airport-patch` 两个中国覆盖包。
- MSFS 2024 SDK 1.5.7 的正式设施编译入口为 `fspackagetool.exe`。2026-08-11 已用一个机场和一条跑道完成真实构建，生成 BGL、`bglIndex.bout`、布局、清单与 ContentInfo。
- Package Tool 项目必须先镜像到纯 ASCII 暂存路径；中文路径会在游戏命令行中损坏并导致 `Main_Z ProgramInit` 启动崩溃。
- `fspackagetool.exe` 可能因 Steam 进程附着竞态先返回非零代码，但后台 `FlightSimulator2024.exe` 仍在构建；必须等待新进程退出，以实际包产物判定成功后再清理暂存目录。
- 内容来源以当期 Fenix `nd.db3` 为主，负责机场、跑道、ILS、终端航点和 SID/STAR/IAP；匹配的 424 `RTE_SEG.csv` 负责航路与端点补充，官方包只负责全球基线和加载契约。
- 2026-08-11 只读加载 Fenix 2608R1 已确认 279 个中国机场、641 条跑道、456 套 ILS、8861 个 Terminal 和 69795 条 TerminalLeg。规范化后得到 17140 个终端航点、20032 个程序分段和 673 条中国等待航线。
- Fenix 2608 的增量 VOR 块为 `Navaids.ID=11396..11515`，共 120 条，全部可在参考 `00_enroute.bgl` 中按标识和坐标匹配。参考 BGL 另有 15 条 VOR 与当前 Fenix 块不重合，具体合法来源规则仍待确认。
- `WaypointLookup` 的主键不是单独的 `ID`；直接连接会把中国程序腿从 69795 条错误展开到 70642 条。加载器必须先按 waypoint ID 归一国家码，对应回归测试为 `test_fenix_loader_uses_fenix_content_and_raw_route_model`。
- 全量 `china-navdata.xml` 为 544433 字节，并通过 SDK `bglcomp.xsd`。没有 BGL、`bglIndex.bout` 和两包元数据时，验证器必须返回 `valid=false`，即使显式允许测试版也不得部署。
- 最小回归覆盖 AIRAC 周期、确定性 XML、SDK 字段格式、候选包完整性、更新版本排序和不完整测试候选的部署拒绝。
- 实机验证仍须检查 ZBCF、ZUNZ、ZUUU 的机场、跑道、SID/STAR/IAP，以及退出飞行和退出模拟器。完成前不得创建正式 Release。
