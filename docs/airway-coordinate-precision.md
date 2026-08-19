# 航路坐标精度契约

## 适用范围

本规则仅适用于默认通用数据适配器写出的 enroute `Waypoint` 坐标。机场、跑道和导航台仍按各自已经验证的投影规则输出。

## 已验证事实

2608 `RTE_SEG.csv` 的端点使用 DMS 文本。MSFS 2024 SDK Package Tool 编译后的 BGL 被离线 Navdatareader 回读时，航路端点与包围盒字段均为 IEEE-754 `float32`。

旧的 6 位小数 XML 格式化会在进入 SDK 前改变一部分 DMS 坐标的 `float32` 量化结果。适配器因此使用 12 位小数文本；该位数足以保留秒级 DMS 转换得到的 `float32` 值。

## 可重复证据

- `airway-coordinate-precision-probe` 使用三组仅保留位数不同的合成航路端点，以 6、9、12 位小数编译并回读端点与包围盒字段。
- `airway-coordinate-precision-audit` 只读扫描 `RTE_SEG.csv`，统计旧版 6 位格式化会改变多少个源端点的 `float32` 值。

两个工具都不读取参考成品，不修改正式候选或 Community。探针结果只能证明 SDK 量化规则；是否减少与参考成品的语义差异，必须由新的隔离候选、完整 semantic diff 和 validate 共同确认。
