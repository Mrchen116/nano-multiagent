# gateway Routing and Delivery Specification (delta for bugfix-508)

## MODIFIED Requirements

### Requirement: 群聊只在被 @提及 / 回复 Agent / 明确的全群控制命令时触发 Agent

群聊流量在分配任何内核会话或队列槽**之前**先过 @提及门控。未被点名的群聊消息不触发 Agent 执行;Agent 判断无需回复时输出约定 token(`NO_REPLY`)则不向用户发言。门控策略由各 Agent 的 `group_reply_policy`决定(默认 `MENTION`;`ALWAYS` 则有消息即回)。裸 `/stop` 与内置 Web IM 群聊中的精确裸 `/new` 不受 MENTION 门控：前者只中断正在运行的 Agent，后者为群内每个 Agent 重开各自的共同会话。`/compact` 和 `/compact <关注点>` 仍必须以 mention 或 reply 明确指向 Agent。

#### Scenario: 群聊未被 @提及的消息不触发 Agent
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 群里来了一条既未 @该 Agent、也非回复该 Agent、也非裸 `/stop` 或精确裸 `/new` 的消息
- **THEN** 不创建内核会话、不发起运行;该消息仅作为后台上下文缓冲到该 Agent 自己的群上下文 buffer, 待该 Agent 下次被点名时随当轮一并带入

#### Scenario: 群聊被 @提及触发并把上下文带入当轮
- **GIVEN** 该 Agent 的群上下文 buffer 里已缓冲了若干条未点名消息
- **WHEN** 群里来了一条 @该 Agent 的消息
- **THEN** Gateway 创建/复用该群会话,把缓冲的消息(各带 `[sender]` 前缀)与当前消息一并提交给内核执行

#### Scenario: 群聊 Agent 输出 NO_REPLY 时不发言
- **WHEN** 群聊一轮运行的最终回复文本为 `NO_REPLY`
- **THEN** Gateway 不把 token 作为正文 delta 投递;若该轮已有用于 running/工具过程的 provisional 气泡则在终态回滚,最终不留下消息行、列表摘要、未读数或桌面通知

#### Scenario: 群聊 Agent 互相 @ 的 fan-out 回复输出 NO_REPLY 时不发言
- **GIVEN** 群聊里 Agent A 的回复 @ 了 Agent B,把 B 拉起(agent-to-agent fan-out),或某 Agent 的后台任务在群聊会话产生回复
- **WHEN** 被拉起的 Agent 判断无需接话,输出 `NO_REPLY`(或心跳静默 token `HEARTBEAT_OK`)
- **THEN** Gateway 对该 fan-out / 后台投递同样抑制,用户在群里看不到 `NO_REPLY` 字面量,该消息也不落库
- **AND** 静默 token 不作为 Agent 发言继续 fan-out,其他 Agent 的群上下文 buffer / run 不得收到该 token

#### Scenario: Web IM 群聊裸 `/new` 为每个 Agent 重开会话
- **GIVEN** 一个 `group_reply_policy=MENTION` 的内置 Web IM 多 Agent 群聊
- **WHEN** 用户发送精确的裸 `/new`
- **THEN** Gateway 为群内每个 Agent 分别切换到新的 Kernel session，并在同一群显示各 Agent 的控制确认
- **AND** 后续面向每个 Agent 的普通消息不携带该 Agent 先前的群会话上下文

#### Scenario: 群聊压缩仍需明确目标
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 用户发送未 @该 Agent、也非回复该 Agent 的 `/compact` 或 `/compact <关注点>`
- **THEN** Gateway 不压缩该 Agent 的群会话，也不发送控制确认
- **WHEN** 用户通过结构化 mention、文本 `@Agent` 或回复该 Agent 发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Gateway 只在被指向 Agent 的群会话上执行命令，并在同一群返回控制确认
