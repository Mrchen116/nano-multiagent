# M2: Platform Background Task Adapters — Progress

## Status

Completed. All 32 unit tests pass (18 M1 + 14 M2).

## What was built

### Platform files created

| File | Purpose |
|---|---|
| `src/agent/platform/background_tasks/__init__.py` | Package exports |
| `src/agent/platform/background_tasks/task_store.py` | `InMemoryTaskStore` — memory dict + optional manifest JSONL append |
| `src/agent/platform/background_tasks/file_output.py` | `BashFileOutput` — workspace-relative path, thread-safe append, 256 MiB cap |
| `src/agent/platform/background_tasks/shell_runner.py` | `ShellRunner` — `subprocess.Popen` with stdout/stderr pump threads, timeout, stop |
| `src/agent/platform/background_tasks/runtime_runner.py` | `RuntimeRunner` — wraps async `AgentRuntime.run()` in background thread with `RunController` stop handle |
| `src/agent/platform/background_tasks/wiring.py` | `wire_background_tasks()` assembly + notification delivery via `RunsRegistry` |

### Minor M1 protocol fix

- `BackgroundSubagentRunner.start()` gained `parent_session_id` parameter so `AgentRuntime.run()` can resolve subagent session JSONL paths.
- `run_subagent_lifecycle()` updated to forward `record.parent_session_id`.

### Notification delivery

`wiring.py` injects a `_NotifyingStore` wrapper: when the store receives an `update` for a terminal record, it calls `_deliver_notification()` which:

1. Builds `<task-notification>` XML via `build_task_notification_xml()`.
2. Checks if parent session has an active run via `RunsRegistry.get_active_run_id()`.
3. If active: injects the XML as a pending message via `inject_pending_message()`.
4. If idle: submits a new run via `runs.submit(origin=BACKGROUND_TASK, source_task_id=task_id)`.

### Tests

| Test category | Count | Coverage |
|---|---|---|
| Clock | 2 | `now_iso` / `now_ms` |
| Store round-trip | 3 | insert/update/get, list_non_terminal, manifest append |
| File output | 4 | path creation, append, stderr prefix, 256 MiB cap |
| Shell runner | 4 | exit 0 complete, exit 1 fail, stop terminates, timeout kills |

## Next

M3: Session Store Metadata Query — add `find_session_by_metadata()` to `JsonlSessionStore` for agent_id → session recovery after kernel restart.
