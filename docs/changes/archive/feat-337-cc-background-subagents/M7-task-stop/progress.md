# M7: task_stop Tool — Progress

## Status

Completed. 6 new unit tests pass; registry terminal idempotency updated.

## What was built

### Files created

| File | Purpose |
|---|---|
| `src/agent/platform/tools/builtins/task_stop.py` | `TaskStopTool` — stop background subagent/bash by task_id |
| `tests/unit/agent/tools/test_task_stop_tool.py` | 6 unit tests covering stop, not-found, already-terminal, serialization |

### Files modified

| File | Change |
|---|---|
| `src/agent/platform/tools/builtins/__init__.py` | Added `TaskStopTool(wiring=wiring)` to `builtin_tools()` |
| `src/agent/platform/http_api/app.py` | Bind wiring to `task_stop` tool |
| `src/agent/products/local_coding/toolsets.py` | Added `task_stop` to `DEFAULT_TOOL_IDS` |
| `src/agent/products/personal_assistant/toolsets.py` | Added `task_stop` to `DEFAULT_TOOL_IDS` |
| `src/agent/core/background_tasks/registry.py` | Terminal transitions are now idempotent no-ops (return old record) instead of raising `ValueError` |
| `tests/unit/agent/background_tasks/test_background_tasks.py` | Updated `test_terminal_state_is_idempotent` to match no-op behavior |
| `tests/unit/test_local_coding_profile.py` | Updated expected tool ids to include `task_stop` |
| `tests/unit/test_product_profiles.py` | Updated expected tool ids to include `task_stop` |

## Design decisions retained

- **Terminal idempotency**: `complete`/`fail`/`kill` on an already-terminal record returns the existing record without raising. This prevents races between `task_stop` (which calls `registry.kill()`) and runner monitor threads (which call `registry.complete()` or `registry.fail()`).
- **Notification delivery**: `TaskStopTool` does not manually deliver notifications. It calls `registry.kill()`, and the `_NotifyingStore` wrapper in `wiring.py` detects the terminal transition and delivers the `<task-notification>` automatically.
- **Error codes**: Custom error conditions use `details={"code": ...}` since `ToolError` hardcodes `code="tool_error"`.
