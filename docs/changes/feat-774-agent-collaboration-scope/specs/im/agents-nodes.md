# im/agents-nodes Specification (delta for feat-774)

## ADDED Requirements

### Requirement: Agent 协作范围决定哪些聊天新消息可以送达

#### Scenario: 创建、保存与查看
- **WHEN** 用户创建或编辑 Agent
- **THEN** 协作范围只有「团队协作」和「仅限本人」，新建默认团队协作。配置接口以 collaboration_scope 的 team / owner_only 读写同一选择，Web、iOS、PA 首建与代建一致。

#### Scenario: 仅限本人
- **WHEN** 选择仅限本人
- **THEN** 只接收创建者亲自发给该 Agent 的一对一私聊。其他人的私聊、所有群消息与 PA 旁观聊天均不进入其收件内容或提醒。

#### Scenario: 收紧范围
- **WHEN** 设置成功切换为仅限本人
- **THEN** 越出范围且尚未交给模型的团队积压停止递送，恢复团队协作后也不补发。已发生的交互保留历史。
