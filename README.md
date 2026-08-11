# Fenix to Default NavData

Fenix/2608 原始数据到 MSFS 2024 默认 Navigraph 通用数据的测试版转换器。

## 当前状态

`0.1.0` 已提供：

- 2608 CSV/PDF 来源解析和统一中间模型；
- 官方 `navigraph-nav-base` 与 `navigraph-nav-jepp` 的只读基线复制；
- BglComp XML 投影、周期字段和确定性排序；
- 编译器探测、候选报告、参考目录差分和 SHA-256 校验；
- Tk GUI、命令行、备份/恢复/测试版部署；
- GitHub Actions 测试与预发布更新包流程。

本机调查确认 MSFS 2024 SDK 1.5.3 目录中只有 `BglExplorer.exe`、`fspackagetool.exe`
和 `bglcomp.xsd`，没有可调用的 `BglComp.exe`。因此在补齐合法且版本匹配的设施编译器
之前，工具会生成来源 XML 和完整官方基线，但将候选标记为 `deployable=false`，不会
伪造 BGL 或宣称字节级一致。

## 使用

```powershell
python -m pip install -e .
python -m fenix_default_navdata.cli detect
python -m fenix_default_navdata.cli build --output output/candidate-2608-default
python -m fenix_default_navdata.cli validate --candidate output/candidate-2608-default
python -m fenix_default_navdata.gui
```

也可以双击 `run_gui.bat`。

找到合法编译器后可显式传入：

```powershell
python -m fenix_default_navdata.cli build `
  --raw "<工作区>\424源数据\2608\2608" `
  --nav-base "<Community>\navigraph-nav-base" `
  --nav-jepp "<Community>\navigraph-nav-jepp" `
  --reference "<工作区>\424源数据\2608\Default navdata 2608R1" `
  --bglcomp "C:\path\to\BglComp.exe" `
  --output output/candidate-2608-default
```

测试版覆盖必须显式使用 `--allow-test-build`，并且部署前会拒绝正在运行的
`FlightSimulator2024.exe`。每次覆盖都会先创建带时间戳的 Community 备份。

## 数据边界

源 CSV/PDF 是内容来源；官方 Community 包是目标基线和加载契约模板；参考成品只用于
只读差分和回归，不会被复制进源码或作为转换结果。

## 发布约束

实机验证完成前只允许 GitHub prerelease 测试包，不创建正式 Release。原始数据库、官方
导航包、备份、日志、反编译结果和测试输出均不进入仓库。
