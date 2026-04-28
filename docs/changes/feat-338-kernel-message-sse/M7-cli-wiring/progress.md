# M7: CLI Wiring — Progress

## Completed Roadpoints

### RP1: SessionStreamReader ✅
- `coding_cli/session_stream.py` already created in prior work.
- Added `session_id` public property to avoid private attribute access from `commands.py`.
- Fixed `drain_run()` deprecation warning: removed `asyncio.get_event_loop().time()` call, using `time.monotonic()` exclusively.

### RP2: `--text` NDJSON runner ✅
- `coding_cli/text_runner.py` already created in prior work.
- No changes needed.

### RP3: REPL wiring ✅
- Updated `coding_cli/commands.py` `_run_repl()`:
  - On session enter, starts `SessionStreamReader` when client supports SSE.
  - Added `_supports_sse_repl_events()` to detect `submit_message` + `stream_session` availability.
  - Added `_send_message_via_sse()` helper: submits message, drains run events, builds compatibility payload.
  - Each turn: SSE path uses `submit_message()` → `reader.drain_run()` → renders events → builds payload.
  - Falls back to old `send_message()` / `_send_message_from_repl()` for stub clients without SSE methods.
  - Removed `ReplRunQueue` / `_wait_for_inflight_messages` / queuing logic from REPL flow.
  - Removed async injection and backlog enqueue paths.
- `commands.py` imports updated: added `SessionStreamReader`, `run_text`, `asyncio`.
- Kept backward-compatible imports (`_consume_async_run_events`, `_print_event_preview`) for refactor boundary tests.

### RP4: Parser & subcommand cleanup ✅
- Added `--text` argument to main parser in `build_parser()`.
- Removed `create-session` and `send-message` subparsers.
- Updated `run_cli()`: when `--text` is provided, creates session (or uses `--resume`), runs `asyncio.run(run_text(...))`.
- Updated `_run_single_command()`: removed `create-session` and `send-message` handling.

### RP5: Render updates ✅
- `_send_message_via_sse()` handles `assistant_message`, `tool_start`, `tool_end`, `turn_end`, `run_status` events.
- TTY path uses `ReplLiveRenderer` with event name mapping (`tool_end` → `tool_exec_exit` for renderer compat).
- Non-TTY path collects events and builds payload; summary rendering handles text display.
- Payload includes `_text_streamed` flag so `print_repl_turn_summary()` skips duplicate text when live-rendered.

## Tests

- `tests/unit/test_cli_main.py`: 96 passed (updated: removed 5 old queue tests, added 6 new SSE/text tests).
- `tests/unit/test_text_runner.py`: 5 passed (new file).
- `tests/unit/test_session_stream.py`: 7 passed (new file).
- Total CLI-related unit tests: **108 passed**.
- Integration tests (`tests/integration/api/test_submit_and_stream.py`): 6 passed (no regression).

## Exit Criteria

- ✅ `tests/unit/test_text_runner.py` passes.
- ✅ `tests/unit/test_session_stream.py` passes (equivalent to `tests/cli/test_repl_streaming.py`).
- ✅ Interactive REPL SSE path is wired and tested with stub clients.
- ✅ No regression in existing contract/integration tests.
