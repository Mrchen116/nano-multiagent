# M5: Endpoints — Progress

## Completed Roadpoints

### RP1: POST /messages → JSON submit RPC ✅
- `SendMessageRequest` 已移除 `stream` 字段（RP3 中统一清理）。
- 新增 `SubmitMessageResponse` Pydantic model：含 `run_id`, `anchor_sequence`, `injected`, `status`。
- `submit_message` route 实现完整语义：
  - `priority="now"` → `runs.interrupt(session_id)` 抢占旧 run。
  - `priority="next"` + active run 存在 → `inject_pending_message` 注入，返回 `injected=true, status=injected`。
  - 其他情况 → `runs.submit()` 新建 run，返回 `status=queued`。
  - `anchor_sequence` 在 submit/inject **之前**从 `event_hub.current_sequence()` 原子读取。

### RP2: GET /stream persistent SSE ✅
- `session_stream` route 实现：
  - 校验 session 存在。
  - 解析 `Last-Event-ID` header；越界时返回单帧 `error{code=resume_window_exceeded}`。
  - 无 `Last-Event-ID` 时以 `current_sequence()` 为起点（不回放历史）。
- `_session_stream_generator` 异步生成器：
  - 调用 `event_hub.stream_session()` 回放历史 + 切换实时队列。
  - 捕获 `SubscriberOverflowError` → yield `error{code=subscriber_overflow, retryable=true}` 后关闭。
  - 客户端断开 (`asyncio.CancelledError`) 不取消任何 run。

### RP3: Delete legacy endpoints ✅
- 删除 `send_message_async` route (`POST /messages:async`)。
- 删除 `stream_session_events` route (`GET /events`)。
- 删除旧 Pydantic models：`SendMessageResponse`, `SendMessageAsyncRequest`, `SendMessageAsyncResponse`。

## Key Fixes During Implementation

1. **`has_sequence` resume 语义修正**：旧实现 `sequence_num >= oldest_sequence` 导致 `Last-Event-ID: N-1` 被判定为越界。修正为 `sequence_num >= oldest_sequence - 1`，使客户端可正确续传。
2. **`stream_session` async 化**：原始同步实现使用 `queue.get(timeout=...)` 会阻塞 FastAPI 事件循环。改为 `async def` + `buffer.get_nowait()` + `await asyncio.sleep(tick_seconds)` 的轮询模式。
3. **测试可控关闭**：`TestClient` / `AsyncClient` 的 `ASGITransport` 不支持无限流读取超时。引入 `max_empty_ticks: int | None = None` 参数（默认 `None` 表示永久），测试通过 monkey-patch 设为 2 实现可控关闭。
4. **`_AsyncBlockingRuntime` 跨 loop 兼容性**：`asyncio.Event` 在创建时绑定到特定事件循环，与 `RunsRegistry` 的独立 async loop 线程不兼容。改用 `threading.Event` + `await asyncio.sleep(0.01)` 轮询。

## Test Results

- `tests/unit/platform/http_api/test_event_hub.py`: **13 passed**
- `tests/integration/api/test_submit_and_stream.py`: **6 passed**
  - `test_submit_message_returns_json_rpc`
  - `test_stream_replays_completed_run_events`
  - `test_stream_resume_with_last_event_id`
  - `test_stream_resume_window_exceeded`
  - `test_priority_now_preempts_active_run`
  - `test_priority_next_injects_into_active_run`

## Exit Criteria

✅ 全部集成测试与单元测试通过。
