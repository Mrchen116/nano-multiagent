# M59 - 工具契约对齐-task 返回文本模板

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_task_tool_blocking.py tests/unit/test_task_tool_non_blocking.py tests/contract/test_task_tool_contract.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py tests/e2e/test_task_tool_non_blocking_e2e.py`
- Result:
  - `14 passed, 14 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 当前 `task` 返回结构化 payload，与设计稿“直接返回字符串模板”不一致。
  - 约束：仅改 task 工具与指定测试，不触碰 CLI 范围。
- Decision:
  - 将 M59 收敛为单一 Roadpoint `R59.1`，以“先红后绿”一次完成四路径模板 + 错误模板 + 校验优先级验证。
- Rationale:
  - 变更核心集中在 `task.py` 输出层，单 Roadpoint 可最小化并行冲突与回滚成本。
- Evidence:
  - Tests: 基线门禁全绿（`14 passed`）。
  - Entry: 目标入口均通过 `tool.run` 与 `tool_registry.execute` 可直达验证。
- Rollback:
  - 回退到本计划提交前稳定点。
- Commits: C1=`a3112eb`, C2=`9ac2dce`, C3=`本提交`
- Next:
  - R59.1 完成后更新 `data/dev-tasks.json` 为 `DONE`。

### R59.1 task 返回文本模板收口（四路径 + 错误模板）
- Context:
  - `task` 仍返回结构化对象，无法满足设计稿要求的字符串模板输出。
  - 约束：保留 continuation 优先级与现有 session 续跑能力，仅在允许范围内最小改动。
- Decision:
  - 将 `TaskTool.run` 改为直接返回字符串，并将 blocking/non-blocking + continuation 四路径统一模板化。
  - 保留原参数语义：`load_skills` 严格数组校验；新增 `run_in_background` 布尔硬校验；`session_id` 存在时优先走 continuation，跳过新任务互斥校验。
  - registry/e2e 路径保持兼容：由 `ToolRegistry` 将字符串包装为 `{\"result\": \"...\"}`。
- Rationale:
  - 在不改 registry/CLI 的前提下，将变更聚焦在 `task.py` 输出层与对应测试，避免跨模块联动风险。
- Evidence:
  - Tests:
    - 红测（C1）：`PYTHONPATH=src pytest -q tests/unit/test_task_tool_blocking.py tests/unit/test_task_tool_non_blocking.py tests/contract/test_task_tool_contract.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py tests/e2e/test_task_tool_non_blocking_e2e.py` -> `12 failed, 3 passed`（旧结构化返回不满足新契约）。
    - 绿测（C2）：同命令 -> `15 passed, 14 warnings`。
  - Entry:
    - `tool.run(...)` 直接返回文本模板；
    - `tool_registry.execute(\"task\", ...)` 返回 `{\"result\": \"<template>\"}`；
    - 四路径模板均包含 `<task_metadata>` 与 `session_id` 行。
- Rollback:
  - `a3112eb`（R59.1 红测提交）。
- Commits: C1=`a3112eb`, C2=`9ac2dce`, C3=`本提交`
- Next:
  - 更新 `data/dev-tasks.json` 中 `M59` 为 `DONE` 并写入 result。
