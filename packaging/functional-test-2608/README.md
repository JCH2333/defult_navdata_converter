# MSFS 2024 中国区域导航数据功能测试包

这是 `2608 / r385` 功能测试包，不是正式 Release，也不保证与官方参考包字节级一致。

压缩包只包含两个自定义中国区域包：

- `zzz-pmdg-china-navdata`：中国区域航路和导航数据。
- `zzz-pmdg-china-navdata-airport-patch`：中国区域机场程序补充数据。

压缩包不包含 `navigraph-nav-base` 和 `navigraph-nav-jepp`。这两个官方 2608 包必须已经安装在 Community 中，安装脚本会保留它们原样不动。

## 安装

1. 完全退出 MSFS 2024，包括后台的 `FlightSimulator2024.exe`。
2. 将压缩包解压到临时目录，不要直接解压到 Community。
3. 在解压目录打开 PowerShell，执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Install-FunctionalTest.ps1 -CommunityPath "F:\games\community\Community"
```

如果 Community 路径不同，将参数替换为实际路径：

```powershell
.\Install-FunctionalTest.ps1 -CommunityPath "D:\MSFS\Community"
```

脚本会检查 MSFS 是否退出、检查官方包、校验自定义文件 SHA-256，备份旧的两个 `zzz-pmdg-*` 包，然后只替换这两个包。

## 恢复

安装完成后脚本会显示备份路径，例如：

```text
F:\games\community\backups\functional-test-2608-r385_20260822_180000
```

测试结束并完全退出 MSFS 后执行：

```powershell
.\Restore-FunctionalTest.ps1 `
  -CommunityPath "F:\games\community\Community" `
  -BackupPath "F:\games\community\backups\functional-test-2608-r385_20260822_180000"
```

恢复脚本只恢复两个 `zzz-pmdg-*` 包，不会修改官方 Navigraph 包。

## 测试重点

优先测试 `ZBCF`、`ZUNZ`、`ZUUU` 的机场、跑道、SID、STAR、ILS/RNAV 进近、普通航路、VOR/NDB/航点搜索，以及重启后的重复加载。详细项目见 `TEST-CHECKLIST.md`。

边界端点 `P225`、`P127`、`P188`、`P121`、`P239`、`APOGO`、`LELIM` 当前属于已知拒绝项，首轮只验证不会导致导航数据库或模拟器崩溃。
