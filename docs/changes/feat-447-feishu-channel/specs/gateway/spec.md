# gateway Specification (delta for feat-447)

## ADDED Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。1:1 私聊直接响应;群聊仅在用户 @Bot 时触发响应,未 @ 的群聊消息暂存为该群上下文,待下次 @Bot 时一并带入。

#### Scenario: 用户在飞书 1:1 私聊中发消息并收到回复
- **GIVEN** Gateway 配置了某个 Agent 对应的飞书 Bot
- **WHEN** 用户在该飞书 Bot 的 1:1 对话窗口中发送一条文本消息
- **THEN** Bot 在合理时间内把 Agent 回复发回同一个 1:1 对话窗口

#### Scenario: 群聊中 @Bot 触发回复
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @Bot 并发送消息
- **THEN** Bot 在群里回复该消息

#### Scenario: 群聊中未 @Bot 的消息不触发回复但作为上下文
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里发消息但未 @Bot
- **THEN** Bot 不在群里回复
- **AND** 当用户随后 @Bot 提问时,Bot 回复能引用之前未 @ 的群聊消息作为上下文

### Requirement: 飞书多 Bot 路由

每个飞书 Bot 通过 channel name `feishu:<agent_id>` 绑定一个 Agent。用户与哪个 Bot 对话,消息就路由到对应的 Agent。

#### Scenario: 不同飞书 Bot 对应不同 Agent
- **GIVEN** Gateway 配置了分别绑定 plato、luban、hume 的三个飞书 Bot
- **WHEN** 用户与绑定 plato 的 Bot 对话
- **THEN** 回复来自 plato Agent,而非 luban 或 hume

### Requirement: 飞书对话同步到内部 IM

飞书消息触发的 Agent 回复,通过现有 kernel event observer 机制自动同步到内部 IM 服务,使用户在内部 IM 的对应 Agent 会话中也能看到飞书侧的对话内容。

#### Scenario: 飞书私聊回复出现在内部 IM
- **GIVEN** 用户在飞书与某 Bot 1:1 对话
- **WHEN** Bot 回复用户
- **THEN** 该回复同步出现在内部 IM 对应该 Agent 的会话中

#### Scenario: 飞书群聊回复出现在内部 IM
- **GIVEN** 用户在飞书群 @Bot 对话
- **WHEN** Bot 在群里回复
- **THEN** 该回复同步出现在内部 IM 对应该 Agent 的会话中
