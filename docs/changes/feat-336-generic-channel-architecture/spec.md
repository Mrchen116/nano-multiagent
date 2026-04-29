# Spec: Generic Multi-IM Channel Architecture

## 1. 背景

`personal_assistant` Node Gateway 现在已经有一套可工作的极简 Channel 骨架：

- `ChannelAdapter` 只有 `start(on_inbound)`、`send(outbound)`、`stop()` 三个方法。
- `WebRelayAdapter` 已经把内置 Web IM 的 `relay.message` 转成 `InboundMessage`。
- `InboundPipeline` 已经完成 Agent 路由、会话绑定、串行队列、Agent 执行、回复原通道。
- `SessionBindingStore` 已经支持 SQLite 持久化，并在恢复时验证 kernel session 是否还存在。
- `send_message` 工具已经通过 Gateway internal dispatch 走 IM 业务目标寻址：`user_id`、`agent_id`、`conversation_id`。

这套骨架的方向是对的，但要接入飞书以及后续更多 IM，需要补齐跨平台共用的消息面能力：去重、防抖、群聊门控、附件表达、回复目标、投递降级、重试、回执。设计目标是保持 Gateway 的核心抽象简洁，不把每个 IM 的特殊性扩散到业务流水线里。

本 spec 的第一阶段目标：

- 增加 Feishu Channel。
- 抽象出可复用的多 IM 消息面架构。
- 让内置 Web IM 的聊天消息能力和外部 IM 走同一套 Gateway 入口。
- 保持 IM 服务控制面不混入 Channel 抽象。
- 为后续 Slack、Telegram、QQ 等 IM 留出扩展点。

## 2. 参考项目研究

### 2.1 OpenClaw 的设计

OpenClaw 的核心优点不在于某个单独 Channel，而在于它把“平台接入”和“运行时编排”拆得比较清楚。

值得吸收的设计：

- **声明式 Channel 能力**：Channel 声明支持的 chat types、threads、media、edit、presentation 等能力，核心运行时根据能力选择行为，而不是到处写平台判断。
- **通用 inbound debouncer**：`createInboundDebouncer` 采用 key-based debounce，同一个 key 的消息在短窗口内合并，同时保留跨 key 并发能力；还有限制最大 tracked keys 的保护，避免长期运行时内存无限增长。
- **MessagePresentation 抽象**：OpenClaw 用 `MessagePresentation` 表达 title、tone、blocks、buttons 等更高层的消息呈现，再由平台 renderer 变成卡片、富文本或 fallback text。
- **outbound delivery 编排**：核心 outbound pipeline 负责统一调用 channel renderer、fallback 和 delivery，而平台 adapter 负责具体格式渲染。
- **session binding 独立服务**：会话绑定不是散落在 adapter 中，而是作为运行时服务维护。
- **conversation resolution 独立化**：route/binding/conversation 解析被放在 channel 之外，避免 adapter 背业务路由逻辑。
- **run-scoped agent events**：Web 端可以在最终回复前展示 agent 过程事件。事件 envelope 大致是 `runId + seq + stream + ts + data + sessionKey`，其中 `stream=tool` 支持 `start/update/result`，`stream=assistant` 支持文本 delta/final，另有 `compaction/fallback/lifecycle/thinking` 等过程流。
- **工具过程不污染 assistant 正文**：OpenClaw 将工具调用和工具结果建模成独立临时消息/卡片，UI 再把历史消息、流式文本段、工具卡和当前 stream 合成聊天列表。工具 start 前会 flush 已有 assistant delta，避免“先说一句话，再调用工具”的显示顺序错乱。
- **tool-events capability**：WebSocket client 需要声明支持工具事件，Gateway 才把工具事件发给该连接或 session subscriber，避免把详细过程广播给不需要的客户端。

不适合直接复制的部分：

- OpenClaw 的 adapter/plugin 接口面很大，包含过多可选 adapter 能力。对本项目当前规模来说，会让接入一个新 IM 的成本变高。
- OpenClaw 的 presentation/card 体系较完整，但第一阶段只需要为未来保留数据结构，不应该把交互卡片闭环作为 Feishu v1 的门槛。
- OpenClaw 的插件生态设计偏平台化，本项目现在更需要稳定的内置 Gateway 模块，而不是完整插件市场。
- OpenClaw 的 `thinking` 实时事件后端有，但 Control UI 未完整消费；不应把“实时思考流”当作已验证体验直接复制。
- OpenClaw 的 trace/event 类型很多，实际 UI 只消费子集。第一阶段应收敛为少量稳定的 run activity 事件，而不是一次性引入完整 trace timeline。

对本项目的结论：

- 吸收 OpenClaw 的 `capabilities`、keyed debouncer、presentation fallback、session binding 边界。
- 吸收 OpenClaw 的 run-scoped event envelope、工具卡独立于 assistant message、按客户端能力订阅工具事件。
- 不复制 OpenClaw 的大插件接口面。
- Gateway 只编排共性行为，平台特殊格式由 Channel adapter/renderer 处理。

### 2.2 Hermes Agent 的设计

Hermes Agent 的优势是飞书等平台的实战细节很完整，尤其是边界错误处理和长期运行稳定性。

值得吸收的设计：

- **Feishu post/text 降级**：飞书富文本发送失败时降级为 plain text，保证消息最终可读。
- **reply fallback create**：回复某条消息失败时，例如原消息被撤回，降级为向 chat 直接发送新消息。
- **message_id 去重**：平台事件可能重复投递，需要基于 message id 做 TTL 去重，且最好支持重启恢复。
- **文本 burst batching**：用户连续短消息在短窗口内合并后再触发 Agent，减少碎片化执行。
- **媒体 burst batching**：图片/文件等连续上传可以短窗口内收敛，避免多次启动 Agent。
- **Webhook 安全**：签名校验、限流、异常追踪对 webhook 模式必要。
- **群聊 ACL 与 mention gate**：群聊必须有访问控制和触发门控，否则 agent 很容易被无关群消息打扰。
- **媒体落盘与引用**：图片、文件等内容要转成稳定的本地引用或可访问 URL，交给 Agent 或工具处理。
- **UTF-16 感知截断**：Telegram 等平台用 UTF-16 code units 计长度，通用 chunking 要允许平台声明长度函数。
- **流式与工具进度拆分**：Hermes 的 IM 网关把 token stream、工具进度、typing、busy/session 状态分成独立通道。IM 侧常用“先发送一条进度消息，再编辑同一条消息”的方式展示工具进度，减少刷屏。
- **Web/API 侧更完整，IM 侧更克制**：Hermes 的 Web/API SSE 可以暴露 `tool.started/tool.completed/message.delta/run.completed` 等结构化事件；IM 平台默认只展示工具开始摘要和必要状态，不直接展示完整工具输出。

不适合直接复制的部分：

- Hermes 的 `BasePlatformAdapter` 太大，平台接入、session、delivery、typing、reaction、interrupt、media 等逻辑都混在一个继承层次里。
- Hermes 的很多策略隐藏在基类里，长期会让新增平台必须理解大量隐式行为。
- Hermes 的 delivery/session/platform 边界耦合较重，不适合本项目已经存在的 `InboundPipeline` 和 `SessionBindingStore`。
- Hermes 对 IM 的过程展示依赖 `edit_message` 时体验更好，但很多 IM 不支持可靠编辑；本项目不能把 edit 作为 run activity 的唯一实现方式。
- Hermes 默认不展示完整工具结果是合理取舍。完整 stdout/result 有隐私、长度和噪音风险，本项目也不应默认向所有 channel 透出。

对本项目的结论：

- 吸收 Hermes 的 Feishu 可靠性细节和错误处理策略。
- 吸收 Hermes 的 process visibility 降级策略：Web IM 展示结构化过程，外部 IM 默认展示摘要/typing/可编辑进度，完整工具输出需要显式能力和策略允许。
- 不复制 Hermes 的大基类模式。
- 飞书 adapter 应该薄而明确：做平台协议转换、平台格式渲染、平台发送错误分类。

## 3. 本项目架构判断

### 3.0 Channel 能力面盘点

当前 `ChannelAdapter start/send/stop` 只能表达生命周期和最基本发送，不能表达一个 IM channel 的完整能力。参考 OpenClaw 和 Hermes 后，Channel 能力可以分成 10 类。

| 能力类 | OpenClaw 对应设计 | Hermes 对应设计 | 本项目判断 |
|---|---|---|---|
| 生命周期 | `gateway.startAccount/stopAccount`、account status snapshot、fatal/runtime 状态 | `connect/disconnect/is_connected`、fatal error、platform lock | v1 需要保留 `start/stop`，并补 `status/health` 观察能力 |
| 入站消息 | channel gateway adapter 调用 runtime reply dispatch，mentions/group/security 分 adapter | 各平台解析原生 update 成 `MessageEvent`，含 media、reply、thread、sender | v1 需要 canonical `InboundMessage`，原生解析仍在 adapter |
| 出站文本 | `outbound.sendText/sendFormattedText/sendPayload`、delivery mode | `send(chat_id, content, reply_to, metadata)` | v1 需要 `send(outbound) -> DeliveryResult`，支持 reply/thread metadata |
| 富文本/呈现 | `MessagePresentation`、`renderPresentation`、fallback payload | Feishu `post -> text`，Telegram/Discord markdown 处理 | v1 需要 renderer/fallback 能力，但 presentation 只保留结构，交互卡片延后 |
| 附件/媒体 | `sendMedia`、media access、markdown image extraction、local roots | `send_image/send_document/send_voice/send_video`，入站媒体下载落盘 | v1 需要附件 schema 和文本/图片/文件基本发送；语音/视频延后 |
| 分片/格式化 | `chunker`、`textChunkLimit`、`chunkerMode`、sanitizeText | `truncate_message`、UTF-16 长度、代码块友好分片 | v1 需要 capability 声明长度限制和长度语义，chunking 放 DeliveryPipeline |
| 群聊/安全 | `security`、`groups`、allowlist、mention strip、require mention | group ACL、mention gate、admin/allowlist/blacklist | v1 需要群聊 ACL/mention gate，但策略主要在 Gateway，平台提供 mention 解析 |
| 目录/解析 | `directory`、`resolver`、target resolution、conversation binding | `channel_directory`、platform:chat:thread 显式目标 | v1 不放进 `send_message`，但为未来主动外部 IM 留目录/解析扩展点 |
| 交互与运行态 | commands、actions、approval、reactions、typing、edit、unsend、polls、heartbeat typing | typing、edit_message、reaction lifecycle、approval/card action | v1 只保留可选 `typing`/`edit` 能力声明，不实现交互闭环 |
| 过程可见性 | `agent` run events、`tool-events` capability、工具卡、assistant delta、thinking stream | Web/API SSE 完整；IM 侧进度摘要 + edit message + typing | v1 需要通用 Run Activity 事件模型；Web IM 完整展示，外部 IM 按能力降级 |

从这个盘点看，`start/send/stop` 作为唯一接口确实不够；但也不应该一次性复制 OpenClaw 的 20+ adapter 面，或 Hermes 的大基类。合理方式是把接口分层：

- **必备核心接口**：生命周期、入站回调、出站 delivery、状态快照。
- **声明式 capabilities**：平台支持什么，不通过大量 optional methods 表达。
- **可选能力 provider**：renderer、media、directory、typing/edit/reaction、activity 等按需挂载。
- **Gateway 通用服务**：dedupe、debounce、session binding、delivery fallback、chunking、ACL 编排。

### 3.1 两个平面

本项目需要明确拆成两个平面。

**Channel Plane** 负责当前会话消息：

- 外部 IM 或 Web IM 的消息进入 Gateway。
- Gateway 路由到 Agent。
- Agent 回复发回原始 chat/thread。
- 这是飞书、Web IM、Slack、Telegram 需要统一的部分。

**Dispatch Plane** 负责主动投递：

- Agent 调用 `send_message(text, to)` 主动发给某个业务目标。
- 现在目标是 IM 业务域的 `user_id`、`agent_id`、`conversation_id`。
- 这依赖 IM 服务的用户、Agent、Conversation 目录，不等价于外部平台的 `chat_id`。

第一阶段只统一 Channel Plane。`send_message` 继续保持业务寻址，不扩展为外部 IM transport address。

### 3.2 内置 Web IM 的边界

内置 Web IM 和外部 IM 的“聊天消息能力”应统一：

- `relay.message` 进入 Gateway 后视为 `web_relay` channel 的 inbound message。
- Web IM 回复走同一套 delivery pipeline。
- 去重、防抖、群聊门控、session binding、reply context 与外部 IM 一致。

IM 服务控制面不进入 Channel：

- `node.register`
- `node.heartbeat`
- `node.report`
- `node.delivery_receipt`
- `config.sync`
- `agent.create`
- `agent.capabilities.resolve`
- `node.capabilities.resolve`
- `heartbeat.trigger`

这些仍然属于 Gateway 与 IM 服务之间的控制协议，不属于多 IM Channel 抽象。

### 3.3 Adapter 职责

Adapter 负责平台协议转换：

- 接收平台事件。
- 校验平台事件的基础合法性。
- 将原生 payload 转成 canonical `InboundMessage`。
- 把 canonical outbound 渲染成平台格式。
- 执行平台发送 API。
- 将平台发送错误分类成 typed delivery error。

Adapter 不负责：

- Agent 选择。
- kernel session 创建。
- session binding。
- 跨平台去重策略。
- 跨平台防抖策略。
- IM 业务目标解析。
- Agent 执行队列。

## 4. 目标架构

### 4.1 总体流向

```text
External IM / Web IM
    |
    v
ChannelAdapter
    - native payload -> canonical InboundMessage
    - platform renderer / sender
    |
    v
IngressController
    - schema validation
    - dedupe
    - debounce / burst merge
    - group ACL / mention gate precheck
    |
    v
InboundPipeline
    - agent routing
    - session binding
    - per-session FIFO queue
    - kernel run
    |
    v
DeliveryPipeline
    - chunk
    - render fallback
    - retry
    - reply fallback create
    - receipt
    |
    v
ChannelAdapter.send()

Kernel session events
    |
    v
RunActivityBridge
    - text delta
    - tool start/output/completed
    - run completed/failed
    |
    v
Web IM conversation_events / channel activity delivery
```

### 4.2 Channel contract

`start/send/stop` 需要升级成“小核心 + 能力 provider”的接口。核心仍然克制，但要能表达状态、账号、capabilities 和 delivery result。

```python
class ChannelAdapter(Protocol):
    name: str
    account_id: str
    capabilities: ChannelCapabilities

    def start(self, on_inbound: InboundHandler) -> None: ...
    def send(self, outbound: OutboundMessage) -> DeliveryResult: ...
    def stop(self) -> None: ...
    def status(self) -> ChannelStatus: ...
```

设计要求：

- `start` 只启动平台接入，不做业务路由。
- `send` 返回 delivery result，或者抛 typed delivery error。
- `status` 用于 Gateway 观察 channel 是否 connected/degraded/fatal。
- `capabilities` 是声明式字段，不用一堆 boolean 参数散落在 Gateway。
- 如果某个平台需要 webhook、socket、polling 等不同 transport，作为 adapter 内部配置处理，不改变 Gateway 主接口。

建议的可选 provider：

```python
class ChannelAdapter(Protocol):
    renderer: ChannelRenderer | None
    media: ChannelMediaProvider | None
    directory: ChannelDirectoryProvider | None
    interactions: ChannelInteractionProvider | None
    activity: ChannelActivityProvider | None
```

第一阶段只要求 `renderer`。其他 provider 作为后续扩展，不阻塞 Feishu v1。

能力分层：

| 层级 | 是否 v1 必备 | 内容 |
|---|---:|---|
| Core adapter | 是 | `name/account_id/capabilities/start/send/stop/status` |
| Renderer | 是 | `render_text/render_markdown/render_fallback` 或等价能力 |
| Media provider | 部分 | 入站 image/file attachment；出站文件发送可先只做 Feishu |
| Directory provider | 否 | 外部 chat/user/group 查询、解析、主动寻址 |
| Interaction provider | 否 | typing、edit、delete、reaction、button/card action |
| Activity provider | 部分 | Web IM 支持结构化 run activity；外部 IM 默认摘要降级 |
| Health/doctor | 否 | 配置诊断、权限探测、修复建议 |

### 4.3 Canonical message model

`InboundMessage` 扩展为跨 IM 可表达的 schema：

```python
@dataclass(frozen=True, slots=True)
class InboundMessage:
    channel_name: str
    account_id: str
    message_id: str | None
    text: str
    sender: ChannelActor
    chat: ChannelChat
    thread_id: str | None = None
    reply_to_message_id: str | None = None
    mentions: tuple[ChannelMention, ...] = ()
    attachments: tuple[ChannelAttachment, ...] = ()
    agent_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

兼容当前代码时可先保留旧字段映射：

- `external_user_id` 由 `sender.id` 派生。
- `external_chat_id` 由 `chat.id` 派生。
- `is_group` 由 `chat.type == "group"` 派生。

建议新增的子结构：

```python
@dataclass(frozen=True, slots=True)
class ChannelActor:
    id: str
    type: Literal["user", "agent", "bot", "system", "unknown"]
    display_name: str | None = None

@dataclass(frozen=True, slots=True)
class ChannelChat:
    id: str
    type: Literal["direct", "group"]
    title: str | None = None

@dataclass(frozen=True, slots=True)
class ChannelMention:
    id: str
    type: Literal["user", "agent", "bot", "unknown"]
    text: str | None = None

@dataclass(frozen=True, slots=True)
class ChannelAttachment:
    id: str | None
    kind: Literal["image", "file", "audio", "video", "unknown"]
    url: str | None = None
    local_path: str | None = None
    content_type: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None
```

`OutboundMessage` 扩展为 delivery pipeline 可用的 schema：

```python
@dataclass(frozen=True, slots=True)
class OutboundMessage:
    channel_name: str
    account_id: str
    target_chat_id: str
    text: str
    thread_id: str | None = None
    reply_to_message_id: str | None = None
    format: Literal["plain", "markdown", "presentation"] = "markdown"
    attachments: tuple[ChannelAttachment, ...] = ()
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

第一阶段可以只实现 `plain` 和 `markdown`，保留 `presentation` 字段但不做交互卡片闭环。

### 4.4 Channel capabilities

`ChannelCapabilities` 用于声明平台能力，不用于表达业务策略：

```python
@dataclass(frozen=True, slots=True)
class ChannelCapabilities:
    chat_types: frozenset[Literal["direct", "group"]]
    supports_threads: bool = False
    supports_reply: bool = False
    supports_markdown: bool = False
    supports_rich_text: bool = False
    supports_media: bool = False
    supports_message_edit: bool = False
    supports_typing: bool = False
    activity_visibility: Literal["none", "summary", "structured"] = "none"
    max_text_length: int | None = None
    length_semantics: Literal["python_chars", "utf16_units"] = "python_chars"
```

Gateway 使用 capabilities 决定：

- 是否带 `thread_id` 发送。
- 是否优先尝试 reply。
- 是否需要 chunk。
- 是否允许附件透传。
- 渲染 fallback 顺序。
- run activity 是完整结构化展示、摘要展示，还是完全关闭。

### 4.5 IngressController

新增 `IngressController`，位于 adapter 与 `InboundPipeline` 之间。

职责：

- 校验 canonical `InboundMessage` 必要字段。
- 基于 `channel_name:account_id:message_id` 去重。
- 基于 `channel_name:account_id:chat_id:sender_id:thread_id` 做文本 burst debounce。
- 把合并后的消息交给 `InboundPipeline`。
- 对群聊执行统一 ACL 与 mention gate 的前置判断。

非职责：

- 不解析平台原生 payload。
- 不知道飞书 post、Slack block、Telegram entity 的原生格式。
- 不创建 kernel session。
- 不解析 `send_message` 的业务目标。

去重策略：

- 如果 `message_id` 存在，则使用 `channel_name:account_id:message_id`。
- 如果 `message_id` 不存在，不做强去重，只依赖平台 adapter 自身的 best effort。
- TTL 默认 24 小时。
- 使用 SQLite 持久化，支持 Gateway 重启恢复。

防抖策略：

- 默认只对文本消息启用，窗口 600ms。
- 附件消息默认不合并到文本，除非 adapter 标注为同一 burst。
- 同一 key 串行 flush，不阻塞其他 key。
- 最大 tracked keys 默认 2048，超过后淘汰最旧 key。

### 4.6 Session binding

会话绑定统一使用 chat 维度，而不是 sender 维度。

默认 session key：

```text
{channel_name}:{account_id}:{chat_id}:{agent_id}
```

支持 thread 的平台可以启用 thread-aware key：

```text
{channel_name}:{account_id}:{chat_id}:{thread_id}:{agent_id}
```

原因：

- 飞书、Slack、Telegram 的 direct chat 里，稳定对话容器是 chat/conversation，不是 sender id。
- 群聊和单聊统一按 chat 建模，能减少分支。
- 当前代码实际上已经倾向于 `external_chat_id` 维度，应让 spec 与实现方向一致。

### 4.7 DeliveryPipeline

`OutboundRouter` 升级为 `DeliveryPipeline`，但保持目标是“回复原会话”，不承担主动业务寻址。

职责：

- 从 `ReplyContext` 构造 `OutboundMessage`。
- 根据 `ChannelCapabilities` 做 chunk。
- 调用 channel renderer 选择格式：`markdown -> rich_text/post -> plain`。
- 调用 `adapter.send()`。
- 对可恢复错误执行有限次重试。
- 对 reply 失败执行 create-message fallback。
- 产出 delivery receipt，供 IM 服务或日志观察。

错误分类建议：

```python
class DeliveryErrorKind(Enum):
    TRANSIENT = "transient"
    RATE_LIMITED = "rate_limited"
    FORMAT_REJECTED = "format_rejected"
    REPLY_TARGET_UNAVAILABLE = "reply_target_unavailable"
    AUTH_FAILED = "auth_failed"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
```

fallback 规则：

- `FORMAT_REJECTED`：降级格式后重试。
- `REPLY_TARGET_UNAVAILABLE`：去掉 `reply_to_message_id` 后向 chat 发送。
- `TRANSIENT` / `RATE_LIMITED`：指数退避重试。
- `AUTH_FAILED` / `PERMISSION_DENIED`：不重试，直接失败并上报。

### 4.8 Dispatch Plane

`send_message` 第一阶段不扩展到外部 IM transport address。

保持当前语义：

```text
send_message(text, to=user_id|agent_id|conversation_id)
```

原因：

- 这是 IM 服务业务域的 Actor/Conversation 寻址。
- 外部 IM 的 `chat_id` 不一定能映射到内部 `conversation_id`。
- 把 `feishu:<chat_id>` 混入同一个 `to` 字段会让模型难以区分“业务目标”和“平台地址”。

未来如需主动发外部 IM，另起设计：

- 方案 A：增加显式 channel target schema，如 `channel://feishu/{account_id}/{chat_id}`。
- 方案 B：增加单独工具，如 `send_channel_message(channel, account_id, chat_id, text)`。
- 方案 C：建立外部 chat 与内部 conversation 的绑定目录，然后仍使用 `conversation_id`。

第一阶段不实现。

### 4.9 Run Activity Plane

Web IM 需要展示 assistant 最终回复之前的工具调用过程，类似 Claude Code。这不应该被设计成普通 assistant 文本，也不应该只属于 Web IM 私有逻辑。建议新增轻量的 **Run Activity Plane**，与 Channel Plane 同属消息面，但语义不同：

- Channel Plane 负责用户消息和最终 assistant 回复。
- Run Activity Plane 负责一次 run 内的可观察过程：run 状态、文本 delta、工具开始、工具输出片段、工具结束、失败、用量等。
- Dispatch Plane 仍只负责主动业务投递，不参与 run activity。

本项目已有可复用基础：

- Agent core 已有 hook 事件：`message_update`、`tool_call`、`tool_result`、`tool_execution_update`、`turn_end`。
- `realtime_stream` hook 已能发布 `text_delta`、`tool_start`、`tool_end`、`tool_exec_chunk`、`turn_end`。
- Kernel HTTP 已有 session-scoped SSE：`/v1/sessions/{session_id}/events`。
- Web IM 已有 `conversation_events` 落库和 user websocket replay。

当前缺口：

- personal assistant 默认 hook 未启用 `realtime_stream` 或等价发布器。
- Gateway 只上报粗粒度 `accepted/running/completed/failed`，没有逐条桥接 kernel session events。
- Web IM 前端只有普通消息和 relay synthetic message，没有 run activity store/组件。
- kernel SSE 是内存 history，Web IM `conversation_events` 才是用户可恢复事件流，两者需要桥接。

#### 4.9.1 RunActivityEvent schema

Gateway 内部使用统一的 run activity envelope：

```python
@dataclass(frozen=True, slots=True)
class RunActivityEvent:
    channel_name: str
    account_id: str
    chat_id: str
    agent_id: str
    session_key: str
    kernel_session_id: str
    run_id: str
    seq: int
    event: Literal[
        "agent.run.started",
        "agent.text.delta",
        "agent.tool.started",
        "agent.tool.output_delta",
        "agent.tool.completed",
        "agent.run.completed",
        "agent.run.failed",
    ]
    turn_id: str | None = None
    message_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    status: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)
```

字段原则：

- `run_id + seq` 是同一 run 内排序依据。
- `chat_id/session_key/agent_id` 用于 Gateway 与 Web IM 做路由和权限过滤。
- `message_id` 指向最终 assistant message 或 relay synthetic message；如果最终 message 尚未创建，可先为空，前端按 `run_id` 聚合。
- `tool_call_id` 用于把 `started/output_delta/completed` 聚合成同一工具步骤。
- `data` 可以带 `delta`、`arguments_summary`、`output_preview`、`exit_code`、`duration_ms`、`usage`、`error` 等，但不能默认带完整敏感输出。

#### 4.9.2 Kernel event mapping

Kernel SSE 到 Run Activity 的建议映射：

| Kernel event | Run Activity event | 说明 |
|---|---|---|
| run status running/accepted | `agent.run.started` | 可由 Gateway 在拿到 `run_id` 后立即生成 |
| `text_delta` | `agent.text.delta` | Web IM 可以实时更新 assistant draft；外部 IM 默认不逐 token 发送 |
| `tool_start` | `agent.tool.started` | 带工具名和参数摘要，不默认带完整参数 |
| `tool_exec_chunk` | `agent.tool.output_delta` | 仅在 Web IM 或 debug policy 允许时展示；需要截断和限速 |
| `tool_end` / `tool_exec_exit` | `agent.tool.completed` | 带 status、耗时、错误摘要、输出摘要 |
| `turn_end` / run completed | `agent.run.completed` | 带 usage、stop_reason；最终文本仍由正常 Channel Plane 投递 |
| run failed/cancelled | `agent.run.failed` | 带错误摘要 |

#### 4.9.3 RunActivityBridge

新增 `RunActivityBridge`，由 `InboundPipeline` 在提交 async run 后启动，职责是轮询 kernel session events 并转成 `RunActivityEvent`：

- 使用 `KernelApiClient.stream_session_events(session_id, after_sequence, max_events)`。
- 只桥接当前 `run_id` 的事件，忽略同 session 旧事件。
- 维护 `after_sequence`，避免重复转发。
- 对 `tool_exec_chunk` 做限速、截断和最大累计输出限制。
- run terminal 后 flush 剩余事件，再停止。
- 桥接失败不能影响最终回复投递，只记录 `agent.run.activity_failed` 或日志。

这个 bridge 不应该直接调用 Web 前端；它只把 activity 发给 activity sink。

```text
Kernel SSE -> RunActivityBridge -> ActivitySink
```

第一阶段 ActivitySink 有两个实现：

- `WebImActivitySink`：写入 IM `conversation_events`，由现有 user websocket replay 到 Web。
- `ChannelActivitySink`：根据 channel capabilities 降级到 typing、summary progress message 或 no-op。Feishu v1 可先 no-op 或 summary。

#### 4.9.4 Web IM 展示模型

Web IM 应把 run activity 作为 conversation event，而不是普通聊天消息正文。

建议新增前端模型：

```ts
type AgentRunActivity = {
  runId: string
  agentId: string
  status: "running" | "completed" | "failed"
  textDraft: string
  tools: AgentToolActivity[]
  usage?: TokenUsage
}

type AgentToolActivity = {
  toolCallId: string
  name: string
  status: "running" | "completed" | "failed"
  argumentsSummary?: string
  outputPreview?: string
  outputChunks?: string[]
  startedAt?: string
  completedAt?: string
  durationMs?: number
}
```

UI 规则：

- assistant 最终回复前，在 agent 气泡下方展示“正在处理”的可折叠过程区。
- 工具步骤默认折叠，只显示工具名、状态、耗时和输出摘要。
- stdout/stderr chunk 默认折叠，并做行数/长度上限。
- `agent.text.delta` 可用于实时 assistant draft；最终 `relay.completed/message.delivered` 到达后，以最终消息为准。
- 如果页面重连，前端从 `conversation_events` replay 恢复 run activity 状态。

不建议：

- 不把工具过程拼进 `ChatMessage.content`。
- 不把完整工具结果默认写进最终 assistant message。
- 不默认展示模型 hidden reasoning；如果以后支持，需要单独产品开关和安全策略。

#### 4.9.5 外部 IM 降级策略

不同 IM 的过程展示能力差异很大，所以 activity 必须按 capability 降级：

| `activity_visibility` | 行为 |
|---|---|
| `structured` | Web IM：落 structured events，前端完整展示 |
| `summary` | 外部 IM：发送或编辑一条进度摘要，如“正在调用 web_search...”，不展示完整 output |
| `none` | 只发送 typing 或不展示过程，最终回复照常发送 |

Feishu v1 建议：

- 默认 `activity_visibility=summary` 或 `none`，不要把每个工具 chunk 都发到飞书群。
- 如果启用 summary，优先使用可编辑进度消息；若 edit 不可靠，则最多发送一条“正在处理...”和最终回复，不刷屏。
- 完整工具输出只在 Web IM 展示，或后续通过 debug/trace 面板查看。

#### 4.9.6 安全与隐私

工具过程展示默认遵循最小披露：

- 默认展示工具名、状态、耗时、参数摘要、输出摘要。
- 完整参数和完整输出需要按工具声明 `safe_to_display=true` 或 debug policy 允许。
- 对 shell/stdout 类输出做最大字节数、最大行数、敏感 key redaction。
- 对外部 IM 默认不展示完整工具输出。
- run activity 不进入 LLM 会话历史，避免下一轮模型误读自己的工具日志。

## 5. Feishu Channel v1

### 5.1 Transport

Feishu v1 优先使用长连接事件模式。

理由：

- Node Gateway 是用户机器上的常驻进程，长连接更符合当前进程模型。
- 不要求用户暴露公网 webhook endpoint。
- 可以先避开 webhook 签名、公网部署、反向代理、IP 限流等运维复杂度。

Webhook 模式作为 phase 1.5：

- HMAC 签名验证。
- 请求体大小限制。
- IP/window 限流。
- 异常计数和告警日志。

### 5.2 Inbound 支持

Feishu adapter 必须支持：

- direct chat text。
- group chat text。
- post 富文本解析为 readable text。
- mentions 解析为 `ChannelMention`。
- image/file 转为 `ChannelAttachment`。
- `message_id`、`chat_id`、`sender_id`、`thread_id`、`reply_to_message_id` 提取。
- bot 自身消息过滤，避免回环。

Feishu adapter 可延后支持：

- audio/video 内容理解。
- merge forward 深度展开。
- interactive card action。
- reaction/emoji ack。

### 5.3 Outbound 支持

Feishu delivery fallback 顺序：

```text
markdown/presentation intent
    -> Feishu post/rich text
    -> plain text
```

发送策略：

- 有 `reply_to_message_id` 且能力允许时，优先 reply。
- reply 失败且错误表示原消息不可回复时，降级为 create message。
- 富文本格式被拒绝时，降级为 plain text。
- 长消息按飞书限制 chunk。
- chunk 需要尽量保留代码块和段落可读性。

### 5.4 配置

Feishu channel 配置建议：

```yaml
channels:
  feishu:
    enabled: true
    account_id: default
    app_id: "${FEISHU_APP_ID}"
    app_secret: "${FEISHU_APP_SECRET}"
    transport: websocket
    group_policy:
      mode: mention
      allowed_chat_ids: []
      blocked_chat_ids: []
    debounce_ms: 600
```

配置原则：

- `account_id` 必填，未来支持多个 bot/account。
- secret 从 env 或本地 secret store 读取，不写入普通配置。
- 群聊默认 mention gate，不默认响应所有群消息。
- run activity 默认不向飞书发送完整工具过程；如启用，只发送摘要进度。

## 6. 内置 Web IM 改造

`WebRelayAdapter` 应迁移到新的 canonical schema，但保留现有 payload 兼容。

迁移要求：

- `relay.message` 的 `conversation_id` 映射为 `chat.id`。
- `conversation_type` 映射为 `chat.type`。
- `sender_user_id` 映射为 `sender.id`。
- `sender_display_name` 映射为 `sender.display_name`。
- `participants` 继续通过 metadata 或后续 structured participants 字段传入 session metadata。
- `idempotency_key` 可继续作为 Web IM 特有 dedupe key，同时也填充 canonical `message_id`。

控制面保持不变：

- Gateway 与 IM 服务的 WebSocket 连接继续处理 node registration、heartbeat、config sync、agent create、capability resolve。
- 这些消息不进入 `IngressController`。

### 6.1 Web IM Run Activity

Web IM 是第一阶段唯一要求完整展示 run activity 的 channel。

后端要求：

- Gateway 将 kernel session events 转成 `agent.*` conversation events。
- `conversation_events.payload_json` 保存 run activity payload，支持 reconnect replay。
- `EventService` 只做 enrich，不把 activity event 合成为普通 message。
- `message_id` 可以为空，但必须带 `run_id`、`agent_id`、`conversation_id`、`seq`。

建议事件类型：

- `agent.run.started`
- `agent.text.delta`
- `agent.tool.started`
- `agent.tool.output_delta`
- `agent.tool.completed`
- `agent.run.completed`
- `agent.run.failed`

前端要求：

- user stream 收到 `agent.*` event 后写入独立 `AgentRunActivity` store。
- 聊天列表在对应 agent 回复位置展示过程区。
- 过程区在 run 完成后默认收起，保留可展开查看。
- 最终回复仍使用现有 message/relay completed 路径展示，activity 只补充过程。

## 7. 需求边界

### 7.1 第一阶段做什么

- 扩展 canonical Channel message schema。
- 新增 `ChannelCapabilities`。
- 新增 `IngressController`。
- 新增通用 SQLite-backed dedupe store。
- 新增 keyed debounce 服务。
- 将 `OutboundRouter` 演进为 `DeliveryPipeline`。
- 将 WebRelayAdapter 接入新 ingress/delivery。
- 新增 Run Activity 事件模型和 Gateway bridge。
- Web IM 展示结构化工具过程和文本 draft。
- 新增 Feishu adapter v1。
- 为 Feishu 支持 text、post、mention、image/file attachment、reply fallback、format fallback。
- Feishu 对 run activity 只做 summary/no-op 降级，不做完整工具流。
- 保持现有 `send_message` 业务寻址不变。

### 7.2 第一阶段不做什么

- 不做交互卡片 action 闭环。
- 不做 ACK emoji/reaction。
- 不做语音 ASR/TTS。
- 不做 OCR 或文件内容解析。
- 不做 webhook transport，除非长连接模式被证实不可用。
- 不做平台锁。
- 不做代理自动检测。
- 不把外部 IM chat id 暴露为 `send_message(to=...)` 的一等目标。
- 不默认向外部 IM 展示完整工具参数、stdout/stderr 或工具结果。
- 不展示模型 hidden reasoning；只展示工具/执行过程和可公开文本 delta。
- 不引入 OpenClaw 式大型插件接口。
- 不引入 Hermes 式大基类。

## 8. 验收标准

### A1. Web IM 仍然可用

给定现有 Web IM `relay.message` payload，当消息进入 Gateway 时，应被转换为 canonical `InboundMessage` 并进入统一 `IngressController`。现有 direct/group 聊天、mention gate、session binding、reply delivery 行为保持兼容。

### A2. Feishu direct text 可用

给定飞书用户私聊 bot 发送文本，Gateway 应创建或复用 session，Agent 回复应发回同一飞书 chat。

### A3. Feishu group mention gate 可用

给定飞书群聊消息未 mention 当前 agent，Gateway 不应创建 kernel run。给定消息 mention 当前 agent，Gateway 应执行 Agent，并将回复发送回原群。

### A4. 去重跨重启生效

给定一条 `message_id=abc123` 的飞书消息已经处理，Gateway 重启后再次收到相同 message id，应静默丢弃，不创建重复 run。

### A5. 文本 burst 合并生效

给定同一 sender 在同一 chat/thread 内 600ms 发送多条短文本，Gateway 应合并为一次 Agent 输入。不同 chat 或不同 sender 的消息不能互相合并。

### A6. Feishu post 解析可读

给定飞书 post 富文本消息，adapter 应生成可读 `text`，并保留 mentions 与 attachments 信息。

### A7. Reply fallback 生效

给定 Feishu reply API 返回“原消息不可回复/已撤回”类错误，DeliveryPipeline 应降级为 create message，并产出 fallback receipt。

### A8. Format fallback 生效

给定 Feishu rich text/post 发送被拒绝，DeliveryPipeline 应降级为 plain text。最终用户看到的文本应保留核心内容。

### A9. Chunking 生效

给定 Agent 回复超过目标平台限制，DeliveryPipeline 应按平台 capabilities 分片发送，并避免破坏 Unicode surrogate pair 和常见 code fence。

### A10. send_message 语义不变

给定 Agent 调用 `send_message(text, to=agent_id|user_id|conversation_id)`，仍应走 IM 业务目标解析，不要求也不接受外部 IM chat address。

### A11. Web IM run activity 可恢复展示

给定 Web IM 用户触发一次会调用工具的 Agent run，Web 端应在最终回复前展示 run started、tool started、tool completed、run completed 等过程。页面刷新或 websocket 重连后，应能从 `conversation_events` replay 恢复过程区状态。

### A12. 工具输出默认受限

给定工具产生长 stdout/stderr 或包含潜在敏感字段，Web IM 过程区默认只展示摘要或截断预览，不将完整输出写入最终 assistant message，也不发送到外部 IM。

### A13. 外部 IM 不刷屏

给定 Feishu channel 上发生多次 tool event，Gateway 不应逐 chunk 发送多条飞书消息。若启用过程提示，只允许摘要/可编辑进度消息；否则只发送最终回复。

## 9. 迁移计划

### Phase 0. Spec 与测试骨架

- 更新本 spec。
- 补充针对 canonical schema、dedupe key、session key、delivery fallback 的单元测试计划。
- 明确 `NodeGateway-SPEC` 中 session key 从 sender 维度修正为 chat 维度。

### Phase 1. Channel 基础设施

- 扩展 `channels/base.py`。
- 新增 capabilities、actor/chat/mention/attachment 数据结构。
- 新增 ingress dedupe 和 debounce。
- 保持旧 `InboundMessage` 字段的兼容 shim，降低一次性迁移风险。

### Phase 2. WebRelay 迁移

- 将 `WebRelayAdapter` 转为 canonical schema。
- 让 Web IM 走 `IngressController`。
- 保持现有 IM integration tests 通过。

### Phase 3. DeliveryPipeline

- 将 `OutboundRouter` 演进为 delivery pipeline。
- 支持 delivery result、typed error、format fallback、reply fallback、chunking。
- WebRelay 先用简单 renderer，验证无行为回归。

### Phase 4. Feishu v1

- 实现 Feishu long-connection adapter。
- 支持 inbound text/post/mention/image/file。
- 支持 outbound post/plain fallback。
- 支持 reply fallback create。
- 补充 Feishu adapter 单元测试和必要的 fake client integration tests。

### Phase 5. Run Activity for Web IM

- personal assistant kernel 启用 `realtime_stream` 或等价 session event publisher。
- Gateway 增加 `RunActivityBridge`，把 kernel SSE 转成 `agent.*` conversation events。
- IM user stream 支持 `agent.*` event replay/enrich。
- Web 前端新增 activity store 和过程区组件。
- 增加重连恢复、长输出截断、工具失败状态测试。

### Phase 6. Feishu activity summary

- 基于 Feishu capabilities 决定 `summary` 或 `none`。
- 如启用 summary，优先编辑单条进度消息；不支持可靠 edit 时降级为 typing/no-op。
- 验证不会在群聊中刷屏。

### Phase 7. 文档同步

- 更新 `NodeGateway-SPEC.md` 的 Channel、session key、outbound delivery、send_message 边界。
- 更新 `IM-SPEC.md` 中 Web IM 消息面与控制面的边界描述。
- 增加 Feishu 配置示例。

## 10. 开放问题

以下问题不阻塞第一阶段架构，但实现前需要确认：

- Feishu long-connection SDK 的依赖和运行方式是否符合当前打包/部署策略。
- Feishu 附件是只保留平台 URL/file_key，还是 v1 就下载落盘到本地 workspace/cache。
- 群聊 ACL 配置放在 channel config、agent config，还是二者组合。
- thread-aware session key 是否 Feishu v1 默认开启，还是等接入 Slack/Discord 类强 thread 平台时再开启。
- delivery receipt 是否第一阶段只写日志，还是同步上报 IM 服务。
- Web IM 的工具输出展示策略是默认只摘要，还是提供 per-user debug 开关展示完整输出。
- `agent.text.delta` 是否第一阶段就做实时 assistant draft，还是只先做工具过程卡片。
- Run activity 是否需要长期持久化保留，还是按 conversation event replay 窗口/清理策略裁剪。
