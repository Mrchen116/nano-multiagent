# ROADMAP

## Project Conventions
- 入口类型: HTTP API (`FastAPI`), app factory 为 `nano_multiagent.server.app:create_app`
- 测试命令: `pytest -q`
- tests 映射:
  - `tests/unit`: 纯逻辑与边界
  - `tests/contract`: 协议与结构契约
  - `tests/integration`: 组件串联链路
  - `tests/e2e`: 真实入口主流程

## Milestone M0
- Title: 工程骨架 + 最小可用 HTTP
- Goal: 建立可运行项目骨架并打通健康检查与创建会话最小链路。
- Exit Criteria: `GET /v1/health` 与 `POST /v1/sessions` 主流程可用，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R0.1 | `a004a39` | `2f3d783` | `e407f14` | `pytest -q` -> `4 passed in 0.32s` |
| R0.2 | `123cbae` | `db3c09f` | `b8f1446` | `pytest -q` -> `8 passed in 0.34s` + minimal e2e |

## Milestone M1
- Title: core 契约层实现与冻结
- Goal: 落地并冻结 `core/types/events/errors/ids` 稳定契约。
- Exit Criteria: core 契约覆盖 unit/contract/integration/e2e 并通过，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R1.1 | `87b119e` | `0efbd91` | `0236df1` | `pytest -q` -> `19 passed in 0.51s` |

## Milestone M2
- Title: session 事件源与 sqlite 存储
- Goal: 完成会话事件模型、版本化序列化与 sqlite/jsonl 双存储，支持重建。
- Exit Criteria: manager 接线后会话可落盘并重建，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R2.1 | `c76fb5b` | `fc4dbdc` | `5dfaced` | 目标测试 `6 passed`；`pytest -q` -> `25 passed in 0.93s` |
| R2.2 | `b1ac468` | `75087c6` | `164ef59` | 目标测试 `4 passed`；`pytest -q` -> `29 passed in 0.33s` |

## Milestone M3
- Title: LLM 抽象层 + openai_compat provider
- Goal: 建立统一 LLM 抽象与 provider 工厂，完成 openai_compat 非流式链路。
- Exit Criteria: provider 可配置切换，LLM 请求带 `X-Session-Id`，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R3.1 | `3937147` | `92344bc` | `ece29e6` | 目标测试 `7 passed in 0.14s` |
| R3.2 | `58e5048` | `fd859fe` | `dd714a8` | e2e `1 passed`；`pytest -q` -> `37 passed in 1.76s` |

## Milestone M4
- Title: agent 最小闭环（无工具）
- Goal: 打通 runtime 文本主链路与 turn 事件落盘。
- Exit Criteria: text/image(parts 占位) -> context -> llm -> assistant 闭环可用，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R4.1 | `2fc990e` | `aa455be` | `132604e` | 目标测试 `10 passed in 0.13s` |
| R4.2 | `6912f2f` | `f60f488` | `ce43210` | 目标测试 `7 passed in 3.16s`；`pytest -q` -> `54 passed in 3.33s` |

## Milestone M5
- Title: server 主入口（同步优先）
- Goal: 完成 server 分层、会话接口与同步 `messages` 主入口。
- Exit Criteria: `POST /v1/sessions/{session_id}/messages` 同步链路可用，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R5.1 | `807e366` | `dfc66b0` | `bf653a4` | 目标测试 `9 passed in 0.48s` |
| R5.2 | `6b7dfe6` | `aa42097` | `46c86e1` | 目标测试 `6 passed in 0.35s`；`pytest -q` -> `64 passed in 4.14s` |

## Milestone M6
- Title: tools 子系统与安全护栏（不含 task）
- Goal: 完成内置 `read/write/edit/bash`、目录工具加载与最小安全策略。
- Exit Criteria: `/v1/tools` 返回内置+目录工具，工具执行具备沙箱与超时保护。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R6.1 | `aeab958` | `303d616` | `98cd165` | 目标测试 `14 passed in 1.31s`；`pytest -q` -> `78 passed in 5.01s` |

## Milestone M7
- Title: hooks 子系统（observe + intercept）
- Goal: 完成 Hook 基础层、双源加载、优先级/超时/异常隔离与拦截契约。
- Exit Criteria: observe/intercept 语义稳定，双源加载生效，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R7.1 | `6d84dc9` | `2da3a90` | `0ba7e76` | 目标测试 `7 passed in 0.04s`；`pytest -q` -> `85 passed in 5.55s` |

## Milestone M8
- Title: agent-tool-hook 深度集成
- Goal: 在 runtime/loop/tools 链路接入 Hook 触发点并补强集成回归。
- Exit Criteria: input/tool_call/tool_result 拦截生效，fail-open 生效，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R8.1 | `296e21b` | `fb77fe1` | `2aa5fae` | 目标测试 `10 passed in 0.31s`；`pytest -q` -> `95 passed in 4.40s` |
| R8.2 | `7e7fd18` | `532f34a` | `4fac5ba` | `pytest -q` -> `99 passed in 11.73s` |

## Milestone M9
- Title: skills 自动发现与 `/skill` 改写
- Goal: 支持 `<available_skills>` 注入与 `/skill:name` 输入改写。
- Exit Criteria: skills 非空时注入，`/skill` 改写进入常规推理链路，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R9.1 | `c71191c` | `ae706e2` | `fc30c3e` | 目标测试 `7 passed in 0.34s`；`pytest -q` -> `105 passed in 5.13s` |

## Milestone M10
- Title: compaction 子系统
- Goal: 完成 `policy/planner/applier/summarizer` 基线与 runtime preflight/overflow/manual 接线。
- Exit Criteria: threshold/overflow/manual 三路径可用并保留 `first_kept_event_id` 审计锚点，`pytest -q` 全绿。
- Status: Completed
- Evidence & Commits:

| Roadpoint | C1 | C2 | C3 | Evidence |
| --- | --- | --- | --- | --- |
| R10.1 | `d7950f0` | `5ac5758` | `ec6a086` | 目标测试 `10 passed in 0.12s` |
| R10.2 | `41fd8bf` | `e223a5b` | `0da8768` | 目标测试 `9 passed`；`pytest -q` -> `116 passed in 5.26s` |

## Milestone M11
- Title: `task` 工具与进程内 subagent 调度
- Goal: 交付 `task` 工具（`blocking/non_blocking`）并将 subagent 调度纳入 runtime 主链路。
- Exit Criteria:
  - `/v1/tools` 可见 `task` schema（含模式、超时、幂等键等关键参数）。
  - `blocking` 模式可等待子任务完成并回传结构化结果。
  - `non_blocking` 模式可返回可追踪任务标识并可在同节点完成执行。
  - subagent LLM 请求沿用主会话 `X-Session-Id`，且与 `task.session_id` 语义不混淆。
  - `pytest -q` 全绿，且 R11.* 保持 C1/C2/C3 证据链闭环。
- Status: Completed

### Roadpoint R11.1: task 契约冻结与 Red 基线
- Public Surface:
  - `src/nano_multiagent/tools/builtins/task.py`（新建）
  - `src/nano_multiagent/tools/registry.py`
  - `src/nano_multiagent/agent/runtime.py`
- Acceptance (3-5):
  - 定义 `task` 工具 schema（必填参数、模式枚举、错误码约束）。
  - 红测明确当前能力缺口：`task` 不可用或行为不符合契约。
  - 固定 `X-Session-Id` 传递规则与 `task.session_id` 语义边界。
  - 红测失败原因与预期一致。
- Tests Plan:
  - unit: `tests/unit/test_task_tool_schema.py`
  - contract: `tests/contract/test_task_tool_contract.py`
  - integration: `tests/integration/test_task_runtime_wiring_integration.py`
  - e2e: `tests/e2e/test_task_tool_blocking_e2e.py`
- Commit Plan:
  - C1: `test(R11.1): 固化task工具契约与红测基线（先红）`
  - C2: `feat(R11.1): 接入task工具最小链路（全绿）`
  - C3: `docs(R11.1): 记录task契约证据与下一步（记录hash/证据/下一步）`
- Commits:
  - C1: `f7d3f71`
  - C2: `d0e4160`
  - C3: `9559922`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_task_tool_schema.py tests/contract/test_task_tool_contract.py tests/integration/test_task_runtime_wiring_integration.py tests/e2e/test_task_tool_blocking_e2e.py` -> `4 failed`
  - 转绿（C2）: 同命令 -> `4 passed in 0.39s`
  - 入口约束: `test_task_tool_contract_is_exposed_by_tools_endpoint` 与 `test_tools_listing_contains_task_without_task_http_endpoint` 断言 `task` 仅经 ToolRegistry 暴露，无 `/v1/tasks` HTTP 入口
  - C3 收口: 四文档已记录真实 `R11.1 C3=9559922`，证据链闭环

### Roadpoint R11.2: blocking 模式最小闭环
- Public Surface:
  - `src/nano_multiagent/tools/builtins/task.py`
  - `src/nano_multiagent/agent/{runtime.py,loop.py}`
- Acceptance (3-5):
  - `task(mode=blocking)` 可在单节点内拉起 subagent 并等待完成。
  - 返回结果包含子任务输出、耗时与错误结构（失败时）。
  - 子任务执行失败不破坏主流程错误契约。
- Tests Plan:
  - unit: `tests/unit/test_task_tool_blocking.py`
  - contract: `tests/contract/test_task_tool_contract.py`
  - integration: `tests/integration/test_task_blocking_integration.py`
  - e2e: `tests/e2e/test_task_tool_blocking_e2e.py`
- Commit Plan:
  - C1: `test(R11.2): task blocking 链路失败用例（先红）`
  - C2: `feat(R11.2): 实现task blocking最小闭环（全绿）`
  - C3: `docs(R11.2): 记录blocking证据并更新下一步（记录hash/证据/下一步）`
- Commits:
  - C1: `5a55783`
  - C2: `868fcfb`
  - C3: `c77293c`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_task_tool_blocking.py tests/integration/test_task_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py` -> `5 failed`
  - 转绿（C2）: `pytest -q tests/unit/test_task_tool_schema.py tests/contract/test_task_tool_contract.py tests/integration/test_task_runtime_wiring_integration.py tests/unit/test_task_tool_blocking.py tests/integration/test_task_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py` -> `8 passed in 0.47s`
  - blocking 错误契约: `test_task_blocking_wraps_subagent_errors_without_raising` 与 `test_task_blocking_respects_timeout_seconds` 断言 `task_execution_failed/task_timeout` 结构化错误

### Roadpoint R11.3: non_blocking 模式与可追踪回执
- Public Surface:
  - `src/nano_multiagent/tools/builtins/task.py`
  - `src/nano_multiagent/session/manager.py`
  - `src/nano_multiagent/core/events.py`
- Acceptance (3-5):
  - `task(mode=non_blocking)` 返回可追踪任务标识并异步执行。
  - 主流程可继续推理，不阻塞当前回合。
  - 任务状态可通过已有会话/事件机制追踪。
- Tests Plan:
  - unit: `tests/unit/test_task_tool_non_blocking.py`
  - contract: `tests/contract/test_task_tool_contract.py`
  - integration: `tests/integration/test_task_non_blocking_integration.py`
  - e2e: `tests/e2e/test_task_tool_non_blocking_e2e.py`
- Commit Plan:
  - C1: `test(R11.3): task non_blocking 链路失败用例（先红）`
  - C2: `feat(R11.3): 实现task non_blocking与回执（全绿）`
  - C3: `docs(R11.3): 记录non_blocking证据并收口M11（记录hash/证据/下一步）`
- Commits:
  - C1: `0bcea2f`
  - C2: `7570d8f`
  - C3: `ac5ed40`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_task_tool_non_blocking.py tests/integration/test_task_non_blocking_integration.py tests/e2e/test_task_tool_non_blocking_e2e.py tests/contract/test_task_tool_contract.py` -> `6 failed`
  - 转绿（C2）: 同命令 -> `8 passed in 0.34s`
  - `X-Session-Id` 透传: `test_task_blocking_passes_parent_session_id_to_subagent_llm` 断言 `llm_client.requests[0].session_id == hook_context.session_id`，且 `task.session_id != 主会话`
  - non_blocking 回执/追踪: `test_task_non_blocking_returns_receipt_and_executes_in_background`、`test_task_non_blocking_executes_on_same_node_and_returns_receipt` 验证 `queued` 回执与同节点后台执行
  - M11 全量验收: `pytest -q` -> `131 passed in 6.08s`

## Milestone M12
- Title: 运行与事件流（SSE + runs 异步链路）
- Goal: 交付 `messages:async`、`runs/*` 与会话/全局 SSE 增量事件流，打通异步运行主链路。
- Exit Criteria:
  - `POST /v1/sessions/{session_id}/messages:async` 可提交异步运行并返回 `run_id`。
  - `GET /v1/runs/{run_id}` 与 `POST /v1/runs/{run_id}/cancel` 可用。
  - `GET /v1/events` 与 `GET /v1/sessions/{session_id}/events` 可输出 `text_delta/tool_start/tool_end/turn_end` 等事件。
  - 异步取消与中断行为一致，`pytest -q` 全绿。
- Status: Completed

### Roadpoint R12.1: async 提交与 run_id 生命周期基线
- Public Surface:
  - `POST /v1/sessions/{session_id}/messages:async`
  - `GET /v1/runs/{run_id}`
  - `server/routes/run.py`、`session/entries.py`（run 事件最小扩展）
- Acceptance (3-5):
  - 异步提交返回 `202` 与稳定 `run_id`。
  - `run_id` 状态最小集合可查询（queued/running/completed/failed/cancelled）。
  - run 事件可持久化并支持会话重建时读取。
  - 错误结构与 trace_id 兼容现有 server 统一错误格式。
- Tests Plan:
  - unit: `tests/unit/test_runs_registry.py`
  - contract: `tests/contract/test_runs_async_contract.py`
  - integration: `tests/integration/test_runs_store_integration.py`
  - e2e: `tests/e2e/test_messages_async_submission_e2e.py`
- Commit Plan:
  - C1: `test(R12.1): async提交与run状态契约红测（先红）`
  - C2: `feat(R12.1): 实现async提交与run状态最小闭环（全绿）`
  - C3: `docs(R12.1): 记录async提交证据并推进下一步（记录hash/证据/下一步）`
- Commits:
  - C1: `91cd896`
  - C2: `264eab5`
  - C3: `388d263`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_runs_registry.py tests/contract/test_runs_async_contract.py tests/integration/test_runs_store_integration.py tests/e2e/test_messages_async_submission_e2e.py` -> `1 error`（`ModuleNotFoundError: nano_multiagent.runs`）
  - 转绿（C2）: 同命令 -> `6 passed in 0.46s`
  - 持久化证据: `test_async_run_status_entries_persist_in_sqlite_store` 断言 `session.run.status` 事件序列为 `queued -> running -> completed`

### Roadpoint R12.2: run cancel 语义与中断一致性
- Public Surface:
  - `POST /v1/runs/{run_id}/cancel`
  - `agent/runtime.py`（异步运行取消钩子）
  - `server/routes/run.py`
- Acceptance (3-5):
  - `cancel` 对 queued/running 有效，对 terminal 状态幂等返回。
  - 取消后状态转移可审计，且不破坏会话事件链。
  - 取消语义与现有 `abort` 行为对齐（错误码/回执结构一致）。
- Tests Plan:
  - unit: `tests/unit/test_run_cancel.py`
  - contract: `tests/contract/test_run_cancel_contract.py`
  - integration: `tests/integration/test_run_cancel_integration.py`
  - e2e: `tests/e2e/test_run_cancel_e2e.py`
- Commit Plan:
  - C1: `test(R12.2): run cancel语义红测（先红）`
  - C2: `feat(R12.2): 实现run取消与状态流转（全绿）`
  - C3: `docs(R12.2): 记录cancel证据并推进下一步（记录hash/证据/下一步）`
- Commits:
  - C1: `145011a`
  - C2: `00c1ed5`
  - C3: `6150798`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_run_cancel.py tests/contract/test_run_cancel_contract.py tests/integration/test_run_cancel_integration.py tests/e2e/test_run_cancel_e2e.py` -> `6 failed`
  - 转绿（C2）: 同命令 -> `6 passed in 0.40s`
  - 取消审计证据: `test_cancelled_run_status_is_persisted_to_store` 断言 `session.run.status` 最终状态为 `cancelled`

### Roadpoint R12.3: SSE 全局/会话事件流
- Public Surface:
  - `GET /v1/events`
  - `GET /v1/sessions/{session_id}/events`
  - `server/sse.py`
- Acceptance (3-5):
  - SSE 输出最小事件集：`text_delta/tool_start/tool_end/turn_end/run_status`。
  - 会话级与全局级订阅都可工作，断连重连具备最小安全行为（无崩溃/无阻塞）。
  - 异步提交与 SSE 消费链路可串联验证。
- Tests Plan:
  - unit: `tests/unit/test_sse_encoder.py`
  - contract: `tests/contract/test_sse_event_contract.py`
  - integration: `tests/integration/test_sse_session_stream_integration.py`
  - e2e: `tests/e2e/test_async_run_sse_e2e.py`
- Commit Plan:
  - C1: `test(R12.3): SSE事件流红测（先红）`
  - C2: `feat(R12.3): 实现全局与会话SSE事件流（全绿）`
  - C3: `docs(R12.3): 记录SSE证据并收口M12（记录hash/证据/下一步）`
- Commits:
  - C1: `4fa2b61`
  - C2: `c99c593`
  - C3: `029a991`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_sse_encoder.py tests/contract/test_sse_event_contract.py tests/integration/test_sse_session_stream_integration.py tests/e2e/test_async_run_sse_e2e.py` -> `1 error`（`ModuleNotFoundError: nano_multiagent.server.sse`）
  - 转绿（C2）: 同命令 -> `5 passed in 1.07s`
  - 异步+SSE 串联: `pytest -q tests/unit/test_runs_registry.py tests/contract/test_runs_async_contract.py tests/integration/test_runs_store_integration.py tests/e2e/test_messages_async_submission_e2e.py tests/unit/test_run_cancel.py tests/contract/test_run_cancel_contract.py tests/integration/test_run_cancel_integration.py tests/e2e/test_run_cancel_e2e.py tests/unit/test_sse_encoder.py tests/contract/test_sse_event_contract.py tests/integration/test_sse_session_stream_integration.py tests/e2e/test_async_run_sse_e2e.py` -> `17 passed in 1.19s`
  - M12 全量收口: `pytest -q` -> `148 passed in 7.61s`

## Milestone M13
- Title: Hook 查询 API 与可观测性收口
- Goal: 交付 Hook 只读查询接口，并完成结构化日志/trace 关联字段收口。
- Exit Criteria:
  - `GET /v1/hooks/events` 返回事件清单、类型（observe/intercept）与返回契约摘要。
  - `GET /v1/hooks` 返回已加载 Hook 列表（含 source、订阅事件、priority、timeout_ms）。
  - 运行日志可关联 `session_id/turn_id/tool_call_id/trace_id`，`pytest -q` 全绿。
- Status: Completed

### Roadpoint R13.1: Hook 查询 API（events + registry）
- Public Surface:
  - `GET /v1/hooks/events`
  - `GET /v1/hooks`
  - `server/routes/hook.py`
- Acceptance (3-5):
  - `hooks/events` 返回事件名、类型（observe/intercept）、返回契约摘要。
  - `hooks` 返回模块名、路径、source、订阅事件、priority、timeout_ms。
  - 仅只读查询，无注册/更新/卸载写接口。
  - 响应结构与错误格式遵循现有 server 契约。
- Tests Plan:
  - unit: `tests/unit/test_hook_query_models.py`
  - contract: `tests/contract/test_hooks_query_contract.py`
  - integration: `tests/integration/test_hooks_registry_query_integration.py`
  - e2e: `tests/e2e/test_hooks_query_e2e.py`
- Commit Plan:
  - C1: `test(R13.1): hook查询接口红测（先红）`
  - C2: `feat(R13.1): 实现hooks只读查询接口（全绿）`
  - C3: `docs(R13.1): 记录hook查询证据并推进下一步（记录hash/证据/下一步）`
- Commits:
  - C1: `3578aad`
  - C2: `e1ccd61`
  - C3: `b653447`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_hook_query_models.py tests/contract/test_hooks_query_contract.py tests/integration/test_hooks_registry_query_integration.py tests/e2e/test_hooks_query_e2e.py` -> `1 error`（`ModuleNotFoundError: nano_multiagent.server.routes.hook`）
  - 转绿（C2）: 同命令 -> `6 passed in 0.39s`
  - 接口契约验证: `test_hooks_registry_contract_shape` 与 `test_hook_query_integration_orders_and_reports_registered_hooks` 断言 `source/module_name/file_path/priority/timeout_ms` 与排序稳定

### Roadpoint R13.2: 可观测性字段收口（日志/trace 关联）
- Public Surface:
  - `observability/logger.py`
  - `observability/tracing.py`
  - server/runtime/tools 关键日志输出点
- Acceptance (3-5):
  - 结构化日志统一包含 `session_id/turn_id/tool_call_id/trace_id` 关联字段。
  - 关键路径（run、tool、hook、error）至少各有一条可验证日志记录。
  - 日志字段在无上下文时行为稳定（空值或缺省，不抛异常）。
- Tests Plan:
  - unit: `tests/unit/test_observability_fields.py`
  - contract: `tests/contract/test_observability_contract.py`
  - integration: `tests/integration/test_trace_log_correlation_integration.py`
  - e2e: `tests/e2e/test_observability_chain_e2e.py`
- Commit Plan:
  - C1: `test(R13.2): 可观测性字段红测（先红）`
  - C2: `feat(R13.2): 完成日志与trace关联字段收口（全绿）`
  - C3: `docs(R13.2): 记录可观测性证据并收口M13（记录hash/证据/下一步）`
- Commits:
  - C1: `65348a0`
  - C2: `7ebde86`
  - C3: `d72863c`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_observability_fields.py tests/contract/test_observability_contract.py tests/integration/test_trace_log_correlation_integration.py tests/e2e/test_observability_chain_e2e.py` -> `4 errors`（`ModuleNotFoundError: nano_multiagent.observability`）
  - 转绿（C2）: 同命令 -> `5 passed in 0.44s`
  - 关联字段验证: `test_run_tool_hook_logs_share_correlation_fields` 断言 run/tool/hook 日志共享 `session_id/turn_id/tool_call_id/trace_id`
  - M13 全量收口: `pytest -q` -> `159 passed in 11.58s`

## Milestone M13R
- Title: 细化一致性优先修复（系统提示词 + 工具契约 + Hook/Skill关键差距）
- Goal: 对齐 `内核设计细化/` 与现状实现的高优先级偏差，恢复设计一致性基线。
- Exit Criteria:
  - system prompt 模板按 `内核设计细化/系统提示词.md` 落地（含工具段、guidelines、datetime、cwd 占位填充）。
  - `tools` 关键契约差距修复（至少覆盖 task 参数契约、load_skills、read 沙箱与 skills 可见性冲突）。
  - Hook 关键事件触发与 `before_agent_start.message` 契约补齐，`pytest -q` 全绿。
- Status: Expanded (Active)

### Roadpoint R13R.1: system prompt 模板对齐
- Public Surface:
  - `agent/prompting.py`
  - `内核设计细化/系统提示词.md`（作为模板源）
  - `tests/unit/test_agent_prompting.py`
- Acceptance (3-5):
  - 默认提示词采用细化文档模板语义，包含 `Available tools` 与 `Guidelines` 段。
  - 支持运行时填充 `AVAILABLE_TOOLS/SKILLS_SECTION/CURRENT_DATETIME/CURRENT_WORKING_DIRECTORY`。
  - 保持 skills 注入机制不退化。
- Tests Plan:
  - unit: `tests/unit/test_agent_prompting.py`
  - contract: `tests/contract/test_system_prompt_contract.py`
  - integration: `tests/integration/test_prompt_runtime_fill_integration.py`
  - e2e: `tests/e2e/test_system_prompt_render_e2e.py`
- Commit Plan:
  - C1: `test(R13R.1): system prompt模板对齐红测（先红）`
  - C2: `feat(R13R.1): 落地系统提示词模板与运行时填充（全绿）`
  - C3: `docs(R13R.1): 记录系统提示词对齐证据（记录hash/证据/下一步）`
- Commits:
  - C1: `3fd75c2`
  - C2: `3e465c3`
  - C3: `30d325b`
- Evidence:
  - 红测（C1）: `pytest -q tests/unit/test_agent_prompting.py tests/contract/test_system_prompt_contract.py tests/integration/test_prompt_runtime_fill_integration.py tests/e2e/test_system_prompt_render_e2e.py` -> `5 failed, 1 passed`
  - 转绿（C2）: 同命令 -> `6 passed in 0.38s`

### Roadpoint R13R.2: tools/task 契约修复
- Public Surface:
  - `tools/builtins/task.py`
  - `tools/builtins/read.py`
  - `tools/safety.py`
  - `skills/workspace.py`
- Acceptance (3-5):
  - `task` 参数契约与细化文档一致（含 `load_skills`、`run_in_background`、新任务分支互斥规则）。
  - `task` 子任务技能注入与 continuation 语义可验证。
  - 修复 skills 可见性与 `read` 沙箱可读范围冲突。
- Tests Plan:
  - unit: `tests/unit/test_task_tool_schema.py`
  - contract: `tests/contract/test_task_tool_contract.py`
  - integration: `tests/integration/test_task_skills_integration.py`
  - e2e: `tests/e2e/test_task_load_skills_e2e.py`
- Commit Plan:
  - C1: `test(R13R.2): tools/task契约修复红测（先红）`
  - C2: `feat(R13R.2): 修复task与skills-read关键契约（全绿）`
  - C3: `docs(R13R.2): 记录tools契约修复证据（记录hash/证据/下一步）`
- Commits:
  - C1: TBD
  - C2: TBD
  - C3: TBD
- Evidence:
  - Pending

### Roadpoint R13R.3: Hook 关键事件与拦截契约补齐
- Public Surface:
  - `agent/runtime.py`
  - `agent/compaction/*`
  - `hooks/runner.py`
  - `hooks/builtins/*`
- Acceptance (3-5):
  - `session_start/session_compact/session_shutdown/run_error/run_timeout/run_abort` 在主链路可触发。
  - `before_agent_start.message` 返回值接入主流程。
  - 补齐至少一个内置 hook 示例模块（`base_guard/default_status` 等）。
- Tests Plan:
  - unit: `tests/unit/test_hook_event_coverage.py`
  - contract: `tests/contract/test_hook_intercept_contract.py`
  - integration: `tests/integration/test_hook_critical_events_integration.py`
  - e2e: `tests/e2e/test_hook_error_timeout_abort_e2e.py`
- Commit Plan:
  - C1: `test(R13R.3): hook关键事件覆盖红测（先红）`
  - C2: `feat(R13R.3): 补齐hook关键事件与拦截契约（全绿）`
  - C3: `docs(R13R.3): 记录hook一致性修复证据并收口M13R（记录hash/证据/下一步）`
- Commits:
  - C1: TBD
  - C2: TBD
  - C3: TBD
- Evidence:
  - Pending

## Milestone M14
- Title: 第二 Provider（anthropic）与切换验收
- Goal: 在不改 runtime/tool/session 核心代码前提下新增 `anthropic` 协议实现与工厂接线。
- Exit Criteria:
  - `llm/protocols/anthropic/*` 落地并通过与 `openai_compat` 同一契约测试集。
  - provider 切换仅改配置（不改 runtime/tool/session 代码）。
  - OpenAI/Anthropic 双链路集成测试通过，`pytest -q` 全绿。
- Status: Planned (Not Expanded)

## Milestone M15
- Title: 发布前硬化与回放审计验收
- Goal: 完成全局能力收口（capabilities/openapi/薄CLI）与稳定性硬化，达成蓝图最小验收。
- Exit Criteria:
  - `GET /v1/capabilities` 与 `GET /v1/openapi.json` 可用且反映当前模型/工具能力。
  - CLI 保持 HTTP-only（不直连 runtime）并可完成主流程调用。
  - 回放一致性、故障注入与恢复性检查通过，关键长会话压缩/重试链路稳定。
  - 满足《内核设计蓝图.md》第 11 节最小验收项，`pytest -q` 全绿。
- Status: Planned (Not Expanded)
