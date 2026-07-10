# M8: Gateway Cutover — Roadpoint Plan

## Goal
Update personal_assistant Gateway inbound pipeline to use submit + persistent SSE stream.

## Roadpoints

### RP1: KernelApiClient usage update
- Update `inbound_pipeline.py` `_run()` to use `submit_message()` instead of `send_message_async()`.
- Make `_await_terminal_run()` async and consume `stream_session()` async generator.
- Handle new event types: `assistant_message`, `tool_start`, `tool_end`, `turn_end`, `run_status`.
- Keep fallback to old sync path when `stream_session` is not available (stub compatibility).

### RP2: Origin handling path
- In `_await_terminal_run()`, when `run_status.origin != "user"`, route through session_key serial queue for outbound.
- Add code path (with fixture test) for non-user origin events even though no real trigger exists yet.
- Origin header rendering: print background wake indicator before first event of non-user run.

### RP3: Run Activity mapping readiness
- Ensure Gateway can map kernel SSE events to feat-336 Run Activity events:
  - `run_status{running}` → `agent.run.started`
  - `assistant_message` → `agent.text.message`
  - `tool_start` → `agent.tool.started`
  - `tool_end` → `agent.tool.completed`
  - `run_status{completed}` / `turn_end` → `agent.run.completed`
  - `run_status{failed|cancelled}` → `agent.run.failed`
- Add mapping helper (no ActivitySink yet; feat-336 will wire it).

### RP4: Tests
- Update existing Gateway unit tests to work with new submit+stream path.
- Add integration test: `tests/integration/personal_assistant/test_gateway_kernel_stream.py`.
- Fixture test for non-user origin routing path.

## Exit Criteria
- `tests/unit/personal_assistant/` passes with no regression.
- `tests/integration/personal_assistant/test_gateway_kernel_stream.py` passes (or equivalent).
- A10: Gateway can map kernel stream events to Run Activity events.
