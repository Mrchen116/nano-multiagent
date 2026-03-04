# M42 - CLI界面收敛：对齐Codex交互观感（独立并行修复）

## Milestone Contract
- Milestone: `M42`
- Title: `CLI界面收敛：对齐Codex交互观感（独立并行修复）`
- Goal: 在独立 worktree 中修复 REPL 真实终端行错位/缩进乱套，并将默认输出收敛为更紧凑、答案优先、工具过程清晰的 Codex 风格。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_cli_error_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 严禁内核改动；如需内核支持仅记“未实施建议”。
  - 优先修复终端错位/缩进乱套（P0），再做视觉收敛。
  - 默认 REPL 输出要自然会话化，避免每轮机械字段列表刷屏。
  - 运行中输入排队与非交互 `send-message` JSON 契约必须有回归测试。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `94 passed, 38 warnings`

## Roadpoints

### R1 终端渲染稳定化（并发输出不串行错位）
- Acceptance:
  - REPL 输入行渲染与后台 run 结果输出并发时，不再出现错位、残留缩进、菜单污染。
  - 多行事件内容（tool output/text）在预览路径统一单行化，避免把终端光标推入异常缩进区。
  - 输入中仍可接收后台结果，且下一次按键后提示行可正常恢复。
  - 不影响 `send-message` 单 JSON 输出。
- Tests Plan:
  - unit: 选；覆盖输入渲染中插入后台输出时的行恢复与事件预览单行化。
  - contract: 选；确认 `send-message` stdout 契约无污染。
  - integration: 选；覆盖 REPL 异步队列+输出共存场景。
  - e2e: 不选；仓内 CLI e2e 由 integration 入口替代。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_repl_input_external_output_replays_prompt_without_layout_break`
  - `tests/unit/test_cli_main.py::test_send_message_with_async_events_sanitizes_multiline_tool_preview`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - 红测先失败后通过。
  - 门禁全绿。
  - 形成 C1/C2/C3 并在 PROGRESS 记录证据/回滚点/提交哈希。
- Commits:
  - C1: `05f39bc`
  - C2: `b2c53ed`
  - C3: `79b8075`
- Status: `DONE`

### R2 输出信息架构收敛（答案优先 + 紧凑摘要）
- Acceptance:
  - 默认 REPL 单轮输出改为“答案优先 + 紧凑状态/工具/用量”，避免大块字段分区刷屏。
  - 工具过程仍可见且可读；错误展示保持分层（layer/suggestion）。
  - 运行中输入排队行为保持可用，且不与新渲染冲突。
  - 非交互 `send-message` 单 JSON 契约不变。
- Tests Plan:
  - unit: 选；覆盖新输出格式（成功/失败）与关键字段保留。
  - contract: 选；锁定单命令 JSON 契约与 HTTP-only 边界。
  - integration: 选；验证真实入口文本包含新风格关键信号。
  - e2e: 不选；同 R1。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_error_summary_for_failed_run`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - 红测先失败后通过。
  - 门禁全绿。
  - 形成 C1/C2/C3 并在 PROGRESS 记录证据/回滚点/提交哈希。
- Commits:
  - C1: `26a4694`
  - C2: `37d2935`
  - C3: `71d36b3`
- Status: `DONE`

### R3 收口与集成（门禁、文档、合并）
- Acceptance:
  - M42 范围内测试门禁全绿。
  - TASKS/PROGRESS 完整记录方案、证据、回滚点、提交哈希。
  - 分支 rebase 到 `origin/main` 后完成整体集成。
  - 使用脚本把 `data/dev-tasks.json` 中 M42 更新为 `DONE`（含 commits/tests/result）。
- Tests Plan:
  - unit: 选；复跑门禁中的全部 unit。
  - contract: 选；复跑全部 contract。
  - integration: 选；复跑 CLI HTTP 流程。
  - e2e: 不选；本里程碑无独立 e2e 入口。
- Expected Tests:
  - 完整门禁命令（同 Baseline Gate）
- DoD:
  - 全量门禁全绿。
  - main 集成成功并 push。
  - `dev-tasks` 标记 DONE。
- Commits:
  - C1: `N/A（收口路标无独立红测提交）`
  - C2: `9fcedb2`
  - C3: `本提交（docs R3.1）`
- Status: `DONE`
