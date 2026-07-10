# M5: Agent Tool (Replace TaskTool) — Progress

## Status

Completed. Unit tests pass (13 new tests in `tests/unit/agent/tools/test_agent_tool.py` plus updated existing tests).

## What was built

### Files created

| File | Purpose |
|---|---|
| `src/agent/platform/tools/builtins/agent.py` | `AgentTool` — background/foreground/continuation subagent execution |
| `tests/unit/agent/tools/test_agent_tool.py` | 13 unit tests covering all AgentTool paths |
| `tests/unit/test_agent_tool_schema.py` | Contract tests for Agent tool schema (replaces `test_task_tool_schema.py`) |

### Files modified

| File | Change |
|---|---|
| `src/agent/platform/tools/builtins/__init__.py` | Replaced `TaskTool` with `AgentTool`; added `wiring` param to `builtin_tools()` |
| `src/agent/platform/tools/loader.py` | Added `wiring` param to `build_tool_registry()` |
| `src/agent/platform/http_api/app.py` | Creates `BackgroundTaskWiring`, passes to `build_tool_registry()`, binds to agent tool |
| `src/agent/products/local_coding/toolsets.py` | Changed default tool from `"task"` to `"agent"` |
| `src/agent/products/personal_assistant/toolsets.py` | Changed default tool from `"task"` to `"agent"` |
| `tests/unit/test_agent_runtime.py` | Updated `"task"` → `"agent"` references |
| `tests/unit/test_task_tool_with_resolver.py` | Updated test names and `"task"` → `"agent"` |
| `tests/unit/test_local_coding_profile.py` | Updated default tool ids assertion |
| `tests/unit/test_personal_assistant_profile.py` | Updated default tool ids assertion |
| `tests/unit/test_product_profiles.py` | Updated default tool ids assertion |
| `tests/unit/test_product_profile.py` | Updated default tool ids assertion |

### Files deleted

| File | Reason |
|---|---|
| `src/agent/platform/tools/builtins/task.py` | Replaced by `agent.py` |
| `tests/unit/test_task_tool_schema.py` | Replaced by `test_agent_tool_schema.py` |

## Design decisions retained

- `agent_id == task_id` for subagent tasks: main agent only sees one ID.
- Foreground auto-background uses `ThreadPoolExecutor` + `Future.result(timeout=120s)`. On timeout, registers task and starts watcher thread that updates registry when future completes.
- Continuation path: in-memory registry → running (queue message), terminal (resume), missing → JSONL rehydrate via `find_session_by_metadata` → resume or `ToolError(agent_not_found)`.
- `_make_on_complete` captures `agent_id` in closure because `RuntimeRunner.start()` passes `task_id=agent_session_id` but registry keys are `agent_id`.
- `ToolError` hardcodes `code="tool_error"`; custom codes like `agent_not_found` are placed in `details={"code": ...}`.

## Pre-existing failures

`test_app_factory_with_profile.py::test_create_app_with_profile_uses_resolver_skill_roots_over_legacy_codex` fails on clean HEAD (unrelated to M5 changes). Verified by `git stash` + `pytest`.
