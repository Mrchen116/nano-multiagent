# M9: Integration Tests & Acceptance — Progress

## Status

Completed. 15 integration tests pass; acceptance criteria validated.

## What was built

### Files created

| File | Purpose |
|---|---|
| `tests/integration/background_tasks/__init__.py` | Package init |
| `tests/integration/background_tasks/test_bash_background.py` | 4 tests: explicit background launch, output file, completion notification, failed notification |
| `tests/integration/background_tasks/test_agent_background.py` | 3 tests: async receipt, registry record, completion notification |
| `tests/integration/background_tasks/test_task_stop.py` | 3 tests: stop bash, stop agent, already-terminal error |
| `tests/integration/background_tasks/test_auto_background.py` | 2 tests: bash 15s auto-background, agent 120s auto-background |
| `tests/integration/background_tasks/test_agent_continuation.py` | 3 tests: message queue, JSONL rehydrate, unknown agent error |

### Files modified

| File | Change |
|---|---|
| `src/agent/platform/background_tasks/shell_runner.py` | `_stop_task` no longer blocks waiting for process exit; sends SIGTERM and returns immediately so `registry.kill()` wins the race against the monitor thread's `on_fail` callback. |

## Design decisions retained

- **Integration test stubs**: `_RuntimeStub` provides async `create_session` / `run` with configurable delay. `_RunsRegistryStub` captures `submit` and `inject_pending_message` calls to verify notification delivery without a real async runtime.
- **Real shell runner for bash tests**: Background bash tests use real `subprocess.Popen` and `ShellRunner` to validate stdout/stderr capture, process lifecycle, and output file appending.
- **Auto-background via monkeypatch**: The 15s bash and 120s agent budgets are too long for CI. Integration tests monkeypatch the module-level constants to 0.1s and use slow commands/stubs to trigger auto-background.
- **Bash stop race fix**: `_stop_task` was waiting for the process to exit (up to 2s) before returning. During this wait, the monitor thread could call `on_fail` before `TaskStopTool` called `registry.kill()`, leaving the record in `failed` instead of `killed`. Removing the blocking `process.wait()` from `_stop_task` ensures `registry.kill()` wins the race.

## Verification

- `tests/integration/background_tasks/` — 15 passed
- `tests/unit/agent/background_tasks/` — 17 passed
- `tests/unit/agent/tools/` — 26 passed (agent + bash + task_stop)
- `tests/unit/test_local_coding_profile.py` + `test_product_profiles.py` — 14 passed
- Total feature 337 related tests: **101 passed**
