# M4: Realtime Hook Rewrite — Roadpoint Plan

## Goal
Rewrite `realtime_stream` hook to emit `assistant_message` / `tool_start` / `tool_end` with presentation; inject origin into `run_status`; remove `_emit_turn_events` duplication.

## Roadpoints

### RP1: Extend loop hook payloads
- `_dispatch_tool_result_hook` adds `arguments` (looked up by call_id) and `duration_ms`.
- `StreamingToolExecutor` records `duration_ms` per tool call.

### RP2: Rewrite `realtime_stream` hook
- `on_message_update` → `text_delta` deleted; replaced by `on_message_end` → `assistant_message`.
- `on_tool_call` → `tool_start` with `presentation` (uses `resolve_presenter`).
- `on_tool_result` → `tool_end` with `presentation` (uses `resolve_presenter`) + `duration_ms` + `status`.
- `run_status` event already carries origin from registry (M2); hook does not need to add it.
- `tool_exec_*` events are **not** in the 6-event whitelist; they remain unpublished to SSE stream.

### RP3: Delete `_emit_turn_events`
- Remove `RunsRegistry._emit_turn_events` (registry.py:474-517).
- `_publish_run_status_event` already carries terminal metadata (usage, error, stop_reason, origin).

## Tests
- Existing SSE-related tests in `tests/unit/test_hooks_runner.py` and integration tests must still pass after event renaming.
- New unit test: `tests/unit/platform/hooks/test_realtime_stream_events.py` — verifies `assistant_message`, `tool_start`, `tool_end` schema.

## Exit Criteria
All existing hook/SSE tests pass; new schema test passes.
