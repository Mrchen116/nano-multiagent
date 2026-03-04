# M43 - CLI发布级界面收口（低噪声+可读状态线+命令交互收敛）

## Milestone Contract
- Milestone: `M43`
- Title: `CLI发布级界面收口（低噪声+可读状态线+命令交互收敛）`
- Goal: 在不改内核前提下，把 CLI 默认交互从调试输出风格收敛为发布级界面，减少噪声并提升命令输入体验。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/unit/test_sdk_client.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_cli_error_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 不改内核；仅改 CLI 渲染与交互。
  - 保留 `send-message` 单 JSON stdout 契约。
  - 保留 `run_id` 过滤 + `event_id` 去重行为。
  - 默认 REPL 以可读状态线和过程摘要为主，不暴露裸调试标签风格日志。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `98 passed, 40 warnings`

## Roadpoints

### R1 默认 REPL 输出降噪（状态线+工具摘要发布化）
- Acceptance:
  - 默认 REPL 不再输出 `[status]/[progress]/[tool]/[usage]` 形式的裸标签日志。
  - 成功与失败场景都保留可操作信息（状态、错误层、建议、用量）。
  - 运行过程工具事件仍可见，但以更自然、紧凑的人类可读文案呈现。
  - 不影响 `send-message` 命令模式输出契约。
- Tests Plan:
  - unit: 选；覆盖成功/失败摘要文案与工具过程文案。
  - contract: 选；锁定单命令 JSON 契约不被 REPL 改动污染。
  - integration: 选；覆盖真实 HTTP 入口 REPL 输出形态。
  - e2e: 不选；本里程碑沿用已有 integration 入口。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_error_summary_for_failed_run`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_prints_compact_sections_in_async_turn_output`
- DoD:
  - 红测先失败后通过。
  - 全量门禁全绿。
  - 完成 C1/C2/C3，PROGRESS 写明证据、回滚点、提交哈希。
- Commits:
  - C1: `ca4ec09`
  - C2: `189acff`
  - C3: `本提交（docs R1.1）`
- Status: `DONE`

### R2 `/` 命令提示交互收敛（不刷屏、不污染输入行）
- Acceptance:
  - 输入 `/` 时命令提示不再以多行菜单反复刷屏。
  - 命令补全/选择能力保留（↑/↓ + Enter 仍可用）。
  - `/help`、参数错误、未知命令的可操作提示保持可用。
  - 输入排队能力保持，不影响异步 run 交互路径。
- Tests Plan:
  - unit: 选；覆盖输入渲染不再出现菜单刷屏、命令选择仍可执行、错误提示可用。
  - contract: 选；验证错误输出契约未回归。
  - integration: 选；覆盖 REPL 命令交互真实入口。
  - e2e: 不选；同 R1。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_up_recalls_previous_command_line`
  - `tests/unit/test_cli_main.py::test_repl_input_engine_slash_menu_down_enter_fills_selected_command`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_slash_menu_selects_command_and_executes_it`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_rejects_invalid_command_arguments`
- DoD:
  - 红测先失败后通过。
  - 全量门禁全绿。
  - 完成 C1/C2/C3，PROGRESS 写明证据、回滚点、提交哈希。
- Commits:
  - C1: `TODO`
  - C2: `TODO`
  - C3: `TODO`
- Status: `TODO`

### R3 收口与验收（真实 managed 交互 + 集成）
- Acceptance:
  - 指定门禁测试全绿。
  - 亲自完成一次 `--mode managed` 真实 CLI 交互验收，并记录结果。
  - rebase `origin/main` 后无冲突完成 Milestone 整体合并与 push。
  - 使用脚本将 `M43` 更新为 `DONE`，写入 result（solution/tests/commits/new_rules）。
- Tests Plan:
  - unit: 选；跑完整门禁中的 unit。
  - contract: 选；跑完整门禁中的 contract。
  - integration: 选；跑完整门禁中的 integration。
  - e2e: 选；真实 managed CLI 交互验收一次。
- Expected Tests:
  - 完整门禁命令（同 Baseline Gate）
  - managed 验收命令：`PYTHONPATH=src python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - 全量门禁全绿 + managed 验收通过。
  - main 合并并 push。
  - `dev-tasks` 标记 DONE。
- Commits:
  - C1: `N/A（收口路标无独立红测提交）`
  - C2: `TODO`
  - C3: `TODO`
- Status: `TODO`
