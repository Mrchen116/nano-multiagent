# gateway (personal_assistant) - External Channels Specification (delta for bugfix-499)

## ADDED Requirements

## MODIFIED Requirements

### Requirement: 外部 channel 触发源决定回复去向

Agent 回复是否回写外部 channel 取决于触发该 run 的用户消息来源。飞书消息触发的 run 回写原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话消息触发的 run 只留在内部 IM，不回写飞书。两种入口共享同一个外部会话身份，保证上下文连续。Agent 具有 Lark IM 操作能力不改变当前飞书 chat 的普通回复出口：该回复仍由 Gateway 统一投递和镜像；只有用户明确指定另一段 Lark chat 时，agent 才可对那段独立 chat 直接操作。

#### Scenario: 在内部 IM 影子会话回复不会回写飞书
- **GIVEN** 内部 IM 已存在 `plato · feishu` 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** plato 的回复只出现在内部 IM 会话，不出现在飞书原对话中

#### Scenario: 同一外部会话跨入口上下文连续
- **GIVEN** 用户在飞书问了 plato-bot 一个带上下文的问题
- **WHEN** 用户随后在内部 IM 的 `plato · feishu` 影子会话中追问
- **THEN** plato 能引用飞书入口的前文，不会当成新会话

#### Scenario: 影子群聊入口可使用外部群背景上下文
- **GIVEN** 飞书群里已有未 @plato 的背景消息
- **WHEN** 用户在内部 IM 的 `plato · <群名> · feishu` 影子群聊中发送“总结刚才”
- **THEN** plato 能引用该飞书群的背景消息
- **AND** plato 的回复只出现在内部 IM 影子群聊，不回写飞书

#### Scenario: 当前飞书 chat 的普通回复不走 Lark IM 直发
- **GIVEN** 用户在飞书向 plato-bot 发起一个会产生可见回复的请求
- **WHEN** plato 已获得 Lark IM 操作能力并生成普通助手回复
- **THEN** 回复仍由 Gateway 回写原飞书 chat 并同步到内部 IM 影子会话
- **AND** agent 不使用 Lark IM 向当前 chat 另发绕过 Gateway 的消息

#### Scenario: 用户明确指定另一段 Lark chat
- **GIVEN** 用户正在飞书与 plato-bot 对话
- **WHEN** 用户明确指定要查询、发送或管理另一段 Lark chat 的消息
- **THEN** plato 可使用 Lark IM 对该独立 chat 完成用户请求的操作
- **AND** plato 对操作结果的说明仍经当前飞书 chat 的 Gateway 回复链路返回

## REMOVED Requirements
