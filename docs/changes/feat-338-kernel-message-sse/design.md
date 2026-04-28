# feat-338: Kernel Message SSE — 技术方案

> **版本**: v1.0
> **日期**: 2026-04-28
> **对齐**: spec.md v1.0
> **上游**: feat-335 Streaming Tool Executor
> **下游**: feat-336 Run Activity Plane

---

## 1. 架构总览

### 1.1 当前与目标

```
Before (同步 turn):
  POST /v1/sessions/{id}/messages   (Content-Type: application/json)
    → runtime.run() 阻塞至 TurnResult
    → 一次性返回 SendMessageResponse

  实时事件只能通过单独的 GET /v1/sessions/{id}/events 长轮询拉取，
  与 message submission 不在同一连接上，CLI/Gateway 必须双轨消费。
  无主调用方的 run（heartbeat / 后台任务唤醒）没人持流，事件仅留在 hub history。

After (submit + observe 拆分):
  POST /v1/sessions/{id}/messages   (Content-Type: application/json)
    → 同步决策 priority + 注入/启动 run
    → 返回 200 JSON {run_id, anchor_sequence, injected, status}
    → 不持有长连接

  GET /v1/sessions/{id}/stream     (Accept: text/event-stream, 持久)
    → 首次连接从 hub 当前 sequence 开始；带 Last-Event-ID 则续传
    → session-scoped 全量事件，不按 run_id 过滤
    → 不因任何 run 终态关流；客户端断开为止
    → 任意来源的 run（user/background_task/heartbeat）都通过同一通道下发

  旧 GET /v1/sessions/{id}/events 与 POST /messages:async 删除。
```

### 1.2 关键模块拓扑

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AgentLoop.run()  (feat-335 流式)            │
│  yield Message(assistant) / Message(tool) / Message(turn_meta)       │
└──────┬──────────────────────────┬────────────────────────────┬──────┘
       │ message_end hook         │ tool_call/result hook      │ turn_end
       ▼                          ▼                            ▼
┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐
│ realtime_stream     │  │ realtime_stream      │  │ RunsRegistry     │
│   on_message_end    │  │   on_tool_call /     │  │   _set_status    │
│   → assistant_msg   │  │   on_tool_result     │  │   → run_status   │
│                     │  │   → tool_start /     │  │                  │
│                     │  │     tool_end +       │  │                  │
│                     │  │     presentation     │  │                  │
└──────────┬──────────┘  └──────────┬───────────┘  └────────┬─────────┘
           │                        │                       │
           └────────────────────────┴────────────┬──────────┘
                                                 ▼
                                    ┌─────────────────────────┐
                                    │     EventStreamHub      │
                                    │   bounded history +     │
                                    │   fan-out subscribers   │
                                    └────────────┬────────────┘
                                                 │
                ┌────────────────────────────────┴────────────────────────────┐
                ▼                                                             ▼
   ┌────────────────────────────────────┐                       ┌────────────────────────┐
   │ GET /v1/sessions/{id}/stream        │                       │ Gateway consumer       │
   │ session-scoped persistent SSE       │                       │ (uses /stream)         │
   │ fan-out, all runs, all origins      │                       │ Run Activity sink      │
   └──────────────┬─────────────────────┘                       └────────────┬───────────┘
                  │                                                          │
                  ▼                                                          ▼
            coding_cli REPL                                       personal_assistant
            coding_cli --text                                     Run Activity / Web IM


   POST /v1/sessions/{id}/messages   (sync JSON RPC, no SSE)
        └─ submit / inject; returns {run_id, anchor_sequence, injected, status}
```

### 1.3 改动范围

新增模块：

- `agent.core.runs.origin` — `RunOrigin` 枚举。
- `agent.core.tools.presentation` — `ToolPresentation` Protocol + `ToolPresentationEvent` 数据类。
- `agent.platform.tools.presentation` — 内置工具的 presenter 实现 + `default_presenter`。
- `agent.platform.http_api.streaming` — `/stream` SSE generator（session-scoped 持久）+ `Last-Event-ID` 续传适配器。
- `coding_cli.session_stream` — CLI 端常驻 `/stream` reader（后台线程 + 增量 SSE parser + 事件分发）。
- `coding_cli.text_runner` — `--text` NDJSON 输出器（短命，按 run_id 过滤）。

修改模块：

- `agent.platform.http_api.routes.session` — `POST /messages` 改 JSON submit RPC；新增 `GET /stream` 路由；删除旧 `/events` poll 路由。
- `agent.platform.http_api.sse.EventStreamHub` — 增 `current_sequence()` / `stream_session()` / overflow 标记；session-scoped 长连接迭代器。
- `agent.core.runs.registry.RunsRegistry` — 删除 `_emit_turn_events` 完成时重发；`RunRecord` 加 `origin` / `source_task_id`；`submit(...)` 加 `origin` / `source_task_id` kwargs；终态 run_status payload 含 `error`/`usage`/`stop_reason`/`origin`。
- `agent.platform.hooks.builtins.realtime_stream` — `text_delta` 事件改为 `assistant_message`；`tool_call`/`tool_result` 注入 `presentation` 字段；`run_status` 注入 `origin` / `source_task_id`。
- `agent.core.agent.loop` — `message_end` hook 仍触发；`tool_result` hook payload 加 `arguments` / `duration_ms`。
- `agent.platform.tools.builtins.{read,write,edit,bash,web_fetch,task}` — 实现 `format_start`/`format_end`。
- `coding_cli.client.ServerClient` — 删除 `send_message`/`send_message_async`/`stream_session_events`；新增 `submit_message()` + `stream_session()`。
- `coding_cli.commands` / `coding_cli.runtime/*` — REPL 启动后开常驻 reader；turn 实现改为 submit + 在 reader 推送中等 terminal。
- `coding_cli.render.repl_live` — 渲染新事件名；处理 origin 标头（`origin != user` 时打前置标头）。
- `coding_cli.events.event_pipeline` — 调整 dedupe 集合（删 `text_delta`，加 `assistant_message`）；按 `run_id` 分流多 run 渲染。
- `personal_assistant.client.kernel_api_client` — 删除 `send_message_async`；新增 `submit_message()` + `stream_session()`。
- `personal_assistant.gateway.inbound_pipeline` — 切换到 submit + 常驻 stream；新增非 user origin 的 outbound 路由（路径就位但本 feature 不触发）。

删除模块/路径：

- `SendMessageRequest.stream` 字段。
- `SendMessageResponse` 整体删除（以前作为 `/messages` 的 response；新 `/messages` 响应是新的 `SubmitMessageResponse`）。
- `POST /v1/sessions/{id}/messages:async` 端点。
- `GET /v1/sessions/{id}/events` 端点（旧 long-poll 窗口）。
- `coding_cli.commands` 中 `send-message` / `create-session` 子命令（保留底层 `ServerClient.create_session` 内部调用）。

---

## 2. 数据契约

### 2.1 POST `/messages` Response

```json
{
  "run_id": "run_abc",
  "anchor_sequence": 1234,
  "injected": false,
  "status": "queued"
}
```

`anchor_sequence` 在服务端 submit / inject 之前从 `EventStreamHub.current_sequence()` 取，确保客户端可借此在 `/stream` 上从锚点之后接收本次提交触发的所有事件。

### 2.2 `/stream` Wire Format

```
id: 1235
event: run_status
data: {"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"queued","origin":"user","source_task_id":null}

id: 1236
event: run_status
data: {"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"running","origin":"user","source_task_id":null}

id: 1237
event: assistant_message
data: {"event":"assistant_message","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","message_id":"msg_1","content":"我先检查项目结构。","metadata":{}}

id: 1238
event: tool_start
data: {"event":"tool_start","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","call_id":"call_1","name":"read","arguments":{"path":"src/app.py"},"presentation":{"visible":true,"label":"Read","summary":"src/app.py","detail":null}}

id: 1239
event: tool_end
data: {"event":"tool_end","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","call_id":"call_1","name":"read","status":"completed","duration_ms":12,"error":null,"presentation":{"visible":true,"label":"Read","summary":"120 lines","detail":null}}

id: 1240
event: turn_end
data: {"event":"turn_end","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","completed":true,"stop_reason":"stop","usage":{"prompt_tokens":1024,"completion_tokens":256,"total_tokens":1280}}

id: 1241
event: run_status
data: {"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"completed","origin":"user","source_task_id":null,"turn_id":"turn_1","stop_reason":"stop","usage":{"prompt_tokens":1024,"completion_tokens":256,"total_tokens":1280}}
```

`/stream` 不发 `stream_anchor` 帧；anchor 由 POST 同步返回。

### 2.3 NDJSON 输出（CLI `--text`）

每行一个完整 JSON event；保留 SSE `event` 字段。CLI 在 `/stream` 上按目标 `run_id` 过滤后输出，因此每行都属于该 run。

```jsonl
{"event":"submit_response","run_id":"run_abc","anchor_sequence":1234,"injected":false,"status":"queued"}
{"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"queued","origin":"user","source_task_id":null}
{"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"running","origin":"user","source_task_id":null}
{"event":"assistant_message","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","message_id":"msg_1","content":"...","metadata":{}}
{"event":"tool_start","session_id":"sess_x","run_id":"run_abc","turn_id":"turn_1","call_id":"call_1","name":"read","arguments":{"path":"src/app.py"},"presentation":{"visible":true,"label":"Read","summary":"src/app.py","detail":null}}
...
{"event":"run_status","session_id":"sess_x","run_id":"run_abc","status":"completed","origin":"user","source_task_id":null,"turn_id":"turn_1","stop_reason":"stop","usage":{...}}
```

第一行是 CLI 在收到 POST 响应后自己合成的 `submit_response` 帧（让 NDJSON 自包含），不来自 `/stream`。

### 2.3 ToolPresentationEvent 数据结构

```python
# src/agent/core/tools/presentation.py

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ToolPresentationEvent:
    """User-facing tool render payload, attached to tool_start / tool_end SSE."""

    visible: bool = False
    label: str = ""
    summary: str = ""
    detail: Mapping[str, Any] | None = None  # {"diff": ..., "stdout": ..., "truncated": bool}


class ToolPresenter(Protocol):
    """Per-tool user-facing render strategy. Pure function, no IO."""

    def format_start(
        self,
        args: Mapping[str, Any],
    ) -> ToolPresentationEvent: ...

    def format_end(
        self,
        args: Mapping[str, Any],
        result: "ToolResult",
        duration_ms: int,
    ) -> ToolPresentationEvent: ...
```

绑定方式：`Tool` Protocol 增加可选 `presenter: ToolPresenter | None`（默认 `None` → 自动用 `default_presenter`）。

---

## 3. Server 端实现

### 3.1 `EventStreamHub` 扩展

```python
# src/agent/platform/http_api/sse.py

class EventStreamHub:
    def current_sequence(self) -> int:
        """Return the last published sequence atomically; used as anchor for POST."""
        with self._lock:
            return self._next_sequence_num - 1

    def has_sequence(self, sequence_num: int) -> bool:
        """Return True if sequence_num still in history window."""

    def stream_session(
        self,
        *,
        session_id: str,
        after_sequence: int,
        tick_seconds: float = 1.0,
    ) -> Iterator[StreamEvent]:
        """Long-lived session-scoped stream.

        Behavior:
          - Replays history events with sequence > after_sequence (subject to history_limit).
          - Then switches to real-time queue.
          - Does NOT close on terminal run_status — keeps yielding until caller cancels.
          - On subscriber overflow, raises SubscriberOverflowError; caller emits
            stream-level error frame and closes.
        """
```

`stream_session` 在 `_lock` 内取一次 history snapshot + `after_sequence`，先 yield 历史，然后切换到实时 queue。终止条件：
1. caller 关闭（`StreamingResponse` 检测 client disconnect）。
2. subscriber overflow → 抛 `SubscriberOverflowError`，由路由层转换为 `error{subscriber_overflow}` 帧后关闭。

注意：旧设计中按 `run_id` 过滤的 `stream_run` 不再需要。`/stream` 是 session-scoped 的，按 run_id 过滤是客户端职责。

### 3.2 POST `/messages` Route

```python
# src/agent/platform/http_api/routes/session.py

class SubmitMessageResponse(BaseModel):
    run_id: str
    anchor_sequence: int
    injected: bool
    status: Literal["queued", "running", "injected"]


@router.post("/{session_id}/messages", response_model=SubmitMessageResponse)
async def submit_message(
    session_id: str,
    payload: SendMessageRequest,
    runs: RunsRegistry = Depends(get_runs_registry),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
    session_service: SessionService = Depends(get_session_service),
) -> SubmitMessageResponse:
    if session_service.get_session(session_id) is None:
        raise APIError(404, "session_not_found", ...)

    if payload.priority == "now":
        runs.interrupt(session_id)

    if payload.priority == "next" and runs.get_active_run_id(session_id) is not None:
        anchor = event_hub.current_sequence()
        active_run_id = runs.get_active_run_id(session_id)
        injected = runs.inject_pending_message(
            session_id,
            LLMMessage(role="user", content=_text_from_parts(payload.parts)),
        )
        if injected:
            return SubmitMessageResponse(
                run_id=active_run_id,
                anchor_sequence=anchor,
                injected=True,
                status="injected",
            )

    anchor = event_hub.current_sequence()
    record = runs.submit(
        session_id=session_id,
        parts=payload.parts,
        origin=RunOrigin.USER,
        trace_id=get_trace_id(request),
    )
    return SubmitMessageResponse(
        run_id=record.run_id,
        anchor_sequence=anchor,
        injected=False,
        status=record.status.value,
    )
```

POST 是同步、幂等-by-message_id 的 RPC，不持有任何长连接。错误以 HTTP 状态码 + 标准 error JSON 返回。

### 3.3 GET `/stream` Route

```python
# src/agent/platform/http_api/routes/session.py

@router.get("/{session_id}/stream")
async def session_stream(
    session_id: str,
    request: Request,
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
    session_service: SessionService = Depends(get_session_service),
) -> StreamingResponse:
    if session_service.get_session(session_id) is None:
        raise APIError(404, "session_not_found", ...)

    last_event_id = _parse_last_event_id(request.headers)
    if last_event_id is not None and not event_hub.has_sequence(last_event_id):
        async def _err_only():
            yield encode_stream_error(
                session_id=session_id,
                run_id=None,
                code="resume_window_exceeded",
                message="event history pruned beyond Last-Event-ID",
            )
        return StreamingResponse(_err_only(), media_type="text/event-stream")

    after = last_event_id if last_event_id is not None else event_hub.current_sequence()
    return StreamingResponse(
        _session_stream_generator(session_id=session_id, after_sequence=after, event_hub=event_hub),
        media_type="text/event-stream",
    )


async def _session_stream_generator(*, session_id, after_sequence, event_hub):
    try:
        for event in event_hub.stream_session(session_id=session_id, after_sequence=after_sequence):
            yield encode_sse_event(event)
    except SubscriberOverflowError:
        yield encode_stream_error(session_id=session_id, run_id=None,
                                  code="subscriber_overflow",
                                  message="server backlog overflow; reconnect with Last-Event-ID")
    except asyncio.CancelledError:
        # Client disconnect; do NOT cancel any run.
        return
```

`stream_session` 是 sync iterator（基于 `queue.get(timeout=...)`），FastAPI 端用 `iterate_in_threadpool` 包装，避免在事件循环上阻塞。

### 3.4 Backpressure 与 overflow

`EventStreamHub._Subscriber.queue` 现有 `queue.Full` 处理是 silent drop。在 `/stream` 场景下这是产品 bug。

新增：subscriber 收到 `queue.Full` 时打标 `overflow_marked = True`；下次 `stream_session` 检查到该标记，抛 `SubscriberOverflowError`。路由层捕获后 yield `error{subscriber_overflow, retryable=true}` 后关闭。client 通过 `Last-Event-ID` 重连，由 history replay 补齐（若仍越界 → `resume_window_exceeded`，再降级为重新拉历史快照）。

### 3.5 删除 `_emit_turn_events`

`RunsRegistry._emit_turn_events` 删除（registry.py:474-517）。`_publish_run_status_event` 在终态时已经携带 `usage` / `error` / `stop_reason`，本 feature 增加 `origin` / `source_task_id` 字段。terminal `run_status` 是该 run 在 `/stream` 上的最后一帧，但**不**触发 `/stream` 关流。

### 3.6 RunOrigin 与 RunRecord

```python
# src/agent/core/runs/origin.py
from enum import StrEnum

class RunOrigin(StrEnum):
    USER = "user"
    BACKGROUND_TASK = "background_task"
    HEARTBEAT = "heartbeat"
```

```python
# src/agent/core/runs/registry.py
@dataclass
class RunRecord:
    ...
    origin: RunOrigin = RunOrigin.USER
    source_task_id: str | None = None


class RunsRegistry:
    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        trace_id: str | None = None,
        ...
    ) -> RunRecord:
        ...
```

`_publish_run_status_event` 把 `origin` / `source_task_id` 写入事件 payload。本 feature 中只有 `RunOrigin.USER` 被实际写入；`BACKGROUND_TASK` / `HEARTBEAT` 是 schema 占位，由后续 feature 复用同一参数。

### 3.7 抢占语义实现

`runs.interrupt(session_id)` 当前调用 `controller.abort()`，loop 检测后以 `stop_reason="aborted"` 退出（loop.py:171-183）。但目前最终 `_mark_completed` 把 status 标为 `COMPLETED`——这与 spec "抢占→cancelled" 不符。

修改 `RunsRegistry._run_worker_async`：捕获 controller `is_aborted` 退出路径，调用新方法 `_mark_aborted_async(run_id, source="priority_now")`，set status=CANCELLED，error={code: "run_aborted_by_priority_now", retryable: false}，stop_reason="aborted"。被抢占的旧 run 在 `/stream` 上以这帧 terminal `run_status` 收尾；客户端按 `run_id` 过滤即可识别（`/stream` 不断开，下一个 run 的事件继续推送）。

### 3.8 Stream-level error 编码

```python
def encode_stream_error(*, session_id, run_id, code, message) -> bytes:
    payload = {
        "event": "error",
        "session_id": session_id,
        "run_id": run_id,
        "code": code,
        "message": message,
        "retryable": code in {"resume_window_exceeded": False, "subscriber_overflow": True}.get(code, False),
    }
    # Stream-level errors are NOT published into hub (they pertain to one stream).
    return f"event: error\ndata: {json.dumps(payload)}\n\n".encode()
```

---

## 4. Hook 改造

### 4.1 `realtime_stream` 重写

```python
# src/agent/platform/hooks/builtins/realtime_stream.py

async def on_message_end(event, ctx):
    # Replaces on_message_update text_delta emission.
    msg_role = event.get("role")
    if msg_role != "assistant":
        return
    payload = {
        "event": "assistant_message",
        "run_id": _extract_run_id(event),
        "turn_id": event.get("turn_id"),
        "message_id": event.get("message_id"),
        "content": event.get("content") or "",
        "metadata": {},
    }
    ctx.publish_session_event(event="assistant_message", data=payload)


async def on_tool_call(event, ctx):
    presenter = _resolve_presenter(event.get("name"))
    presentation = presenter.format_start(event.get("arguments") or {}) if presenter else _default_start(event)
    payload = {
        "event": "tool_start",
        "run_id": _extract_run_id(event),
        "turn_id": event.get("turn_id"),
        "call_id": event.get("call_id"),
        "name": event.get("name"),
        "arguments": dict(event.get("arguments") or {}),
        "presentation": _presentation_dict(presentation),
    }
    ctx.publish_session_event(event="tool_start", data=payload)


async def on_tool_result(event, ctx):
    presenter = _resolve_presenter(event.get("name"))
    duration_ms = event.get("duration_ms") or 0
    presentation = (
        presenter.format_end(event.get("arguments") or {}, _build_tool_result(event), duration_ms)
        if presenter else _default_end(event)
    )
    payload = {
        "event": "tool_end",
        "run_id": _extract_run_id(event),
        "turn_id": event.get("turn_id"),
        "call_id": event.get("call_id"),
        "name": event.get("name"),
        "status": "failed" if event.get("error") else "completed",
        "duration_ms": duration_ms,
        "error": event.get("error"),
        "presentation": _presentation_dict(presentation),
    }
    ctx.publish_session_event(event="tool_end", data=payload)
```

删除：

- `on_message_update` → `text_delta`（被 `on_message_end` → `assistant_message` 取代）。
- `on_tool_execution_update` 的 phase=started/running/chunk → SSE，仅保留 `phase=exit`（用于 `tool_end` 增量）——实际上完全可删，`tool_end` 已经覆盖最终态。chunk 事件用于 future Web IM 实时输出（如 bash 流式 stdout），feat-338 不消费，但保留 hook 不发 SSE。

> **决策**：`tool_exec_*` 系列事件**不**进入 feat-338 的 6 种 SSE 事件白名单。message stream generator 按 `event_name in ALLOWED_SET` 过滤；其他事件留给 `/v1/sessions/{id}/events` 调试通道。

### 4.2 hook 触发参数依赖

`on_tool_call` 现在需要 `arguments`。loop.py 已经在 `_dispatch_tool_call_hook` 里传了。`on_tool_result` 需要 `arguments`，目前没有——loop 的 `_dispatch_tool_result_hook` 只传 `output`/`error`。需扩展 hook payload：

```python
# loop.py: _dispatch_tool_result_hook
{
    "session_id": ...,
    "turn_id": ...,
    "call_id": result.call_id,
    "name": result.name,
    "arguments": _lookup_arguments_for_call_id(result.call_id),  # NEW
    "output": result.output,
    "error": result.error,
    "duration_ms": ...,  # NEW (executor must record)
}
```

`StreamingToolExecutor` 在调度工具时已有 args；执行时记录 start/end 时间，emit result 时附 `duration_ms`。需要在 `agent.core.tools.executor.streaming_executor` 增 `_started_at_ns` 字段。

---

## 5. ToolPresenter 实现

### 5.1 注册机制

```python
# src/agent/platform/tools/presentation.py

from collections import defaultdict
from agent.core.tools.presentation import ToolPresenter, ToolPresentationEvent


_PRESENTERS: dict[str, ToolPresenter] = {}


def register_presenter(tool_name: str, presenter: ToolPresenter) -> None:
    _PRESENTERS[tool_name] = presenter


def resolve_presenter(tool_name: str) -> ToolPresenter:
    return _PRESENTERS.get(tool_name) or _DEFAULT


class _DefaultPresenter:
    """Fallback for unknown / MCP tools: visible=true, label=name, summary='...'."""
    def format_start(self, args):
        return ToolPresentationEvent(visible=True, label=tool_name, summary=_truncate(json.dumps(args), 80))
    def format_end(self, args, result, duration_ms):
        if result.error:
            return ToolPresentationEvent(visible=True, label=tool_name, summary=f"failed: {_truncate(result.error,80)}", detail={"error": {"message": result.error}})
        summary = _truncate(_stringify(result.output), 80)
        return ToolPresentationEvent(visible=True, label=tool_name, summary=summary)
```

### 5.2 内置工具 presenter

| Tool | format_start.summary | format_end.summary | format_end.detail |
|---|---|---|---|
| `read` | `<displayPath>` | 文本：`120 lines` / `lines 40-80`；图片：`image (1024x768)`；PDF：`8 pages`；notebook：`6 cells` | 文本：`null`（避免重复）；图片：`{type:"image", width, height}`；PDF：`{type:"pdf", pages}` |
| `write` | `<displayPath>` | `created` / `overwritten (N bytes)` | `{path, content, bytes, truncated}`，content 整体放入；超过 hard cap 时截断尾部并 `truncated=true` |
| `edit` | `<displayPath>` | `updated (line N)` 或 `failed: <reason>` | `{path, diff, firstChangedLine, truncated}` |
| `bash` | `<command>`（截断 80 字符） | `exit=N elapsed=Xms` | `{command, exit_code, duration_ms, stdout, stderr, truncated}`，stdout/stderr 整体放入；超 hard cap 尾部截断 |
| `web_fetch` | `<url>`（截断 100 字符） | `status=200 (<title>)` | `{url, final_url, status, title, body_excerpt}` |
| `task` | `<description>`（截断 80） | `status=<status>` | `{description, status, summary, artifacts}` |

### 5.3 hard cap

```python
# src/agent/platform/tools/presentation.py

PRESENTATION_DETAIL_HARD_CAP_BYTES = 256 * 1024  # 256 KiB per tool_end

def _enforce_cap(detail: dict[str, Any]) -> dict[str, Any]:
    # Walk known string fields (stdout/stderr/diff/content), tail-truncate,
    # set detail["truncated"] = True.
    ...
```

256 KiB 是经验值——大到能容纳大多数 build log，小到能在浏览器一帧内渲染。可在配置（`agent_settings.yaml`）覆盖。

---

## 6. 客户端实现

### 6.1 `coding_cli.client.ServerClient`

```python
# src/coding_cli/client.py

from collections.abc import AsyncIterator

class ServerClient:
    # 删除：send_message(), send_message_async(), stream_session_events()
    # 保留：create_session, list_sessions, get_session_messages, ...

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /messages. Returns {run_id, anchor_sequence, injected, status}."""
        body = {
            "parts": [{"type": "text", "text": text}],
            "priority": priority,
        }
        if message_id:
            body["message_id"] = message_id
        return self._request("POST", f"/v1/sessions/{session_id}/messages", json=body)

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """GET /stream as persistent SSE iterator.

        Yields decoded events {"event": str, "_id": int, **payload}.
        Closes only when HTTP connection closes (server-side error or
        client-side cancel of the iterator).
        """
        headers = self._build_headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=None) as client:
            async with client.stream("GET", f"/v1/sessions/{session_id}/stream", headers=headers) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(f"stream_session failed: {resp.status_code}")
                parser = _IncrementalSseParser()
                async for chunk in resp.aiter_bytes():
                    for event in parser.feed(chunk):
                        yield event
```

`_IncrementalSseParser`：行级状态机，按 `\n\n` 分帧；提取 `id:` / `event:` / `data:`；支持多行 data 拼接。返回 `{"event": str, "_id": int | None, **json.loads(data)}`。

### 6.2 REPL 常驻 reader + turn 等待

REPL 启动时在后台线程跑 `stream_session`，把事件分发到一个进程内 broker；主线程的 turn 实现订阅 broker，按 `run_id` 等 terminal。

```python
# src/coding_cli/session_stream.py (NEW)

class SessionStreamReader:
    """Background thread that owns a persistent stream_session() iterator
    and dispatches events to per-run_id awaiters + the live renderer."""

    def start(self, *, session_id: str) -> None: ...
    def stop(self) -> None: ...

    def subscribe_run(self, run_id: str) -> RunSubscription:
        """Return a future-like handle that yields events for run_id and
        signals when terminal run_status is seen."""

    def attach_renderer(self, renderer: ReplLiveRenderer) -> None:
        """All events are also forwarded to the renderer (with origin
        header injection for non-user origins)."""
```

```python
# src/coding_cli/runtime/streaming_runner.py (NEW)

async def run_one_turn(
    *,
    client: ServerClient,
    reader: SessionStreamReader,
    session_id: str,
    text: str,
) -> TurnSummary:
    submit = client.submit_message(session_id=session_id, text=text)
    sub = reader.subscribe_run(submit["run_id"])
    async for event in sub:
        if _is_terminal_run_status(event):
            return TurnSummary.from_run_status(event)
    raise RuntimeError("stream closed without terminal frame")
```

reader 在 `Last-Event-ID` 续传失败 (`resume_window_exceeded`) 时记录最后已知 sequence、丢弃 marker 重新 GET（从当前 tail 开始）；丢失窗口期间未及时渲染的事件由用户态判断是否需要从消息历史 API 补拉。

### 6.3 `--text` NDJSON 输出器

```python
# src/coding_cli/text_runner.py (NEW)

async def run_text(client: ServerClient, *, session_id: str, text: str, out: TextIO) -> int:
    submit = client.submit_message(session_id=session_id, text=text)
    out.write(json.dumps({"event": "submit_response", **submit}, ensure_ascii=False) + "\n")
    out.flush()

    target_run_id = submit["run_id"]
    async for event in client.stream_session(session_id=session_id):
        if event.get("run_id") != target_run_id:
            continue
        out.write(json.dumps(event, ensure_ascii=False) + "\n")
        out.flush()
        if _is_terminal_run_status(event):
            return 0 if event["status"] == "completed" else 1
        if event["event"] == "error":
            return 2
    return 1
```

`coding_cli.main`：

```python
# src/coding_cli/main.py

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.text:
        return asyncio.run(run_text(...))
    return start_repl(...)
```

CLI 删除 subcommand `send-message` / `create-session`；保留底层 `ServerClient.create_session` 在 REPL 启动时静默调用。

### 6.4 `personal_assistant.client.kernel_api_client`

形态对齐 6.1：`submit_message()` + `stream_session()`，删除 `send_message_async` / 旧 `stream_session_events`。

Gateway inbound pipeline（`personal_assistant.gateway.inbound_pipeline`）：

- 每个 channel-绑定的 session 在 binding 期间维持一条常驻 `stream_session` 任务；事件交给 per-session 分发器。
- 入站消息走 session_key 串行队列：拿锁 → `submit_message` → 在分发器上等该 `run_id` 的 terminal run_status，期间 assistant_message 走 outbound → 释放锁。
- 分发器对 `origin != user` 的 run（本 feature 阶段不会出现，由后续 feature 触发）：仍按 session_key 串行队列调度 outbound，路径与正常回复一致；ActivitySink 上报附带 `origin` / `source_task_id`。
- 分发器要做的事：维持 `Last-Event-ID`、断线重连、按 run_id 路由到等待者、对未注册 run_id 的事件直接走"非用户消息"出站路径。

---

## 7. 时序

### 7.1 新启动 run，纯文本回答

```
Client (CLI)                         Server                       Hub      Loop
   │ GET /stream (持久, 已建立)       │ ◄────────────── (已订阅) ──┤        │
   │                                  │                            │        │
   │ POST /messages                   │                            │        │
   ├─────────────────────────────────►│                            │        │
   │                                  │ anchor = hub.current_seq() │        │
   │                                  │ run = runs.submit(origin=USER) ─────┤
   │                                  │   ├──► publish run_status{queued,origin=user} ──►│
   │                                  │   └──► async _run_worker ─────────► │
   │ ◄── 200 {run_id, anchor, ...} ───│                            │        │
   │                                  │                            │ ◄──────┤ run_status{running}
   │ ◄ id:N run_status{running}  ─ via /stream ─                   │        │
   │                                  │                            │ ◄──────┤ message_end → assistant_message
   │ ◄ id:N+1 assistant_message  ─ via /stream ─                   │        │
   │                                  │                            │ ◄──────┤ turn_end
   │ ◄ id:N+2 turn_end           ─ via /stream ─                   │        │
   │                                  │                            │ ◄──────┤ run_status{completed,usage,origin=user}
   │ ◄ id:N+3 run_status{compl}  ─ via /stream ─                   │        │
   │ (REPL 主线程见到该 run_id 终态，归还提示符；/stream 不断开)    │        │
```

### 7.2 priority=next 注入到 active run

```
Client                       Server                  RunsRegistry        Hub
   │ POST /messages priority=next ─►│                            │            │
   │                                │ anchor = hub.current_seq() │            │
   │                                │ active = runs.get_active_run_id()       │
   │                                │ runs.inject_pending_message(...) ──────►│ controller.enqueue
   │ ◄── 200 {run_id=active, anchor, injected=true, status=injected} ────────│
   │                                │                            │            │
   │  (active run 在下一轮 round drain pending → 继续生成)         │            │
   │ ◄ id:M assistant_message    ─ via 同一 /stream ─              │            │
   │ ◄ id:M+1 run_status{compl}  ─ via 同一 /stream ─              │            │
```

### 7.3 priority=now 抢占

```
Two clients sharing /stream of same session
                                   Server                       RunsRegistry
                                     │                            │
   Client B: POST /messages priority=now ─►                       │
                                     │ runs.interrupt(session) ──►│ controller.abort()
                                     │ anchor = hub.current_seq() │
                                     │ runs.submit(new_run, origin=USER) ──►│
                                     │                            │
   Client A on /stream ◄── id:K run_status{cancelled,error:run_aborted_by_priority_now}
                       (Client A 按 run_id 过滤识别为旧 run 终态)
                                     │ 200 to B {new run_id, ...} │
   Both clients on /stream ◄── id:K+1 run_status{queued, origin=user, run_id=new}
                                  ◄── ... new run events ...      │
```

### 7.4 断线重连

```
Client                               Server                       Hub
   │ GET /stream                     │                            │
   ├────────────────────────────────►│ after = current_sequence()  │
   │ ◄ id:100 .. id:150 events ──────│                            │
   │ (network drop)                   │ CancelledError; runs unaffected
   │                                  │                            │
   │ GET /stream Last-Event-ID:150 ─►│ has_sequence(150)? YES      │
   │                                  │ stream_session(after=150)   │
   │ ◄ id:151 .. (history replay) ───│                            │
   │ ◄ id:N (live) ──────────────────│                            │
```

如果断开太久导致 hub history 已裁剪到 `>150`：服务端发 `error{resume_window_exceeded}` 并关闭，客户端丢弃 `Last-Event-ID` 重连。

### 7.5 非 user origin 的 run（本 feature 不触发，由后续 feature 落地）

```
(后续 feature) 内部模块                Server                       Hub
   │ runs.submit(..., origin=BACKGROUND_TASK, source_task_id=...) ─►        │
   │                                  │                            │ ◄ run_status{queued, origin=background_task, source_task_id=...}
                                                                   │ ...
All clients on /stream ◄── id:N run_status{running, origin=background_task,...}
                       (REPL 渲染 origin 标头；Gateway 通过串行队列调度 outbound)
                       ◄── ... assistant/tool events ...           │
                       ◄── id:N+M run_status{completed,...}        │
```

本 feature 仅落地：渲染逻辑、Gateway 路由、schema、`runs.submit(origin=...)` 入参。实际触发由 feat-337 等后续 feature 完成，无需回改本 feature 任何代码。

---

## 8. 测试策略

### 8.1 Unit

| 测试 | 文件 | 验证 |
|---|---|---|
| SSE encoder 输出合法帧 | `tests/unit/platform/http_api/test_sse_encode.py` | `id:` / `event:` / `data:` 三行 + 空行；JSON 紧凑无空格 |
| 增量 SSE parser | `tests/unit/coding_cli/test_sse_parser.py` | 跨 chunk 边界、多行 data、忽略 comment |
| `EventStreamHub.stream_run` 终止 | `tests/unit/platform/http_api/test_event_hub.py` | 终态 run_status 后 generator 退出 |
| Last-Event-ID 续传 | `tests/unit/platform/http_api/test_resume.py` | history 充足→续传；history 越界→error 帧 |
| ToolPresenter (per builtin) | `tests/unit/platform/tools/test_presentation.py` | 每个内置工具 start/end 输出符合表格 |
| presenter hard cap | `tests/unit/platform/tools/test_presentation_cap.py` | bash stdout > 256KiB 尾截断、truncated=true |
| RunsRegistry abort_by_priority_now | `tests/unit/agent/runs/test_abort_priority.py` | `interrupt + submit` 流转 → cancelled+stop_reason=aborted+error.code |

### 8.2 Integration

| 测试 | 验证 |
|---|---|
| `tests/integration/api/test_message_stream.py::test_pure_text_run` | 纯文本 run 完整事件序列 |
| `..::test_run_with_tool` | text/tool/text/run_status 顺序 |
| `..::test_run_failed` | terminal `run_status{failed,error}` |
| `..::test_priority_next_injection` | inject 不创建新 run；anchor 不回放 |
| `..::test_priority_now_preemption` | 旧 stream 收 cancelled+error.code，新 stream 拿到新 run_id |
| `..::test_client_disconnect_does_not_cancel_run` | client 断开后 run 继续；后续 `RunsRegistry.get` 看到 completed |
| `..::test_resume_with_last_event_id` | 重连续传 |
| `..::test_resume_window_exceeded` | 超出 history → error 帧 |

### 8.3 Contract

`tests/contract/test_message_endpoint_contract.py`：

- `media_type == "text/event-stream"`
- request 不接受 `stream` 字段（pydantic 拒绝）
- 6 种事件 schema 各一个 fixture，验证 round-trip
- 终态帧穷举三态

### 8.4 CLI

| 测试 | 验证 |
|---|---|
| `tests/cli/test_repl_streaming.py` | 交互式 REPL 每个 turn 走 `stream_message` |
| `tests/cli/test_text_runner.py` | `--text` 输出 NDJSON、最后一行终态 run_status |
| `tests/cli/test_help_no_send_message.py` | help 文案不含 `send-message` / `create-session` 指引 |

### 8.5 Gateway

`tests/integration/personal_assistant/test_gateway_kernel_stream.py`：从 user message 入站到 ActivitySink 的全链路用 `stream_message`，验证 Run Activity 映射表 6 种关键事件。

---

## 9. 性能与资源

### 9.1 单 stream 吞吐

每帧 SSE 约 200–800 字节；典型 turn ≈ 20–60 帧；峰值 < 50 KiB/turn。`StreamingResponse` 使用 chunk encoding，无聚合延迟。

### 9.2 Hub history footprint

`history_limit = 2000`，每帧 `StreamEvent` 约 1 KiB Python 对象，总 ~2 MiB。可以容纳 ~30–100 个并发 run 的近期历史。如果实际并发更高，考虑：

- per-session bucket（按 session 分桶各自 limit）
- 增大 limit 到 8000

不在 feat-338 范围内。

### 9.3 异步 vs 线程

`RunsRegistry` 已有专用 async loop 线程（registry.py:91）。SSE generator 在 FastAPI 主 loop 跑；用 `iterate_in_threadpool` 把 sync `queue.get(timeout=...)` 包到线程池里，避免阻塞主 loop。

---

## 10. 安全与隔离

- `presentation.detail` 大字段在 server 端经过 hard cap；外部 IM Gateway 进一步剥离。
- SSE response 不含模型 hidden reasoning（loop 不 yield 该类 block，hook 不 publish）。
- bearer auth 复用 `require_bearer_auth`，与现有 endpoint 一致。
- session 边界：`run_id` 过滤防止跨 session 泄漏；hub `_Subscriber.session_id` 已实现。

---

## 11. 待决策点

| # | 问题 | 建议默认 |
|---|---|---|
| D1 | `/messages:async` 与旧 `/events` 端点 | **同时删除**。新架构下 POST 是同步 RPC，`/stream` 是唯一观察通道。 |
| D2 | `tool_exec_*` 增量事件 | publish 到 hub 但不在 6 种白名单内；`/stream` generator 按 `event_name in ALLOWED_SET` 过滤，只下发 6 种产品事件。 |
| D3 | `presentation.detail` hard cap 阈值 | 256 KiB 默认；通过 `AgentSettings.presentation_detail_hard_cap_bytes` 覆盖。 |
| D4 | POST 是否要求 idempotency-key | 暂不要求。POST 重试由调用方自行避免；future 引入 `message_id` 已可作幂等键。 |
| D5 | `--text` 失败退出码 | run failed → 1；stream 级 error → 2；client 自身错误 → 3。 |
| D6 | `/stream` 多客户端订阅是否限流 | 单 session 默认无上限；hub overflow 即失败重连。如未来出现单 session 高扇出（>50 客户端）再加 per-session subscriber cap。 |

---

## 12. 里程碑切分

| Milestone | 目标 | 关键产出 | 退出标准 |
|---|---|---|---|
| **M1. Hub Extensions** | EventStreamHub `current_sequence` / `has_sequence` / `stream_session` / overflow → `SubscriberOverflowError` | `sse.py` | `tests/unit/platform/http_api/test_event_hub.py` 全绿 |
| **M2. RunOrigin & Registry** | `RunOrigin` 枚举；`RunRecord.origin` / `source_task_id`；`submit(...)` kwargs；`run_status` payload 加 `origin`；priority=now → cancelled | `core/runs/origin.py`, `runs/registry.py` | `test_run_origin.py`, `test_abort_priority.py` 全绿 |
| **M3. Presentation Layer** | `ToolPresenter` Protocol + 内置 6 个 presenter + hard cap | `core/tools/presentation.py`, `platform/tools/presentation.py`, builtins | `test_presentation.py` 全绿 |
| **M4. Realtime Hook Rewrite** | `realtime_stream` 改 `assistant_message` + `tool_start`/`tool_end` 携带 presentation；`run_status` 注入 `origin`；删除 `_emit_turn_events` | `realtime_stream.py`, loop hook payload 增 `arguments`/`duration_ms` | 现有 SSE 测试改造通过 |
| **M5. Endpoints** | POST `/messages` → JSON RPC 返回 `SubmitMessageResponse`；新增 GET `/stream`；删除旧 `/events` 与 `/messages:async` | `routes/session.py`, `streaming.py` | `tests/integration/api/test_submit_and_stream.py` / `test_priority_*` / `test_resume.py` 全绿 |
| **M6. Client Streaming** | `submit_message()` + `stream_session()` + `_IncrementalSseParser` | `coding_cli/client.py`, `personal_assistant/client/kernel_api_client.py` | client unit 测试全绿；contract 测试通过 |
| **M7. CLI Wiring** | REPL 常驻 `SessionStreamReader` + `run_one_turn`；`--text` NDJSON；origin 标头渲染（fixture 测试覆盖） | `coding_cli/session_stream.py`, `coding_cli/runtime/streaming_runner.py`, `coding_cli/text_runner.py`, render 模块 | `tests/cli/*` 全绿，验收 A1–A3、A9 通过 |
| **M8. Gateway Cutover** | Gateway 每 session 常驻 `stream_session`；inbound 走 submit + 等 terminal；非 user origin 路由路径就位（fixture 校验） | `inbound_pipeline.py` | `tests/integration/personal_assistant/test_gateway_kernel_stream.py` 全绿，A10 通过 |
| **M9. Cleanup** | 删除 `SendMessageRequest.stream`、旧 `SendMessageResponse`、旧测试夹具 | 多文件 | 全仓 `pytest -m "not e2e"` 全绿；contract 测试白名单收紧 |

依赖关系：

```
M1 ─┐
M2 ─┼─► M5 ─► M6 ─► M7 ─┐
M3 ─┤              └─► M8 ─► M9
M4 ─┘
```

M1–M4 可并行。M5 依赖 M1+M2+M4。M6 依赖 M5。M7/M8 依赖 M6。M9 最后。

---

## 13. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| client 同步 send_message 调用残留 | 中 | 调用方 5xx | grep `send_message(` 清扫；contract 测试断言 endpoint 不返回 JSON |
| hub history overflow 静默丢事件 | 中 | client 看到事件断裂 | §3.3 overflow flag → 显式 error 帧 + 重连 |
| priority=now 旧 stream 不收到 cancelled | 低 | 旧 client 永久挂起 | `_run_worker_async` `finally` 中确保 status 落地，generator 检测 active run 消失即查 registry 终态 |
| presenter exception 阻断 SSE | 低 | 本帧丢失 | hook runner 已有 isolation；presenter 抛错 → fallback to `_DefaultPresenter` |
| 注入消息后 anchor 漏事件 | 低 | client 看到不完整序列 | anchor 在 `inject_pending_message` 调用**前**取，取后到注入完成的瞬间 hub 不会有该 run 的事件（pending 没触发 hook） |

回滚：feat-338 是 atomic cutover（Phase 1 + Phase 2 同 commit）。一旦发布发现严重 bug，revert 该 commit 即可恢复同步 endpoint。

---

## 14. 与其他 feature 的衔接

### 14.1 feat-336（Run Activity）

feat-336 依赖本设计的 6 种事件作为输入。Gateway 端映射表见 spec §9。feat-338 不实现 Run Activity bridge / 落库 / 前端，但保证：

- 事件 schema 稳定（在 spec §6 固定）。
- `presentation` 字段足够 Web IM 渲染（label/summary/detail）。
- `run_id` / `turn_id` / `message_id` / `call_id` 保证唯一可关联。

feat-336 在此基础上接 `RunActivityBridge`，无需再改 kernel 事件源。

### 14.2 feat-337（CC 风格后台任务）

feat-337 的"后台任务唤醒父会话"完全复用本设计的 `/stream` + `RunOrigin` 机制。feat-338 已在本 feature 范围内落地：

- `RunsRegistry.submit(...)` 接受 `origin: RunOrigin`、`source_task_id: str | None`。
- `run_status` 事件携带 `origin` / `source_task_id`，REPL 渲染 origin 标头、Gateway 走 session_key 串行队列调度 outbound。
- `/stream` 是 session-scoped 持久通道，承载所有 origin 的 run。

feat-337 落地时只需：

- 后台任务完成后调 `runs.submit(parts=[<task-notification>], origin=RunOrigin.BACKGROUND_TASK, source_task_id=task_id)`。
- 不新增任何 HTTP 端点。
- 不改任何客户端代码。

本 feature 与 feat-337 的实现顺序：feat-338 先落地（含 origin schema、客户端处理逻辑、fixture 测试覆盖非 user origin 渲染/路由路径），feat-337 后落地（仅在 wake-up 调用点写入 `BACKGROUND_TASK`）。两者无循环依赖。
