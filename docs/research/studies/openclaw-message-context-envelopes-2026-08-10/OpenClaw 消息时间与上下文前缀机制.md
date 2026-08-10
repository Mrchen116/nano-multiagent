---
status: research-snapshot
recorded-at: 2026-08-10
nano-baseline: 6a5860b488bd87f88e9c12d452d3657b39dfdd65
upstream: openclaw
upstream-baseline: be94853de0d0a282cfbe63316084a73613819084
source-baseline: openclaw@be94853de0d0a282cfbe63316084a73613819084; installed-openclaw@2026.4.2
current-owner: pending-adoption
---

# OpenClaw 消息时间与上下文前缀机制

OpenClaw 让模型在一个从早用到晚的会话里自然知道时间，核心并不是定时改 system prompt，而是把时间固定在每条 user message 的模型侧表示上：

```text
[Mon 2026-08-10 09:17 CST] 早上先看看今天的安排
...
[Mon 2026-08-10 20:46 CST] 现在把结果汇总一下
```

模型看到完整历史时，自然能比较两条消息的时间。这个时钟是事件驱动的：新消息到达时生成一次，之后不再变化。工具调用、重试和历史重放继续使用同一时间；没有新消息时，普通对话历史不会每分钟被刷新。

这一点同时解决了“时间感”和 prompt cache 的矛盾：旧消息永远不变，新时间只出现在新增的最后一条消息上，因此长历史的共同前缀仍可复用。

## 它没有告诉模型“这是发送时间”

OpenClaw 没有在 system prompt 里显式解释：`[Mon 2026-08-10 09:17 CST]` 就是紧随其后消息的发送时间。system prompt 只提供用户时区；当模型确实需要精确的“现在几点”时，指示它调用 `session_status`。

模型能理解，是因为时间与正文紧邻，而且这种 envelope 形式在训练数据里十分常见。这种设计很克制：无需为了一个明显的格式惯例，在每次请求中重复说明时间语义。

但实现和文档不能偷换概念。direct 路径通常固定 runtime 接收消息的时间；channel 路径还可能使用上游平台提供的 timestamp。它们都可以叫 message timestamp，却不一定都等于用户设备点击发送的瞬间。

## 一条普通消息前面可能有什么

channel message 的 header 不是只有时间。OpenClaw 按固定顺序组合已有字段：

```text
[channel, from + elapsed, host, ip, timestamp] body
```

例如：

```text
[WebChat user1 mac-mini 10.0.0.5 Thu 2025-01-02T03:04:05Z] hello
[Telegram] hi
[Discord Guild #general] Alice: hi
```

正文内部还会根据 direct、group 和 self 场景补 sender，例如 `Alice: hi` 或 `(self): hi`。

这里的“按需出现”是代码层的确定性判断，不是模型决定要不要看：调用方给了 `from` 才显示来源；同时有上一条和当前时间且开启 elapsed 才显示 `+2m`；给了 host/IP 才显示；能解析出 sender 才在正文前显示 sender。没有字段就不生成占位符。

因此它不是一份每条消息都携带的巨大 metadata 模板，而是一种稀疏、固定顺序的序列化。

## 一行 header 放不下的上下文

回复链、群聊、转发、位置和历史等信息不会硬塞进一行方括号。OpenClaw 把它们作为 user-role 的结构化 context，仍然只在场景存在时生成：

- conversation、message、reply、thread 和 topic ID；
- sender、群聊或 conversation label；
- thread starter、reply target 或 quoted text；
- forwarded message、location；
- since last reply 的 chat history；
- active goal 和 channel-specific current message。

较稳定的 account、channel、provider、surface、chat type、response format 则进入独立的 trusted inbound meta。人名、群名、引用文本和历史仍被视作外部 user content，不能因为长得像 metadata 就提升信任级别。

这层分离同时服务于安全和缓存：稳定字段可以待在较稳定的位置，每条消息变化的 ID、名称与正文留在 user-role 尾部。

## 哪些特殊 prefix 值得单独理解

几种前缀不是普通展示字段，而是在声明来源或运行状态：

```text
[Inter-session message] sourceSession=... sourceChannel=... sourceTool=... isUser=false
[Queued messages while agent was busy]
Queued #1 (from Sender)
[cron:<jobId> <name>]
System: [timestamp] event text
```

其中跨会话消息明确写 `isUser=false`，并告诉模型它是内部路由数据而不是直接用户指令。OpenClaw 对普通时间采用隐式格式惯例，对会影响信任边界的来源却显式说明；这是两类不同问题，不应为了“统一”而用同一种处理。

## 时间更新与 cache 的真正平衡

OpenClaw 的平衡不是“每隔多久牺牲一次 cache”，而是让会变化的内容待在正确的位置：

1. stable system prefix 放工具、skills、静态项目上下文，不放 exact current time；
2. system prompt 只放相对稳定的 timezone；
3. 每条历史消息保存自己的固定 timestamp；
4. 新消息连同新 timestamp 追加在末尾；
5. 精确当前时间通过 `session_status`，heartbeat/cron 则在自己的事件 prompt 中刷新时间块。

upstream 当前实现还在 system prompt 中划出显式 cache boundary。Anthropic 只给 stable prefix 标记 cache control；动态 system suffix 与新增消息可以变化而不要求重写稳定前缀。当前轮和历史轮统一在 LLM boundary 序列化，并有 OpenAI Chat Completions 与 Responses 的字节稳定测试。

所以即使两条消息相隔十小时，第二条消息仍可携带正确的新时间，同时第一条消息及此前的长前缀保持不变。cache TTL 过期只意味着下一次请求需要冷缓存，并不造成“模型看到旧时间”。

## nano 值得学习的最小版本

我们本轮形成的候选契约是：

- 原始/UI body 不变，只在送 provider 前生成模型侧 envelope；
- direct/internal message 先采用 `[DOW YYYY-MM-DD HH:MM TZ] body`；
- 不额外解释该时间的语义，沿用 OpenClaw 的邻接惯例；
- timestamp 属于消息且只固定一次，重试和历史重放必须一致；
- channel 字段保持固定顺序，只渲染真实存在且有消费者的内容；
- reply、group、thread、forward、history 只在实际发生时加；
- 跨会话来源必须显式带 source 与 `isUser=false`；
- exact current time 不进入 stable system prompt。

不应机械照搬 host、IP 或完整 inbound JSON。OpenClaw 的价值不在字段越多越好，而在三件事：稳定内容与动态内容分层、每条消息序列化可重现、只为真实发生的场景付上下文成本。

这仍是研究结论，不是 nano-multiagent current behavior。源码基线、逐项证据和未知项见 [`research.md`](research.md)。
