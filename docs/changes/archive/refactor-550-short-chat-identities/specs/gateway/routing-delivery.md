# MODIFIED Requirements

### Requirement: 内核中的产品工具可把 Agent 产出的消息投递到目标会话

以下工具显式指定目标、权限校验和真实投递结果适用于两种模式。当前群来源的复核适用于 single_thread；global 按其目标群已接收范围复核，无隐含当前聊天。全局模式对应行为以 [global-agent](global-agent.md) 为准。

内核中运行的产品工具(如 `send_message`)可把 Agent 产出的消息投递到另一目标会话;模型参数 `target` 使用聊天成员的短 `user_id` 或短 `conversation_id`，人和 Agent 均以 `user_id` 联系。Gateway 经 live IM 连接路由到目标会话,目标直聊不存在则创建、已存在则复用;IM 连接不可用时返回明确错误而非静默丢弃。

#### Scenario: IM 在线时投递成功并回执
- **GIVEN** Gateway 的 IM 连接已激活
- **WHEN** 工具发起投递 `{target, text}`
- **THEN** 消息经 IM 连接投递到目标会话,投递返回 `ok=True` 与目标会话标识

#### Scenario: IM 连接不可用时返回明确错误
- **WHEN** IM 连接缺失或未连接时收到投递请求
- **THEN** 投递返回 `ok=False` 并附带错误说明(不静默丢消息)

#### Scenario: 缺必填字段时拒绝投递
- **WHEN** 投递请求缺 `text` 或 `target`
- **THEN** 投递返回 `ok=False` 与字段校验错误


#### Scenario: 当前群工具发送遇到尚未采纳的新消息
- **GIVEN** 当前群运行的发送工具准备向同群投递正文
- **WHEN** 该运行在投递提交前接受了本轮尚未采纳的新消息
- **THEN** 工具明确回报正文未发送、需要结合新消息继续处理，不产生群发言；之后仍由原运行按原回复规则继续
- **AND** 网络失败保留原错误语义，不把未发送当成功回执
