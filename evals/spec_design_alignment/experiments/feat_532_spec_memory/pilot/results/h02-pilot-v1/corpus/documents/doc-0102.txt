# feat-338: Kernel Message SSE — 需求规格

> **变更单元**: feat-338  
> **状态**: 需求已澄清，待设计  
> **对齐日期**: 2026-04-28  
> **上游背景**: feat-335 Streaming Tool Executor  
> **下游依赖**: feat-336 Generic Channel Architecture / Run Activity Plane

---

## 1. 背景

feat-335 已把 Agent 内核改成流式执行模型：

- Provider `generate()` 按 content block 流式 yield。
- `AgentLoop.run()` 边接收 assistant block 边 yield `Message`。
- `StreamingToolExecutor` 在 tool_use block 完整后立即调度工具。
- `realtime_stream` hook 将 `message_update`、`tool_call`、`tool_result`、`turn_end` 转成 session SSE 事件。

当前问题在 HTTP 产品边界：

- `POST /v1/sessions/{session_id}/messages` 等待 `runtime.run()` 完整结束后才返回。
- coding_cli 的主入口是 `PYTHONPATH=src python3 -m coding_cli.main --model <model>`，用户进入交互式 CLI 后提交任务；当前体验是长任务中间无稳定实时反馈。
- personal_assistant / IM Gateway 需要实时拿到 assistant 完整消息、工具生命周期和工具执行过程，才能支撑 feat-336 的 Web IM Run Activity。
- 现有的 `GET /v1/sessions/{id}/events` 是 long-poll 窗口，绑在某个 `run_id` 上拉到 `turn_end` 就停。无主调用方的 run（heartbeat、后台任务唤醒等）没有客户端持流，事件只在 hub history 里漂着。

结论：

1. message 提交回到 RPC 形态：`POST /messages` 返回小 JSON，包含 `run_id` 和 anchor。
2. 观察通道升级：`/v1/sessions/{id}/stream` 是唯一观察入口，session-scoped 持久 SSE，承载该 session 全部 run（用户提交的、heartbeat、后台任务唤醒）。
3. `run_status` 携带 `origin` 字段，让客户端区分 run 来源并正确渲染。
4. 不做后向兼容；项目处于开发态。

---

## 2. 目标

建立"提交 + 观察"分离的两端架构：

- 提交：`POST /v1/sessions/{id}/messages` 返回 `{run_id, anchor_sequence, injected, status}` JSON。
- 观察：`GET /v1/sessions/{id}/stream` 持久 SSE，session-scoped，承载该 session 全部 run 的事件，按 `run_id` / `origin` 由客户端过滤分类。

目标：

- coding_cli 交互式入口在 session 生命周期内常驻 `/stream`，每个 turn 走 POST submit。
- coding_cli 非交互入口（顶层 `--text`）打开 `/stream`，POST submit，按目标 `run_id` 过滤事件，输出 NDJSON 直到该 run terminal。
- personal_assistant / IM Gateway 对每个 channel-绑定 session 维持一条常驻 `/stream`，inbound message 走 POST submit。
- 同一 session 多客户端订阅天然 fan-out，事件流共享。
- 非用户提交的 run（feat-337 后台任务唤醒、heartbeat 等）在 `/stream` 上和用户提交的 run 走同一条通道；`run_status.origin` 字段标识来源，客户端按 origin 渲染或路由。
- 旧同步 message endpoint、旧 long-poll `/events` 端点从产品契约中删除。
- CLI 删除面向用户的 `send-message` 和 `create-session` 子命令路径。

---

## 3. CLI 产品形态

### 3.1 交互式入口

用户启动 CLI：

```bash
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

启动后进入交互式 CLI。用户输入任务后，CLI 必须实时显示：

- 完整 assistant 文本消息
- 用户可见工具的开始
- 用户可见工具的完成或失败
- run 完成或失败

### 3.2 非交互入口

非交互模式使用顶层 `--text`，不使用子命令：

```bash
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215 --text "检查项目并修复问题"
```

该模式也必须流式输出。输出格式为 NDJSON：一行一个 JSON event，最后一行必须是终态 `run_status` 或 stream 级 `error`。

### 3.3 删除的 CLI 产品路径

以下子命令不再属于 coding_cli 产品契约：

- `create-session`
- `send-message`

实现阶段必须从帮助文案、用户文档、验收样例中删除这些子命令。测试中仍需要覆盖迁移后无子命令入口。

---

## 4. 核心决策

| # | 决策 | 选择 |
|---|---|---|
| 1 | 提交与观察 | 拆分。`POST /messages` 是 JSON RPC submit；`GET /stream` 是 session-scoped 持久 SSE 观察通道 |
| 2 | 观察通道生命周期 | 持久。客户端断开为止，不因 terminal `run_status` 关流 |
| 3 | 观察通道范围 | session-scoped 全量事件，承载该 session 全部 run（用户、heartbeat、background task 唤醒）；按 `run_id` / `origin` 由客户端过滤 |
| 4 | 旧同步 endpoint / 旧 `/events` poll | 删除，不做后向兼容 |
| 5 | CLI 交互模式 | 默认入口，无子命令 |
| 6 | CLI 非交互模式 | 顶层 `--text` |
| 7 | CLI stream 开关 | 不提供，永远流式呈现 |
| 8 | 非交互输出格式 | NDJSON（仅目标 run_id 的事件） |
| 9 | SSE 事件粒度 | semantic events，共 6 种：`run_status` / `assistant_message` / `tool_start` / `tool_end` / `turn_end` / `error` |
| 10 | Provider raw SSE | 不透传 |
| 11 | 最终结果 | run 终态由 `run_status{completed\|failed\|cancelled}` 承载；最后一条 assistant 内容就是该 run 流里最后一帧 `assistant_message` |
| 12 | Run Activity | kernel 提供稳定事件源，Gateway 做映射 |
| 13 | Run 来源标识 | `run_status.origin ∈ {user, background_task, heartbeat}`；扩展枚举不破坏 schema |
| 14 | sequence 编号 | hub 全局单调，非 run 内 |
| 15 | 多 client 订阅同 session | fan-out，非独占；history replay 共享 |
| 16 | priority=next 注入 | POST 注入到 active run，返回该 run_id 与 `injected=true`；客户端在 `/stream` 上等同一 run_id 的事件 |
| 17 | priority=now 抢占旧 run | 旧 run 在 `/stream` 上收到 `run_status{cancelled, error:{code=run_aborted_by_priority_now,...}}`；客户端按 `run_id` 过滤即可识别 |
| 18 | 断线重连 | `/stream` 通过 `Last-Event-ID` header 续传；POST 是幂等无状态的 RPC，不参与重连 |

---

## 5. 范围

### 5.1 In Scope

- `POST /v1/sessions/{session_id}/messages` 改为 JSON submit 端点：返回 `{run_id, anchor_sequence, injected, status}`。
- 新增 `GET /v1/sessions/{session_id}/stream`：session-scoped 持久 SSE，承载该 session 全部事件。
- 删除旧同步 message endpoint 的 SSE 路径与同步 JSON response 产品契约（不存在中间形态）。
- 删除 request 中的 `stream` 字段。
- 删除旧的 long-poll `GET /v1/sessions/{id}/events` 端点。
- request schema 保留本次提交所需字段：
  - `message_id`
  - `parts`
  - `model`
  - `priority`
- POST 内部创建或注入 run，返回 `run_id`。
- `RunsRegistry.submit(...)` 接受 `origin: RunOrigin` 参数（默认 `USER`）；`RunRecord` 持久化该字段；`run_status` 事件携带 `origin`。
- 客户端按 `origin` 决定渲染 / 路由策略。本 feature 阶段 origin 唯一可能值是 `USER`，但渲染 / 路由代码必须能处理任意 origin。
- 工具展示由 tool-specific presenter 决定，不把所有工具一刀切展示给用户。
- SSE 事件包含（共 6 种）：
  - `run_status`（含 `origin`、`source_task_id?`）
  - `assistant_message`
  - `tool_start`
  - `tool_end`
  - `turn_end`
  - `error`
- 每个 run 在 `/stream` 上必须以 terminal `run_status` 帧结束：
  - 成功：`run_status{status=completed}`
  - 失败：`run_status{status=failed, error:{...}}`
  - 取消：`run_status{status=cancelled, error:{...}}`
  - stream 自身异常（如 history 已被裁掉）：`error`，run 状态不变；`/stream` 在该错误后关闭，客户端重新发起 GET。
- `/stream` 持久至客户端断开；不因任何 run 终态关闭。
- coding_cli 交互式入口在 session 生命周期内常驻 `/stream`，每个 turn POST submit。
- coding_cli 顶层 `--text` 打开 `/stream`，POST submit，按 run_id 过滤事件输出 NDJSON 直到该 run terminal。
- `ServerClient` 提供：`stream_session()`（持久 SSE iterator）+ `submit_message()`（POST RPC）。
- personal_assistant kernel client 同形态。
- 测试覆盖 API、CLI、Gateway consumption 所需契约。

### 5.2 Out of Scope

- Web IM 前端过程区组件。
- feat-336 的 `RunActivityBridge` 落库、replay、前端展示。
- Feishu/外部 IM 的过程摘要展示。
- 模型 hidden reasoning 展示。
- provider raw SSE 透传。
- `send_message` 工具的外部 IM transport address。

---

## 6. HTTP API

### 6.1 POST `/v1/sessions/{session_id}/messages` —— Submit RPC

```http
POST /v1/sessions/{session_id}/messages
Content-Type: application/json
Accept: application/json
```

Request：

```json
{
  "message_id": "optional-client-id",
  "parts": [{"type": "text", "text": "..."}],
  "model": null,
  "priority": "next"
}
```

Response（200 application/json）：

```json
{
  "run_id": "run_abc",
  "anchor_sequence": 12345,
  "injected": false,
  "status": "queued"
}
```

字段：

- `run_id`：本次提交绑定的 run。`priority=next` 注入活跃 run 时，等于该活跃 run 的 id；其他情况是新 run。
- `anchor_sequence`：服务端在执行 submit / inject 这一动作**之前**取的 hub 全局 sequence。客户端可以借此在 `/stream` 上从该锚点之后过滤事件，确保不会错过本次提交触发的任何事件。
- `injected`：true 表示本次提交注入到了已有活跃 run；false 表示新建 run（含 `priority=now` 抢占后新建）。
- `status`：本次 submit 完成后 run 的瞬时状态（`queued` / `running` / `injected`）；客户端不依赖此值判断 run 终态，终态以 `/stream` 上的 terminal `run_status` 为准。

语义：

- `priority="next"`：session 有 active run 时注入 pending message 到 active run，复用其 `run_id`，`injected=true`；没有 active run 时启动新 run，`injected=false`。
- `priority="now"`：中断 active run（旧 run 在 `/stream` 上收到 `run_status{cancelled, error:{code=run_aborted_by_priority_now,...}}`），随后启动新 run，返回新 `run_id`。
- POST 不返回 SSE，不持有长连接。事件全部经由 `/stream` 投递。
- 错误以 HTTP 状态码 + 标准 JSON error body 返回（404 session not found / 400 payload invalid / 5xx 内部错误）。

### 6.2 GET `/v1/sessions/{session_id}/stream` —— 持久观察通道

```http
GET /v1/sessions/{session_id}/stream
Accept: text/event-stream
Last-Event-ID: <sequence_num>           (可选，断线续传)
```

Response：`text/event-stream`，持久连接。

语义：

- session-scoped：推送该 session 上所有 run 的事件，不按 run_id 过滤；客户端按 `run_id` / `origin` 自行分类。
- 持久：服务端不主动关流。任何 run 的 terminal `run_status` 不会触发关流；只有客户端断开、session 被销毁、或 stream 级 `error` 才结束。
- 多 client fan-out：同 session 多个客户端同时订阅，收到一致事件序列（按 hub 全局 sequence）。
- 首次连接（无 `Last-Event-ID`）：从连接建立瞬间的 hub 当前 sequence 开始推送实时事件，不回放历史。
- 续传（带 `Last-Event-ID`）：从该 sequence 之后的所有事件按序推送（含 hub history 中尚未裁剪部分 + 实时增量）。

### 6.3 SSE Envelope

Wire format：

```text
id: <sequence_num>
event: <event_name>
data: <json>
```

`id` = `EventStreamHub` 全局单调 sequence（非 run 内、非 session 内），与 `/v1/events` 共用同一序号空间。

每个 `data` 必须包含：

```json
{
  "event": "assistant_message",
  "session_id": "sess_...",
  "run_id": "run_..."
}
```

有 `turn_id` 后必须携带 `turn_id`。

#### 6.3.1 断线重连

- `/stream` 接受 HTTP header `Last-Event-ID: <sequence_num>`。重连时按它作为 `after_sequence` 续传。
- replay 上限 = `EventStreamHub.history_limit`（默认 2000）。超出窗口时：服务端发 `error{code=resume_window_exceeded, retryable=false}` 后关闭。客户端应丢弃 `Last-Event-ID` 重新 GET `/stream`，从当前实时 tail 开始接收；丢失窗口期间的事件无法补齐，应同时通过其他 API（如 `/v1/sessions/{id}/messages` 的历史接口）拉取该期间的会话消息状态。
- 客户端断开不取消任何 run；run 继续运行，事件继续进 hub history。

### 6.4 Event Types

#### Run 内事件序列规范

`/stream` 是 session-scoped 持久通道，下面描述的是某一 `run_id` 在该流上从 queued 到 terminal 的事件子序列（按 hub 全局 sequence 顺序，但中间可能交织其他 run 的事件，客户端按 `run_id` 过滤）。

成功：

```
run_status{run_id=R, status=queued, origin=...}
run_status{run_id=R, status=running}
[ assistant_message | tool_start | tool_end | turn_end ] × N   (run_id=R)
run_status{run_id=R, status=completed, stop_reason, usage}     ← R 的最后一帧
```

失败：`... → run_status{run_id=R, status=failed, stop_reason, usage, error:{...}}`。
取消：`... → run_status{run_id=R, status=cancelled, stop_reason, error:{...}}`。
stream 级异常（仅 history 越界等，不改变任何 run 状态）：`error{code, message, retryable}`，随后 `/stream` 关闭，客户端重新 GET。

客户端识别"自己提交的某 turn 已结束"：在 `/stream` 上按 `run_id` 过滤，看到任意终态 `run_status` 即视为该 turn 结束，但不应据此断流。
"最终回答内容"就是该 run 流里最后一帧 `assistant_message.content`，kernel 不另发"final"事件。

#### `run_status`

控制面事件，描述 run 生命周期。承载 run 级聚合元信息（`stop_reason`、`usage`、终态 `error`、`origin`）。不承载用户正文。

```json
{
  "event": "run_status",
  "session_id": "sess_...",
  "run_id": "run_...",
  "status": "queued|running|completed|failed|cancelled",
  "origin": "user|background_task|heartbeat",
  "source_task_id": null,
  "turn_id": "turn_...",
  "stop_reason": "stop",
  "usage": {
    "prompt_tokens": 1,
    "completion_tokens": 2,
    "total_tokens": 3
  },
  "error": {
    "code": "run_execution_failed",
    "message": "...",
    "retryable": false
  }
}
```

字段约束：

- `origin` 必填，描述 run 触发源。本 feature 阶段唯一可能值是 `user`；`background_task` / `heartbeat` 由后续 feature 写入（本 feature 仅保证 schema 与渲染逻辑就位）。新增枚举值不破坏 schema。
- `source_task_id` 仅在 `origin=background_task` 时出现，承载触发本 run 的后台任务 id。其他 origin 为 `null`。
- `usage` 仅在 `status ∈ {completed, failed}` 时出现（取决于是否拿到了模型 usage）。
- `error` 仅在 `status ∈ {failed, cancelled}` 时出现，code 取值见 §6.4 `error` 章节的 code 表。
- `queued` / `running` 不含 `usage` / `error`。
- terminal `run_status`（completed / failed / cancelled）是该 `run_id` 在 `/stream` 上的最后一帧；`/stream` 本身**不**因此关闭，下一个 run 的事件继续在同一连接上推送。

#### `assistant_message`

```json
{
  "event": "assistant_message",
  "session_id": "sess_...",
  "run_id": "run_...",
  "turn_id": "turn_...",
  "message_id": "msg_...",
  "content": "完整 assistant 文本",
  "metadata": {}
}
```

`assistant_message` 在 loop yield 一条 assistant `Message` 后立即发送（对应 `message_end` hook 触发点）。CLI 必须一次性输出 `content`，不做打字机效果。

混合 block 语义（与 `agent.core.agent.loop` 实现对齐）：一个 LLM 返回的 message 可同时包含文字和 tool_use；它对应**一帧 `assistant_message` + N 帧 `tool_start`**（同 `message_id` / 同 `turn_id`）：

- 纯文字：`content` 非空，无后续 `tool_start`。
- 纯工具：`content=""`，跟随 N 个 `tool_start`。
- 混合：`content` 非空 + 跟随 N 个 `tool_start`。

CLI 渲染规则：

- `content == ""` 不输出文字行（避免空行噪声）。
- `content` 非空一律输出。模型 narration 必须显示。

#### `tool_start` / `tool_end`

streaming executor 模型下，"模型请求工具调用"和"执行器开始执行"在同一帧表达。kernel 不再单独发出 `tool_call`，由 `tool_start` 承载 tool_use block 完成 + 调度入执行器两层语义。受并发上限阻塞时通过 `tool_start.status="queued"` 表达，无需新增事件。CLI 仅在 `tool_start.presentation.visible=true` 时展示。

```json
{
  "event": "tool_start",
  "session_id": "sess_...",
  "run_id": "run_...",
  "turn_id": "turn_...",
  "call_id": "call_...",
  "name": "read",
  "arguments": {"path": "src/app.py"},
  "presentation": {
    "visible": false,
    "label": "",
    "summary": ""
  }
}
```

#### `tool_end`

```json
{
  "event": "tool_end",
  "session_id": "sess_...",
  "run_id": "run_...",
  "turn_id": "turn_...",
  "call_id": "call_...",
  "name": "read",
  "status": "completed",
  "duration_ms": 12,
  "error": null,
  "presentation": {
    "visible": false,
    "label": "",
    "summary": "",
    "detail": null
  }
}
```

字段分层：

- 顶层 `name` / `status` / `duration_ms` / `error` 是 kernel 生命周期事实，供 Run Activity / 调试使用。`error` 仅承载工具执行级错误（例如非 0 exit、IO 失败），不与 run-terminal `run_status.error` 混用。
- `presentation.summary` / `presentation.detail` 是面向用户的渲染字段，按 §6.4 规则使用。
- LLM-facing tool result 不在 SSE 中流转（不进入 `tool_end`），仅作为 prompt 的下一轮 `tool_result` LLM message 由 loop 内部处理。

### 6.5 Tool Presentation Contract

工具事件分成两层：

- Kernel lifecycle：所有工具都产生 `tool_start` 和 `tool_end`，用于排序、Run Activity 和调试。
- User presentation：CLI 只展示 `presentation.visible=true` 的工具事件。

每个工具必须实现用户展示策略：

```python
class ToolPresentation(Protocol):
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent: ...
    def format_end(
        self,
        args: Mapping[str, Any],
        result: ToolResult,
        duration_ms: int,
    ) -> ToolPresentationEvent: ...
```

`ToolPresentationEvent` 字段：

```json
{
  "visible": true,
  "label": "Write",
  "summary": "src/app.py",
  "detail": null
}
```

字段规则：

- `visible=false`：CLI / Web IM 默认不输出该事件。
- `label`：用户看到的工具名（一行）。
- `summary`：默认折叠态展示的一行主体信息。
- `detail`：完整原始详情，供前端展开查看。承载工具的全量结构化内容：
  - `edit`：完整 diff（unified diff，原始未截断）。
  - `write`：完整写入内容。
  - `bash`：完整 stdout / stderr / exit_code / duration（不截断）。
  - `read`：普通文本仍不放入 detail（避免与 LLM 上下文重复，且文件本身可被 IDE 打开）；非普通文本资源（图片元数据、PDF 摘要等）按需放入。
  - `web_fetch`：完整响应摘要、最终 URL、状态码。
  - `task`：子任务最终摘要、产物路径列表。
  - 失败：完整 traceback / error message。
  - `detail` 是结构化对象（见下），允许多字段；前端按工具类型渲染。
- `detail` 用途分层：
  - CLI 默认折叠，仅展示 `label` + `summary`；用户可通过命令展开（未来）。
  - Web IM 在过程区默认折叠 `summary`，用户点击展开后渲染 `detail`（diff 着色、bash 完整输出滚动等）。
  - 转发到外部 IM（Feishu 等）按 §10 `activity_visibility` 降级，**不携带 `detail`**，仅 `summary`。
- 给模型看的 tool result 与给用户看的 presentation 必须分离；presentation 不进入 LLM 会话历史。
- presentation 事件大小不设硬上限，但 server 必须对极端大小（如 bash 输出 > 1MB）做行/字节级别的尾部截断并在 `detail.truncated=true` 标记，避免压垮 SSE / 浏览器。具体阈值在设计文档中确定，spec 仅约束契约。

`detail` 结构化字段（按工具区分）示例：

```json
{
  "edit": {"diff": "@@ -1,3 +1,3 @@\n-old\n+new", "path": "src/app.py", "truncated": false},
  "write": {"path": "src/app.py", "content": "...", "bytes": 1234, "truncated": false},
  "bash": {"command": "pytest", "exit_code": 0, "duration_ms": 2100, "stdout": "...", "stderr": "", "truncated": false},
  "web_fetch": {"url": "...", "status": 200, "title": "...", "body_excerpt": "..."},
  "task": {"description": "...", "status": "completed", "summary": "...", "artifacts": []},
  "error": {"message": "...", "traceback": "..."}
}
```

内置工具展示策略：

| Tool | Start 展示 | End 展示 | 用户可见内容 |
|---|---:|---:|---|
| `read` | 是 | 是 | 路径；完成后只显示读取摘要，不展示文件内容 |
| `write` | 是 | 是 | 路径；完成后显示创建/覆盖摘要和短内容预览 |
| `edit` | 是 | 是 | 路径；完成后显示修改摘要和 diff 预览 |
| `bash` | 是 | 是 | 命令；完成后显示 exit code、耗时、stdout/stderr 摘要 |
| `web_fetch` | 是 | 是 | URL；完成后显示标题/状态/摘要 |
| `task` | 是 | 是 | 子任务描述；完成后显示子任务状态和摘要 |
| unknown/MCP tool | 是 | 是 | tool name；完成后显示截断后的安全摘要 |

Read 的展示规则：

- `tool_start` 展示读取目标，例如 `Read src/app.py`。
- 普通文本 `tool_end` 只展示摘要，例如 `Read 120 lines` 或 `Read lines 40-80`。
- 普通文本 read 不展示文件正文。
- 图片、PDF、notebook、agent output 等非普通文本资源展示一行类型摘要，例如 `Read image`、`Read PDF`、`Read 6 cells`。

Write/Edit/Bash 的展示规则：

- `summary` 是一行折叠态信息（路径、命令、exit code、耗时等）。
- `detail` 承载完整内容（完整 diff、完整 stdout/stderr），不做行数限制；仅当尾部超过 server 配置的 hard cap 时尾部截断并置 `detail.truncated=true`。
- 失败时 `tool_end.presentation.visible=true`，`summary` 展示错误一行摘要，`detail.error` 承载完整 message + traceback。
- CLI 默认仅渲染 `summary`，不渲染 `detail`；Web IM 在过程区允许用户展开 `detail` 查看全量内容。

#### `turn_end`

```json
{
  "event": "turn_end",
  "session_id": "sess_...",
  "run_id": "run_...",
  "turn_id": "turn_...",
  "completed": true,
  "stop_reason": "stop",
  "usage": {}
}
```

#### `error`

仅用于 **stream 级异常**——run 状态不发生改变，但当前这条 SSE 不能继续。run 终态错误**不**通过 `error` 帧表达，而是嵌入到 `run_status{failed|cancelled}.error`。

```json
{
  "event": "error",
  "session_id": "sess_...",
  "run_id": "run_...",
  "code": "resume_window_exceeded",
  "message": "...",
  "retryable": false
}
```

`code` 取值表（穷举）

run 终态错误（出现在 `run_status.error` 内）：

| code | 触发 | retryable | run 终态 | 备注 |
|---|---|---|---|---|
| `run_execution_failed` | runtime / 上游异常 | false | failed | |
| `run_timeout` | runtime 超时 | true | failed | 对应 `RunsRegistry._mark_timed_out_async` |
| `model_error` | provider 上游模型错误（透传 `ModelError.code/retryable`） | 透传 | failed | 仅当透传 code 已存在时使用 |
| `run_cancelled` | 显式 `runs.cancel(run_id)` | false | cancelled | |
| `run_aborted_by_priority_now` | 被后续 priority=now 抢占 | false | cancelled | 对应 controller `is_aborted`，`stop_reason=aborted` |

stream 级错误（出现在独立 `error` 事件，run 状态不变）：

| code | 触发 | retryable | 备注 |
|---|---|---|---|
| `resume_window_exceeded` | SSE 重连时 history 已被裁掉且 run 未终态 | false | client 应直接重连，不需重新提交用户消息 |

cancelled 与 stop_reason 的对应：`status=cancelled` 时 `stop_reason ∈ {aborted, cancelled}`，分别对应被抢占（aborted）与显式 cancel（cancelled）。

---

## 7. Server Implementation

### 7.1 POST `/messages` Route Flow（同步 RPC）

1. 校验 session 存在；不存在返 404。
2. 校验 payload；非法返 400。
3. 锁定 active run 状态：
   - `priority="now"` 调 `runs.interrupt(session_id)` 中断当前 active run。被抢占的旧 run 在 `/stream` 上以 `run_status{cancelled, error.code=run_aborted_by_priority_now}` 收尾。
   - `priority="next"` 且存在 active run：调 `runs.inject_pending_message(...)`，复用 active run_id。
4. 取 `anchor = event_hub.current_sequence()`（在 submit / inject 之前取，保证客户端按 anchor 过滤不会漏事件）。
5. 调用 `runs.submit(session_id, parts, origin=USER, ...)` 启动新 run（注入路径除外）。
6. 返回 200 JSON `{run_id, anchor_sequence, injected, status}`。

### 7.2 GET `/stream` Route Flow（持久 SSE）

1. 校验 session 存在；不存在返 404。
2. 解析 `Last-Event-ID` header；无则取 `event_hub.current_sequence()` 作为起点（不回放）。
3. 若指定 `Last-Event-ID` 已超出 `event_hub.history_limit`：发一帧 `error{code=resume_window_exceeded}` 后关闭。
4. 进入 `event_hub.stream_session(session_id, after_sequence=...)` 主循环：history 内事件先回放，然后切换到实时 queue。
5. 客户端断开（`asyncio.CancelledError`）：仅关闭 HTTP 连接，不影响任何 run。
6. 不按 `run_id` 过滤；同 session 全部事件原样下发。终态 `run_status` 不触发关流。

### 7.3 Backpressure 与断开

- SSE generator 使用 bounded wait，不忙等。
- 客户端断开只关闭当前 HTTP stream，不取消 run。
- subscriber queue 满时打 overflow 标记，下次 yield 时发一帧 `error{code=subscriber_overflow}` 后关闭，客户端按 `Last-Event-ID` 重连。

### 7.4 Error Handling

- POST payload 校验错误：HTTP 400。
- POST session missing：HTTP 404。
- run 启动后的 provider/model 错误：以 `run_status{failed, error:{code=model_error,...}}` 终态收尾，仅在 `/stream` 上出现，不影响其他 run。
- hook failure 不终止 `/stream`，除非该 failure 已导致 run failed。

### 7.5 移除冗余的完成时重发

`RunsRegistry._emit_turn_events` 当前在 run 完成时重发 `tool_start` / `tool_end` / `turn_end`（与 `realtime_stream` hook 实时已发的事件重复）。feat-338 必须删除这段重发逻辑，仅保留 `_publish_run_status_event`。run 完成时事件序列收敛为：实时已发的业务事件 → 终态 `run_status{completed|failed|cancelled}`（携带 `usage` / `stop_reason` / `error` / `origin`）。

### 7.6 RunOrigin 与 RunRecord

```python
# core/runs/origin.py
class RunOrigin(StrEnum):
    USER = "user"
    BACKGROUND_TASK = "background_task"
    HEARTBEAT = "heartbeat"
```

- `RunRecord` 增加 `origin: RunOrigin`、`source_task_id: str | None` 两个字段（默认 `USER` / `None`）。
- `runs.submit(...)` 接受 `origin` 与 `source_task_id` 关键字参数，默认 `USER` / `None`。
- 所有 `run_status` 事件 payload 必须携带 `origin` 与 `source_task_id`（后者可为 null）。
- 本 feature 中 origin 唯一被实际写入的值是 `USER`。`BACKGROUND_TASK` / `HEARTBEAT` 由后续 feature（feat-337 等）使用；schema、字段、客户端处理逻辑必须在本 feature 完成，使后续 feature 可纯增量接入。

---

## 8. CLI 设计

### 8.1 交互式 CLI

无子命令启动进入交互式 CLI：

```bash
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

REPL 进入 session 后必须立即开一条常驻 `GET /stream` 连接（后台 reader 线程），将事件推入渲染管道。每次用户输入：

1. `POST /messages` 拿到 `{run_id, anchor_sequence, injected}`；
2. 主线程在 reader 推送的事件里按 `run_id` 等待 terminal `run_status`；
3. terminal 后归还提示符，`/stream` 不断开。

reader 在用户未提交期间也持续运行；遇到 `origin != user` 或 `run_id` 不属于本 REPL 提交的事件，仍然渲染（前置一行 origin 标头），不抢占输入行。

保留行为：

- active run 注入
- 本地输入队列
- `/exit`
- `/new`
- `/use <session_id>`
- `/session`
- `/tools`
- `/compact`
- `/history`
- context budget summary

删除行为：

- 不在产品文档中要求用户执行 `create-session`。
- 不在产品文档中要求用户执行 `send-message`。

### 8.2 顶层 `--text`

非交互提交使用顶层 `--text`：

```bash
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215 --text "检查项目并修复问题"
```

执行步骤：

1. 打开 `GET /stream`（长连接）；
2. `POST /messages` 拿到 `run_id`；
3. 在 `/stream` 上按 `run_id` 过滤事件，逐行 NDJSON 写到 stdout；
4. 见到该 `run_id` 的 terminal `run_status` 即关闭 stream 并退出。

最后一行必须是该 `run_id` 的终态 `run_status` 或 stream 级 `error`。`--text` 不承接其他 origin 的 run（已退出，不再监听）。

### 8.3 终端渲染

交互式终端渲染规则：

- `assistant_message` 一次性输出完整 assistant 文本（`content==""` 时不输出）。
- `tool_start.presentation.visible=true` 时显示工具开始行。
- `tool_end.presentation.visible=true` 时显示工具完成或错误，包含耗时和工具自定义摘要。
- `tool_start.presentation.visible=false` 和 `tool_end.presentation.visible=false` 不输出到终端。
- 收到终态 `run_status{completed|failed|cancelled}` 时打印一行 turn 结束摘要（`status` + `stop_reason` + 简短 usage），并结束当前 turn 渲染。最终回答内容已经在最后一帧 `assistant_message` 输出，不重复。
- 收到 stream 级 `error` 时显示错误摘要并自动重连 `/stream`（必要时丢弃 `Last-Event-ID`）；run 仍可能在后台继续。
- Origin 标头：当 `run_status{queued|running}` 的 `origin != user`，渲染器在该 run 的第一帧业务事件之前打印一行 origin 标头（如 `── background wake (task_id=...) ──`、`── heartbeat ──`），让用户区分非本人发起的输出。本 feature 阶段 origin 永远是 `user`，但渲染逻辑必须存在并被 fixture 验证，以便后续 feature 直接复用。

示例：

```text
> 我先检查项目结构。
▸ Tool: read src/agent/core/agent/loop.py
✓ Tool: read src/agent/core/agent/loop.py (read 420 lines)
▸ Tool: bash pytest tests/unit/test_agent_loop.py
✓ Tool: bash (exit=0 elapsed=2100ms)
> 问题定位在 HTTP message endpoint 仍然等待完整 TurnResult。
▸ Tool: edit docs/changes/feat-338-kernel-message-sse/spec.md
✓ Tool: edit docs/changes/feat-338-kernel-message-sse/spec.md (updated)
State: completed | stop_reason=stop
```

---

## 9. Personal Assistant / IM Gateway

personal_assistant kernel client 必须支持：

- `submit_message(session_id, parts, priority)` —— POST RPC。
- `stream_session(session_id, last_event_id?)` —— 持久 SSE iterator。

Gateway 行为：

- 每个 channel-绑定 session 在 binding 期间维持一条常驻 `/stream` 订阅。
- 入站 IM 消息：经 session_key 串行队列拿锁后，调 `submit_message` 拿 `run_id`，在 `/stream` 上等该 `run_id` 的 terminal run_status，期间 assistant 输出走 outbound 回 IM channel。释放锁。
- `/stream` 上看到的 `origin != user` 的 run（本 feature 阶段不会出现，由后续 feature 触发）：仍按 session_key 串行队列调度 outbound，走和正常回复同一路径；上报 `report` 时携带 `origin` 与 `source_task_id`。本 feature 必须实现该路径并以 fixture 校验，以便后续 feature 直接复用。

Gateway 将 kernel events 映射到 feat-336 Run Activity：

| Kernel SSE | Run Activity |
|---|---|
| `run_status` running | `agent.run.started` |
| `assistant_message` | `agent.text.message` |
| `tool_start` | `agent.tool.started` |
| `tool_end` | `agent.tool.completed` |
| `run_status{completed}` / `turn_end` | `agent.run.completed` |
| `run_status{failed\|cancelled}` | `agent.run.failed` |
| `error` (stream-level) | (Gateway 内部，不映射到 Run Activity) |

Gateway 不等待 final response 才上报过程。Gateway 收到每个 kernel event 后立即转发到 ActivitySink。

---

## 10. 安全与隐私

- SSE 不包含模型 hidden reasoning。
- CLI 可以展示本机工具过程。
- `presentation.summary` 是面向所有渲染目标的一行摘要，必须不含敏感大字段。
- `presentation.detail` 承载完整原始详情（完整 diff、完整 stdout/stderr、完整 traceback），仅在受信任前端（CLI 展开、Web IM 过程区展开）可见。
- Gateway 转发到外部 IM（Feishu 等）时必须按 feat-336 的 `activity_visibility` 降级，并**剥离 `detail` 字段**，仅保留 `label` / `summary`。
- 外部 IM 不接收完整工具 stdout/stderr / 完整 diff。
- `detail` 超过 server 配置 hard cap 时尾部截断并置 `detail.truncated=true`，避免压垮 SSE / 浏览器。
- 过程事件不进入 LLM 会话历史；presentation 与 LLM-facing tool result 严格分离。

---

## 11. 测试计划

### Unit

- SSE encoder 输出合法 frame。
- SSE incremental parser 能逐 event 消费。
- CLI renderer 正确处理 `assistant_message`、tool events、terminal events。
- run-id filter 丢弃其他 run 事件。
- NDJSON writer 每行输出完整 JSON event。

### Integration

- `POST /v1/sessions/{session_id}/messages` 返回 `text/event-stream`。
- 纯文本回答返回 `assistant_message` 和终态 `run_status{completed}`。
- 多轮工具调用按 run 内顺序返回 text/tool/text/run_status{completed} 序列。
- 长工具运行期间必须先返回 `tool_start`，完成后返回 `tool_end`。
- run failed 返回 `run_status{failed, error:{...}}`。
- run cancelled 返回 `run_status{cancelled, error:{...}}`。
- 客户端断开不取消 run；重连通过 `Last-Event-ID` 续传。

### CLI

- 无子命令启动进入交互式 CLI。
- 交互式 CLI 每个 turn 都走 streaming message API。
- 顶层 `--text` 走 streaming message API。
- 顶层 `--text` 输出 NDJSON，并以终态 `run_status` 或 stream 级 `error` 结束。
- help 文案不出现 `create-session` 和 `send-message` 产品路径。

### Contract

- `/messages` 的 response media type 是 `text/event-stream`。
- `/messages` request 不接受 `stream` 字段。
- `/messages` 成功、失败、取消均以终态 `run_status` 收尾。
- `run_status` event schema 固定（含 `usage` / `error` 出现条件）。
- `error` event schema 固定，仅出现在 stream 级异常。

---

## 12. 验收标准

### A1. 交互式 CLI 实时反馈

给定一次会调用工具且持续超过 5 秒的任务，用户通过无子命令 CLI 入口提交任务后，终端必须在 run 完成前显示实时事件。

### A2. 顶层 `--text` 流式输出

给定用户通过顶层 `--text` 提交任务，stdout 必须输出 NDJSON event stream，最后一行必须是终态 `run_status` 或 stream 级 `error`。

### A3. 删除子命令产品路径

CLI help、README、验收样例不得引导用户使用 `create-session` 或 `send-message`。

### A4. POST /messages 是 JSON RPC

给定调用 `POST /v1/sessions/{session_id}/messages`，response media type 必须是 `application/json`，body 含 `run_id` / `anchor_sequence` / `injected` / `status`。不得返回 SSE。

### A5. /stream 持久语义

给定打开 `GET /v1/sessions/{id}/stream`，连接保持开放直到客户端断开；run terminal `run_status` 不触发关流；后续 run 的事件继续在同一连接推送。

### A6. SSE terminal guarantee（per run）

给定 run 成功、失败、取消三种结果，该 `run_id` 在 `/stream` 上以对应终态 `run_status` 作为最后一帧出现。

### A7. 多轮工具调用可见

给定 Agent 先输出文字、调用工具、再输出最终文字，`/stream` 上对应 `run_id` 必须按顺序出现 `assistant_message` / `tool_start` / `tool_end` / `assistant_message` / 终态 `run_status`。

### A8. Run ID 隔离（客户端）

`/stream` 全量下发；客户端按 `run_id` 过滤后只看到目标 run 事件。`--text` 必须按 `run_id` 过滤后输出 NDJSON。

### A9. Origin 渲染就位

模拟 fixture 注入 `origin=background_task` 的 `run_status{running, source_task_id=...}`，REPL 必须打印 background 标头；Gateway 必须按 session_key 串行队列调度 outbound。本 feature 不实际产生该 origin，但渲染 / 路由代码必须存在并被测试。

### A10. feat-336 可消费

Gateway 必须能从 kernel stream 映射出 `agent.run.started`、`agent.text.message`、`agent.tool.started`、`agent.tool.completed`、`agent.run.completed`。

---

## 13. 迁移计划

### Phase 1. Kernel Endpoints + Origin Schema

- 新增 `core/runs/origin.py:RunOrigin`；`RunRecord` 加 `origin` / `source_task_id` 字段；`runs.submit(...)` 接受 `origin` / `source_task_id` kwargs（默认 `USER` / `None`）。
- 改造 `POST /v1/sessions/{session_id}/messages` 为 JSON submit RPC，返回 `{run_id, anchor_sequence, injected, status}`。
- 新增 `GET /v1/sessions/{session_id}/stream`：session-scoped 持久 SSE，承载该 session 全部事件，支持 `Last-Event-ID` 续传。
- 删除旧 long-poll `GET /v1/sessions/{id}/events` 与 `POST /messages:async`。
- 删除 `SendMessageRequest.stream`、删除作为 `/messages` response model 的 `SendMessageResponse`。
- run 终态错误嵌入 `run_status.error`；保留独立 `error` 事件仅用于 stream 级异常（`resume_window_exceeded` / `subscriber_overflow`）。
- 删除 `RunsRegistry._emit_turn_events` 在 run 完成时对 `tool_start/tool_end/turn_end` 的重发（见 §7.5）。
- 全部 `run_status` 事件必须带 `origin` / `source_task_id`。

### Phase 2. Client Streaming

- `ServerClient` 提供 `submit_message()` + `stream_session()`；删除 `send_message()` / `send_message_async()`。
- personal_assistant kernel client 同形态。
- 增量 SSE parser 与 `Last-Event-ID` 续传逻辑。

### Phase 3. CLI / REPL Shape

- REPL 进入 session 即开常驻 `/stream` reader 线程。
- 每个 turn：POST submit → 在 reader 推送的事件里按 `run_id` 等 terminal。
- 增加顶层 `--text`：打开 `/stream`、POST submit、按 `run_id` 过滤输出 NDJSON、终态后退出。
- Origin 标头渲染逻辑就位（本 feature 阶段触发不到，但以 fixture 测试覆盖）。
- help 文案移除 `create-session` 和 `send-message` 产品路径。

### Phase 4. Gateway Readiness

- Gateway 对每个 channel-绑定 session 维持常驻 `/stream`。
- 入站消息走 `submit_message`，在常驻 stream 上按 run_id 等待 terminal。
- 非 user origin 的 run 路由路径就位并由 fixture 校验（本 feature 不实际触发）。
- feat-336 在 `RunActivityBridge` 中消费同一 event schema。

Phase 1 与 Phase 2/3/4 是破坏性切换，必须同 commit / 同发版。
