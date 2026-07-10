# M4: Safety Protocol Extension for Background Commands — Progress

## Status

Completed. All 5 unit tests pass.

## What was built

### Modified files

| File | Change |
|---|---|
| `src/agent/core/tools/safety_types.py` | Added `BackgroundCommandHandle` Protocol with `pid`, `output_file`, `wait()`, `terminate_tree()`; added `start_command_background()` to `ToolSafetyLike` |
| `src/agent/platform/tools/safety.py` | Implemented `start_command_background()` using `subprocess.Popen` + pump threads; added `_BackgroundCommandHandle` class |

### Design

- `start_command_background()` enforces command policy via `enforce_command_policy()`, then launches `subprocess.Popen`
- stdout and stderr are pumped to the caller-provided `output_file` in separate daemon threads
- stderr lines are prefixed with `[stderr] `
- `_BackgroundCommandHandle.wait()` blocks until process exit and reads the output file
- `_BackgroundCommandHandle.terminate_tree()` sends SIGTERM then SIGKILL
- Timeout is handled in `wait()` (not at start time), so the caller can decide when to wait

### Tests

| Test | Coverage |
|---|---|
| `test_start_command_background_populates_output_file` | echo hello → output file contains text |
| `test_start_command_background_stderr_prefix` | stderr lines get `[stderr]` prefix |
| `test_start_command_background_nonzero_exit` | `false` returns exit code 1 |
| `test_start_command_background_terminate_tree` | `sleep 30` terminated by stop |
| `test_start_command_background_timeout` | `sleep 30` with 0.2s timeout marked `timed_out` |

## Next

M5: Agent Tool — replace `TaskTool` with `Agent` tool supporting background/foreground/continuation.
