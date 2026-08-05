# Gateway Routing and Delivery Specification (delta for feat-501)

> Target canonical: `docs/specs/gateway/routing-delivery.md`

## ADDED Requirements

### Requirement: 用户可用文本命令切换当前 Agent 会话

Gateway 在已路由的 direct chat，或明确指向 Agent 的 group chat 中，把精确的 `/new` 作为当前 Gateway session 的新会话命令。命令确认留在原聊天，既有可见历史不删除；后续普通消息使用新的 Kernel session。若原 session 正在执行，Gateway 先撤销并收敛旧 run 的所有尚未完成用户可见输出，再中断它；已排队但尚未提交的旧输入不能在新会话执行，旧 run 的 stream、final reply 或 external mirror 也不得在新会话确认之后抵达。`/new` 之外带有额外文本的 slash 消息按普通用户消息处理。

#### Scenario: `/new` 保留可见历史并切换后续上下文
- **GIVEN** 用户与某 Agent 已在一个 direct chat 中进行多轮对话
- **WHEN** 用户发送精确的 `/new`
- **THEN** 原聊天显示开始新会话的确认，既有可见消息仍可阅读
- **AND** 后续普通消息由新的 Kernel session 处理，不携带旧会话上下文

#### Scenario: 运行中开始新会话
- **GIVEN** 当前 Gateway session 有正在执行或已接受但尚未提交的用户工作
- **WHEN** 用户发送 `/new`
- **THEN** Gateway 中断已执行的旧 run，丢弃未提交的旧输入，并确认旧操作已停止且新会话已就绪
- **AND** 不再向该聊天投递旧 run 的 stream、final reply 或 external mirror，也不把旧输入提交到新 Kernel session
- **AND** 若旧 run 已有 provisional bubble，Gateway 在新会话确认前将其以无正文的终态关闭或丢弃

#### Scenario: 重放同一入站 `/new` 不重复切换会话
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/new`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的新会话结果和控制确认
- **AND** 不创建第二个 Kernel session，也不因第二次切换丢弃第一次切换后的用户输入

#### Scenario: 新会话发布失败不吞掉旧 run 输出
- **GIVEN** 当前 Gateway session 的 old run 已产生一条尚未投递的 stream、terminal reply 或 external mirror
- **AND** 用户发送 `/new` 后，Gateway 已临时暂停该 old run 的可见输出
- **WHEN** 新 Kernel session 无法持久发布为当前 binding
- **THEN** Gateway 保持原 binding 与后续上下文，不发送“已开始新会话”确认
- **AND** 暂挂的 old run output 以原 identity 恰好一次恢复投递，old run 后续输出仍可见

### Requirement: 用户可安全地手动压缩当前 Agent 会话

Gateway 在已路由的聊天中把精确的 `/compact` 和 `/compact <关注点>` 作为当前 Kernel session 的手动压缩命令。非空关注点仅指导这次摘要保留重点；它不作为普通用户 turn 写入会话。Gateway 只在当前 session 无 active 或 queued work 时执行压缩，并在同一聊天明确区分成功、无需压缩、忙碌和失败；失败不得改变调用前上下文。其他 slash 文本按普通用户消息处理。

#### Scenario: 空闲会话按关注点压缩
- **GIVEN** 当前聊天已有可压缩的历史，其中含认证方案和未完成事项
- **WHEN** 用户发送 `/compact 保留认证方案与未完成项`
- **THEN** Gateway 在原聊天确认已按该关注点压缩
- **AND** 随后的 Agent run 可从压缩摘要延续认证方案和未完成事项，关注点本身不成为一条普通 user message

#### Scenario: 当前没有可压缩会话
- **GIVEN** Gateway 尚未为当前聊天建立 Kernel session，或已有 session 但没有新的可压缩历史
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 在原聊天说明无需压缩
- **AND** 不为该 no-op 创建空 Kernel session，也不改变已有会话上下文

#### Scenario: 忙碌或失败时上下文不变
- **GIVEN** 当前 session 有 active 或 queued run
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 提示等待当前操作完成或先使用 `/stop`，且不调用压缩
- **GIVEN** 当前 session 空闲但手动压缩无法生成或持久提交摘要
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 报告压缩未完成，后续运行仍使用压缩前上下文

#### Scenario: 重放同一入站压缩不产生第二个压缩边界
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/compact <关注点>`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的压缩结果和控制确认
- **AND** 当前 Kernel session 不产生第二个 compaction record，关注点不作为重放 identity

## MODIFIED Requirements

### Requirement: 群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent

群聊流量在分配任何内核会话或队列槽**之前**先过 @提及门控。未被点名的群聊消息不触发 Agent 执行;Agent 判断无需回复时输出约定 token(`NO_REPLY`)则不向用户发言。门控策略由各 Agent 的 `group_reply_policy`决定(默认 `MENTION`;`ALWAYS` 则有消息即回)。裸 `/stop` 保持唯一不受 MENTION 门控的控制命令例外；`/new`、`/compact` 和 `/compact <关注点>` 必须以 mention 或 reply 明确指向 Agent，才操作该群与 Agent 共有的会话。

#### Scenario: 群聊未被 @提及的消息不触发 Agent
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 群里来了一条既未 @该 Agent、也非回复该 Agent、也非裸 `/stop` 的消息
- **THEN** 不创建内核会话、不发起运行;该消息仅作为后台上下文缓冲到该 Agent 自己的群上下文 buffer, 待该 Agent 下次被点名时随当轮一并带入

#### Scenario: 群聊被 @提及触发并把上下文带入当轮
- **GIVEN** 该 Agent 的群上下文 buffer 里已缓冲了若干条未点名消息
- **WHEN** 群里来了一条 @该 Agent 的消息
- **THEN** Gateway 创建/复用该群会话,把缓冲的消息(各带 `[sender]` 前缀)与当前消息一并提交给内核执行

#### Scenario: 群聊新会话与压缩命令必须明确指向 Agent
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 用户发送未 @该 Agent、也非回复该 Agent 的 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Gateway 不切换或压缩该群会话，也不发送控制确认
- **WHEN** 用户通过结构化 mention、文本 `@Agent` 或回复该 Agent 发送相同命令
- **THEN** Gateway 在该群的共同会话上执行命令，并在同一群返回控制确认

#### Scenario: 群聊 Agent 输出 NO_REPLY 时不发言
- **WHEN** 群聊一轮运行的最终回复文本为 `NO_REPLY`
- **THEN** Gateway 不把 token 作为正文 delta 投递;若该轮已有用于 running/工具过程的 provisional 气泡则在终态回滚,最终不留下消息行、列表摘要、未读数或桌面通知

#### Scenario: 群聊 Agent 互相 @ 的 fan-out 回复输出 NO_REPLY 时不发言
- **GIVEN** 群聊里 Agent A 的回复 @ 了 Agent B,把 B 拉起(agent-to-agent fan-out),或某 Agent 的后台任务在群聊会话产生回复
- **WHEN** 被拉起的 Agent 判断无需接话,输出 `NO_REPLY`(或心跳静默 token `HEARTBEAT_OK`)
- **THEN** Gateway 对该 fan-out / 后台投递同样抑制,用户在群里看不到 `NO_REPLY` 字面量,该消息也不落库
- **AND** 静默 token 不作为 Agent 发言继续 fan-out,其他 Agent 的群上下文 buffer / run 不得收到该 token
