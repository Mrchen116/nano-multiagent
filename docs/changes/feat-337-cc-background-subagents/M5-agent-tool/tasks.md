# M5: Agent Tool (Replace TaskTool) — Roadpoint Plan

## Goal

Replace the existing `task` tool with a new `Agent` tool that supports:
- `Agent(run_in_background=true)` → register + start worker + return async_launched
- `Agent(run_in_background=false)` → register + start worker + wait up to 120s + auto-background if timeout
- `Agent(agent_id=..., prompt=...)` → resolve agent (memory → JSONL rehydrate) + queue message or resume
- Worker completion delivers `<task-notification>` to parent via RunsRegistry

## Roadpoints

### RP1: Tool Infrastructure Wiring
- Modify `wiring.py` to expose `deliver_notification` as a public function and add `runs_registry` to `BackgroundTaskWiring`
- Modify `platform/tools/loader.py` to pass `wiring` to `builtin_tools()`
- Modify `platform/http_api/app.py` to create `BackgroundTaskWiring` and pass it to `build_tool_registry()`

### RP2: Create AgentTool
- Create `src/agent/platform/tools/builtins/agent.py` with `AgentTool` class
- Implement background launch, foreground with auto-background, and continuation
- Implement result formatting aligned with CC style

### RP3: Replace TaskTool Registration
- Modify `src/agent/platform/tools/builtins/__init__.py` to replace `TaskTool` with `AgentTool`
- Update toolsets in both products (`local_coding`, `personal_assistant`) to use "agent" instead of "task"

### RP4: Tests
- Unit tests for background launch, foreground auto-background, continuation, message queuing, JSONL rehydrate

## Exit Criteria
- `pytest tests/unit/agent/tools/ -q` passes
- Agent tool background/foreground/continuation paths verified
