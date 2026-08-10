# gateway (personal_assistant) - Routing and Delivery Specification Delta

## MODIFIED Requirements

### Requirement: 用户可安全地手动压缩当前 Agent 会话

Gateway 在已路由的聊天中把精确的 `/compact` 和 `/compact <关注点>` 作为当前 Kernel session 的手动压缩命令。非空关注点仅指导这次摘要保留重点；它不作为普通用户 turn 写入会话。命令按同一 session 的 FIFO 顺序执行：到达前已经接受的工作先完成，命令之后到达的普通输入不能越过它；若 `/new` 先切换了 session generation，旧压缩按 superseded 结果收敛而不改写新会话。Gateway 在同一聊天明确区分成功、无需压缩、被新会话取代和失败；失败不得改变调用前上下文。其他 slash 文本按普通用户消息处理。

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

#### Scenario: 忙碌会话按 FIFO 执行压缩

- **GIVEN** 当前 session 有 active 或 queued work
- **WHEN** 用户发送 `/compact`，随后又发送一条普通消息
- **THEN** 已接受工作先完成，压缩随后执行，之后的普通消息最后开始
- **AND** 后续普通消息使用压缩后的上下文，当前工作不被压缩命令中断

#### Scenario: 新会话取代尚未执行的压缩

- **GIVEN** `/compact` 已在旧 session 的 FIFO 中等待
- **WHEN** 用户的 `/new` 先成功切换到新的 session generation
- **THEN** 旧压缩不改写新会话，用户得到既有 superseded 结果，后续消息使用新会话上下文

#### Scenario: 压缩失败时上下文不变

- **GIVEN** 当前 session 已轮到执行手动压缩，但无法生成或持久提交摘要
- **WHEN** Gateway 收到失败结果
- **THEN** Gateway 报告压缩未完成，后续运行仍使用压缩前上下文

#### Scenario: 重放同一入站压缩不产生第二个压缩边界

- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/compact <关注点>`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的压缩结果和控制确认
- **AND** 当前 Kernel session 不产生第二个 compaction record，关注点不作为重放 identity
