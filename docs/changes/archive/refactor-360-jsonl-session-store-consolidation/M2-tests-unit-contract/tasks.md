# M2 tasks — tests-unit-contract

## 目标

3 个文件不再 import `agent.platform.persistence.session`，全部改走
`SessionService(store=JsonlSessionStore(data_dir=...))` 真实路径，
单跑 `pytest <file>` 全绿，整套 `pytest tests/` 不回归。

## 退出标准

- `tests/unit/test_agent_runtime_m246.py` 不再 import platform 层 store
- `tests/contract/test_compaction_replay_audit_contract.py` 不再 import platform 层 store
- `tests/contract/test_hooks_query_contract.py` 不再 import platform 层 store
- 三个文件单跑 `pytest <file>` 全绿
- `pytest tests/` 不回归（baseline ~207 failed 已知，无新增失败）

## 测试策略

纯迁移任务：测试行为不变，只改 store 构造路径。
- C1 确认红：现有代码因用 platform 层 (B)/(C) store 而失败，记录失败原因
- C2 迁移：改走 SessionService 真实路径，3 个文件单跑全绿
- C3 文档：progress.md 补齐

前端 UI 状态矩阵：N/A（纯后端测试迁移）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 确认红测：记录 3 文件当前失败原因 | DONE |
| R2 | 迁移 test_agent_runtime_m246.py | DONE |
| R3 | 迁移 test_compaction_replay_audit_contract.py | DONE |
| R4 | 迁移 test_hooks_query_contract.py | DONE |
| R5 | 全套 pytest tests/ 不回归验证 | DONE |
