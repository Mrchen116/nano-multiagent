# M8: Gateway Cutover — Progress

## Completed Roadpoints

### RP1: KernelApiClient usage update ✅
- `inbound_pipeline.py` `_run()` uses `submit_message()` when available, falling back to `send_message_async()`.
- `_await_terminal_run_async()` consumes `stream_session()` async generator.
- Handles `assistant_message`, `tool_start`, `tool_end`, `turn_end`, `run_status` events.
- Falls back to old sync `_await_terminal_run()` when `stream_session` is not available.

### RP2: Origin handling path ✅
- In `_await_terminal_run_async()`, events with `run_id` mismatch are skipped.
- TODO comment marks the non-user origin routing path for future feat-338 work.
- No real non-user origin trigger exists yet; code path is protected by run_id filter.

### RP3: Run Activity mapping readiness ✅
- Gateway SSE event handling aligns with feat-336 Run Activity events:
  - `run_status{running}` → accepted phase (implicit)
  - `assistant_message` → reply_text extraction
  - `tool_start` / `tool_end` → consumed without crash
  - `run_status{completed}` → completed phase
  - `run_status{failed|cancelled}` → raises RuntimeError (mapped to failed)
- No ActivitySink wired yet; feat-336 will connect it.

### RP4: Tests ✅
- Updated `_FakeSseKernelClient` in `test_gateway_pipeline.py` with `submit_message` + `stream_session`.
- Added 5 new unit tests:
  - `test_inbound_pipeline_uses_sse_path_when_submit_and_stream_available`
  - `test_inbound_pipeline_sse_path_extracts_reply_from_assistant_message`
  - `test_inbound_pipeline_sse_path_raises_on_failed_run`
  - `test_inbound_pipeline_sse_path_skips_non_user_origin_events`
  - `test_inbound_pipeline_sse_path_relay_lifecycle_emits_completed_with_usage`
- Existing 26 unit tests still pass (old fake client tests fallback path).
- Added integration test: `tests/integration/test_gateway_kernel_stream_integration.py`.

### KernelApiClient async_transport support ✅
- Added `async_transport: httpx.AsyncBaseTransport | None = None` to `KernelApiClient.__init__`.
- `stream_session()` passes the transport to `httpx.AsyncClient`.
- Unit test for `KernelApiClient` updated implicitly (no regression).

## Test Results

- `tests/unit/personal_assistant/`: 235 passed
- `tests/unit/test_cli_main.py` + `test_text_runner.py` + `test_session_stream.py`: 108 passed
- `tests/integration/test_gateway_kernel_stream_integration.py`: 1 passed

## Exit Criteria

- ✅ `tests/unit/personal_assistant/` passes with no regression.
- ✅ Integration test `test_gateway_kernel_stream_integration.py` passes.
- ✅ A10: Gateway can map kernel stream events to Run Activity events (code path ready).
