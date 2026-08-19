# 航路坐标精度实验结果：2608R1

日期：2026-08-19

## 输入边界

- 内容来源：2608 `RTE_SEG.csv`。
- SDK：`C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`。
- 离线读取器：Navdatareader 1.2.4。
- 参考成品仅用于只读 semantic diff；本实验没有读取其字段值，也没有将其作为转换输入。

## 量化证据

`airway-coordinate-precision-probe-r161-20260819` 使用同一组坐标的 6、9、12 位小数写法。三种输入回读的航路端点和包围盒字段完全相同，均为 IEEE-754 `float32` 量化值。

`r161-source-airway-coordinate-precision-audit.json` 只读扫描了 4,446 条 `RTE_SEG.csv` 记录的 17,784 个端点坐标。旧版 6 位 XML 格式化会改变 1,129 条记录、1,262 个坐标的 `float32` 值。因此正式 enroute `Waypoint` 输出改为 12 位小数。

## 候选验证

使用与 r155 相同的中间模型、官方索引和 SDK 构建 r162：

- `validate`：`valid=true`、`local_contract_verified=true`、`deployable=false`。
- 航路语义差分：严格相等行从 1,267 增至 1,383；字段差异行从 2,161 降至 2,045。
- 仍有 2,045 条航路字段差异，主要集中在端点与包围盒；此规则解决了 116 条差异，不能单独实现字节级一致。

候选仍为测试版，不得部署到 Community 或创建正式 Release。
