# M59 - 工具契约对齐-task 返回文本模板

## Milestone Contract
- Milestone: `M59`
- Title: `工具契约对齐-task 返回文本模板`
- Goal: 将 `task` 工具返回从结构化对象切换为设计稿约定的字符串模板（background/sync/continuation/error），并保持现有 session 续跑能力。
- Scope:
  - Allowed: `src/nano_multiagent/tools/builtins/task.py`、`tests/unit/test_task_tool_blocking.py`、`tests/unit/test_task_tool_non_blocking.py`、`tests/contract/test_task_tool_contract.py`、`tests/integration/test_task_blocking_integration.py`、`tests/integration/test_task_non_blocking_integration.py`、`tests/e2e/test_task_tool_blocking_e2e.py`、`tests/e2e/test_task_tool_non_blocking_e2e.py`、`TASKS/PROGRESS` 里程碑文档
  - Forbidden: `src/nano_multiagent/cli/**`、`src/nano_multiagent/tools/builtins/read.py`、`src/nano_multiagent/tools/builtins/bash.py`、`src/nano_multiagent/tools/builtins/edit.py`、`src/nano_multiagent/tools/builtins/write.py`
- Prevention Rules:
  - 严格按 C1/C2/C3。
  - 仅解决 M59，不做额外重构。
  - 保持 continuation 优先级与参数校验语义。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_task_tool_blocking.py tests/unit/test_task_tool_non_blocking.py tests/contract/test_task_tool_contract.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py tests/e2e/test_task_tool_non_blocking_e2e.py`
- Result:
  - `14 passed, 14 warnings`（2026-03-04）

## Roadpoints

### R59.1 task 返回文本模板收口（四路径 + 错误模板）
- Acceptance:
  - `run_in_background=true/false` + `session_id` 有/无四路径都返回字符串模板。
  - 每条模板包含 `<task_metadata>`，且含 `session_id` 行。
  - continuation 优先级保持（有 `session_id` 时跳过新任务 `category/subagent_type` 二选一校验）。
  - 参数校验保持：`load_skills` 数组校验、`run_in_background` 布尔校验、新任务 `category/subagent_type` 互斥。
  - 失败路径返回错误字符串模板（非结构化错误对象）。
- Tests Plan:
  - unit: 选；覆盖四路径文本模板、错误模板、参数校验与 continuation 优先级。
  - contract: 选；保持 `/v1/tools` 中 task 输入契约不回退。
  - integration: 选；覆盖 registry 执行时文本结果包装与 session 透传。
  - e2e: 选；覆盖真实入口下 blocking/non-blocking 文本模板结果。
- Expected Tests:
  - `tests/unit/test_task_tool_blocking.py`
  - `tests/unit/test_task_tool_non_blocking.py`
  - `tests/contract/test_task_tool_contract.py`
  - `tests/integration/test_task_blocking_integration.py`
  - `tests/integration/test_task_non_blocking_integration.py`
  - `tests/e2e/test_task_tool_blocking_e2e.py`
  - `tests/e2e/test_task_tool_non_blocking_e2e.py`
- DoD:
  - C1 红测 -> C2 实现绿测 -> C3 文档完成。
  - 指定 `test_command` 全绿。
  - `PROGRESS` 写清决策/证据/回退点/提交哈希。
- Status: `TODO`
