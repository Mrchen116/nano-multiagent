# Gateway External Channels Specification (delta for bugfix-497)

> Target canonical: `docs/specs/gateway/external-channels.md`

## MODIFIED Requirements

### Requirement: IM 离线时飞书对话不阻塞

Gateway 对内部 IM 的外部 channel 同步不阻塞飞书主路径：IM 不可达时 Agent 仍需正常回复用户，并持久保留本次影子消息的恢复事实；IM 恢复或 Gateway 重启后，当前与后续飞书消息均按原影子会话自动收敛，不要求用户手工触发。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** 本次消息在 IM 离线期间可暂不可见，恢复后自动补齐唯一完整影子时间线

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书群 @plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 本次消息在 IM 离线期间可暂不可见，恢复后自动补齐唯一完整影子时间线
