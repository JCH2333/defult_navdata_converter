# 默认通用数据契约记录

## 2608R1

- 内容来源：工作区 `424源数据\2608\2608` 的 CSV/PDF。
- 官方全球基线：`navigraph-nav-base` 与 `navigraph-nav-jepp`。
- 参考覆盖层：`Default navdata 2608R1`，仅用于只读差分。
- 周期：2608，Revision 1，起止日期 `20260806` 至 `20260903`。
- 参考覆盖层包含 `00_enroute.bgl`、按区域划分的机场 BGL，以及 `bglIndex.bout`、`layout.json`、`manifest.json` 和 ContentHistory。

## 已验证限制

2026 年 8 月 11 日，本机 SDK 1.5.3 的工具目录中未找到 `BglComp.exe`。`BglExplorer.exe`
的字符串和行为表明它是 ImGui 交互式查看器；无参数或带 BGL 路径启动都会等待窗口，
不能作为无头编译器。`fspackagetool.exe` 的无参数调用也未提供可用的无头帮助。

因此当前实现能确定性地产生 BglComp XML、复制官方基线并报告阻塞原因，但不能承诺
生成与 Navigraph 成品字节级一致的 BGL。获得合法的、版本匹配的编译器后，必须补充
最小 XML fixture、BGL 结构比较、`bglIndex.bout` 生成和参考 SHA-256 回归。
