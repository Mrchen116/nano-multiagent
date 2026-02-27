# TASKS (Current Milestone: M13R)

## [DONE] R13R.1 system prompt 模板对齐
- Steps:
  - 新增 system prompt 模板红测，固定 `Available tools/Guidelines/datetime/cwd` 缺口（Red）。
  - 将 `内核设计细化/系统提示词.md` 作为模板源，完成运行时占位填充。
  - 保持 skills 注入机制并验证输出结构。
  - 运行目标测试并记录证据。
- Expected Tests:
  - `tests/unit/test_agent_prompting.py`
  - `tests/contract/test_system_prompt_contract.py`
  - `tests/integration/test_prompt_runtime_fill_integration.py`
  - `tests/e2e/test_system_prompt_render_e2e.py`
- DoD:
  - R13R.1 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13R.1 hash 与证据
- Commits:
  - `3fd75c2` | `3e465c3` | `30d325b`

## [DONE] R13R.2 tools/task 契约修复
- Steps:
  - 新增 task 参数契约与 load_skills 红测，固定 `run_in_background`/互斥规则缺口（Red）。
  - 修复 `task` 参数面与执行分流，补齐技能注入路径。
  - 修复 skills 可见性与 `read` 沙箱可读范围冲突。
  - 跑目标测试并记录证据。
- Expected Tests:
  - `tests/unit/test_task_tool_schema.py`
  - `tests/contract/test_task_tool_contract.py`
  - `tests/integration/test_task_skills_integration.py`
  - `tests/e2e/test_task_load_skills_e2e.py`
- DoD:
  - R13R.2 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13R.2 hash 与证据
- Commits:
  - `c764024` | `5bacaf1` | `ee6c304`

## [DONE] R13R.3 Hook 关键事件与拦截契约补齐
- Steps:
  - 新增关键 hook 事件红测，固定 `run_abort` 缺口（Red）。
  - 接入 `before_agent_start.message` 到主流程，并确保回归通过。
  - 对齐 `tool_result` 字段语义测试基线。
  - 运行目标测试并记录证据。
- Expected Tests:
  - `tests/unit/test_hook_event_coverage.py`
  - `tests/unit/test_agent_runtime_hooks.py`
  - `tests/contract/test_hook_integration_contract.py`
  - `tests/integration/test_m8_agent_tool_hook_r81_integration.py`
- DoD:
  - R13R.3 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13R.3 hash 与证据
- Commits:
  - `e4fa2c7` | `b9283ae` | `82a7595`

## [TODO] R13R.4 Hook 生命周期全事件与示例补齐
- Steps:
  - 新增 `session_start/session_compact/session_shutdown/run_error/run_timeout` 红测（Red）。
  - 在 runtime/compaction/runs 链路补齐事件触发。
  - 增加至少一个内置 hook 示例模块并验证加载链路。
  - 执行全量回归并收口 M13R。
- Expected Tests:
  - `tests/unit/test_hook_event_coverage.py`
  - `tests/contract/test_hook_intercept_contract.py`
  - `tests/integration/test_hook_critical_events_integration.py`
  - `tests/e2e/test_hook_error_timeout_abort_e2e.py`
- DoD:
  - R13R.4 目标测试红转绿
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13R.4 hash 与证据
