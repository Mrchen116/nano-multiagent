# M10 CLI Background Render Refactor Progress

## Context

After feat 337 landed, manual REPL testing found three CLI-side gaps:

- Background subagent wake output was not visible while the prompt waited for user input.
- TTY output could drift right because raw mode and direct `print()` paths emitted bare LF.
- IME commits such as `你好吗` only rendered the first character until another keypress.

The first fix restored behavior but concentrated background event state and terminal rendering inside `commands.py`.

## Decision

Refactor the CLI implementation without changing behavior:

- `events/background_runs.py` owns non-user run detection, buffering, and display line formatting.
- `render/terminal_output.py` owns TTY-safe CRLF line emission.
- `commands.py` keeps orchestration: poll events, pass them through the processor, and emit returned lines.

## Rationale

This restores the Coding CLI boundary from `docs/CodingCLI-SPEC.md`:

- `commands.py` should orchestrate.
- `events/` should consume and normalize event stream behavior.
- `render/` should own terminal output details.
- `input/` should own raw terminal input and IME-safe key reads.

## Evidence

- `PYTHONPATH=src python -m py_compile src/coding_cli/commands.py src/coding_cli/events/background_runs.py src/coding_cli/render/terminal_output.py` passed.
- `PYTHONPATH=src pytest -q tests/unit/test_cli_background_runs.py tests/unit/test_cli_main.py tests/unit/test_idle_callback.py tests/unit/test_session_stream.py tests/integration/test_idle_background_render.py` passed: 111 passed in 8.40s.
- `PYTHONPATH=src pytest -q tests/contract/test_cli_http_only_contract.py` failed on pre-existing contract drift unrelated to M10:
  - `src/coding_cli/kernel_app.py` imports `agent.platform.http_api.app`.
  - contract still expects `create-session` and `send-message` parser subcommands while current parser exposes `health` and `llm-config`.

## Rollback

Revert this milestone's files and restore the pre-M10 `commands.py` implementation from commit `3555e11`.

## Commits

Planned:

- `feat(337-M10): Refactor CLI background wake rendering`
