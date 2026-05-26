# bugfix-380: LLM 上游错误用户可读 — 技术方案

> 对齐: incident.md v1
>
> Unit branch: `unit/bugfix-380` (will be created by orchestrator)

## Changelog

(空,实施期偏差时由 worker 按 `YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md` 格式追加)

## 现状分析

### 涉及范围

- `src/agent/platform/llm/providers/anthropic/client.py` — `_stream_response` 当前事件分支只覆盖 `content_block_*`、`message_delta`、`message_stop`,缺 `error` 事件分支;`_iter_sse_events` 对非 JSON 数据行 / 未识别 event 一律静默 `continue`。
- `src/agent/platform/llm/providers/openai_compat/client.py` — `_stream_response` 只看 `_first_choice(event)`,缺 top-level `{"error": {...}}` 分支。
- `src/agent/core/agent/runtime.py` — `run()` 已有 `except ModelError` 块(line 388)处理 overflow 重试;非 overflow 错误目前直接 raise → `runs/registry.py:_run_worker_async` 捕获 → `_mark_failed_async` 发 `run_error` 事件,**但不会持久化任何 assistant 消息**。
- `src/agent/core/agent/prompting.py:build_chat_messages` — 把 session history 转成 LLMMessage,**当前无任何过滤**,全部 message 都进 LLM。
- `src/agent/core/session/entries.py:message_from_turn_entry` + `runtime.py:_message_to_entry` — JSONL 持久化双向转换;`metadata` 字段已支持 `is_meta` / `is_compact_summary` / `tool_calls` 等显式 round-trip。
- `src/agent/platform/hooks/builtins/realtime_stream.py` — 把 `message_end` 钩子转成 SSE `assistant_message` 事件给客户端。
- `src/personal_assistant/main.py:_build_kernel_event_observer` — 列了 `run_status/assistant_message/turn_end/tool_*/permission_*`,**缺 run_error 分支**,但已有 `assistant_message → node.streaming_delta(message_delta)` 路径,只要错误以 assistant_message 形式发出来,placeholder 气泡就能填上内容。
- `src/coding_cli/commands.py` — TTY 模式已有 `assistant_message → print "> <content>"`,run failed 时抛 `RuntimeError("run_id=... run failed")`(丢失原始错误文案,需要顺手改)。

### 既有约束

- **feat-335 流式骨架不可破**:provider 层 yield 单位 = 完整 content block;controller 取消传播;tool 执行与 LLM 流并行。任何修改不能改变这些。
- **包依赖方向**(AGENTS.md):`coding_cli` / `personal_assistant` → `agent`(HTTP only,禁直接 import);`core` 不依赖 `platform` / `products`。本 unit 改动全部位于 `agent/core` + `agent/platform/llm/providers` + `personal_assistant/main.py` + `coding_cli`,不违反方向。
- **Session 持久化是 JSONL append-only**,任何新元数据字段必须双向 round-trip,且兼容历史 entry(读老文件不能崩)。
- **ModelError 已是统一抛点**:`agent/core/errors.py` 定义,provider 层抛、runtime 层捕。新增任何上游故障路径都收敛到这里。

### 可复用能力

- **`message_end` 钩子 → `assistant_message` SSE**(realtime_stream 内建 hook):**用**。把合成的 error 消息当作一条 role=assistant 的 Message dispatch `message_end`,SSE/observer/CLI 全链路自动认得,无需新事件类型。
- **`Message.metadata` + `_message_to_entry`/`message_from_turn_entry` round-trip 机制**:**用**。新增一个布尔字段 `is_provider_error`,按 `is_meta` 同模式 round-trip。
- **`build_chat_messages` 是唯一 history → LLMMessage 转换点**:**用**。所有 LLM 调用最终走这里,过滤在这一处加,所有 caller 自动受益。
- **PA observer `assistant_message → message_delta` 路径**:**用**。错误以合成 assistant_message 发出来,observer 不用加新分支(只是需要确认是否要标记 failed 状态)。
- **CC `isSyntheticApiErrorMessage` + `normalizeMessagesForAPI` 过滤模式**(`~/Repos/opensource-hub/claude-code/src/utils/messages.ts:2088`):**对标**。本 unit 在 build_chat_messages 里实现等价 filter。

### 相关历史

- **feat-335-streaming-tool-executor**:本次问题代码所在的流式 provider 架构源头。incident.md RCA 已追溯:feat-335 spec 未定义"流中途上游主动报错"契约,M2-provider-streaming 测试矩阵全部 happy path,error 事件分支被遗漏。
- **bugfix-373 / bugfix-375**:同样动 `anthropic/client.py:_stream_response`,补的是 thinking 块 reasoning_content / signature round-trip。本 unit 在同一函数加 `error` 事件分支,需保住这两个 bugfix 引入的语义(thinking / signature 处理路径不动)。
- **feat-379**:近期对 prompt sections / system prompt 改动较多,与本 unit 无重叠。

## 架构总览

### Before(当前 broken 链路)

```
用户发 "hi"
   ↓
IM → Gateway InboundPipeline → Kernel HTTP /v1/sessions/.../messages
   ↓
AgentRuntime.run() → AgentLoop._generate_with_retry() → LLMClient.generate()
   ↓
AnthropicClient._stream_response()
   └── SSE: {"type":"error","error":{...}}
       ↑ 未识别分支,silently continue
       ↑ 无 message_stop,流自然结束
   ↓ yield 了 0 条 LLMMessage
AgentLoop 把 0 条 LLM 消息整成 turn,empty assistant Message 持久化
   ↓
Gateway 收到 assistant_message(content="") + run_status=completed
   ↓
IM 渲染:空气泡 + "completed" 状态
   ↑ 用户:???
```

### After(修复后链路)

```
用户发 "hi"
   ↓
... AnthropicClient._stream_response()
   └── SSE: {"type":"error","error":{...}}
       ↑ 新增分支:raise ModelError("kimi: <provider 原文>", retryable=False)
   ↓
AgentRuntime.run() except ModelError(非 overflow):
   ├── 合成 assistant Message:
   │     content = "⚠️ 模型调用失败:<provider 原文>"
   │     metadata = {"is_provider_error": True, "error_code": ..., "provider": ...}
   ├── 持久化到 session(_message_to_entry round-trip is_provider_error)
   ├── dispatch_observe("message_end", role="assistant", content=..., metadata=...)
   │     └── realtime_stream hook → SSE assistant_message 事件
   ├── (可选) emit 同步 turn_end 事件
   └── 让 ModelError 继续抛 → runs/registry _mark_failed_async → SSE run_error
   ↓
Gateway observer:
   ├── 收到 assistant_message → node.streaming_delta(message_delta) 填满 placeholder 气泡
   └── 收到 run_status=failed → node.delivery_receipt(status=failed) 标记气泡 failed
   ↓
IM 渲染:Arch 头像 + 气泡内容 "⚠️ 模型调用失败:..." + "失败" 状态
   ↑ 用户一眼明白

下一轮用户再发新消息:
   ↓
AgentRuntime.run() → AgentLoop → build_chat_messages(history=...)
   └── 新增 filter:跳过 metadata.is_provider_error=True 的 assistant 消息
   ↓
LLM 看到的 messages:[user(hi), user(新消息)] — 失败那一轮的错误消息被剥离
   ↓ 失败 user message 自然保留,LLM 一并处理
```

### 模块拓扑(改动点标 ★)

```
┌─ src/agent/core/agent/
│    ├── runtime.py ★         (except ModelError 块新增 error 消息合成 + 持久化 + hook dispatch)
│    └── prompting.py ★       (build_chat_messages 新增 is_provider_error filter)
│
├─ src/agent/core/session/
│    └── entries.py ★          (message_from_turn_entry 读 is_provider_error)
│
├─ src/agent/platform/llm/providers/
│    ├── anthropic/client.py ★  (_stream_response 加 error 事件分支 + 收口"流提前结束")
│    └── openai_compat/client.py ★  (_stream_response 加 top-level error 分支 + 收口"流提前结束")
│
├─ src/personal_assistant/
│    └── main.py                (无需加 run_error 分支;若需 assistant_message 时标 failed,微调一处)
│
└─ src/coding_cli/
     └── commands.py            (run failed 抛出时透传原始 error 文案,而非吞掉)
```

## 关键决策

### 决策 1: 错误如何呈现给"上层"(runtime → observer/CLI)

- **选择**:把上游错误**合成为一条 role=assistant 的 Message**,带 `metadata.is_provider_error=True`,正文 = `⚠️ 模型调用失败:<provider 原文>`;persist 到 session;通过现有 `message_end` 钩子链路自动转成 SSE `assistant_message` 事件。然后**继续**让 ModelError 抛上去触发 `run_status=failed`。
- **理由**:
  - 复用既有 hook → SSE → observer → IM message_delta / CLI 打印 链路,零新事件类型,零新观察者分支(IM 前端、CLI、PA observer 都不用改 happy path)。
  - assistant 消息走 session 持久化,后续重启 / 历史回放 / IM `/messages` API 自动可见。
  - `run_status=failed` 仍正常发出,符合既有 telemetry / receipt 语义(`delivery_status=failed` 由此触发)。
- **拒绝的备选**:
  - **方案 B:加新事件类型 `provider_error`,各 observer / CLI / 前端单独处理**。理由:5 个组件都要加 case,UI 又要新增气泡渲染分支,边际收益低,且与 CC `isApiErrorMessage` 设计相反(CC 也是 assistant 消息打标,不是新事件类型)。
  - **方案 C:只在 PA observer 加 `run_error → message_delta` 分支,不动 runtime**。理由:CLI 那边吃不到(CLI 不走 PA observer);assistant 消息不进 session,/messages API 看不到错误;不符合"对齐 CC 语义"。
- **风险**:同时发 assistant_message + run_status=failed 时,observer 必须**先消费 assistant_message(填内容) 再消费 run_status=failed(标失败)**。runtime 已保证 hook dispatch 是同步顺序(message_end → 再抛 ModelError → registry mark_failed),自然有序。

### 决策 2: history 过滤的位置

- **选择**:在 `agent/core/agent/prompting.py:build_chat_messages` 第一步加 filter:`history_messages = tuple(m for m in history_messages if not _is_provider_error(m))`。
- **理由**:
  - 唯一收敛点 —— 所有 LLM 调用(主 loop / compaction summarizer / context fork)都走它,改一处全部覆盖。
  - 不动 session 持久化(错误消息仍在 JSONL 里,IM /messages API 仍能读出来给用户看)。
  - 对标 CC `normalizeMessagesForAPI` 的 `isSyntheticApiErrorMessage` 过滤(同一层位置)。
- **拒绝的备选**:
  - **runtime 不持久化错误消息**:错误消息变成"只发事件不存储"。理由:后续会话回放 / IM 历史浏览看不到错误,与 incident.md 期望(对话流里看得见)冲突。
  - **runtime 在 history 加载时过滤**:每个 caller 都要记得过滤,容易漏。
- **风险**:无 —— 这是纯函数级别过滤,有单测就稳。

### 决策 3: `is_provider_error` 字段如何 round-trip

- **选择**:沿用 `is_meta` / `is_compact_summary` 的同款做法:
  - 写:`_message_to_entry` 检测 `msg.metadata.get("is_provider_error")` → 写到顶层 entry `entry["is_provider_error"] = True`(不展开 metadata,与 `is_meta` 对称)。
  - 读:`message_from_turn_entry` 读 `entry.get("is_provider_error")` → 塞回 `metadata["is_provider_error"]`。
  - 兼容老文件:读不到该字段 → 默认 `False`,不报错。
- **理由**:既有约定,镜像 is_meta 模式,零认知负担;JSONL 兼容性天然(新字段不破老 reader)。
- **拒绝的备选**:把整个 `metadata` dict 一股脑写进 entry。理由:entry 现在是平铺式字段,统一升级到嵌套 metadata 是另一件事(refactor),不该在本 bugfix 里做。
- **风险**:无。

### 决策 4: 错误文案的格式

- **选择**:
  - 中文前缀固定为 `⚠️ 模型调用失败:`(后面带半角冒号 + 空格)
  - 后接 provider 错误原文(不翻译,保留 URL 等可操作信息);若原文为空则用通用兜底 `<provider> 上游错误(详见日志)`
  - 如果能从错误里识别 provider 名字 / model 名字,**不**额外拼进文案(provider 信息已经在 ModelError.details,后续可在 metadata 里带,但用户文案保持极简)。
- **理由**:incident Q1 用户直接确认了这个形态。
- **拒绝**:加 HTTP code、加 stack hint、加重试时间提示 —— 均超本 unit 范围(Q6 已定不做 retry-after UI)。
- **风险**:provider 原文可能极长(provider 偶尔会塞 stack)—— 加 1KB 截断兜底(超出末尾追加 `…(truncated)`)。

### 决策 5: provider 层"哪些场景必须抛 ModelError"

- **选择**:provider client 的 `_stream_response` 完成两类收口:
  1. **显式错误事件**:Anthropic SSE `{"type":"error", "error":{...}}` / OpenAI compat `{"error":{...}}` → 立即 raise `ModelError("<provider>: <error.message>", details={"error_type": ..., "raw": ...}, retryable=False)`。
  2. **流提前结束**:Anthropic 流跑完没收到 `message_stop` 且没收到任何 content_block_stop yield;OpenAI compat 流跑完没收到 `finish_reason` 且 text_buffer 为空且 tool_calls_buffer 为空 → raise `ModelError("<provider>: stream ended without terminal event", retryable=True)`。
- **理由**:覆盖 incident Q4 列的所有失败形态。HTTP 4xx/5xx 已有 `raise_for_status` 路径走起来,无需重复。传输层错误已被外层 `httpx.HTTPError` catch。
- **拒绝**:让 happy 路径继续静默(现状)。理由:incident 列了这是同根问题。
- **风险**:
  - 老的 happy path 单测如果用了"故意流不完整"的 mock,会从"yield 0 条"变成"抛 ModelError"。**对策**:跑全部单测,改修任何依赖旧静默行为的测试(预期数量小)。

### 决策 6: 是否同步动 CLI / PA observer / IM 前端

- **选择**:
  - **PA observer**:**不加新分支**,仅做一处微调 —— 当 `assistant_message` 的 `metadata.is_provider_error=True`(假设事件 payload 带 metadata)时,把后续 `message_completed` 帧的 status 标 failed。也可以完全不动 observer,依靠现有 `run_status=failed → delivery_receipt(failed)` 自然标 failed —— **采纳此简化版**,observer 零改动。
  - **CLI commands.py**:run failed 时把 `terminal_run_status.get("error")` 透传到 RuntimeError 文案里,而非吞成 `"run_id=... run failed"`。改动 ~3 行。
  - **IM 前端**:**不动**。前端已支持 `delivery_status="failed"` 渲染(message-pane.tsx:437),且 assistant_message 的 content 已经走 message_delta 进了气泡,渲染天然正确。
- **理由**:最小改动覆盖范围。决策 1 把错误塞进 assistant_message 已经让现有路径"自动正确",剩下只补 CLI 的文案丢失。
- **风险**:无显著风险。

## 接口与数据流

### 新增/修改的数据结构

```python
# Message.metadata 新增可选键(无需改 dataclass,本就是 Mapping[str, Any])
{
    "is_provider_error": True,           # 必填(新增)
    "provider_error_code": "permission_error",  # 可选,从 ModelError.details 透传
    "provider_name": "anthropic",        # 可选,便于运维过滤
}
```

JSONL entry 新增顶层键(与 `is_meta` 镜像):

```json
{
  "type": "turn",
  "uuid": "...",
  "role": "assistant",
  "content": "⚠️ 模型调用失败:You've reached your usage limit...",
  "is_provider_error": true,
  "metadata": { ... }
}
```

### 关键调用链(修复后)

```
AnthropicClient.generate()
  └── _stream_response(response)
        ├── SSE event_type == "error" → raise ModelError(...)
        └── 流结束 + 未触发任何 yield + 无 message_stop → raise ModelError(...)

AgentRuntime.run()
  ├── try: async for msg in self._execute_loop(...): ...
  └── except ModelError as exc:
        ├── if not _overflow_retried and _is_context_overflow_error(exc):
        │     [既有 overflow 重试路径,不动]
        └── else:
              # ★ 新增分支:合成可视错误消息
              error_msg = _build_provider_error_message(
                  exc, parent_message_id=user_msg.message_id, session_id=...
              )
              history.append(error_msg)
              self._session_manager.writer.enqueue(path, _message_to_entry(error_msg, session_id))
              await self._session_manager.writer.flush_async()
              await self._dispatch_observe("message_end", {
                  "session_id": ..., "turn_id": ..., "message_id": error_msg.message_id,
                  "content": error_msg.content, "role": "assistant",
              }, hook_ctx)
              raise  # 继续走 runs/registry _mark_failed_async

build_chat_messages(history_messages, user_text)
  ├── history_messages = tuple(m for m in history_messages if not _is_provider_error(m))  # ★
  ├── history_messages = _coalesce_assistant_group(history_messages)
  └── ...
```

### 新增工具函数

- `agent/core/agent/runtime.py::_build_provider_error_message(exc: ModelError, ...) -> Message`
  - 把 `ModelError.message` 包成 `⚠️ 模型调用失败:<msg>`,截断 1KB,设 metadata。
- `agent/core/agent/prompting.py::_is_provider_error(msg: Message) -> bool`
  - `bool(msg.metadata.get("is_provider_error"))`,一行。

### 钩子事件

无新事件类型。仅复用既有 `message_end`,但 payload 不传 `metadata`(`realtime_stream.py` 当前也没传)—— assistant_message SSE 事件保持现有 schema,IM 与 CLI 自动正确渲染。

## 风险与回退

### 风险

- **R1: 老单测预期"流不完整 = yield 0 条静默成功"**。fix 后会变 raise ModelError → 这些测试需要修。**对策**:M1 worker 跑完整 `pytest`,逐个修;预期影响 < 5 条测试。
- **R2: provider 错误原文可能极长 / 含敏感信息**(stack、原始 prompt 摘要)。**对策**:决策 4 已定 1KB 截断;若运维发现原文常带敏感字段,后续可加 sanitize(本 unit 不做)。
- **R3: assistant_message + run_status=failed 顺序竞态**。runtime 同步先 dispatch hook 再 raise,registry 在 `_mark_failed_async` 才发 run_error。同进程顺序由 Python 语义保证。**对策**:M1 worker 加端到端测试(mock provider 强制 SSE error → 断言 IM messages API 既能看到错误内容,delivery_status 也是 failed)。
- **R4: PA / CLI 双消费同一 SSE 流时,assistant_message 出来后才到 run_status=failed —— UI 上看到的是"先打字 → 再失败"**。这是期望行为,正是用户视角想看到的。
- **R5: 历史 JSONL 文件没有 `is_provider_error` 字段**。read path 兜底 `entry.get("is_provider_error")` 默认 False,旧文件无影响。

### 降级路径

- 若 provider 抛了非预期 exception(非 ModelError、非 httpx),agent loop 既有的 `except Exception` 路径仍会兜住 → registry mark_failed → run_status=failed → IM 标 failed 状态(气泡可能空,但至少状态对)。这是 worst-case 兜底,本 unit 不引入新失败模式。

### 回滚方案

- 单 PR / 单 commit 路径(M1 完成后合 unit/bugfix-380 → 提主仓 PR)。回滚 = `git revert <merge-sha>`,无 schema 迁移、无数据破坏(`is_provider_error` 字段读端兜底,即使存量 JSONL 有了该字段,回滚后老 build_chat_messages 也只是不过滤而已 —— 老 IM 用户可能看到错误消息进了下一轮 LLM 上下文,但不 crash)。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM (uvicorn) | `kill $(cat .im.pid 2>/dev/null) 2>/dev/null; rm -f .im.pid` | `IM_JWT_SECRET="demo-jwt-secret-for-bugfix380" PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s http://127.0.0.1:$IM_PORT/im/v1/health \| grep -q ok` |
| Gateway | `kill $(cat .gateway.pid 2>/dev/null) 2>/dev/null; rm -f .gateway.pid` | (按 AGENTS.md `Gateway config 隔离` 节生成 `.gateway-config.yaml`)`PYTHONPATH=src python -m personal_assistant.main --config "$WT_ROOT/.gateway-config.yaml" --im-service-url "http://127.0.0.1:$IM_PORT" > "$WT_ROOT/.gateway.log" 2>&1 & echo $! > "$WT_ROOT/.gateway.pid"` | `tail -20 .gateway.log \| grep -q "connected"` |
| Agent kernel API(managed) | `kill $(cat .coding-cli.pid 2>/dev/null) 2>/dev/null; rm -f .coding-cli.pid` | `PYTHONPATH=src python -m uvicorn agent.platform.http_api.app:app --host 127.0.0.1 --port "$API_PORT" > .api.log 2>&1 & echo $! > .api.pid`(Gateway 配里 `agent.api_base_url` 指向 `http://127.0.0.1:$API_PORT`) | `curl -s http://127.0.0.1:$API_PORT/v1/health \| grep -q ok` |

reviewer 走旅程前一律:`for f in .im.pid .gateway.pid .api.pid .coding-cli.pid; do [[ -f $f ]] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"; done`,然后按上表顺序启动(IM → Agent kernel → Gateway)。

**用真实 LLM provider 配额耗尽** 不易构造;reviewer 走旅程使用 mock 路径:把 agent 配的 model 指向一个返回 SSE error 的本地小桩(M1 worker 在 `tests/integration/` 里提供一个 fixture provider,reviewer 可直接复用)。详情见 M1-impl/progress.md。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-380-M1 | impl | — | A | `src/agent/platform/llm/providers/anthropic/client.py`、`src/agent/platform/llm/providers/openai_compat/client.py`、`src/agent/core/agent/runtime.py`(except ModelError 块 + `_build_provider_error_message` 辅助 + `_message_to_entry` 加 is_provider_error 字段)、`src/agent/core/agent/prompting.py`(`build_chat_messages` 加 filter)、`src/agent/core/session/entries.py`(`message_from_turn_entry` 读 is_provider_error)、`src/coding_cli/commands.py`(透传 run error 文案);新增 `tests/unit/test_llm_anthropic_client_streaming.py`、`tests/unit/test_openai_compat_client_streaming.py` 用例;新增 `tests/integration/test_provider_error_user_visible.py` 端到端 | `[reviewer]` 覆盖 incident.md 全部 Scenario:Req-SSE error 事件 / Req-任何 ModelError 路径(HTTP4xx/HTTP5xx/传输/流断/非法 JSON)/ Req-失败后 LLM 上下文恢复 / Req-CLI 行为对齐 / Req-不回归 happy path<br>`[worker]` `pytest -q tests/unit/test_llm_anthropic_client_streaming.py tests/unit/test_openai_compat_client_streaming.py tests/unit/test_agent_runtime*.py tests/unit/test_prompting*.py tests/unit/test_session_entries*.py` 全绿<br>`[worker]` `pytest -q tests/integration/test_provider_error_user_visible.py` 全绿<br>`[worker]` `pytest -q -m "not e2e"` 全绿(确认无 regression)<br>`[worker]` 老的 anthropic/openai_compat 单测中"流不完整 = 静默成功"假设的用例已重写 |

**为何单 milestone**:总改动量 ~400 行(2 个 provider client + runtime 1 分支 + prompting 1 行过滤 + entries 双向 round-trip + CLI 1 处文案 + ~6 个测试文件),不满足 §4.2 任一拆分硬触发条件;layer 间有强逻辑依赖(provider 抛 ModelError ← runtime 合成消息 ← entries round-trip ← prompting filter,串行写一遍即可),拆分反而增加协调成本。
