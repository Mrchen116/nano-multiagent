# M4: Safety Protocol Extension for Background Commands — Roadpoint Plan

## Goal

Enable bash to run commands without blocking the caller by extending the safety protocol.

## Roadpoints

### RP1: Core Protocol Extension
- `core/tools/safety_types.py`: Add `BackgroundCommandHandle` Protocol with `pid`, `output_file`, `wait()`, `terminate_tree()`
- `core/tools/safety_types.py`: Add `start_command_background()` to `ToolSafetyLike`

### RP2: Platform Implementation
- `platform/tools/safety.py`: Implement `start_command_background()` using `subprocess.Popen`
- stdout/stderr pump to caller-provided `output_file` in background threads
- `wait()` blocks until process exit and returns `CommandExecution`
- `terminate_tree()` sends SIGTERM then SIGKILL

### RP3: Tests
- Unit tests for background command start, wait, terminate
- Unit tests for output file population

## Exit Criteria
- `pytest tests/unit/agent/tools/ -q` passes
- Background command handle start/wait/terminate verified
