## ADDED Requirements

### Requirement: Inbox 与会话查询使用同一查看者视角的名称

来源命名遵循 [IM 私聊名称投影](../im/conversations-messages.md#requirement-私聊名称按实际查看者投影)，以实际 Agent 为查看者；PA 的主人读取权限不替代 PA 的展示视角。

#### Scenario: 私聊被用户改名后读取
- **WHEN** 用户修改私聊会话名后 Agent 再查询或读取该会话
- **THEN** Inbox 显示同一个新标题，身份和回复目标不变

## REMOVED Requirements

### Requirement: Inbox 与聊天使用同一会话标题

该旧标题由本 unit 的新查看者视角契约替代。
