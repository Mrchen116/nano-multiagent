# TASKS (Current Milestone: M5)

## [DONE] R5.1 server 分层骨架 + 会话接口最小完善
- Steps:
  - 新增鉴权/trace/error 契约失败测试（Red）
  - 拆分 `server` 分层：`app.py`、`deps.py`、`auth.py`、`routes/*`
  - 完成 `POST /v1/sessions`、`GET /v1/sessions/{id}`、`GET /v1/sessions`（`limit/offset`）
  - 加入统一错误格式与 `X-Request-Id` 回传
  - 运行目标测试并记录证据
- Expected Tests:
  - `tests/unit/test_server_auth.py`
  - `tests/contract/test_sessions_contract.py`
  - `tests/integration/test_app_bootstrap.py`
  - `tests/e2e/test_minimal_flow.py`
  - `tests/e2e/test_core_contract_entry_e2e.py`
  - `tests/e2e/test_session_rebuild_e2e.py`
- DoD:
  - 目标测试全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R5.1 hash 与证据

## [DONE] R5.2 同步消息主入口接线（route -> runtime -> session）
- Steps:
  - 先补 `POST /v1/sessions/{session_id}/messages` 的失败测试（Red）
  - 在 `routes/session.py` 实现同步消息入口并调用 `agent.runtime`
  - 完成错误映射与 `trace_id` 回传校验
  - 校验调用链：route -> runtime -> session store
  - 跑全量 `pytest -q`，更新四文档并回填 `PENDING-C3-R5.1`
- Expected Tests:
  - `tests/unit/test_server_message_route.py`
  - `tests/contract/test_message_sync_contract.py`
  - `tests/integration/test_message_sync_runtime_wiring.py`
  - `tests/e2e/test_message_sync_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R5.2 hash 与同步主入口证据
  - 回填任何 `PENDING-C3-*` 占位

## Milestone M5 状态
- R5.1 与 R5.2 已完成，M5 Exit Criteria 达成。
