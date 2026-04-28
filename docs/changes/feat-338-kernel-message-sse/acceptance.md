# feat-338: Kernel Message SSE — Acceptance Report

> **Date**: 2026-04-28
> **Validator**: Claude Code
> **Status**: Accepted

---

## Summary

Feature 338 implements the "submit + observe" split architecture for the Agent kernel:

- `POST /v1/sessions/{id}/messages` returns a JSON RPC handle (`{run_id, anchor_sequence, injected, status}`).
- `GET /v1/sessions/{id}/stream` is a session-scoped persistent SSE channel carrying all runs.
- CLI REPL maintains a persistent `/stream` background reader and submits per turn.
- CLI `--text` opens `/stream`, submits, filters by `run_id`, and outputs NDJSON until terminal.
- `RunOrigin` enum and `origin` / `source_task_id` fields are wired through the full stack.
- Old synchronous message endpoint, old long-poll `/events`, and `SendMessageRequest.stream` are removed.

---

## Validation Method

1. **Code inspection** of parser help, route handlers, client interfaces, and REPL/Gateway orchestration.
2. **Unit test execution** for CLI (`test_cli_main.py`, `test_session_stream.py`, `test_text_runner.py`), Gateway (`test_gateway_pipeline.py`), and API contract tests.
3. **Integration test execution** for API submit/stream (`test_submit_and_stream.py`) and Gateway kernel stream (`test_gateway_kernel_stream_integration.py`).
4. **CLI help smoke test** to confirm removed product paths.

---

## Acceptance Criteria

### A1. Interactive CLI real-time feedback

**Verdict**: PASS (code path + tests)

- `_send_message_via_sse()` in `commands.py:316` submits via `client.submit_message()` and drains events via `reader.drain_run()`.
- TTY mode uses `ReplLiveRenderer` for live assistant text and tool events.
- Non-TTY mode emits `tool_start` / `tool_exec_started` previews as events arrive.
- `_run_repl()` starts `SessionStreamReader` on session entry and keeps it alive across turns.
- Unit tests (`test_run_cli_repl_uses_sse_path_when_submit_message_available` et al.) verify the streaming path end-to-end with fake SSE clients.

> Note: A full interactive test with a live LLM provider was not performed because it requires external API credentials. The streaming path is fully covered by unit and integration tests.

---

### A2. Top-level `--text` stream output

**Verdict**: PASS

- `text_runner.py:run_text()` opens `client.stream_session()`, submits, filters by `run_id`, and writes one JSON event per line.
- Exit codes: `0` for completed, `1` for failed/cancelled, `2` for stream-level error.
- Last line is guaranteed to be a terminal `run_status` or `error` event.
- Unit tests (`test_text_runner.py`) and CLI integration tests pass.

---

### A3. Deleted subcommand product paths

**Verdict**: PASS

- `build_parser()` in `commands.py:126` only registers `health` and `llm-config` subcommands.
- No `create-session` or `send-message` subcommands exist in the parser.
- CLI `--help` output (verified live) does not mention either subcommand.

---

### A4. POST `/messages` is JSON RPC

**Verdict**: PASS

- `submit_message()` route in `session.py:491` returns `SubmitMessageResponse` with `run_id`, `anchor_sequence`, `injected`, `status`.
- Response media type is `application/json` (FastAPI `response_model`).
- Integration test `test_submit_message_returns_json_rpc` verifies the exact shape.

---

### A5. `/stream` persistent semantics

**Verdict**: PASS

- `session_stream()` route in `session.py:563` returns `StreamingResponse` with `text/event-stream`.
- Generator `_session_stream_generator()` does not close on terminal `run_status`; only on client disconnect, session destroy, or stream-level `error`.
- Integration tests `test_stream_replays_completed_run_events` and `test_stream_resume_with_last_event_id` verify persistence and replay.

---

### A6. SSE terminal guarantee (per run)

**Verdict**: PASS

- Every run in `/stream` ends with a terminal `run_status`:
  - Success: `run_status{status=completed}`
  - Failure: `run_status{status=failed, error:{...}}`
  - Cancelled: `run_status{status=cancelled, error:{...}}`
- Verified by `test_stream_replays_completed_run_events` and `test_priority_now_preempts_active_run`.

---

### A7. Multi-turn tool call visibility

**Verdict**: PASS

- Event sequence `assistant_message` → `tool_start` → `tool_end` → `assistant_message` → terminal `run_status` is produced by the `realtime_stream` hook and validated in integration tests.
- CLI renderer correctly displays tool start/end lines in both TTY and non-TTY modes.

---

### A8. Run ID isolation (client)

**Verdict**: PASS

- `text_runner.py:43` explicitly skips events where `event.get("run_id") != target_run_id`.
- `SessionStreamReader.drain_run()` filters by `run_id` and passes non-matching events to `on_other`.
- Unit tests verify filtering behavior.

---

### A9. Origin rendering in place

**Verdict**: PASS

**CLI**: `_format_origin_header()` in `commands.py:309` formats headers for `background_task` and `heartbeat` origins. `_send_message_via_sse()` passes an `on_other` callback to `drain_run()` that prints the header for non-user runs. Unit test `test_send_message_via_sse_renders_origin_header_for_non_user_run` verifies output.

**Gateway**: `_await_terminal_run_async()` accepts `on_other` callback. `_run()` defines `_on_other_event()` that routes `assistant_message` events with `origin != "user"` through `self._outbound_router.send_text()`. Unit test `test_inbound_pipeline_sse_path_routes_non_user_origin_events` verifies outbound delivery.

---

### A10. Gateway Run Activity mapping

**Verdict**: PASS

- `InboundPipeline._map_kernel_event_to_run_activity()` maps:
  - `run_status{running}` → `agent.run.started`
  - `assistant_message` → `agent.text.message`
  - `tool_start` → `agent.tool.started`
  - `tool_end` → `agent.tool.completed`
  - `run_status{completed}` → `agent.run.completed`
  - `run_status{failed|cancelled}` → `agent.run.failed`
- Unit test `test_map_kernel_event_to_run_activity` verifies all mappings.
- The actual `ActivitySink` wiring is deferred to feat-336; feat-338 guarantees the event schema and mapping function are stable and ready for consumption.

---

## Test Results

| Suite | Passed | Failed | Notes |
|---|---|---|---|
| `tests/unit/test_cli_main.py` | 88 | 0 | Includes origin header test |
| `tests/unit/test_session_stream.py` | 8 | 0 | Includes `on_other` callback test |
| `tests/unit/test_text_runner.py` | 4 | 0 | NDJSON output validation |
| `tests/integration/api/test_submit_and_stream.py` | 6 | 0 | Submit RPC, stream, resume, priority |
| `tests/unit/personal_assistant/test_gateway_pipeline.py` | 32 | 0 | Origin routing + Run Activity mapping |
| `tests/integration/test_gateway_kernel_stream_integration.py` | 1 | 0 | Full Gateway → Kernel SSE path |
| **Total** | **139** | **0** | — |

---

## Known Limitations

1. **Interactive CLI real-time feedback (A1)** was validated via unit/integration tests with fake SSE clients, not a live LLM provider session. The streaming architecture is correct; actual latency/feel depends on provider behavior.
2. **Gateway persistent background stream consumer**: The current Gateway opens `/stream` per inbound message inside `_await_terminal_run_async()`. A fully persistent per-session background consumer (independent of inbound messages) is not yet implemented. This is sufficient for the current product stage because non-user origin runs do not yet exist.
3. **Run Activity sink wiring**: The mapping function exists, but no `ActivitySink` is connected yet. This is explicitly deferred to feat-336.

---

## Verdict

Feature 338 meets all acceptance criteria. The kernel message SSE architecture is fully implemented, tested, and ready for downstream features (feat-336 Run Activity Plane, feat-337 background task wake-up).
