# SDK 编译契约

## MSFS 2024 SDK 1.5.7

- 适用对象：默认通用数据 2608R1 覆盖层的机场程序 XML。
- 证据来源：2026-08-11 使用 `C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe` 对完整 2608 模型生成的 `candidate-2608-default-r4` 真实构建。
- 触发条件：`CR` 航段未提供 `theta` 时，BGL 编译器报 `C2577`，指出缺少 `Theta`。
- 解决方式：默认 BGL 适配器将 `CR` 纳入 `theta` 输出和必填回退集合；原始 `theta` 缺失时使用可用的 course，仍缺失时写入 `0`。
- 自动化测试：`test_cr_leg_without_source_theta_uses_course_fallback`。

## 已处理的相邻契约

- `CF` 等要求距离的航段在 Fenix 未提供距离或 rho 时必须输出 `distance="0N"`；证据为 `candidate-2608-default-r3` 真实编译报错，自动化测试为 `test_cf_leg_without_source_distance_uses_sdk_zero_distance`。
- 同一机场内的 `NAMED` Terminal Waypoint 以 `waypointRegion + waypointIdent` 为唯一身份；即使坐标不同，SDK 也会报 `C2596 DUPLICATE WAYPOINT`。相同身份且输出到六位小数后坐标相同的记录必须去重；坐标不同的记录必须保留并分配稳定的八字符替代标识。所有程序腿的 `fixIdent`、`recommendedIdent`、RF 的 `arcCenterFixIdent`，以及进近和进近过渡起点都必须使用同一映射。证据为 `candidate-2608-default-r5` 的 ZUTF `ZGA`/`ZYG` 与 ZUUU `UU704`/`UU723` 真实编译报错；自动化测试为 `test_airport_terminal_waypoint_collisions_are_renamed_with_all_references`。
- `CA` 航段必须带 `Altitude1`。当 Fenix 记录没有高度限制时，默认 BGL 适配器写入 `altitude1="0F"`；证据为 `candidate-2608-default-r6` 的 ZSFZ、ZSZS 真实编译报错，2608 全量模型中仅有 3 条此类 `CA` 航段；自动化测试为 `test_ca_leg_without_source_altitude_uses_sdk_zero_altitude`。
- Fenix 2608 的 `Terminals.ID=173126` 在 ZLZY 跑道 29R 到达程序中把名称损坏为 `P91A闁?`，SDK 因非 ASCII 名称报 `C2553 TAXI_NAME too long`。同组跑道成对记录及参考成品两个 `ZL_airports.bgl` 均证实正确名称为 `P9119A`。读取器仅对机场、程序类型、跑道和损坏原值全部匹配的记录执行精确修复；自动化测试为 `test_fenix_loader_repairs_known_zlzy_arrival_label`。
