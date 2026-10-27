# Gateway Global Agent Specification (delta for feat-667)

## ADDED Requirements

### Requirement: Global 主 Agent 专属产品聊天工具

#### Scenario: 内部执行者需要资料或交付
- **GIVEN** 普通 Global Agent 或 PA 使用内部一级或二级执行者
- **WHEN** 执行者需要产品聊天资料、公开汇报或交付成果
- **THEN** 通过原生内部通信向父级请求或回传，由主 Agent 使用现有权限查询并决定发送。
- **AND** 子 Agent 的工具列表没有 inbox、conversations、send_user_message 或 send_message 的 target/text 公开分支；保留 agent_id/message 的原生内部通信，直接调用受限产品入口也不能越过主 Agent 身份限制。

#### Scenario: 新建、fork 和恢复角色一致
- **WHEN** Global 子 Agent 被创建、fork 或恢复到原会话
- **THEN** 使用同一主/子工具边界，不因旧历史或配置继承恢复产品聊天权限；当前提示不要求子 Agent 消费主 Inbox 或向用户公开回复。
- **AND** 主 Agent 的产品读取/发送、来源权限与真实投递检查保持，主 PA 的代表发送仍为主 PA 专属。
