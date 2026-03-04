# M44 - CLI发布级二次收敛（会话文案化+工具过程折叠）

## Milestone Contract
- Milestone: `M44`
- Title: `CLI发布级二次收敛（会话文案化+工具过程折叠）`
- Goal: 在 M43 基础上进一步去噪，把 REPL 主阅读流收敛为会话优先：新会话不再原始 JSON 直出，工具过程默认折叠为关键节点摘要。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/unit/test_sdk_client.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_cli_error_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 不改内核；如需内核支持只在 PROGRESS 记录未实施建议。
  - `send-message` 单 JSON stdout 契约必须保持。
  - `run_id` 过滤 + `event_id` 去重必须保持。
  - 默认输出遵循 `event -> semantic -> render`，不暴露原始事件术语。
  - 输出降噪优先，保证会话主内容优先可读。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `101 passed, 40 warnings`
  - Verified at `2026-03-04`

## Handover Context
- 接手来源：上一位 worker 中断，当前分支尚无 M44 功能提交，仅有未提交文档草稿。
- 当前状态：已复核约束/范围并完成基线复跑，全绿。
- 执行顺序：`R1（会话文案） -> R2（工具过程折叠） -> R3（门禁+managed验收+main集成+dev_tasks更新）`

## Roadpoints

### R1 会话创建文案化（去 JSON 直出）
- Acceptance:
  - 新会话创建时（自动建会话与 `/new`）输出人类可读文案，不直出原始 JSON。
  - 会话切换/查看信息遵循 REPL 可读文案风格，不破坏现有命令语义。
  - 会话主阅读流保持“Assistant/State/Tool/Usage”优先。
  - `send-message`、`create-session` 单命令 JSON 契约不受影响。
- Tests Plan:
  - unit: 选；覆盖自动建会话与 `/new` 文案输出、去 JSON 回归。
  - contract: 选；锁定单命令 JSON 契约未受 REPL 改动影响。
  - integration: 选；覆盖 HTTP 入口 REPL 新会话文案输出。
  - e2e: 不选；R3 统一做 managed 真实验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_supports_required_commands`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_use_switches_active_session`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_slash_menu_selects_command_and_executes_it`
  - `tests/contract/test_cli_http_only_contract.py::test_cli_send_message_command_prints_single_line_json_stdout`
- DoD:
  - 红测先失败后通过。
  - 全量门禁命令全绿。
  - 完成 C1/C2/C3 并在 PROGRESS 记录证据、回滚点、哈希。
- Commits:
  - C1: `TBD`
  - C2: `TBD`
  - C3: `TBD`
- Status: `DOING`

### R2 工具过程折叠（关键节点摘要优先）
- Acceptance:
  - 默认工具过程仅展示关键节点（start/exit/error/关键进度），低价值明细（如 running/chunk）默认隐藏。
  - 工具过程保留长输出截断摘要能力（head + ellipsis + tail）。
  - 保持异步 REPL 正确性：`run_id` 过滤、`event_id` 去重、输入排队不回归。
  - 输出遵循语义化文案，不直露原始事件术语。
- Tests Plan:
  - unit: 选；覆盖工具节点折叠、错误与截断、排队与过滤去重不回归。
  - contract: 选；CLI 错误契约与 HTTP-only 契约不回归。
  - integration: 选；覆盖 async tool 流、bash tool 执行流、队列场景。
  - e2e: 不选；R3 统一做 managed 真实验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution`
  - `tests/unit/test_cli_main.py::test_send_message_with_async_events_truncates_long_tool_output_with_head_and_tail`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_uses_async_events_with_run_filter_and_dedup`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running`
- DoD:
  - 红测先失败后通过。
  - 全量门禁命令全绿。
  - 完成 C1/C2/C3 并在 PROGRESS 记录证据、回滚点、哈希。
- Commits:
  - C1: `TBD`
  - C2: `TBD`
  - C3: `TBD`
- Status: `TODO`

### R3 收口验收与集成（managed 真机验收 + main 集成）
- Acceptance:
  - 指定门禁命令全绿。
  - 真实 `--mode managed` CLI 交互验收完成，并记录前后对比片段。
  - rebase `origin/main` 成功后无冲突合并到 `main` 并 push。
  - 用脚本更新 `data/dev-tasks.json`，将 `M44` 标记 `DONE` 并写入 result。
- Tests Plan:
  - unit: 选；执行门禁中的所有 unit。
  - contract: 选；执行门禁中的所有 contract。
  - integration: 选；执行门禁中的所有 integration。
  - e2e: 选；执行一次真实 managed CLI 交互验收。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - 全量门禁 + managed 验收通过。
  - main 合并并 push。
  - `dev-tasks` 更新完成。
- Commits:
  - C1: `N/A（收口路标无独立红测提交）`
  - C2: `N/A（收口路标无实现代码提交）`
  - C3: `TBD`
- Status: `TODO`
