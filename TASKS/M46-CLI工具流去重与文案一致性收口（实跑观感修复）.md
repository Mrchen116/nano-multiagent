# M46 - CLI工具流去重与文案一致性收口（实跑观感修复）

## Milestone Contract
- milestone_id: `M46`
- title: `CLI工具流去重与文案一致性收口（实跑观感修复）`
- goal: 修复 managed REPL 实跑中的工具事件重复、Tool 文案风格不一致与队列模式摘要重复问题，让工具过程信息层次稳定可读。
- execution_mode: `serial`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M46`
- branch: `milestone/M46`
- gate:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`

## Scope Guard
- Allowed:
  - `src/nano_multiagent/cli/**`
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
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
- Prevention:
  - 不改内核；仅改 CLI 层。
  - `send-message` 单命令 stdout JSON 契约不变。
  - `run_id` 过滤 + `event_id` 去重不能回归。
  - 严格先红后绿（C1/C2/C3）。
  - 必须附 managed CLI 实跑片段。

## Baseline
- Result: `103 passed, 42 warnings`（2026-03-04）

## Roadpoints

### R1 队列模式工具事件去重（含无 event_id 回放）
- Acceptance:
  - 同一工具调用在队列模式下不重复输出 `start`/`exit` 关键线。
  - 历史回放无 `event_id` 时仍能去重，不因 `event_id` 缺失产生重复。
  - `run_id` 过滤语义保持，跨 run 事件不会混入当前输出。
  - 非交互单命令 `send-message` 输出契约不受影响。
- Tests Plan:
  - unit: 选；新增 REPL 异步事件回放/无 `event_id` 场景回归。
  - contract: 不新增；本 Roadpoint 不改命令输出结构，依赖门禁 contract 套件守护。
  - integration: 选；补队列 REPL 场景下工具线不重复断言。
  - e2e: 不在本 Roadpoint 执行；集中在 R3 用 managed CLI 完成。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_...`（新增：无 event_id 回放去重）
  - `tests/unit/test_cli_main.py::test_run_cli_repl_...`（新增：队列模式 start/exit 去重）
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_...`（新增：队列摘要不重复）
- DoD:
  - C1 红测提交 + C2 代码提交 + C3 文档提交。
  - 门禁命令全绿。
- Status: `TODO`

### R2 Tool 文案一致性与“预览已出则摘要不重播”
- Acceptance:
  - 工具实时预览与最终摘要统一采用 `Tool: ` 前缀风格。
  - 若实时预览已输出关键工具线，最终摘要不重复同一信息。
  - 仍保留必要状态/usage/assistant 主摘要，不丢关键信息。
  - 现有工具多次调用、bash 流式片段聚合行为不回归。
- Tests Plan:
  - unit: 选；覆盖 `Tool:` 前缀统一与“preview->summary 去重”行为。
  - contract: 不新增；依赖现有 `send-message` JSON contract 门禁。
  - integration: 选；覆盖真实 HTTP REPL 输出文案一致性。
  - e2e: 不在本 Roadpoint 执行；集中在 R3 managed 实跑。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_...`（新增：preview 与 summary 文案一致）
  - `tests/unit/test_cli_main.py::test_run_cli_repl_...`（新增：preview 已输出时 summary 去重）
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events`
- DoD:
  - C1/C2/C3 完整提交链。
  - 门禁命令全绿。
- Status: `TODO`

### R3 收口（全量门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Acceptance:
  - 指定门禁全绿。
  - 真实 managed CLI 实跑（工具过程可读）片段留证。
  - 里程碑分支 rebase 到 `origin/main` 后完成合并与 push。
  - `data/dev-tasks.json` 中 M46 更新为 `DONE` 且写入 result。
- Tests Plan:
  - unit/contract/integration: 执行完整 gate。
  - e2e: managed CLI 真实入口验证（非 mock）。
- Expected Tests:
  - gate 命令（同上）
  - managed CLI 命令：`PYTHONPATH=src ... /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed ...`
- DoD:
  - R1/R2 均 `DONE`。
  - 合并、push、dev_tasks 更新证据齐全。
- Status: `TODO`
