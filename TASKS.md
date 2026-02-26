# TASKS (Current Milestone: M2)

## [DONE] R2.1 session 事件模型与双存储实现
- Steps:
  - 先新增 entries/serializers/store 的 unit+contract+integration 失败测试（Red）
  - 实现 `session/entries.py` 与 `CompactionEntry` 预留结构
  - 实现 `session/serializers.py` 最小版本化序列化（entry/snapshot）
  - 实现 `SessionStore` 抽象与 sqlite/jsonl 两种存储
  - 运行目标测试与 `pytest -q`，记录证据
- Expected Tests:
  - `tests/unit/test_session_entries.py`
  - `tests/contract/test_session_serializers_contract.py`
  - `tests/integration/test_session_store_persistence_integration.py`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R2.1 hash 与证据
  - 回填 R1.1 的 `PENDING-C3-R1.1`（已完成）

## [DONE] R2.2 manager/服务接线与可重建验证
- Steps:
  - 先新增 manager/service/server 接线相关 unit/integration/e2e 失败测试（Red）
  - 实现 `session/manager.py`，通过事件流构建/重建 session 状态
  - 改造 `session/service.py` 与 `server/app.py`，确保创建会话写入事件存储
  - 补充 sqlite 持久化“重启后可读”验证链路
  - 运行 `pytest -q` 并记录证据
- Expected Tests:
  - `tests/unit/test_session_manager.py`
  - `tests/integration/test_session_manager_wiring_integration.py`
  - `tests/e2e/test_session_rebuild_e2e.py`
  - `tests/contract/test_sessions_contract.py`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R2.2 hash 与证据
  - 输出 sqlite/jsonl 能力验证摘要

## Milestone M2 状态
- `R2.1` 与 `R2.2` 均已完成，达到 M2 Exit Criteria。
