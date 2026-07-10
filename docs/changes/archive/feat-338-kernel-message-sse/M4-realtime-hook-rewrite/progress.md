# M4: Realtime Hook Rewrite — Progress

## RP1: Extend loop hook payloads
- `_dispatch_tool_result_hook` now carries `arguments` (looked up from `call_id_to_arguments` map) and `duration_ms`.
- `call_id_to_arguments` map is populated when each tool call is dispatched in `AgentLoop.run()`.

## RP2: Extend StreamingToolExecutor with duration tracking
- `_QueuedTool` gained `duration_ms: int = 0` and `_started_at_ns: int = 0`.
- `_execute_one` records start time in `perf_counter_ns()`, computes `duration_ms` in `finally`, and injects it into `ToolResult`.

## RP3: Rewrite `realtime_stream` hook
- Deleted `on_message_update` / `text_delta`; replaced by `on_message_end` → `assistant_message`.
- `on_tool_call` → `tool_start` with `presentation` via `resolve_presenter`.
- `on_tool_result` → `tool_end` with `presentation` + `duration_ms` + `status`.
- `on_turn_end` preserved (still publishes `turn_end` to hub).
- `on_tool_execution_update` removed from this hook file entirely.
- Hook registrations reduced to: `tool_call`, `tool_result`, `message_end`, `turn_end`.

## RP4: Delete `_emit_turn_events`
- Removed `RunsRegistry._emit_turn_events` method and its call site in `_mark_completed`.
- Terminal `run_status` now carries all metadata; no duplicate `tool_start`/`tool_end`/`turn_end` replay.

## Test Results
```
tests/unit/test_hooks_runner.py: 3 passed
tests/unit/test_runs_registry.py: 6 passed
tests/unit/platform/hooks/test_realtime_stream_events.py: 5 passed

14 passed total
```

## Commits
- `core/types.py`: `ToolResult.duration_ms` field.
- `core/agent/tool_executor.py`: duration tracking in `_QueuedTool` and `_execute_one`.
- `core/agent/loop.py`: `call_id_to_arguments` map, `arguments` and `duration_ms` in `_dispatch_tool_result_hook`.
- `platform/hooks/builtins/realtime_stream.py`: complete rewrite to `assistant_message` + `tool_start`/`tool_end` with presentation.
- `core/runs/registry.py`: removed `_emit_turn_events`.
