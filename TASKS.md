# TASKS (Current Milestone: M0)

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

## [NEXT] R0.2 新建会话接口与最小 e2e 闭环
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
