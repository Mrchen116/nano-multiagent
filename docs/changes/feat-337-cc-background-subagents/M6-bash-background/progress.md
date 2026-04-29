# M6: Bash Background Support — Progress

## Status

Completed. 8 new unit tests pass; 1 pre-existing contract test failure confirmed on clean HEAD.

## What was built

### Files modified

| File | Change |
|---|---|
| `src/agent/platform/tools/builtins/bash.py` | Added `run_in_background` and `description` parameters; background launch; foreground with 15s auto-background; legacy sync fallback when wiring is missing |
| `src/agent/core/tools/safety_types.py` | Added `poll()` method to `BackgroundCommandHandle` protocol |
| `src/agent/platform/tools/safety.py` | Implemented `poll()` on `_BackgroundCommandHandle` |
| `src/agent/platform/tools/builtins/__init__.py` | Pass `wiring` to `BashTool()` constructor |
| `src/agent/platform/http_api/app.py` | Bind wiring to bash tool via `_bind_runtime_to_tool_registry()` |
| `tests/unit/test_tools_builtins.py` | Updated BashTool description and schema assertions |

### Files created

| File | Purpose |
|---|---|
| `tests/unit/agent/tools/test_bash_tool.py` | 8 unit tests covering background launch, foreground completion, auto-background, failure, legacy fallback, serialization |

## Design decisions retained

- **Legacy fallback**: When `wiring` is `None` and `run_in_background=false`, BashTool falls back to the original `ctx.safety.run_command_stream()` sync path. This preserves contract/integration tests and CLI direct-use scenarios.
- **Registration before start**: Both `_run_background()` and `_run_foreground()` register the task in `BackgroundTaskRegistry` before calling `bash_runner.start()`, eliminating a race where the monitor thread could complete before registration.
- **Auto-background timeout**: 15.0 seconds, matching Claude Code assistant mode semantics.
- **serialize_result** for background returns a formatted receipt with `task_id`, `description`, `output_file`, and usage instructions.

## Pre-existing failures

`tests/contract/test_tools_bash_contract.py::test_bash_truncation_contract_exposes_full_output_path` fails on clean HEAD (unrelated to M6 changes). Verified by `git stash` + `pytest`.
