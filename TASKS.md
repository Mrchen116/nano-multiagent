# TASKS (Current Milestone: M12)

## [DONE] R12.1 async 提交与 run_id 生命周期基线
- Steps:
  - 新增 `messages:async` 与 `runs/{id}` 红测，先固定状态机与返回契约（Red）。
  - 最小实现 run registry/store，支持 `queued/running/completed/failed/cancelled`。
  - 打通 `POST /v1/sessions/{id}/messages:async` 与 `GET /v1/runs/{id}`。
  - 验证错误结构与 `trace_id` 一致性。
- Expected Tests:
  - `tests/unit/test_runs_registry.py`
  - `tests/contract/test_runs_async_contract.py`
  - `tests/integration/test_runs_store_integration.py`
  - `tests/e2e/test_messages_async_submission_e2e.py`
- DoD:
  - R12.1 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R12.1 hash 与证据
  - 已完成：`91cd896` | `264eab5` | `388d263`

## [DONE] R12.2 run cancel 语义与中断一致性
- Steps:
  - 为 `POST /v1/runs/{id}/cancel` 新增红测，固定 queued/running/terminal 行为。
  - 实现取消状态流转与幂等处理。
  - 对齐 cancel 与现有 abort 语义（错误码/返回结构）。
  - 验证取消后事件链可审计且不破坏会话状态。
- Expected Tests:
  - `tests/unit/test_run_cancel.py`
  - `tests/contract/test_run_cancel_contract.py`
  - `tests/integration/test_run_cancel_integration.py`
  - `tests/e2e/test_run_cancel_e2e.py`
- DoD:
  - R12.2 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R12.2 hash 与证据
  - 已完成：`145011a` | `00c1ed5` | `TBD（docs commit 后回填）`

## [TODO] R12.3 SSE 全局/会话事件流
- Steps:
  - 新增 `GET /v1/events` 与 `GET /v1/sessions/{id}/events` 红测，固定事件格式。
  - 实现 SSE 编码与最小事件集（`text_delta/tool_start/tool_end/turn_end/run_status`）。
  - 串联 async 提交与 SSE 消费链路，验证增量输出与断连行为。
  - 执行全量回归并收口 M12。
- Expected Tests:
  - `tests/unit/test_sse_encoder.py`
  - `tests/contract/test_sse_event_contract.py`
  - `tests/integration/test_sse_session_stream_integration.py`
  - `tests/e2e/test_async_run_sse_e2e.py`
- DoD:
  - R12.3 目标测试红转绿
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R12.3 hash 与证据
