# ADDED Requirements

### Requirement: Inbox 与聊天使用同一会话标题

#### Scenario: 私聊被用户改名后读取
- **WHEN** 用户修改私聊会话名后 Agent 再查询或读取该会话
- **THEN** Inbox 显示同一个新标题，身份和回复目标不变
