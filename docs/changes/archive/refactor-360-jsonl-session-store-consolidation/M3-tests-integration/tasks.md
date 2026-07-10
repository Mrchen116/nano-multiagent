# M3 — tests-integration: tasks.md

## 目标

将 `tests/integration/` 下 16 个引用 `agent.platform.persistence.session` 的文件迁移到
`SessionService(store=JsonlSessionStore(data_dir=...))` 真实路径（(a) 类 × 13，(c) 类混合 × 1）。

## 退出标准

- 16 个文件不再 import `agent.platform.persistence.session`（保留 service.py 导入除外）
- `pytest tests/integration/` 全绿（允许预先 baseline failures 但不新增）
- 整套 `pytest tests/` 不回归

## 测试策略

重构类：现有测试不改就该通过（行为不变）。本 milestone 是把直造 SQLiteSessionStore/平台层 JsonlSessionStore
改为走 SessionService 真实路径，行为语义不变，断言逻辑保持一致（除已知 metadata 字段宽松化外）。

无前端 UI 变更。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 基线确认 + tasks 提交 | DONE |
| R2 | 迁移 (a) 类 batch-1：test_agent_runtime*.py × 2 + test_compaction_runtime.py | TODO |
| R3 | 迁移 (a) 类 batch-2：test_hook_critical*.py + test_hooks_registry*.py + test_message_sync*.py + test_prompt_runtime*.py | TODO |
| R4 | 迁移 (a) 类 batch-3：test_run_cancel.py + test_runs_store.py + test_session_manager_wiring.py + test_sse*.py | TODO |
| R5 | 迁移 (a) 类 batch-4：test_task_non_blocking.py + test_trace_log_correlation.py | TODO |
| R6 | 处理 (c) 混合文件：test_session_store_persistence_integration.py — 补等价覆盖 + 删 (B)(C) 测试函数 | TODO |
| R7 | 整套 pytest 不回归确认 + 进度文档 | TODO |
