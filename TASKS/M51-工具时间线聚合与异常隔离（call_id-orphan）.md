# M51 - 工具时间线聚合与异常隔离（call_id/orphan）

## Milestone Contract
- Milestone: `M51`
- Title: `工具时间线聚合与异常隔离（call_id/orphan）`
- Goal: 按 `call_id` 聚合工具时间线，隔离 orphan 异常事件，减少跨调用串味，同时保持长输出与高频事件可读。
- Execution Mode: `parallel`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M51`
- Branch: `milestone/M51`
- Test Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_cli_error_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: 非 CLI 目录（`src/nano_multiagent/{core,server,agent,runs,tools,session,llm,hooks}/**`）
- Prevention Rules:
  - 只改 CLI 与指定测试文件，不动内核/API/运行时目录。
  - 保持 `send-message` 单行 JSON stdout 契约不变。
  - 保持 `run_id` 过滤 + 去重窗口语义不回退。
  - orphan 终态必须独立呈现，不能并入 active call 组。

## Startup Checklist
- [x] 已阅读：`LOGBOOK.md`
- [x] 已阅读：`内核设计蓝图.md`（仅边界参考）
- [x] 已阅读：`COMMENTING_GUIDE.md`，承诺遵守注释规范
- [x] Baseline Gate：`106 passed, 42 warnings`（2026-03-04）

## Roadpoints

### R1 call_id 时间线聚合与 orphan 隔离（核心语义）
- Acceptance:
  - 工具摘要聚合以 `call_id` 为主键，不因同名工具互相覆盖。
  - `tool_exec_exit/tool_end` 未命中 active call 时，输出独立 orphan 条目。
  - orphan 条目不覆盖已有 active timeline。
  - 保持 preview 阶段 `tool_start/tool_exec_started/tool_exec_exit` 幂等不回归。
- Tests Plan:
  - unit: 选；核心语义在 `event_pipeline/repl_events`，可纯单测锁定。
  - contract: 不选；R2/R3 统一跑门禁。
  - integration: 不选；R2/R3 覆盖入口链路。
  - e2e: 不选；R3 做 managed。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_build_repl_view_model_isolates_orphan_exec_exit_from_active_call_timeline`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_renders_orphan_tool_exit_as_isolated_timeline`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_groups_same_tool_name_events_by_call_id`
- DoD:
  - C1 红测提交、C2 实现提交、C3 文档提交齐全。
  - 全量门禁命令在 C2 前全绿。
- Status: `TODO`

### R2 高频事件可读性与异常指标收口
- Acceptance:
  - 高频 `tool_exec_chunk` 仍以聚合进度行呈现，不刷屏。
  - orphan 事件计数以可读进度行输出（如 `orphan_events=1`）。
  - 长输出截断逻辑不回归（head + ellipsis + tail）。
  - 工具摘要输出顺序稳定且可定位（start/progress/exit + orphan）。
- Tests Plan:
  - unit: 选；高频与可读性逻辑主要在渲染/聚合层。
  - contract: 选；保证错误/HTTP-only 契约不回归。
  - integration: 选；验证 CLI HTTP 异步事件链路。
  - e2e: 不选；R3 managed 验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_build_repl_view_model_reports_orphan_event_count_in_status_updates`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - 全量门禁命令全绿。
  - C1/C2/C3 提交齐全。
- Status: `TODO`

### R3 收口验收与集成（门禁 + managed + main + dev_tasks）
- Acceptance:
  - 全量门禁通过。
  - managed CLI 实跑通过并留存关键片段（含 orphan/聚合可读性证据）。
  - `rebase origin/main` 成功，合并到 `main` 并 `push origin main`。
  - 使用脚本更新 `data/dev-tasks.json`：`M51 -> DONE`（含 result）。
- Tests Plan:
  - unit: 选；执行全量门禁。
  - contract: 选；执行全量门禁。
  - integration: 选；执行全量门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - main 合并并 push。
  - `M51` 在 `dev_tasks` 中为 `DONE`。
- Status: `TODO`
