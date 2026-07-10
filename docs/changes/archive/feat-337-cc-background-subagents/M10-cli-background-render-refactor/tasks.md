# M10 CLI Background Render Refactor Tasks

## Goal

Clean up the CLI-side delivery path added for feat 337 so background wake rendering is behaviorally stable and aligned with the Coding CLI module boundaries.

## Scope

- Document the missing REPL delivery contract in `design.md`.
- Move background-origin run classification and buffering out of `commands.py`.
- Move terminal-safe CRLF line output out of `commands.py`.
- Keep user-visible CLI behavior unchanged.
- Preserve HTTP-only boundaries; no agent/core behavior changes.

## Roadpoints

1. Update design docs with REPL idle delivery, TTY rendering, IME input, and test contracts.
2. Add `coding_cli.events.background_runs.BackgroundRunEventProcessor` for non-user run state.
3. Add `coding_cli.render.terminal_output` for terminal-safe line output.
4. Make `_run_repl`, `_send_message_via_sse`, and grace drains share one background processor instance per session.
5. Add regression tests for cross-phase background event delivery and terminal line contracts.
6. Run focused CLI/background tests.

## Test Strategy

```bash
PYTHONPATH=src python -m py_compile src/coding_cli/commands.py src/coding_cli/events/background_runs.py src/coding_cli/render/terminal_output.py
PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_idle_callback.py tests/unit/test_session_stream.py tests/integration/test_idle_background_render.py
PYTHONPATH=src pytest -q tests/unit/test_cli_background_runs.py
```

## Exit Criteria

- `commands.py` no longer owns background-origin run state transitions.
- Background event state is shared across main-run drain, grace drain, and idle drain.
- TTY output helpers are centralized.
- IME and prompt-idle rendering regressions remain covered.
- Focused tests pass in seconds, not minutes.
