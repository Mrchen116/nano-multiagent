# gateway Specification (delta for feat-447)

## ADDED Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。1:1 私聊直接响应;群聊仅在用户 @Bot 时触发响应,未 @ 的群聊消息暂存为该群上下文,待下次 @Bot 时一并带入。Bot 收到待响应的消息后先在飞书消息上显示 THINKING 反应,回复发送后移除该反应。

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

#### Scenario: Bot 对即将响应的消息显示 THINKING 反应并在回复后移除
- **GIVEN** Gateway 配置的飞书 Bot 收到一条需要响应的消息
- **WHEN** Bot 开始处理并随后发出回复
- **THEN** 用户在飞书里看到该消息先出现 THINKING 反应,回复发出后该反应消失

### Requirement: 飞书多 Bot 路由

每个飞书 Bot 通过 channel name `feishu:<agent_id>` 绑定一个 Agent。用户与哪个 Bot 对话,消息就路由到对应的 Agent。一个 `agent_id` 只能对应一个飞书 Bot。

#### Scenario: 不同飞书 Bot 对应不同 Agent
- **GIVEN** Gateway 配置了分别绑定 plato、luban、hume 的三个飞书 Bot
- **WHEN** 用户与绑定 plato 的 Bot 对话
- **THEN** 回复来自 plato Agent,而非 luban 或 hume

### Requirement: 外部 channel 用户消息同步到内部 IM

Gateway 收到来自外部 channel（以飞书为首个实现）的用户消息后,调用 IM 服务创建或查找对应的影子会话,并将用户消息写入该会话。1:1 私聊的影子会话名为 `agent名 · channel名`;群聊的影子会话名为 `agent名 · 群名 · channel名`。外部群聊消息携带原发送者显示名;IM owner 自己从外部 channel 发送的消息显示为「你」。

#### Scenario: 外部 1:1 用户消息同步到内部 IM
- **GIVEN** 用户在飞书与 plato-bot 1:1 对话
- **WHEN** 用户发送一条消息
- **THEN** 内部 IM 中出现一个名为 `plato · feishu` 的独立会话,且该消息作为「你」的消息出现在该会话中

#### Scenario: 外部群聊消息同步到内部 IM 并显示发送者名字
- **GIVEN** plato-bot 已加入飞书群「产品群」,且 Alice 在群里发消息
- **WHEN** 该消息被同步到内部 IM
- **THEN** 内部 IM 中出现一个名为 `plato · 产品群 · feishu` 的独立 group 会话,Alice 的消息显示为 Alice 发送

#### Scenario: 未 @ 的群聊上下文消息同步到内部 IM
- **GIVEN** plato 的 group_reply_policy 为 MENTION,Alice 在飞书群「产品群」发了 2 条未 @plato 的消息
- **WHEN** 这些消息作为上下文被暂存
- **THEN** 它们作为普通用户消息同步到内部 IM 的 `plato · 产品群 · feishu` group 会话中,显示发送者名字

### Requirement: 按触发源路由 agent 回复

agent 回复是否回写外部 channel 取决于触发该 run 的用户消息来源。由外部 channel 消息触发的回复回写原 channel 并同步到内部 IM;由内部 IM 影子会话消息触发的回复只留在内部 IM,不回写外部 channel。两种来源都复用同一 kernel session,保证上下文连续。

#### Scenario: 在内部 IM 回复不会回写飞书
- **GIVEN** 内部 IM 已存在 `plato · feishu` 会话
- **WHEN** 用户在该会话中发送消息
- **THEN** plato 的回复只出现在内部 IM 会话,不出现在飞书原对话中

#### Scenario: 在内部 IM 群聊影子会话发消息自动触发 agent 回复
- **GIVEN** 内部 IM 已存在 `plato · 产品群 · feishu` group 影子会话
- **WHEN** 用户在该会话中发送消息（不 @plato）
- **THEN** Gateway 自动在消息文本前注入 `@plato` 后提交给 kernel
- **AND** plato 的回复只出现在内部 IM 会话,不回写飞书

#### Scenario: 同一 kernel session 跨入口上下文连续
- **GIVEN** 用户在飞书问了 plato-bot "我叫什么"
- **WHEN** 用户在内部 IM 的 `plato · feishu` 会话中回复 "你刚才不是知道吗"
- **THEN** plato 能引用前一条上下文,不会当成新会话

### Requirement: IM 离线时飞书对话不阻塞

Gateway 调用 IM HTTP API 同步外部 channel 用户消息时,必须是非阻塞的 best-effort 调用。IM 不可达不得影响飞书主路径,agent 仍需正常回复用户。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** Gateway 记录同步失败日志,不阻塞飞书回复路径

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书群「产品群」@plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 该消息暂不同步到内部 IM

### Requirement: 外部 channel 会话隔离

同一外部 channel 的同一聊天,如果绑定了多个 agent,内部 IM 中为每个 agent 生成独立的影子会话。

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群「产品群」同时配置了 plato-bot 和 luban-bot
- **WHEN** 用户在群里分别 @plato-bot 和 @luban-bot
- **THEN** 内部 IM 中同时存在 `plato · 产品群 · feishu` 和 `luban · 产品群 · feishu` 两个独立的 group 会话,各自的内容互不混淆
