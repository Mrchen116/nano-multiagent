# feat-530: 消息时间与 Channel 上下文

## Relations

- Related: feat-379
- Related: feat-447
- Related: feat-501

## 参考依据

- [`OpenClaw 消息时间与上下文前缀 — 2026-08-10`](../../research/studies/openclaw-message-context-envelopes-2026-08-10/README.md) 是本需求的上游行为证据，不代表 nano-multiagent 的 current contract。

## 原始需求

> 他没显式告诉，我们也学他。他除了时间作为prefix还有什么prefix

> “按需出现”是具体啥意思

> 很好，study中记录下openclaw这些我们学习了的内容，并commit下

> 建立一个spec，我觉得我们可以学习一部分过来，比如时间和channel。先看看我们当前的情况

## 澄清记录

- Q1: 本期是否限定为 PA 的所有真人入站消息——Web IM 与外部 channel、direct 与 group 都获得时间和 channel 感知；Coding CLI、heartbeat/cron、subagent 和内部通知暂不纳入？
  A(原话): 对。只改PA，其他都不改，而且这个需求和sdk无关，所以sdk最好别碰
  Agent 解读: 本期只改变 personal_assistant 的真人消息体验；其他产品入口、后台触发和内部消息维持现状。用户同时明确要求后续设计优先在 PA 边界内完成，不扩张 agent.sdk。
- Q2: 每条 PA 消息的时间语义是否定为：优先采用 channel 记录的消息发生时间；来源没有提供时，回退到 Gateway 接收时间；最终按 PA 用户所在时区呈现？
  A(原话): ok，这个可以仿照openclaw
  Agent 解读: 采用 OpenClaw 同类时间语义；优先保留来源时间、缺失时兜底接收时间，并以用户所在时区呈现，但不宣称它必然等于用户设备点击发送的瞬间。
- Q3: channel 信息本期是否只让模型知道“来源平台 + 会话类型”，例如 `Web IM Direct`、`Feishu Group`，并保留现有群聊 sender；不加入 Bot ID、chat ID、host、IP 等内部信息？
  A(原话): Direct不用说吧，Group现在已经有体现了，也不用说吧
  Agent 解读: 新增 channel 上下文不重复表达 direct/group；群聊继续沿用现有 communication context 与 sender prefix。本期只补来源平台，不加入内部路由身份、host 或 IP。
- Q4: 是否每条 PA 真人消息都标注它这一次的实际入口，例如 `Web IM` 或 `Feishu`；尤其同一个影子会话从飞书发来的消息标 `Feishu`，从内部 IM 发出的消息标 `Web IM`？
  A(原话): 是
  Agent 解读: channel 是逐消息的实际触发来源，不是会话的固定归属；共享同一上下文的跨入口消息也必须分别保留各自来源。
- Q5: 时间和 channel prefix 是否只进入模型上下文，Web IM、Feishu 和影子会话里用户看到的原消息仍保持原文，不显示也不存成正文的一部分？
  A(原话): 对
  Agent 解读: envelope 是模型侧派生上下文，不改变用户消息正文，也不污染聊天展示、复制或搜索。
- Q6: PA 是否同时去掉当前 system prompt 中那条会固定为“会话创建时间”的 `Current date and time`，改为只保留稳定时区，让模型以逐消息时间判断时间进展？
  A(原话): openclaw去掉了吗
  Agent 解读: 用户先确认 OpenClaw 的真实行为；经说明其 system prompt 去掉精确当前时间、只保留时区，并由逐消息 prefix 与 `session_status` 提供时间后，继续确认如下。
  A(原话): follow它
  Agent 解读: PA 跟随 OpenClaw：system prompt 只保留稳定时区，不再把会话创建时间表述为当前时间；其他产品不变。
- Q7: 历史兼容是否采用“不猜测”原则——功能启用后的新 PA 消息，其时间和实际入口在重启、历史重放后仍保持一致；启用前已经存在的旧消息不倒推、不伪造 prefix，继续保持原样？
  A(原话): ok
  Agent 解读: 新行为以启用后的 PA 消息为边界；新消息的时间与实际入口必须稳定重放，旧消息缺少可靠数据时不补写 envelope。
- Q8: OpenClaw 另有 `session_status` 用于主动查询精确当前时间。本期是否不增加类似工具，只做逐消息时间、稳定时区和实际 channel，精确时间查询能力以后有需要再单独立项？
  A(原话): 对
  Agent 解读: 本期不增加精确当前时间查询工具，只解决 PA 真人消息的自然时间感与实际入口感知。

## 用户场景

用户与 PA 保持一个从早上延续到晚上的长会话。当前产品只在 system prompt 中保留会话创建时刻，并把它持续称为 `Current date and time`；每条历史消息进入模型时又没有自己的时间。改进后，Agent 能从每条新消息附带的发生时间理解“早上那条”“刚才”“今天晚上”等自然时间关系，不再把会话创建时刻误认为此刻。时间以 channel 提供的消息发生时间为先，缺失时采用 Gateway 接收时间，并按 PA 用户所在时区理解。

用户还可能在同一段上下文中往返于飞书和内部 Web IM。飞书消息进入对应影子会话后，用户可以在 Web IM 继续发言；Agent 能分辨每条消息这一次真正来自 `Feishu` 还是 `Web IM`，而不是把整段会话永久当成某一个 channel。它只需要知道来源平台，不需要知道 direct/group、Bot ID、chat ID、host 或 IP。

群聊保留现有体验：Agent 继续从 `[display_name]` 与 communication context 理解谁在说话、有哪些参与者以及如何 mention，不再重复增加 `Group`；私聊也不增加没有价值的 `Direct`。时间与 channel envelope 只存在于模型上下文，用户在 Web IM、飞书和影子会话中看到、复制和搜索的消息仍是自己输入的原文。

功能启用后形成的新消息在 Gateway 重启或历史重放后仍保留原来的发生时间与实际入口。启用前的旧消息缺少可靠 channel 或时间时保持原样，不用当前时间或当前入口补造历史。Coding CLI、heartbeat、cron、subagent 与内部通知继续使用既有行为；本期也不增加 `session_status` 一类精确时间查询工具。

## 验收标准

### Requirement: PA Agent 能理解每条真人消息发生的时间

#### Scenario: 长会话跨越一天中的多个时段
- **GIVEN** 用户在同一个 PA 会话中早上发送一条消息，晚上继续发送另一条消息
- **WHEN** 用户在晚上的消息中询问两次交流的时间关系
- **THEN** Agent 能依据两条消息各自的发生时间区分早晚和先后
- **AND** Agent 不把早上的会话创建时刻继续当作晚上的当前时间

#### Scenario: channel 提供消息发生时间
- **GIVEN** channel 记录的消息发生时间与 Gateway 实际收到消息的时间不同
- **WHEN** Agent 在后续对话中理解该消息发生的时间
- **THEN** Agent 采用 channel 记录的消息发生时间，并按 PA 用户所在时区理解

#### Scenario: channel 没有提供消息发生时间
- **GIVEN** 一条 PA 真人消息没有可用的来源时间
- **WHEN** 该消息进入 Agent 对话
- **THEN** Agent 仍能依据 Gateway 收到该消息的时间理解它在会话中的时间位置

### Requirement: PA Agent 能识别每条真人消息的实际入口

#### Scenario: 同一影子会话从飞书继续到 Web IM
- **GIVEN** 飞书聊天与内部 Web IM 影子会话共享同一段 Agent 上下文
- **WHEN** 用户先从飞书发送消息，随后从 Web IM 影子会话发送消息
- **THEN** Agent 能识别前一条消息来自 `Feishu`、后一条消息来自 `Web IM`
- **AND** Agent 不因共享会话而把两条消息误认为来自同一入口

#### Scenario: 群聊继续保留既有参与者语义
- **GIVEN** 用户在 Web IM 或飞书群聊中与 Agent 对话
- **WHEN** 多名参与者先后发送消息并触发 Agent
- **THEN** Agent 既能识别消息的实际来源平台，也继续按现有行为区分各消息发送者
- **AND** 新增 channel 感知不重复表达 `Group` 或暴露内部 Bot ID、chat ID、host、IP

#### Scenario: 私聊只表达有价值的来源平台
- **WHEN** 用户在 Web IM 或飞书私聊中向 PA 发送消息并询问当前消息来自哪里
- **THEN** Agent 能回答实际来源平台
- **AND** 不额外把 `Direct` 当作新的消息上下文重复表达

### Requirement: 上下文 envelope 不改变用户消息原文

#### Scenario: 用户在原入口查看和复制消息
- **WHEN** 用户在 Web IM 或飞书中查看、复制自己发送的消息
- **THEN** 消息仍保持用户输入的原文，不显示时间或 channel prefix

#### Scenario: 外部消息同步到影子会话
- **WHEN** 一条飞书用户消息同步到内部 Web IM 影子会话
- **THEN** 两端展示的用户消息正文都不包含模型侧时间或 channel prefix
- **AND** 用户按正文搜索消息时无需包含这些 prefix

### Requirement: 新消息的时间与入口可稳定延续

#### Scenario: Gateway 重启后继续既有会话
- **GIVEN** 功能启用后，PA 会话已经收到带可靠时间和实际入口的新消息
- **WHEN** Gateway 重启，用户继续该会话并追问先前消息的时间或来源
- **THEN** Agent 看到的先前消息仍保持原来的发生时间与实际入口

#### Scenario: 功能启用前的旧消息缺少可靠上下文
- **GIVEN** 一个既有 PA 会话包含功能启用前形成、没有可靠时间或 channel 的旧消息
- **WHEN** 用户在功能启用后继续该会话
- **THEN** 旧消息保持原样，不被标成当前时间或当前入口
- **AND** 此后新收到的 PA 真人消息开始获得可靠的时间与实际入口

### Requirement: 非 PA 入口保持既有行为

#### Scenario: 用户继续使用 Coding CLI
- **WHEN** 用户在 Coding CLI 中继续或新建会话
- **THEN** Coding CLI 的消息上下文与 system prompt 行为保持不变

#### Scenario: PA 产生非真人入站消息
- **WHEN** heartbeat、cron、subagent 或内部通知进入 PA 会话
- **THEN** 它们继续使用各自既有的来源和时间语义，不套用本期真人消息 envelope

## 范围与非目标

- 在范围：
  - PA 中来自 Web IM 和外部 channel 的真人消息，包括私聊与群聊。
  - 每条新消息的发生时间：优先使用 channel 来源时间，缺失时回退 Gateway 接收时间，并按 PA 用户所在时区理解。
  - 每条新消息的实际入口平台；同一共享会话中的不同入口逐消息区分。
  - PA system prompt 不再把会话创建时刻表达为当前时间，只保留稳定时区。
  - 模型侧 envelope 与用户可见消息正文分离。
  - 功能启用后的新消息在重启和历史重放中保持一致；旧消息不猜测回填。
- 非目标：
  - 不改变 Coding CLI、heartbeat、cron、subagent 或内部通知的消息行为。
  - 不新增 `session_status` 或其他精确当前时间查询工具。
  - 不新增或改变 `agent.sdk` 公共能力与消费者契约。
  - 不重复增加 `Direct` / `Group`，不向模型加入 Bot ID、chat ID、host 或 IP。
  - 不在本期引入 OpenClaw 的 reply、forward、location、queued message、inter-session 等其他动态 prefix。
  - 不改变 Web IM、飞书、影子会话的消息展示、复制与搜索正文。
  - 不为功能启用前缺少可靠元数据的旧消息补造时间或 channel。
