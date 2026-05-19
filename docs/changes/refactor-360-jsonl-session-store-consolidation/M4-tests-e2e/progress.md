# M4: tests-e2e — progress

## 开工报信

已读懂 M4，范围 = 10 e2e 文件迁移 (C)→(A) + 2 workspace_root xfail 转 pass，开始实施。

---

### R1 — C1 红测试基线确认

- Context: 10 个 e2e 文件仍用 `SQLiteSessionStore`（platform 层死代码），pytest 跑出 10 fail + 2 xfail
- Decision: 记录基线状态作为 C1，不修改代码
- Rationale: 符合 TDD 三提交；证明当前缺失能力（使用真实 (A) 路径）
- Evidence:
  - Tests: 10 failed, 11 passed, 1 skipped, 2 xfailed — 失败均因 SQLiteSessionStore 路径
  - Entry: N/A（C1 不写实现）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 基线确认，见 pytest 输出
  - Visual/Interaction: N/A
- Rollback: 无（C1 只加 tasks.md + progress.md）
- Commits: C1=<待填>, C2=<待填>, C3=<待填>
- Next: R2 迁移 8 个简单文件

---

### R2 — 迁移 8 个简单 e2e 文件

- Context: 8 个文件用相同模式：import SQLiteSessionStore + `store = SQLiteSessionStore(db_path=...)` + `create_app(session_store=store, ...)`
- Decision: 统一改为 `from agent.core.session.jsonl_store import JsonlSessionStore` + `from agent.platform.persistence.session.service import SessionService` + `service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))` + `create_app(session_store=service.manager._store, ...)`
- Rationale: test_compaction 和 test_session_rebuild 需要 `store.load_session`，通过 `service.manager._store` 访问；其余文件只用 store 注入 app，不直接访问 store
- Evidence: 见 R2 commit 后 pytest 结果
- Rollback: R1 C1 commit
- Commits: C1=<R1 hash>, C2=<待填>, C3=<待填>
- Next: R3 personal_assistant xfail 处理

---

### R3 — 迁移 test_personal_assistant_main_e2e.py + 去 xfail

- Context: `_runtime_pwd_for_workspace` 函数直造 `SessionManager(store=SQLiteSessionStore(...))` + `create_app(session_store=store, ...)`；2 个测试有 xfail 是因为 SQLiteSessionStore 不支持 create()，改走 (A) 路径后 bug 消失
- Decision: 把 `_runtime_pwd_for_workspace` 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager` + `create_app(session_store=service.manager._store, ...)`；去掉 2 个 xfail 标记
- Rationale: issue #25 的 bug 在 SQLiteSessionStore 不实现 `create()` — (A) JsonlSessionStore 实现了，走真实路径后 workspace_root 正常生效
- Evidence: 见 R3 commit 后 pytest 结果（2 个测试从 xfail 转 pass）
- Rollback: R2 C2 commit
- Commits: C2=<待填>, C3=<待填>
- Next: R4 整套回归

---

### R4 — 整套回归确认

- Context: 所有 10+2 文件迁移完毕，需要跑整套 pytest tests/ 验证无回归
- Decision: 跑 `pytest tests/` 全套
- Rationale: 退出标准要求
- Evidence: <待填>
- Rollback: N/A
- Commits: C3=<待填>
- Next: 合入 unit 分支
