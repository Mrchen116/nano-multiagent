# Gateway routing-delivery Specification (delta for bugfix-608)

## MODIFIED Requirements

### Requirement: PA 为每条真人消息固定模型侧发生时间与实际入口

Gateway 对来自内置 Web IM 或外部 Channel 的真人消息，在不改变用户可见正文的前提下，为送入 Agent 的每条新 user message 固定一个稀疏 context envelope。时间优先采用 Channel 提供的消息发生时间；来源没有合法时间时，采用 Gateway 同步接受该消息时一次固定的接收时间；已知用户时区时，两者都按该消息发生时固定的用户时区呈现为带 offset 的 ISO 时间；未获得用户时区时保留明确 UTC，不猜测用户所在地。入口按该条消息实际经过的 Channel 标为 `Web IM` 或 `Feishu`，不从共享 shadow conversation 推断，也不附加 Direct/Group、Bot ID、chat ID、host 或 IP。

同一消息在 group buffer、normal submit、active steer、retry 和 history replay 中复用同一个固定 envelope；本 requirement 不改变 active steer 的接受、消费、持久化、失败处理或恢复语义。群聊继续保留既有 `[sender]`；模型侧新增 context 不写入 IM message body，也不进入 PA workspace 中供用户查看的简化聊天副本。PA 顶层会话的 system prompt 只保留稳定 timezone，不再把 session 创建时刻称为当前时间；动态时间只随新真人 user message 追加。Heartbeat、cron、subagent 与内部通知不获得真人消息 envelope；没有选择该行为的 Coding CLI 保持既有 prompt/message semantics。

#### Scenario: 长会话中的新消息各自保留发生时间
- **GIVEN** 用户在同一 PA 会话的不同时间先后发送两条真人消息
- **WHEN** 后一条消息进入 Agent context
- **THEN** 两条消息各自携带固定的发生时间，Agent 可判断先后与时段
- **AND** system prompt 不把会话创建时刻继续表述为当前时间

#### Scenario: 来源时间优先且缺失时固定 Gateway 接收时间
- **GIVEN** 一条消息带有合法 Channel occurrence time，另一条没有合法来源时间
- **WHEN** Gateway 为两条消息建立 model context
- **THEN** 第一条采用 Channel occurrence time，第二条采用各自进入 Gateway 时一次固定的 receipt time
- **AND** 后续 buffer、retry 或 replay 不重新读取当前时钟

#### Scenario: 飞书历史补拉沿用消息原发生时间
- **GIVEN** Gateway 在一条飞书群触发消息前通过 provider history API 补拉到先前漏收的真人消息，且该历史消息带合法 create time
- **WHEN** 补拉消息进入 group buffer 并随触发消息提供给 Agent
- **THEN** 该消息采用 provider create time，而不是本次补拉或触发发生的时间

#### Scenario: 同一 shadow context 按逐消息实际入口标注
- **GIVEN** 飞书聊天与 Web IM shadow conversation 共享同一 DSH session
- **WHEN** 用户先从飞书发送消息，随后从 Web IM 继续
- **THEN** Agent 看到前一条来自 `Feishu`、后一条来自 `Web IM`
- **AND** 两条消息都不因 conversation 的外部来源属性而被标成同一入口

#### Scenario: 群聊延续 sender 语义但不重复 chat type
- **GIVEN** Web IM 或飞书群聊中有多名参与者发送消息
- **WHEN** buffered 与当前消息一起进入 Agent context
- **THEN** 每条新消息同时保留实际 Channel、固定时间与既有 `[sender]`
- **AND** envelope 不额外输出 Direct/Group 或内部 routing identity

#### Scenario: model envelope 不污染用户可见正文
- **WHEN** 用户在 Web IM、飞书或 shadow conversation 查看、复制或搜索消息
- **THEN** message body 仍是用户原文，不含模型侧 time/Channel prefix

#### Scenario: workspace 可读聊天副本保持既有正文语义
- **WHEN** PA 将一次真人 user input 写入 `.nanoassistant/chat_history/`
- **THEN** user content 不含新增 time/Channel envelope
- **AND** 群聊仍可保留变更前已有的 `[sender]` 投影

#### Scenario: 功能启用前的旧历史不补造 context
- **GIVEN** 既有 transcript 或 group buffer row 没有可靠 occurrence time/actual Channel marker
- **WHEN** 功能启用后继续原 conversation
- **THEN** 旧内容保持原样，不用当前时间或当前入口补 stamp
- **AND** 此后新收到的真人消息开始使用固定 envelope

#### Scenario: 非 PA 真人入口保持现状
- **WHEN** Coding CLI、heartbeat、cron、subagent 或内部通知继续产生消息
- **THEN** 它们不获得本 requirement 的 time/Channel envelope
- **AND** 退役 Coding CLI 不再参与消息处理；heartbeat、cron、subagent 与内部通知保留各自的可信 message source/time 格式
