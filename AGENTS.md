# Fenix 默认通用数据转换器协作规则

- 所有用户信息使用中文。
- 源 CSV/PDF 与官方 Community 包只作为本地输入，不提交任何导航数据或生成包。
- 默认包必须保留官方 `nav-base`/`nav-jepp` 全球基线，区域覆盖层独立生成。
- 参考成品只读比较，禁止复制参考 BGL 冒充转换结果。
- 没有版本匹配的 BglComp、没有本地验证或未完成实机测试时，输出只能标记测试版。
- 覆盖 Community 前必须确认 `FlightSimulator2024.exe` 已退出，并备份目标包与元数据。
- 每次代码/文档改动都要提交并推送 Git；未经实机验证不得创建正式 Release。

## 2608R1 已确认契约

- 官方全球基线为 Community 中的 `navigraph-nav-base` 与 `navigraph-nav-jepp`，候选复制后分别有 475 和 1752 个文件，2026-08-11 全量 SHA-256 树比较均字节一致。
- 参考成品不是完整全球包，而是 `zzz-pmdg-china-navdata` 与 `zzz-pmdg-china-navdata-airport-patch` 两个中国覆盖包。
- MSFS 2024 SDK 1.5.3 的本机工具目录只有 `BglExplorer.exe`、`fspackagetool.exe` 和 `bglcomp.xsd`，未发现 `BglComp.exe`。前两者的无头调用不能生成导航 BGL。
- 2608 全量来源模型当前包含 275 个机场、640 个跑道、438 个导航台、2573 个去重航点、1354 条航路和 9926 个程序段；另有 6389 条程序证据因无法安全投影而保留拒绝记录。
- 全量 `china-navdata.xml` 为 544433 字节，并通过 SDK 1.5.3 `bglcomp.xsd`。没有匹配编译器、BGL、`bglIndex.bout` 和两包元数据时，验证器必须返回 `valid=false`，即使显式允许测试版也不得部署。
- 最小回归覆盖 AIRAC 周期、确定性 XML、SDK 字段格式、候选包完整性、更新版本排序和不完整测试候选的部署拒绝。
- 实机验证仍须检查 ZBCF、ZUNZ、ZUUU 的机场、跑道、SID/STAR/IAP，以及退出飞行和退出模拟器。完成前不得创建正式 Release。
