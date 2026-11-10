# Gateway 飞书通道增量契约

## MODIFIED Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。1:1 私聊直接响应；群聊按 agent 的群聊回复策略决定是否响应。MENTION 策略下仅真实 @Bot 触发响应，未 @ 的群聊消息进入该 agent 的群背景上下文，待后续触发时一并带入；ALWAYS 策略下普通群消息也触发响应。普通 Global Agent 的 Bot 在应响应的消息持久入箱后添加 OK 反应，完整读取后换成 CheckMark。其他模式的 Bot 使用待响应时添加、回复后移除的 THINKING 反应。

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
- **AND** 当用户随后 @Bot 提问时，Bot 回复能引用之前未 @ 的群聊消息作为上下文

#### Scenario: @所有人 不算 @Bot
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @所有人 发消息，但没有单独 @Bot
- **THEN** Bot 不在群里回复
- **AND** 该消息按普通未 @ 群消息进入群背景上下文

#### Scenario: ALWAYS 策略下普通群消息也触发回复
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群，且该 agent 的群聊回复策略为 ALWAYS
- **WHEN** 用户在群里发送普通消息且没有 @Bot
- **THEN** Bot 也在该群里回复该消息

#### Scenario: 其他模式的 Bot 对即将响应的消息显示 THINKING 反应并在回复后移除
- **GIVEN** Gateway 配置的非普通 Global Agent 飞书 Bot 收到一条需要响应的消息
- **WHEN** Bot 开始处理并随后发出回复
- **THEN** 用户在飞书里看到该消息先出现 THINKING 反应，回复发出后该反应消失

#### Scenario: 普通 Global Agent 的 Bot 展示收件和已读
- **WHEN** 应响应的消息持久入箱，然后由 Agent 完整读取
- **THEN** Bot 在原消息上的反应从 OK 更新为 CheckMark
- **AND** 回执反馈可稍后更新，Agent 的读取和任务执行可独立推进
