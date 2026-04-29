# M8: System Prompt & Tool Description Integration — Progress

## Status

Completed. All unit tests pass; system prompt now includes `<task-notification>` rules.

## What was built

### Files modified

| File | Change |
|---|---|
| `src/agent/core/agent/prompting.py` | `_DEFAULT_TOOL_SPECS` updated from `"task"` to `"agent"` and added `"task_stop"`. `build_system_prompt()` now appends `BACKGROUND_TASK_PROMPT_BLOCK` to all rendered system prompts. |
| `src/agent/products/personal_assistant/prompts.py` | Updated `Agent` reference: changed `Use \`task\` to delegate` → `Use \`Agent\` to delegate complex or multi-step work to sub-agents.` |
| `src/agent/products/local_coding/prompts.py` | Already aligned in prior milestones; `Agent` tool name reflected in coding system prompt. |

### Files unchanged (already aligned)

- `src/agent/platform/tools/builtins/agent.py` — Schema and descriptions aligned with CC semantics in M5.
- `src/agent/platform/tools/builtins/bash.py` — Schema and descriptions aligned with CC semantics in M6.
- `src/agent/platform/tools/builtins/task_stop.py` — Schema and descriptions aligned with CC semantics in M7.
- `src/agent/core/background_tasks/notifications.py` — `BACKGROUND_TASK_PROMPT_BLOCK` defined in M1.

## Design decisions retained

- **Prompt block is core-owned**: `BACKGROUND_TASK_PROMPT_BLOCK` lives in `core/background_tasks/notifications.py` and is appended by `build_system_prompt()` in `core/agent/prompting.py`. Product layers do not invent their own notification rules.
- **Backward compatibility**: The prompt block is appended unconditionally to all system prompts that go through `build_system_prompt()`. Both `local_coding` and `personal_assistant` products benefit without individual changes.
- **Tool specs in prompting.py**: `_DEFAULT_TOOL_SPECS` now lists `"agent"` and `"task_stop"` instead of the old `"task"`, ensuring the fallback tool list shown in system prompts matches the actual available tools.

## Verification

- `tests/unit/agent/tools/test_agent_tool.py` — 8 tests pass
- `tests/unit/agent/tools/test_bash_tool.py` — 8 tests pass
- `tests/unit/agent/tools/test_task_stop_tool.py` — 6 tests pass
- `tests/unit/test_local_coding_profile.py` — expected tool ids include `task_stop`
- `tests/unit/test_product_profiles.py` — expected tool ids include `task_stop`
- `tests/unit/agent/background_tasks/test_background_tasks.py` — prompt block and notification XML tests pass
