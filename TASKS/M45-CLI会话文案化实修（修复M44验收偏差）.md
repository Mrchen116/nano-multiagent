# M45 - CLI会话文案化实修（修复M44验收偏差）

## Milestone Contract
- milestone_id: `M45`
- title: `CLI会话文案化实修（修复M44验收偏差）`
- goal: 修复 REPL 路径中会话相关 JSON 直出，确保自动建会话与 `/new` `/use` `/session` 全部改为人类文案。
- execution_mode: `serial`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M45`
- branch: `milestone/M45`
- gate:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`

## Scope Guard
- Allowed:
  - `src/nano_multiagent/cli/**`
  - `tests/unit/test_cli_main.py`
  - `tests/unit/test_cli_refactor_boundaries.py`
  - `tests/unit/test_sdk_client.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
  - `TASKS/**`
  - `PROGRESS/**`
  - `LOGBOOK.md`（仅必要时）
- Forbidden:
  - `src/nano_multiagent/server/**`
  - `src/nano_multiagent/runs/**`
  - `src/nano_multiagent/tools/**`
  - `src/nano_multiagent/hooks/**`
  - `src/nano_multiagent/agent/**`
  - `src/nano_multiagent/core/**`
  - `data/dev-tasks.json`
- Prevention:
  - 不改内核。
  - `send-message` 单 JSON stdout 契约不变。
  - `run_id` 过滤 + `event_id` 去重 + 排队不回归。

## Baseline
- Result: `101 passed, 40 warnings`（2026-03-04）

## Roadpoints

### R1 会话文案化实修（自动建会话 + /new /use /session）
- Acceptance:
  - 自动建会话不输出 JSON，输出文案提示。
  - `/new` `/use` `/session` 不输出 JSON，输出文案提示。
  - REPL 主路径不存在 `{"session_id": ...}` 会话直出。
  - `send-message` 仍保持单行 JSON 契约。
- Tests Plan:
  - unit: 选；覆盖 auto-create 与 `/new /use /session` 文案。
  - contract: 选；锁定 `send-message` JSON 契约未被污染。
  - integration: 选；覆盖 HTTP 链路下会话文案输出。
  - e2e: 选；通过 managed CLI 真实入口做会话命令验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_supports_required_commands`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_use_switches_active_session`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_auto_creates_session_before_first_message`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_end_to_end_flow_over_http`
  - `tests/contract/test_cli_http_only_contract.py::test_cli_send_message_command_prints_single_line_json_stdout`
- DoD:
  - 先红后绿。
  - 全量门禁全绿。
  - C1/C2/C3 三提交完成，PROGRESS 含证据/回滚点/哈希。
- Status: `TODO`

### R2 收口（全量门禁 + managed 验收 + main 集成 + dev_tasks DONE）
- Acceptance:
  - 全量门禁通过。
  - 使用 `/Users/czj/miniforge3/bin/python3` 的 managed CLI 验收片段可复核。
  - rebase/merge/push 完成。
  - 脚本更新 M45 为 `DONE`。
- Tests Plan:
  - unit/contract/integration: 全量门禁执行。
  - e2e: managed CLI 实跑并保留关键输出片段。
- Expected Tests:
  - 门禁命令（同上）
  - `printf '/new\n/session\n/use <id>\n/exit\n' | PYTHONPATH=src ... /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed ...`
- DoD:
  - R1 已 DONE。
  - 门禁与 managed 验收结果写入 PROGRESS。
- Status: `TODO`
