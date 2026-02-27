# TASKS (Current Milestone: M13)

## [DONE] R13.1 Hook 查询 API（events + registry）
- Steps:
  - 新增 `GET /v1/hooks/events` 与 `GET /v1/hooks` 的红测，固定返回结构与错误契约（Red）。
  - 实现 hooks 查询路由与依赖注入，连接现有 Hook registry/loader 数据。
  - 保证仅只读接口，不引入注册/更新/卸载写操作。
  - 验证 source/priority/timeout_ms 等字段完整返回。
- Expected Tests:
  - `tests/unit/test_hook_query_models.py`
  - `tests/contract/test_hooks_query_contract.py`
  - `tests/integration/test_hooks_registry_query_integration.py`
  - `tests/e2e/test_hooks_query_e2e.py`
- DoD:
  - R13.1 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13.1 hash 与证据

## [DONE] R13.2 可观测性字段收口（日志/trace 关联）
- Steps:
  - 新增日志/trace 字段红测，固定 `session_id/turn_id/tool_call_id/trace_id` 关联要求（Red）。
  - 在 run/tool/hook/error 关键路径补齐结构化日志字段。
  - 处理上下文缺失场景，确保日志输出稳定不崩溃。
  - 执行全量回归并收口 M13。
- Expected Tests:
  - `tests/unit/test_observability_fields.py`
  - `tests/contract/test_observability_contract.py`
  - `tests/integration/test_trace_log_correlation_integration.py`
  - `tests/e2e/test_observability_chain_e2e.py`
- DoD:
  - R13.2 目标测试红转绿
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R13.2 hash 与证据
