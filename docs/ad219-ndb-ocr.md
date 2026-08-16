# AD 2.19 NDB OCR 审计

适用周期：2608R1。

机场 AD 2.19 表可打印 NDB 标识、频率和坐标，但不能单独证明默认 BGL NDB 所需的显示名、磁差、高程和区域。因此该流程只建立可复跑的来源审计，永不直接新增、修改或投影 NDB。

缓存以原始 PDF 相对路径和 SHA-256 分目录；每页 OCR JSON、识别设置和运行时标识由通用 `ocr-cache` 机制校验。缓存必须位于 424 原始目录外。

先仅识别一个已知机场进行受控验证：

```powershell
python -m fenix_default_navdata.cli ad219-ndb-ocr-cache `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\ad219-ndb-ocr-cache-2608r1" `
  --airports ZBCZ
```

随后对账当前周期的直接 `NDB.csv`：

```powershell
python -m fenix_default_navdata.cli ad219-ndb-ocr-audit `
  --source-root "F:\我的世界动画\AI项目\导航数据\424源数据\2608\2608" `
  --cache-root "$env:LOCALAPPDATA\default_navdata_converter\ad219-ndb-ocr-cache-2608r1" `
  --airports ZBCZ `
  --output diagnostics\ad219-ndb-ocr-zbcz.json
```

审计结论仅有以下用途：

1. `matched_complete_direct_424`：OCR 与同周期直接 NDB 记录一致，OCR 仅作交叉证据，仍由 CSV 作为投影来源。
2. `matched_direct_424_with_target_gaps`：同一直接记录存在目标字段空缺，不能以 OCR 或官方参考补值。
3. `physical_match_identifier_difference`：坐标和频率唯一一致但 OCR 标识不同，保留为 OCR 转录差异，不能更名或新增。
4. `direct_424_identity_conflict`、`direct_424_ambiguous`、`direct_424_missing`：全部拒绝投影。

输出报告不保存参考成品字段，且始终固定为 `projection_allowed=false`。

## ZBCZ 首次可复跑证据

2026-08-16 使用 `markdown`、`autocontrast-grayscale`、3 倍渲染建立 `Terminal/ZBCZ/长治王村.pdf` 的完整缓存。源 PDF SHA-256 为 `9be71e6f79601cdc9253d1995c9019b610709593a0637078c61e32c5755e446a`。

第 14 页的 `SQ`、398 kHz 与坐标唯一匹配当期 `NDB.csv` 第 26 行，但直接 CSV 未提供 `VAL_ELEV`。因此审计状态为 `matched_direct_424_with_target_gaps`，剩余缺口为 `elevation_ft`，不得据此新增或修订默认 BGL NDB。该结果由 `test_ad219_ndb_audit_keeps_csv_match_with_missing_target_field_nonprojectable` 约束。
