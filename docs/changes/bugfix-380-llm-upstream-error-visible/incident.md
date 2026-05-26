# bugfix-380: LLM 上游错误不再吃成空气泡,要变成用户可读的失败消息

## Relations

- Related: feat-335-streaming-tool-executor(本次问题代码所在的流式 provider 架构由它引入)
- Refs:
  - bugfix-373-thinking-reasoning-content-roundtrip(同一个 _stream_response,补的是 thinking 块语义)
  - bugfix-375-thinking-signature-roundtrip(同上)

## 原始报告

> http://127.0.0.1:8011/chat/c66ee51f9376487e8fdbe4bb7cdf2afe 没有回复也没有合理的用户反馈
>
> 要变成一个用户可读的错误。

证据捕获:`/Users/czj/Repos/LLM_PROXY/logs/session/2026-05-26_11-35-58_763_sess_13d5cabc3b1f7af1/`,downstream SSE 单 chunk:

```
{"error":{"type":"permission_error","message":"You've reached your usage limit for this billing cycle. Your quota will be refreshed in the next cycle. Upgrade to get more: https://www.kimi.com/code/console?from=quota-upgrade"},"type":"error"}
```

IM 侧 `GET /im/v1/conversations/.../messages` 返回的 assistant 消息:`content=""`,`delivery_status="completed"`,无任何错误线索。

## 澄清记录

- Q1: 用户在气泡里"可读"到什么程度?
  A(原话): 这样挺好的
  Agent 解读: 接受推荐 —— 中文短前缀(例如"⚠️ 模型调用失败:")+ provider 原始错误文案(英文也照搬不翻译,保留 URL 等可操作信息);气泡显示 `failed` 状态。

- Q2: 这次修复要覆盖哪些 provider 和入口?
  A(原话): 没问题,都支持。你可能要考虑的是这个报错给用户了,这轮的 user 可能没处理完。那么后面恢复额度之后,llm 的上下文中带不带这个报错信息。这个你可能要看看 CC 的做法
  Agent 解读: 范围确认 —— 所有 provider(anthropic + openai_compat)+ 所有产品入口(IM 个人助手、Coding CLI)。同时引出 Q3 关于失败后 LLM 上下文恢复语义的追问。

- Q3: 失败那一轮的 user message 和"上游错误"消息,如何进入 / 不进入下次 LLM 上下文?
  A(原话): 。ok
  Agent 解读: 接受推荐(照搬 CC 的语义) —— 失败时生成的 assistant 消息打 `is_provider_error=true` 元数据标记,持久化到 session;agent loop 组装下一轮 LLM history 时**过滤掉所有 is_provider_error 标记的 assistant 消息**;失败那一轮的 user message **保留**在 session 历史里(下一轮 LLM 自然一并看到);**不做跨轮自动重试**。参考代码:`~/Repos/opensource-hub/claude-code/src/utils/messages.ts:2088` 的 `isSyntheticApiErrorMessage` 过滤。

- Q4: 这次"上游错误用户可读"的覆盖范围,要包括哪些失败形态?
  A(原话): 对,统一一下 ModelError 的用户呈现
  Agent 解读: 范围 = 任何最终抛 `ModelError` 的路径都要变成用户可读消息。具体含:SSE 中的 `{"type":"error"}` 事件、HTTP 4xx/5xx、传输层错误(超时/断流/DNS/SSL)、SSE 流中途断开不完整、provider 返回非法 JSON / 形状不符。不含 agent 内部 bug、用户取消、context overflow(已有 compact 重试)、模型输出语义不对(那是行为问题不是上游错误)。

- Q5: 用户看到的错误气泡,是"agent 在说话"还是"系统通知"?
  A(原话): 还是挂在 agent 名下会比较好,因为群里 A agent 挂了,B agent 可能没挂,这样好知道是谁
  Agent 解读: 失败气泡**仍以涉事 agent 的身份**展示(头像 + 名字),用 `delivery_status=failed` + 内容里的 `⚠️` 前缀让用户辨识"这是技术故障"。理由是群聊场景下多个 agent 共存,故障归属必须明确到具体 agent —— 不采用 CC 的"system 通知"形态。

- Q6: 用户在错误气泡上要不要"重试"动作?
  A(原话): 好
  Agent 解读: 本次**不做**"重试" / "切模型再试" 之类的按钮 / 操作。用户要恢复就自己再发新消息,按 Q3 的语义,失败那一轮的 user message 还在历史里,LLM 一并看到 —— 等价于自动续上。重试按钮的 UX 边界(retryable 判定 / 配置漂移 / race)留给后续 unit。

## 现象与复现

### 复现步骤(本次踩到的具体路径)

1. 启动 IM(`PYTHONPATH=src python -m uvicorn IM.app:app --port 8011`)+ Gateway(`python -m personal_assistant.main`),Arch agent 配 Kimi K2.6(走 anthropic provider)。
2. 该 provider 当前 billing cycle 配额已耗尽。
3. IM 前端进入与 Arch 的直接对话,发送一句"hi"。

### 期望 vs 实际

- **期望**:用户看到一条 Arch 名下的错误气泡,内容形如 `⚠️ 模型调用失败: You've reached your usage limit ... Upgrade to get more: <url>`,状态条显示"失败"。
- **实际**:用户看到一条 Arch 名下的**空气泡**,状态条显示"completed"(完成),完全无法判断发生了什么。

### 同根类的其它路径(尚未一一复现,但同一 bug)

- HTTP 4xx/5xx:provider 返回 401/429/500 等,`AnthropicClient.generate` 已抛 `ModelError`,但 PA observer 没有 `run_error` 分支,placeholder 气泡保持空。
- SSE 中途断流 / 非法 JSON:`_iter_sse_events` 静默 `continue`,后续无 `message_stop`,流自然结束,等价空消息。
- openai_compat client 的 `_stream_response`:同样无 top-level `{"error":{...}}` 分支,推测同病。

## 影响范围

- **谁受影响**:任何使用 nano-multiagent 的最终用户 —— IM 个人助手用户(包括 Web IM 和未来其它 channel)、Coding CLI 用户。一旦 LLM 上游故障(配额、限流、网络、provider 故障),用户面前就是空气泡 + "completed" 假象。
- **严重度**:中-高。**功能性**层面用户被欺骗(以为 agent 没话说 / 已回复),会反复重试或放弃使用;**可观测性**层面运维 / 用户都无线索定位是平台 / 配额 / 网络问题,debug 必须翻 LLM_PROXY 日志。
- **数据损坏**:无 —— 会话历史里那条空气泡是合法持久化,只是内容为空;不污染存储层。
- **触发频率**:provider 上游每次故障(配额耗尽、5xx、网络抖动)都触发。Kimi K2.6 这类按 billing cycle 限流的 provider 上,接近用户配额上限时常态发生。

## 根因分析(RCA)

### 直接根因

- `src/agent/platform/llm/providers/anthropic/client.py:_stream_response` 的事件分支只覆盖 `content_block_start/delta/stop`、`message_delta`、`message_stop`。Anthropic 流协议里的 `{"type":"error"}` 事件**没有对应分支**,被默认 `continue` 静默吃掉。
- 同文件 `_iter_sse_events` 把"非 JSON 数据行"和"未识别 event_type"一视同仁地静默丢弃,没有任何 log / 抛错。
- `src/agent/platform/llm/providers/openai_compat/client.py:_stream_response` 同结构问题:`_first_choice(event)` 返回 None 时 `continue`,top-level `{"error":{...}}` 帧不会触发任何抛错。
- `src/personal_assistant/main.py` 的 `_build_kernel_event_observer` 列了 `run_status/assistant_message/turn_end/tool_start/tool_end/permission_request/permission_resolved`,但**没有 `run_error` 分支** —— 即便上游真的抛了 ModelError,导致 `RunStatus.FAILED` + `run_error` 事件,IM 那条已创建的 placeholder 气泡也不会被更新。
- IM 后端 / 前端把 `delivery_status="failed"` 渲染成右下角一个小"失败"字样,但**消息正文不会被填充错误内容** —— 空 content + 小失败字,用户基本看不到。

### 为什么这种错能进来(过程根因)

1. **流式架构落地时(feat-335)的错误事件分支被遗漏**:feat-335 spec 的目标是"流式消费 + 实时工具执行 + 取消传播",**没有专门定义"流中途上游主动报错"的契约**。M2-provider-streaming 实现 anthropic / openai_compat client 时按 happy-path 流转事件,error 事件不在测试矩阵里;后续 bugfix-373 / bugfix-375 都是补 thinking 块语义,没人回头补错误事件。
2. **测试矩阵以"happy path + 形状解析"为主**:`tests/unit/test_llm_anthropic_client_streaming.py` 全部测 thinking / tool_use round-trip,没有一条 "SSE 流以 error 事件结束" 用例。bug 进得来。
3. **跨层契约模糊**:provider 层只承诺"yield LLMMessage",没有"任何 yield 失败要抛 ModelError"的硬契约;agent loop 拿到空流时也没有"空流 = 异常"判定。两层都"觉得是对方处理",空消息一路 happy 地写到 IM。
4. **PA observer 的事件类型清单是隐式的**:`_build_kernel_event_observer` 没有任何 "未识别 event 应做什么" 的兜底 —— 错过 `run_error` 没有人发出警告。

### 原始设计意图追溯(必须保住的不变量)

引入这块代码的 unit 是 **feat-335 "Streaming Tool Executor"**(`docs/changes/feat-335-streaming-tool-executor/spec.md`)。它的设计意图是:

- **流式消费 + 实时工具执行**:LLM 流中 emit 一个完整 content block 就立即 yield,tool_use block 完整即可立即执行;
- **content block 粒度**:provider 层 yield 完整 content block(text / tool_use / thinking 等),不暴露 raw delta;
- **取消传播 + 并发安全**:tool 执行受 controller 控制,LLM 流接收与 tool 执行并行。

修复必须保住的不变量:

- 不破坏流式 yield 语义(yield 顺序、yield 单位、controller 取消传播)
- 不破坏 content block 粒度(provider 内部完成 raw → block 转换)
- 不强迫上层关心 SSE 帧细节(provider 层把上游错误归一到 `ModelError`)

修复路径(下方"修复方向")是**在事件循环里补 error 事件 → 抛 ModelError**,完全位于 provider 内部,不动 feat-335 的流式骨架。

## 修复方向

修复的高层方案:**"任何 provider 上游故障 → ModelError → run_error 事件 → 持久化为标记 `is_provider_error=true` 的 assistant 消息 → 用户在 IM/CLI 看到可读错误气泡"** 这条不变式被打通到每一层。

行级实现在后续 milestone 拆分(由 `change-design-author` 接手),这里只列层次:

1. **Provider 层(anthropic + openai_compat client)**:`_stream_response` 增加 SSE error 事件分支(以及其它"流提前结束 / 非法 JSON"路径),归一抛 `ModelError(provider 原文)`。提供单元测试覆盖各类失败形态。
2. **Agent loop / runs registry**:`ModelError` 已经能传到 `_mark_failed_async` 并发 `run_error` 事件,本身不改;但需要把这次的失败也**持久化为一条带 `is_provider_error=true` 元数据的 assistant 消息**(content 为用户可读文案),让 IM 通过常规消息读取路径就能看到。
3. **History normalize**:agent loop 在为下一轮 LLM 调用组装 history 时,**显式过滤掉 `is_provider_error=true` 的 assistant 消息**(对齐 CC 的 `isSyntheticApiErrorMessage` 过滤)。失败那一轮的 user message 不动 —— 自然保留,下一轮 LLM 一并看到。
4. **Personal assistant observer**:`_build_kernel_event_observer` 增加 `run_error` 分支,转化为 `node.streaming_delta` 的 `message_delta`(填 ⚠️ 前缀 + 错误文案) + `message_completed`(状态置 failed),让 placeholder 气泡显示错误内容。
5. **Coding CLI runner**:CLI 端消费 kernel 事件流时也要识别 `run_error`,在终端打出同样的"⚠️ 模型调用失败: ..."一行 + 退出本轮(不静默)。
6. **IM 前端**(仅必要时):若现有渲染 `delivery_status=failed` + 正文 content 已经能正确显示气泡内容,前端无改动;只有当现有规则把空 content 的失败气泡折叠掉时才需调整。
7. **回归矩阵**:reviewer 阶段产出 `regression.md`,逐项覆盖 Q4 列的失败形态(SSE error / HTTP 4xx / HTTP 5xx / 超时 / 断流 / 非法 JSON)× 入口(IM 直聊 / IM 群聊 / Coding CLI),每条记录"用户实际看到什么"。

---

## 用户场景

### 现状(当前 broken 行为快照,作为修复基线)

**直聊场景(用户 → Arch agent,Kimi 配额已耗尽)**:

> 用户在 IM 与 Arch 的直接对话窗口输入"hi"并发送。前端立刻看到一条"运行中"的 placeholder 气泡(Arch 头像)。约 1 秒后,placeholder 气泡的"运行中"状态变为"完成",但气泡**正文空白**。用户以为 agent 还在思考或卡住,等了一会儿再发"在吗?",得到同样的空气泡 + "完成"。用户开始怀疑自己网络问题、客户端 bug,或干脆放弃。**没有任何线索告诉用户**这是上游 LLM 配额耗尽 —— 信息只在 `/Users/czj/Repos/LLM_PROXY/logs/session/<sid>/downstream-res.json` 里,普通用户根本不会去看。

**群聊场景(用户 + Arch + ArchA + 其它 agent,Arch 配额耗尽,ArchA 没耗尽)**:

> 用户在群里 @Arch + @ArchA 各问一个问题。ArchA 正常回了。Arch 那边出来一个空气泡 + "完成"。用户搞不清是 Arch 没收到 @、还是被群规则过滤了、还是 Arch 觉得没什么可说的;更不知道 ArchA 用了不同 provider 所以没事。

**Coding CLI 场景**:

> 用户在终端运行 `coding_cli` 与 agent 对话,问"列出当前目录"。CLI 端流式 SSE 一切如常,turn_end 后 prompt 重新出现,**啥也没打印**。用户疑似 CLI bug,重启重试。

### 期望(修复后用户能看到的)

**直聊场景**:

> 用户输入"hi" → 看到 Arch 头像下出现一条**红/橙底气泡**(或正常底但标 failed),正文是:
>
> ⚠️ 模型调用失败:You've reached your usage limit for this billing cycle. Your quota will be refreshed in the next cycle. Upgrade to get more: https://www.kimi.com/code/console?from=quota-upgrade
>
> 状态条显示"失败"。用户立刻明白:这是配额问题,不是 agent 卡住;链接还能点。配额恢复后用户再发"hi",Arch 正常回 —— 因为 LLM history 里失败的 assistant 错误消息被过滤掉,只有用户的两条 user message,LLM 一并答。

**群聊场景**:

> Arch 那边出来失败气泡(Arch 头像 + 失败状态 + ⚠️ 文案),ArchA 那边正常回。用户一眼看到"是 Arch 这家挂了 —— 大概该 ping admin 切换 model 或等配额恢复",**故障归属明确到具体 agent**(这正是 Q5 要求挂在 agent 名下的核心理由)。

**Coding CLI 场景**:

> 终端打印一行 `⚠️  Model call failed: <provider 原文>` 后回到 prompt;退出码非 0(便于脚本判定)。用户清楚出错原因。

### 回归基线(本次变更不允许改的既有行为)

- 正常对话(LLM 上游 OK)的 happy path 行为、token usage 统计、tool 调用展示、permission 卡片、群聊回复策略、heartbeat —— 完全保持现状。
- agent 内部错误(tool crash / 代码异常 / context overflow 等非上游错误)的现有展示方式 —— 不在本次范围,行为不变。

## 验收标准

### Requirement: SSE error 事件必须变成用户可读错误气泡

#### Scenario: 直聊 + provider 配额耗尽

- **GIVEN** 某 agent 配置的 LLM provider 上游配额已耗尽(下行 SSE 单帧 `{"type":"error","error":{"message":"..."}}`)
- **WHEN** 用户在该 agent 的直接对话里发任意消息
- **THEN** 用户看到该 agent 头像下一条气泡,**正文包含**"模型调用失败"中文前缀 + provider 原始错误文案(含 URL 等可操作信息)
- **AND** 气泡状态条显示"失败"
- **AND** 用户的原始 user message 仍正常出现在对话历史里

#### Scenario: 群聊 + 仅其中一个 agent 上游故障

- **GIVEN** 群里两个 agent(A、B)使用不同 provider,A 的 provider 上游故障,B 正常
- **WHEN** 用户在群里同时 @A 和 @B 提问
- **THEN** A 名下出现"⚠️ 模型调用失败:..."气泡(A 的头像 + failed 状态)
- **AND** B 名下出现正常回复
- **AND** 用户一眼能区分故障归属到 A 而非 B 或群本身

### Requirement: 任何抛 ModelError 的路径都必须用户可读

#### Scenario: HTTP 4xx/5xx

- **GIVEN** provider 返回 HTTP 401 / 429 / 500
- **WHEN** 用户向使用该 provider 的 agent 发消息
- **THEN** 用户看到带"模型调用失败:..."的气泡(failed 状态),正文含 HTTP 状态码或 provider 错误文案

#### Scenario: 传输层错误(超时 / 连接断 / DNS / SSL)

- **GIVEN** provider 主机不可达或响应超时
- **WHEN** 用户向该 agent 发消息
- **THEN** 用户看到带"模型调用失败:..."的气泡(failed 状态),正文含可识别的传输错误描述(超时 / connection error)

#### Scenario: SSE 流中途断开 / 不完整

- **GIVEN** provider 在 stream 中途断开,未发 `message_stop`
- **WHEN** 用户向该 agent 发消息
- **THEN** 用户看到带"模型调用失败:..."的气泡(failed 状态),正文标记"上游流提前结束"或同义文案,**不再**出现"空气泡 + completed"

#### Scenario: provider 返回非法 JSON

- **GIVEN** provider 返回的 SSE 数据行 JSON 解析失败(或形状不符)
- **WHEN** 用户向该 agent 发消息
- **THEN** 用户看到带"模型调用失败:..."的气泡(failed 状态),**不再**静默吞掉

### Requirement: 失败后 LLM 上下文恢复必须干净

#### Scenario: 配额恢复后用户重新发消息

- **GIVEN** 用户上一轮触发了上游错误(已看到失败气泡)、provider 配额已恢复
- **WHEN** 用户在同一会话发新消息
- **THEN** agent 正常回新消息
- **AND** agent 的回答上下文里**不包含**上一轮的错误文案(即下一轮 LLM 看到的 history 不含 `is_provider_error=true` 的 assistant 消息;用户上一轮的 user message 仍保留并一并被处理)

### Requirement: Coding CLI 与 IM 行为对齐

#### Scenario: CLI 端遇到同类上游故障

- **GIVEN** CLI 用户连接的 agent 触发任一上游故障(同上各类)
- **WHEN** CLI 本轮 turn 结束
- **THEN** CLI 在终端打印一行"⚠️ 模型调用失败: ..."(含 provider 原文)
- **AND** 本轮 turn 以失败状态退出(不是静默回到 prompt)

### Requirement: 不回归既有 happy path 行为

#### Scenario: 上游正常时

- **GIVEN** provider 上游一切正常
- **WHEN** 用户向 agent 发消息
- **THEN** agent 正常流式回复(打字机效果)
- **AND** 气泡状态、token usage、tool 调用展示、permission 卡片、群聊回复策略与变更前一致

## 范围与非目标

### 本期范围

- Provider 层(anthropic + openai_compat client)归一上游错误为 `ModelError`,覆盖 §RCA 列出的所有路径。
- agent kernel 把上游错误持久化为带 `is_provider_error=true` 的 assistant 消息,并在下一轮 LLM history 组装时过滤掉。
- Personal assistant observer 处理 `run_error` 事件,把错误文案灌进 placeholder 气泡。
- Coding CLI 在终端打印对应错误行。
- 单元测试覆盖各 provider 失败形态;回归矩阵在 reviewer 阶段产出。

### 非目标(本期不做)

- **不提供"重试"按钮 / "切模型再试"按钮**(Q6):依靠用户重发新消息实现自然恢复。
- **不引入 system 通知样式新 UX**(Q5):失败气泡复用现有 assistant 气泡 + failed 状态。
- **不做错误分类智能化**(例如自动识别"配额"vs"网络"给出不同建议):本期文案 = 中文前缀 + provider 原文透传,不解析。
- **不改 IM 系统消息 / banner / toast**:错误只走对话流。
- **不动 agent 内部错误**(tool crash / context overflow / 代码异常)的展示路径:那是另一类,有自己的失败语义。
- **不做跨轮自动重试 / 异步重试 / 定时重试**(Q3):由用户主动驱动恢复。
- **不做 retry-after 等待 UI**(例如倒计时):用户重发即可。
- **不调整 LLM_PROXY 日志结构**:错误透传文案以 provider 原文为准。
