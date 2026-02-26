# TASKS (Current Milestone: M1)

## [DONE] R0.1 建立工程骨架与测试基线
- Steps:
  - 新增最小测试，先让导入/health 相关能力失败（Red）
  - 建立 `src/` 包结构与 `pyproject.toml`
  - 实现 `create_app` 与 `GET /v1/health`
  - 跑通 `pytest -q` 并记录证据
- Expected Tests:
  - `tests/unit/test_app_factory.py`
  - `tests/contract/test_health_contract.py`
  - `tests/integration/test_app_bootstrap.py`
  - `tests/e2e/test_health_e2e.py`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R0.1 的 hash 与证据

## [DONE] R0.2 新建会话接口与最小 e2e 闭环
- Steps:
  - 先写 create session 相关测试并制造失败（Red）
  - 实现 session service/store 与 `POST /v1/sessions`
  - 完成 health + create session 的最小 e2e
  - 全量执行 `pytest -q` 并记录证据
- Expected Tests:
  - `tests/unit/test_session_service.py`
  - `tests/contract/test_sessions_contract.py`
  - `tests/integration/test_session_flow_integration.py`
  - `tests/e2e/test_minimal_flow.py`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R0.2 的 hash 与证据

## Milestone M0 状态
- `R0.1` 与 `R0.2` 均已完成，达到 M0 Exit Criteria。

## [DONE] R1.1 core 稳定契约实现与入口级校验
- Steps:
  - 新增 core 契约相关四类测试并制造失败（Red）
  - 实现 `src/nano_multiagent/core/` 下 `types/events/errors/ids/__init__`
  - 最小改造 `SessionService` 使用 `core.ids.make_session_id`
  - 全量执行 `pytest -q` 并锁定证据
  - 更新四文档并补写 M0 C3 回填核对记录
- Expected Tests:
  - `tests/unit/test_core_ids.py`
  - `tests/unit/test_core_errors.py`
  - `tests/contract/test_core_types_contract.py`
  - `tests/contract/test_core_events_contract.py`
  - `tests/integration/test_core_id_wiring_integration.py`
  - `tests/e2e/test_core_contract_entry_e2e.py`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R1.1 的 hash 与证据
  - M0 历史 C3 占位核对并回填为真实 hash

## Milestone M1 状态
- `R1.1` 已完成，M1 目标（core 契约层实现与冻结）已达成。
