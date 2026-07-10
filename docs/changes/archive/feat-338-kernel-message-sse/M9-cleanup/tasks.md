# M9: Cleanup — Tasks

## Goal
Delete all deprecated client methods (`send_message`, `send_message_async`, `stream_session_events`) and old endpoint artifacts. Update all callers and test fixtures. Full test suite green.

## Task List

### 1. Source code cleanup
- [ ] `src/personal_assistant/scheduler/heartbeat_scheduler.py`
  - Update `_KernelClientLike` protocol: `send_message_async` → `submit_message`
  - Update `_submit_run()` to call `submit_message(texts=[message])`
- [ ] `src/personal_assistant/client/kernel_api_client.py`
  - Remove `send_message_async()`
  - Remove `stream_session_events()`
  - Remove `_parse_sse_events()` (only used by old method)
- [ ] `src/personal_assistant/gateway/inbound_pipeline.py`
  - Remove fallback to `send_message_async` in `_run()`
  - Remove fallback to `_await_terminal_run` via `stream_session_events`
  - Make SSE path unconditional
- [ ] `src/coding_cli/client.py`
  - Remove `send_message()`
  - Remove `send_message_async()`
  - Remove `stream_session_events()`
  - Remove `_parse_sse_events()`
- [ ] `src/agent/platform/sdk/client.py`
  - Remove `send_message()`
  - Remove `send_message_async()`
  - Remove `stream_session_events()`
  - Remove `_parse_sse_events()`
- [ ] `src/coding_cli/commands.py`
  - Remove old fallback `_send_message_from_repl()` that uses `client.send_message()`
  - Make REPL always use `_send_message_via_sse()` (SSE path already primary)
  - Remove imports of `_supports_async_repl_events` / `_send_message_with_async_events`
- [ ] `src/coding_cli/events/repl_events.py`
  - Remove `send_message_with_async_events()` (old polling path)
  - Update `supports_async_repl_events()` to check new API, or remove if unused

### 2. Test fixture updates
- [ ] `tests/unit/test_cli_main.py` — update all fake clients from old API to new API
- [ ] `tests/unit/test_sdk_client.py` — update or remove `send_message` test
- [ ] `tests/unit/personal_assistant/test_gateway_pipeline.py` — remove old fake client if still present
- [ ] `tests/im_service/integration/test_m103_im_gateway_e2e.py` — update fake kernel client
- [ ] `tests/im_service/integration/test_m136_group_chat_flow.py` — update fake kernel client
- [ ] `tests/e2e/test_cli_text_streaming_and_injection_e2e.py` — update if needed

### 3. Verification
- [ ] `pytest -m "not e2e"` passes
- [ ] `tests/unit/personal_assistant/` passes
- [ ] `tests/unit/test_cli_main.py` passes
- [ ] `tests/integration/test_gateway_kernel_stream_integration.py` passes

### 4. Documentation
- [ ] Write `progress.md`
