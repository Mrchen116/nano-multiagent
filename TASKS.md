# TASKS (Current Milestone: M11)

## [DONE] R11.1 task 契约冻结与 Red 基线
- Steps:
  - 新增 `task` 工具四类失败测试，先固定 schema 与错误契约缺口（Red）。
  - 明确 `X-Session-Id` 透传约束与 `task.session_id` 语义边界的 contract 断言。
  - 在不实现功能的前提下验证红测失败点与预期一致并记录证据。
- Expected Tests:
  - `tests/unit/test_task_tool_schema.py`
  - `tests/contract/test_task_tool_contract.py`
  - `tests/integration/test_task_runtime_wiring_integration.py`
  - `tests/e2e/test_task_tool_blocking_e2e.py`
- DoD:
  - 红测失败与预期缺口一致，失败原因可复现（`4 failed`）
  - C1/C2/C3 三次提交链完成：`f7d3f71` / `d0e4160` / `9559922`
  - 四文档已写入 R11.1 hash 与证据（R11.2 C3 回填 R11.1 C3 真实 hash）；下一步 `R11.2 Red`

## [DONE] R11.2 task blocking 模式最小闭环
- Steps:
  - 实现 `task(mode=blocking)` 的最小执行路径，支持主流程等待子任务返回。
  - 补齐错误路径（超时/子任务失败）并保持统一错误结构。
  - 跑 R11.2 目标测试并验证主链路不被异常 Hook/工具结果破坏。
- Expected Tests:
  - `tests/unit/test_task_tool_blocking.py`
  - `tests/contract/test_task_tool_contract.py`
  - `tests/integration/test_task_blocking_integration.py`
  - `tests/e2e/test_task_tool_blocking_e2e.py`
- DoD:
  - R11.2 目标测试红转绿：`5 failed` -> `8 passed in 0.47s`
  - C1/C2/C3 三次提交完整：`5a55783` / `868fcfb` / `c77293c`
  - 四文档已记录 blocking 证据与下一步 `R11.3 Red`

## [DONE] R11.3 task non_blocking 模式与可追踪回执
- Steps:
  - 实现 `task(mode=non_blocking)` 返回任务回执并异步执行。
  - 将任务状态追踪接入现有 session/event 机制，保证可观察性。
  - 跑 R11.3 目标测试与全量验收，收口 M11。
- Expected Tests:
  - `tests/unit/test_task_tool_non_blocking.py`
  - `tests/contract/test_task_tool_contract.py`
  - `tests/integration/test_task_non_blocking_integration.py`
  - `tests/e2e/test_task_tool_non_blocking_e2e.py`
- DoD:
  - R11.3 目标测试红转绿：`6 failed` -> `8 passed in 0.34s`
  - `pytest -q` 全绿：`131 passed in 4.65s`
  - C1/C2/C3 三次提交完整：`0bcea2f` / `7570d8f` / `ac5ed40`
