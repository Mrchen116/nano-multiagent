# M7: CLI Wiring — Roadpoint Plan

## Goal
Rewrite coding_cli REPL and non-interactive entry to use submit + persistent SSE stream.

## Roadpoints

### RP1: SessionStreamReader
- New `coding_cli/session_stream.py` with `SessionStreamReader` class.
- Background thread owns persistent `stream_session()` iterator.
- Events dispatched to per-run_id subscribers (asyncio.Event or queue-based).
- Auto-reconnect on `resume_window_exceeded` (drop Last-Event-ID, restart from tail).

### RP2: `--text` NDJSON runner
- New `coding_cli/text_runner.py` with `run_text()` async function.
- Open stream, POST submit, filter by run_id, output NDJSON lines to stdout.
- Exit code: 0 (completed), 1 (run failed/cancelled), 2 (stream error).

### RP3: REPL wiring
- Update `coding_cli/commands.py` `_run_repl()`:
  - On session enter, start `SessionStreamReader`.
  - Each turn: `client.submit_message()` → subscribe to run_id in reader → render events until terminal `run_status`.
  - Remove old `ReplRunQueue` / `send_message_async` / `send_message` sync paths.
- Render origin header when `origin != user`.

### RP4: Parser & subcommand cleanup
- Remove `create-session` and `send-message` subparsers from `build_parser()`.
- Add `--text` argument to main parser.
- When `--text` is provided, run `text_runner` instead of REPL.

### RP5: Render updates
- Update `coding_cli/render/repl_live.py` or create new render path for `assistant_message` / `tool_start` / `tool_end` / `run_status` events.
- Origin header: print `── background wake ──` or similar before first event of non-user run.

## Exit Criteria
- `tests/cli/test_repl_streaming.py` passes (or equivalent unit tests).
- `tests/cli/test_text_runner.py` passes.
- Interactive REPL manual smoke test shows real-time events.
