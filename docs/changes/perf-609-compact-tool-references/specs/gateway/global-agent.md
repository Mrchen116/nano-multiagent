# Global Agent Delta

## ADDED Requirements

### Requirement: 本仓工具引用简短且不改变身份与分页语义

#### Scenario: 飞书消息的目标引用
- **WHEN** Agent 发现、读取或回复一个飞书聊天
- **THEN** 模型使用稳定短目标引用，宿主仍按真实 Agent、应用和收件人执行投递与权限检查。
- **AND** 节点重启后引用保持有效，已有完整目标引用继续可用；其他 Agent 的短引用不能用于当前 Agent。

#### Scenario: 继续读取分页结果
- **WHEN** Agent 继续读取 Inbox、会话或任务图的下一页
- **THEN** 使用简短、不透明的分页引用，无需抄写完整快照或查询条件。
- **AND** 快照、查询 scope、跨工具隔离以及新消息的消费边界保持不变，旧游标仍可用。

#### Scenario: 模型输出精简与来源证明
- **WHEN** Inbox 返回同一会话的多个消息片段或发送工具返回结果
- **THEN** 会话目标不在每个消息片段重复，发送结果不重复返回相同的 target 和 conversation_id。
- **AND** 精确摄取证明、发送前复核、图片访问和工作记录仍使用可信真实来源。
