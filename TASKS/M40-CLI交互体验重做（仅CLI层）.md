# M40 - CLI交互体验重做（仅CLI层）

## Milestone Contract
- Milestone: `M40`
- Title: `CLI交互体验重做（仅CLI层）`
- Goal: 在不改内核前提下，重做 `src/nano_multiagent/cli` 的交互体验，使其从调试输出风格升级为可用 coding CLI，并改善 run 进行中的可交互能力。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/unit/test_cli_refactor_boundaries.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md（仅必要时）`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/core/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/runs/**`、`data/dev-tasks.json（由主 agent 维护）`
- Prevention Rules:
  - 必须保留非交互 `send-message` stdout 单 JSON 契约；禁止混入事件噪声。
  - 若目标需要新增/调整内核 API，停止实现并单列确认项，不直接改内核。
  - 先实现“运行中可输入并排队”的最小闭环，再做渲染增强。
  - 维持 HTTP-only 边界，CLI 不得直连 runtime internals。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `86 passed, 34 warnings`

## Roadpoints

### R1 运行中输入排队与顺序执行（DONE）
- Acceptance:
  - REPL 在 run 进行中不阻塞输入主循环，可继续输入下一条需求。
  - 新输入按 FIFO 排队发送，保持会话一致性与消息顺序。
  - /exit 时若存在运行中与排队任务，行为明确（等待 drain 并退出）。
  - 不改内核接口，仅在 CLI 层实现。
- Tests Plan:
  - unit: 选；覆盖队列调度、顺序、退出 drain 行为。
  - contract: 选；确保 `send-message` 仍单 JSON 且不走异步 REPL 事件路径。
  - integration: 选；真实 CLI+HTTP 流程验证“运行中继续输入并排队”。
  - e2e: 不选；当前仓库 CLI e2e 由 integration 入口覆盖。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_queues_user_input_while_previous_async_run_is_in_progress`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_send_message_command_keeps_single_json_stdout_contract_with_async_capable_client`
- DoD:
  - 新测试先红后绿。
  - 全量 `test_command` 通过。
  - C1/C2/C3 提交齐全并记录哈希到 PROGRESS。
- Commits:
  - C1: `af06611`
  - C2: `43d4d1e`
  - C3: `9d4e60f`
- Status: `DONE`

### R2 REPL 结构化渲染（状态/工具/回答/错误/用量）（DONE）
- Acceptance:
  - 默认 REPL 不再输出原始 JSON 与逐行调试事件日志。
  - 每轮输出结构化分区：状态、工具、回答、错误、用量。
  - 异步事件的关键信息（工具开始/结束、retry 进度）在结构化视图可见。
  - 非交互命令（`send-message`）输出契约不受影响。
- Tests Plan:
  - unit: 选；覆盖结构化文本分区、失败态与 usage 展示。
  - contract: 选；锁定单命令 JSON 契约与 HTTP-only 边界。
  - integration: 选；真实入口验证结构化展示关键词。
  - e2e: 不选；同 R1。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_structured_turn_sections_for_async_flow`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_prints_structured_error_section_for_failed_run`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - 结构化输出覆盖成功与失败两类路径。
  - `send-message` 合同无回归。
  - 全量 `test_command` 通过。
  - C1/C2/C3 提交齐全并记录哈希到 PROGRESS。
- Commits:
  - C1: `fb14031`
  - C2: `8879691`
  - C3: `ee04073`
- Status: `DONE`

### R3 CLI 层回归收口与边界固化（DONE）
- Acceptance:
  - 关键边界（HTTP-only、非交互 JSON、模块边界）保持稳定。
  - 新增/调整的测试纳入现有门禁并全部通过。
  - M40 文档补齐：设计取舍、证据、回滚点、提交哈希。
- Tests Plan:
  - unit: 选；复跑全部 unit 目标。
  - contract: 选；复跑全部 contract 目标。
  - integration: 选；复跑 CLI HTTP 流程。
  - e2e: 不选；该里程碑聚焦 CLI 层。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason`
  - 完整门禁命令（同 Baseline Gate）
- DoD:
  - 门禁全绿。
  - TASKS/PROGRESS 记录完整。
  - C1/C2/C3 提交齐全并记录哈希到 PROGRESS。
- Commits:
  - C1: `f9173dc`
  - C2: `eb14cda`
  - C3: `ee04073`
- Status: `DONE`

## Final Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `92 passed, 38 warnings`
