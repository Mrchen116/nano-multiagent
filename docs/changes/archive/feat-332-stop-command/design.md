# Feat-332 Design: IM Stop Command

## 架构决策

### 决策 1：Kernel 暴露 `POST /v1/sessions/{session_id}/interrupt`

**理由**：`RunsRegistry.interrupt(session_id)` 已存在且能力完整（调用 `controller.abort()`），只是未暴露为 HTTP API。Gateway 天然持有 `kernel_session_id`，以 session 为粒度调用最自然。新增 run-level abort API（如 `POST /v1/runs/{run_id}/abort`）也可以，但 gateway 需要额外维护 run_id → session 的映射，增加复杂度。

**拒绝的方案**：
- **复用 `POST /v1/runs/{run_id}/cancel`**：`cancel()` 只能中断 QUEUED 状态的 run（设置 `cancel_event`），对已在执行的 RUNNING run 无效。AgentLoop 检查的是 `abort_event`，不是 `cancel_event`。
- **修改 `cancel()` 语义同时触发 `abort()`**：会混淆 cancel（温和取消）和 abort（强制中断）的语义，影响现有测试和客户端预期。

### 决策 2：Gateway 维护 `_active_runs: dict[str, str]` 映射

**理由**：`InboundPipeline` 当前是 stateless 的，`handle_inbound` 内部持有 run_id 但不持久化。`/stop` 需要知道"当前 session 有没有活跃 run"以及"run_id 是什么"，才能在无活跃 run 时返回友好提示。

映射结构：`session_key → run_id`

生命周期：
- 注册：`_run()` coroutine 开始执行时（获得 run_id 后立即写入）
- 注销：`_run()` 正常完成、异常、或取消后（`finally` 块中清除）

### 决策 3：`/stop` 跳过 `SessionRunQueue`，直接执行

**理由**：`SessionRunQueue` 是 per-session FIFO。如果 `/stop` 正常排队，它会等到当前活跃 run 完成后才执行，失去"立即终止"的意义。`/stop` 作为控制命令应走插队路径。

**实现**：`handle_inbound` 在最开始（`_resolve_agent` 和 `_should_process` 之后）检查 `message.text.strip() == "/stop"`。如果是，直接走 `_handle_stop_command()` 分支，不调用 `_run_queue.submit()`。

### 决策 4：AgentLoop LLM 生成阶段不增强 abort 检测

**理由**：`AgentLoop.run()` 中 `llm_client.generate()` 调用（第191行）不检查 `controller.is_aborted`。增强需要在 LLM 客户端层传入 abort signal，涉及 provider 层改动，超出本 feat 范围。当前行为是：如果 abort 发生在 LLM 生成阶段，用户需要等待当前生成完成后，在下一轮工具执行前才能检测到中断。

**风险接受**：这是已知限制，在验收标准中通过 e2e 测试的"3秒内终止"来覆盖常见场景（工具执行阶段的中断）。

## 接口设计

### Kernel HTTP API 新增

```
POST /v1/sessions/{session_id}/interrupt
```

**Request**: `{}`（空 body）

**Response**:
```json
{
  "session_id": "sess_xxx",
  "interrupted": true,
  "run_id": "run_yyy"  // 被中断的活跃 run_id，若无活跃 run 则为 null
}
```

**错误**：
- 404：`session_not_found`
- 401/403：鉴权失败

**实现**：调用 `RunsRegistry.interrupt(session_id)`，返回是否成功找到并信号了活跃 run。

### KernelApiClient 新增

```python
def interrupt_session(self, *, session_id: str) -> dict[str, Any]:
    """Request force interrupt for the active run of a session.

    Returns:
        {"session_id": str, "interrupted": bool, "run_id": str | None}
    """
```

### InboundPipeline 变更

新增内部方法：

```python
async def _handle_stop_command(
    self,
    message: InboundMessage,
    *,
    agent_id: str,
    session_key: str,
) -> PipelineResult | None:
    """Handle /stop command: interrupt active run and inject user message.

    Returns PipelineResult with confirmation reply, or None when no active run.
    """
```

新增状态：

```python
self._active_runs: dict[str, str]  # session_key -> run_id
self._active_runs_lock: asyncio.Lock
```

## 数据流

### 场景：工具执行阶段中断（最优路径）

```
User sends "/stop"
  ↓
[Gateway] InboundPipeline.handle_inbound()
  ├── text.strip() == "/stop" → 走 _handle_stop_command()
  ├── 查 _active_runs.get(session_key) → run_id
  ├── KernelApiClient.interrupt_session(kernel_session_id)
  │     ↓
  │   [Kernel] POST /v1/sessions/{sid}/interrupt
  │     ├── RunsRegistry.interrupt(session_id)
  │     ├── controller.abort() → 设置 abort_event
  │     └── return {"interrupted": true, "run_id": "..."}
  │
  ├── KernelApiClient.append_message(
  │       role="user",
  │       content="[Request interrupted by user for tool use]"
  │     )
  │     ↓
  │   [Kernel] session history 追加中断消息（不触发新 run）
  │
  └── return PipelineResult(
        reply_text="已停止当前操作",
        outbound=OutboundMessage(...),
      )

[Kernel AgentLoop] 当前批次工具执行完成后
  ├── controller.is_aborted → True
  ├── 为未完成 tool_use 生成 error="interrupted" 结果
  ├── yield turn_meta(stop_reason="interrupted", completed=False)
  └── return → RunsRegistry._run_worker 结束

[Gateway] _await_terminal_run 轮询到 run 结束
  └── 当前 handle_inbound 的 _run() 返回
      └── _active_runs.pop(session_key, None)
```

### 场景：无活跃 run 时发送 `/stop`

```
User sends "/stop"
  ↓
[Gateway] _handle_stop_command()
  ├── _active_runs.get(session_key) → None
  └── return PipelineResult(
        reply_text="当前没有正在执行的操作",
        outbound=OutboundMessage(...),
      )
```

### 场景：群聊中的 `/stop`

```
User sends "@agent /stop" in group chat
  ↓
[Gateway] _should_process() → True（@mention 命中）
  ├── _resolve_agent() → agent_id
  ├── text.strip() == "@agent /stop" → 仍需识别为 /stop
  └── 走 _handle_stop_command()
```

**注意**：群聊中的 `/stop` 文本可能是 `@agent /stop` 或 `/stop @agent`，需要规范化处理。MVP 方案：去除 `@agent_id` 前缀/后缀后检查是否为 `/stop`。

## 关键权衡

| 权衡点 | 选择 | 理由 |
|--------|------|------|
| session-level vs run-level interrupt API | session-level | Gateway 天然持有 session_id，减少映射维护 |
| `/stop` 是否写入 group context buffer | 不写入 | 控制命令不应作为聊天历史的一部分 |
| 中断消息后是否等待原 run 结束再回复 | 不等 | interrupt 是异步信号，立即返回确认更友好 |
| 中断消息是否触发新 LLM run | 不触发 | 使用 `append_message` 仅写入历史，避免 `/stop` 自身拉起模型调用 |
| 是否支持部分停止（只停某个 tool） | 不支持 | 复杂度远高于收益，MVP 只停整个 turn |
| CLI REPL 是否同步添加 `/stop` | 不加 | CLI 已有 Ctrl+C，语义不同 |

## 变更文件清单

### Kernel 层

| 文件 | 变更 |
|------|------|
| `src/agent/platform/http_api/routes/session.py` | 新增 `POST /{session_id}/interrupt` 端点 |
| `src/agent/core/runs/registry.py` | 确认 `interrupt()` 行为满足需求（无需修改） |

### Gateway 层

| 文件 | 变更 |
|------|------|
| `src/personal_assistant/client/kernel_api_client.py` | 新增 `interrupt_session()` 方法 |
| `src/personal_assistant/gateway/inbound_pipeline.py` | `/stop` 拦截、`_active_runs` 追踪、`_handle_stop_command()` |
| `src/personal_assistant/gateway/inbound_pipeline.py` | `_run()` 中注册/注销活跃 run |

### 测试

| 文件 | 类型 |
|------|------|
| `tests/contract/test_session_interrupt_contract.py` | 契约测试：验证 interrupt API 响应格式 |
| `tests/integration/test_stop_command_integration.py` | 集成测试：Gateway → Kernel 完整链路 |
| `tests/e2e/test_stop_command_e2e.py` | e2e 测试：慢工具 + `/stop` 终止 |

## 与现有系统的兼容性

- `RunsRegistry.interrupt()` 是已有方法，本次仅暴露为 HTTP API，不影响现有行为
- `AgentLoop` 的 abort 检测逻辑不变，现有测试无需修改
- `SessionRunQueue` 的 FIFO 语义不变，正常消息仍排队执行
- `/stop` 仅影响自身 session，不波及其他 session 的并发执行
