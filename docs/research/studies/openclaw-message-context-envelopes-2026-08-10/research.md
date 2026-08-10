---
status: research-snapshot
recorded-at: 2026-08-10
nano-baseline: 6a5860b488bd87f88e9c12d452d3657b39dfdd65
upstream: openclaw
upstream-baseline: be94853de0d0a282cfbe63316084a73613819084
source-baseline: openclaw@be94853de0d0a282cfbe63316084a73613819084; installed-openclaw@2026.4.2
installed-baseline: d74a12264aa5fb0598605e8f04e1864b7239ddd5
current-landing: pending-review
current-owner: pending-adoption
---

# OpenClaw 消息时间与上下文前缀证据记录

## 研究问题

本轮研究回答五个具体问题：

1. 同一会话从早到晚使用时，模型为什么能自然知道消息发生的时间？
2. 时间多久更新一次，是定时刷新还是随消息更新？
3. OpenClaw 是否明确告诉模型“方括号里的时间就是这条消息的发送时间”？
4. 除时间外，普通消息和特殊来源还会带哪些 prefix；“按需出现”的判定在哪里发生？
5. 动态时间如何与 prompt cache 的稳定前缀共存？

## 基线与证据边界

| 对象 | 固定基线 | 用途与限制 |
|---|---|---|
| nano-multiagent | `6a5860b488bd87f88e9c12d452d3657b39dfdd65` | 只记录研究落点；本轮没有实现变更 |
| OpenClaw upstream | `be94853de0d0a282cfbe63316084a73613819084`，2026-06-29 | 当前 `origin/main` 的源码与测试事实 |
| 本机 installed OpenClaw | `2026.4.2`；对应 tag commit `d74a12264aa5fb0598605e8f04e1864b7239ddd5` | 对照已发布版本的旧实现 |

本机 `/opt/homebrew/bin/openclaw` 指向全局安装包，但默认位置没有找到 `~/.openclaw/openclaw.json`。因此本文可以证明 installed package 和 upstream 源码具备什么行为，不能据此断言用户当时正在运行的 Gateway 一定采用默认配置或恰好来自该安装目录。本轮也没有保存真实 provider request；凡称“源码事实”的内容都来自固定 commit 的实现与测试，而不是运行抓包。

本文用以下标签区分结论来源：

| 标签 | 含义 |
|---|---|
| 源码事实 | 固定 commit 中实现或测试直接表达的行为 |
| 综合推论 | 多处源码共同支持的机制解释，但不是 OpenClaw 的显式产品承诺 |
| 采用判断 | 我们认为 nano 值得学习的最小契约；尚未成为 current behavior |

## 一、时间不是系统时钟，而是每条消息的 envelope

### 1.1 upstream 当前行为

在 provider 调用边界，OpenClaw 把裸 user message 变成：

```text
[Mon 2026-08-10 09:17 CST] 消息正文
```

源码事实：

- `attempt.llm-boundary.ts` 在每次送给 LLM 前遍历 user messages；没有 envelope 的裸消息按 `[DOW YYYY-MM-DD HH:MM TZ]` 格式加前缀。
- 它使用消息自身已固定的 timestamp，而不是序列化当下的 wall clock。
- 当前轮与重放历史轮走同一个规范化函数；同一条消息在不同请求中可得到字节一致的文本。
- 已有 channel envelope 或已带时间 envelope 的消息不会再重复加一层。

这意味着“多久更新一次”的准确回答是：**没有后台定时刷新；每收到一条新消息，就为这条消息固定一次时间。** 同一轮中的工具调用、重试和多次 provider 请求复用该消息的 timestamp。没有新消息时，普通聊天上下文中的钟不会自行前进。

direct message 的紧凑前缀精确到分钟；channel envelope 的 ISO-like timestamp 当前精确到秒。精度是序列化格式，不代表存在分钟级或秒级定时器。

### 1.2 它没有显式解释时间语义

OpenClaw 的 system prompt 只写用户时区，并明确说：需要精确的当前日期、时间或星期时调用 `session_status`。测试还断言 exact date/time 不进入 system prompt，以保持缓存稳定。

没有一条 system instruction 告诉模型“紧邻正文的方括号时间代表当条消息发送时间”。模型依靠训练中熟悉的 envelope 惯例和文本邻接关系理解它。因此应严格区分：

- 对 direct/gateway 路径，它通常是 runtime 接收并固定该消息的时间；
- 对 channel 路径，timestamp 可以来自 channel/provider 传入的消息元数据；
- 不能笼统把所有路径都承诺为终端用户点击发送按钮的设备时间。

“模型自然知道”是上述结构产生的综合效果，不是 OpenClaw 额外注入了一段时间语义说明。

### 1.3 heartbeat、cron 与精确当前时间是另一条路径

普通消息时间与“此刻几点”分开处理：

- 要查询精确当前时间，模型调用 `session_status`。
- heartbeat/cron 触发时，OpenClaw 可以注入 `Current time: ...` 与 `Reference UTC: ...`；upstream 当前实现会替换自己上次注入的旧时间块，避免一个特殊事件 prompt 中残留多个互相冲突的时间。
- heartbeat 使用该次 run 的 `startedAt`，cron 使用该次 job 运行时间。

所以长会话里的时间感主要来自逐消息 timestamp；精确 wall clock 则由工具或特殊触发提供，两者不混成一个持续变化的 system prompt。

## 二、普通消息 envelope 还有什么

### 2.1 一行 envelope 的固定顺序

channel message 的普通 header 由 `formatAgentEnvelope` 以固定顺序拼装：

```text
[channel, from + elapsed, host, ip, timestamp] body
```

测试覆盖的形状包括：

```text
[WebChat user1 mac-mini 10.0.0.5 Thu 2025-01-02T03:04:05Z] hello
[Telegram] hi
[Discord Guild #general] Alice: hi
[Signal Signal Group id:123] Bob (42): ping
[iMessage +1555] +1555: hello
```

`formatInboundEnvelope` 再按 direct/group/self 场景决定正文前是否出现 sender：direct self 使用 `(self):`，direct sender 使用可读 label，群聊有 sender 时使用 `<sender>: body`，缺少可用 sender 时保留原正文。

### 2.2 “按需出现”的准确含义

“按需”不是模型临时选择字段，而是 formatter 的确定性条件：

| 字段或块 | 出现条件 |
|---|---|
| `channel` | 总是有；缺省退化为 `Channel` |
| `from` | 调用方提供了来源 label |
| `+2m` 等 elapsed | 开启 elapsed，且当前与上一消息时间均有效、差值非负 |
| `host` / `ip` | 调用方实际提供 |
| `timestamp` | 提供并启用 timestamp，且能成功格式化 |
| sender body prefix | direct/group 规则能解析出 sender 或 self |
| reply/thread/forward/location/history | 当前消息确实处于对应场景 |
| active goal/current-message special | 对应运行状态或 channel 特例存在 |

也就是“字段存在且该路径允许，就按固定位置渲染；场景没有发生，就完全不生成那一块”。它不是每条消息前放一个带大量空值的通用 JSON 模板。

## 三、一行 header 之外的动态上下文

OpenClaw 把不同稳定性的元数据分两层，避免把每条消息都变化的 ID 和名称塞进 system prompt。

### 3.1 稳定 inbound meta

`buildInboundMetaSystemPrompt` 生成可信的 `openclaw.inbound_meta.v2`，只放较稳定的 account、channel、provider、surface、chat type 和 response format。它还明确声明这些 JSON 是 out-of-band 生成的权威 metadata；人名、群名、引用和历史在 user role 中是未信任内容。

### 3.2 user-role 动态 context

`buildInboundUserContextPrefix` 以 `⟦openclaw:ctx⟧` 标记开头，根据本次消息实际携带的数据生成：

- conversation info：chat/message/reply ID、conversation label、sender、timestamp、source modality、group/thread/topic、mentions、history count；
- thread starter；
- reply chain 或 reply target；
- forwarded message context；
- location；
- structured channel context；
- chat history since last reply；
- active goal；
- channel-specific current message，例如 Telegram 被引用的文本。

该 marker 便于后续识别和剥离，但源码明确说它本身不是 security boundary。动态人名和外部正文仍按 untrusted user content 对待。

## 四、特殊来源 prefix

普通 channel envelope 之外，还有几类事件会显式标注来源或调度状态：

| 场景 | 代表形状 | 作用 |
|---|---|---|
| 跨会话/内部工具 | `[Inter-session message] sourceSession=... sourceChannel=... sourceTool=... isUser=false` | 明确告诉模型这是路由进来的数据，不是直接用户指令 |
| agent 忙时排队 | `[Queued messages while agent was busy]`，后接 `Queued #1 (from Sender)` | 保留批次、顺序与发送者 |
| cron | `[cron:<jobId> <name>]`，正文后附 current time | 标记自动任务来源和本次运行时间 |
| session system event | `System: [timestamp] event text` | 把系统事件与用户输入分开 |
| restart/recovery | `[System] ...` | 标记恢复或运行时消息 |

跨会话 prefix 的显式 `isUser=false` 很重要：OpenClaw 对普通时间不额外解释语义，但对会改变指令信任边界的来源会明确说明。

## 五、prompt cache 为什么没有被时间持续破坏

### 5.1 稳定 system prefix 不包含当前时钟

源码事实：system prompt 的时间 section 只保留 timezone，exact date/time 被测试明确排除。upstream 当前还有显式 `OPENCLAW_CACHE_BOUNDARY`：

- 工具、skills 和静态项目上下文进入 `stablePrefix`；
- 动态项目上下文、channel/session guidance、heartbeat 和 runtime 信息进入 `dynamicSuffix`；
- Anthropic provider 只给 stable prefix 标记 `cache_control`。

因此时钟不会周期性改写 system prompt 的开头。

### 5.2 新消息只增长在历史尾部

对完整重发式对话，请求大致是：

```text
stable system prefix
dynamic system suffix
message 1 with fixed timestamp
message 2 with fixed timestamp
...
new message with its new fixed timestamp
```

新时间只属于新增的尾部消息；旧消息的 timestamp 不变，所以已有长前缀仍能命中 provider prefix cache。当前 upstream 的 cache-stability tests 同时覆盖 OpenAI Chat Completions 与 Responses 序列化，验证当前轮和历史轮的字节一致性以及重复调用不会随 wall clock 漂移。

cache TTL 与时间正确性也是两回事：installed 2026.4.2 的 Anthropic direct path 默认 short retention；upstream 当前 short 对应默认约 5 分钟、long 对应约 1 小时，OpenAI 由 provider 自动处理。TTL 到期只意味着下一次冷缓存，不会让模型继续使用旧时钟。heartbeat 可以帮助保温，但不是保证时间正确的机制。

### 5.3 2026.4.2 到 upstream 当前的关键演进

| 版本 | 注入位置 | cache 含义 |
|---|---|---|
| installed 2026.4.2 | gateway `agent` / `chat.send` 路径在组装 `BodyForAgent` 时加 `[DOW ...]`；UI 的 `Body` 保持原文 | 不污染 cached system prompt；不同入口需各自避免重复 envelope |
| upstream 当前 | 在统一 LLM boundary 对当前与历史 user message 规范化 | 固定消息 timestamp，保证历史重放和当前轮序列化一致，专门修复 full-resend prefix cache 稳定性 |

## 六、我们准备学习的最小契约

以下是采用判断，不是 nano 的 current behavior，也不是 OpenClaw 已承诺的 public API。

1. 原始/UI body 保持不变，只在 provider-facing 的 LLM boundary 派生 envelope。
2. direct/internal message 使用紧凑的一行时间前缀：`[DOW YYYY-MM-DD HH:MM TZ] body`。
3. 按用户本轮明确选择，**不额外加入“该时间代表当条消息时间”的 system instruction**，沿用 OpenClaw 的邻接惯例。
4. 每条消息只固定一次 timestamp；重试、工具循环和历史重放必须字节一致；已有 envelope 不重复加。
5. channel envelope 只渲染真实存在且有消费价值的字段，保持固定字段顺序；不默认照搬 host、IP 或大块 JSON。
6. reply/group/thread/forward/history 等结构仅在对应场景存在时加入 user-role context。
7. 跨会话内容必须显式携带 source 与 `isUser=false`，因为这涉及信任语义，不能只靠格式暗示。
8. exact current time 由 status tool 或 heartbeat/cron 等事件提供，不把持续变化的时钟放入 stable system prefix。

采用前仍需在 change unit 中决定：nano 哪个对象持有 canonical message timestamp、channel provider timestamp 的优先级、timezone 解析来源、compaction 后如何保存 timestamp，以及各 provider 的序列化回归测试范围。

## 固定源码索引

以下链接固定到 `be94853de0d0a282cfbe63316084a73613819084`，避免未来 main 漂移：

| 主题 | 源码 |
|---|---|
| LLM boundary 时间规范化 | [`attempt.llm-boundary.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/embedded-agent-runner/run/attempt.llm-boundary.ts#L368-L418) |
| system prompt 时间与 cache boundary | [`system-prompt.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/system-prompt.ts#L1001-L1044)；[`system-prompt-cache-boundary.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/system-prompt-cache-boundary.ts#L1-L35) |
| exact time 不进入 system prompt 的测试 | [`system-prompt.test.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/system-prompt.test.ts#L648-L670) |
| 普通 channel envelope | [`envelope.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/auto-reply/envelope.ts#L171-L247)；[`envelope.test.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/auto-reply/envelope.test.ts) |
| inbound meta 与动态 user context | [`inbound-meta.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/auto-reply/reply/inbound-meta.ts#L561-L808) |
| 跨会话来源 | [`input-provenance.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/sessions/input-provenance.ts#L131-L146) |
| 排队消息 | [`drain.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/auto-reply/reply/queue/drain.ts#L281-L346) |
| heartbeat/cron current time | [`current-time.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/current-time.ts#L39-L79)；[`heartbeat-runner.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/infra/heartbeat-runner.ts#L1780-L1795)；[`isolated-agent/run.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/cron/isolated-agent/run.ts#L764-L799) |
| Anthropic stable-prefix cache | [`anthropic.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/llm/providers/anthropic.ts#L1367-L1418) |
| full-resend cache 稳定性测试 | [`attempt.llm-boundary.cache-stability.test.ts`](https://github.com/openclaw/openclaw/blob/be94853de0d0a282cfbe63316084a73613819084/src/agents/embedded-agent-runner/run/attempt.llm-boundary.cache-stability.test.ts#L154-L267) |

关键演进 commit：[`1af55bc6654f898fc4c39bad3204eb504d160089`](https://github.com/openclaw/openclaw/commit/1af55bc6654f898fc4c39bad3204eb504d160089)，提交说明为 `fix(agents): stabilize user-turn serialization across turns to preserve prompt cache (#90811)`。

## 未知项与后续验证

- 没有捕获真实运行中的 OpenClaw provider payload，因此尚未验证用户实际入口当时选择了 direct prefix 还是 channel envelope。
- 没有验证所有 connector 对 provider timestamp、server receive time 和本地 timezone 的优先级；不能把所有 envelope timestamp 统一命名为“终端发送时间”。
- 没有测量真实 cache hit rate；本文证明的是 cache-friendly 的字节结构和测试契约，不是某 provider/account 的命中率。
- nano 的采用契约还未设计、实现或验收；本文只为后续 change unit 提供固定上游证据。
