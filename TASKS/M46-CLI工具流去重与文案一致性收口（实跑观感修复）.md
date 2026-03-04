# M46 - CLI工具流去重与文案一致性收口（实跑观感修复）

## Milestone Contract
- Milestone: `M46`
- Title: `CLI工具流去重与文案一致性收口（实跑观感修复）`
- Goal: 修复 managed REPL 实跑中的工具事件重复、Tool 文案风格不一致与队列模式摘要重复问题，让工具过程信息层次稳定可读。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 不改内核；只改 CLI 层。
  - `send-message` 单 JSON stdout 契约必须保持。
  - `run_id` 过滤 + `event_id` 去重不能回归。
  - 实跑 managed CLI 验收必须执行。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `105 passed, 42 warnings`（R3.2 全量门禁）

## Roadpoints

### R1 工具事件重复与文案风格红测约束
- Acceptance:
  - 队列模式下，工具实时预览与摘要不再重复 `start/started/exit`。
  - 无 `event_id` 的回放事件不会造成工具关键线重复。
  - 工具实时预览与摘要文案统一使用 `Tool:` 前缀风格。
- Tests Plan:
  - unit: 选；覆盖无 event_id 去重、实时预览/摘要去重、文案一致性。
  - integration: 选；覆盖 HTTP 入口下工具实时链路文案一致。
  - contract: 不选；本路标不改命令 JSON 契约。
  - e2e: 不选；在 R3 执行 managed 实跑验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_uses_async_events_with_run_filter_and_dedup`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events`
- DoD:
  - 红测先失败并锁定目标回归。
  - 提交 C1。
- Status: `DONE`

### R2 CLI 事件渲染去重与风格统一实现
- Acceptance:
  - 工具实时预览文案统一使用 `Tool:` 前缀。
  - 摘要渲染与预览格式兼容，不出现 `Tool: Tool: ...` 双前缀。
  - HTTP 集成链路中 `echo/bash` 工具预览文案统一为 `Tool:`。
- Tests Plan:
  - unit: 选；验证上述行为全部通过。
  - integration: 选；验证 HTTP 真实链路不回归。
  - contract: 选；确保 send-message 契约不受影响。
  - e2e: 不选；在 R3 执行 managed 实跑。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - 目标门禁全绿。
  - 完成 C2/C3。
- Status: `DONE`

### R3 收口验收与集成
- Acceptance:
  - 队列模式下最终摘要不复读已在实时预览输出的工具关键线（`start/started/exit`）。
  - 全量门禁通过。
  - managed CLI 实跑确认工具事件无重复且文案统一。
  - 分支 rebase/merge/push 完成，`dev-tasks` 更新 DONE。
- Tests Plan:
  - unit/integration/contract: 选；执行 milestone 门禁。
  - e2e: 选；managed CLI 脚本化验收。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - 完成“队列摘要去重”红测->绿测闭环（C1/C2/C3）。
  - main 合并并 push。
  - `data/dev-tasks.json` 更新为 DONE，记录结果与证据。
- Status: `DONE`
