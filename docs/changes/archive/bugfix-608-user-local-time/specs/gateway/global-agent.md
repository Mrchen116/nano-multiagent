# Gateway global-agent Specification (delta for bugfix-608)

## ADDED Requirements

### Requirement: Inbox 保留真人消息原发生时间和已知用户时区

#### Scenario: owner 从飞书发来早间消息
- **GIVEN** 可信映射的 owner 时区为 Asia/Shanghai，飞书消息原时间为 UTC 01:00
- **WHEN** 全局 Agent 从 Inbox 读取消息
- **THEN** time 为该日 09:00:00+08:00，包含 offset，保留实际消息来源；不会因飞书原时间字段未映射而返回 null。

#### Scenario: 历史消息不随当前时区变化
- **GIVEN** 消息接收时固定了原发生时间及用户时区
- **WHEN** 用户换时区后 Agent 再读历史
- **THEN** 该消息仍使用原时间快照。
