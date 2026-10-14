# Gateway heartbeat-cron Specification (delta for bugfix-608)

## ADDED Requirements

### Requirement: Heartbeat 活跃时段、文件 cron 与唤醒时间采用同一用户时区

#### Scenario: 本地早间触发
- **GIVEN** 用户已自动报告 Asia/Shanghai，Heartbeat 活跃时段覆盖 09:00，HEARTBEAT.md 任务 cron 为每日 09:00
- **WHEN** UTC 01:00 到达
- **THEN** 按上海 09:00 判断时段与任务到期，唤醒给 Agent 的当前时间带 +08:00 与 Asia/Shanghai。

#### Scenario: 设置页不要求填写 timezone
- **WHEN** 用户在 iOS 设置 Heartbeat 时段
- **THEN** 仅需设置时段，不需手动填写 timezone；小字说明“按你所在地时间”。

#### Scenario: 未知时区不猜测用户所在地
- **GIVEN** 没有已保存用户时区或旧明确配置时区
- **WHEN** 评估时钟活跃窗口或文件 cron
- **THEN** 不以 Gateway 系统时区猜测执行。
- **AND** 相对 every 节律和 DSH 原生定时工具行为不因本变更改写。
