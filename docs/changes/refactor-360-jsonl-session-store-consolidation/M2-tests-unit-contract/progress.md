# M2 progress — tests-unit-contract

## 澄清记录

无疑问。范围清晰：3 个 (a) 类文件，全部改走 SessionService 真实路径。

---

### R1 — 确认红测：3 文件当前失败原因

- Context: unit 分支上 3 个文件仍使用 platform 层死代码，且旧 API 签名已不匹配 (A) 层
- Decision: 记录失败原因，作为 C1 基线
- Rationale: 确认失败点 = 当前缺失能力（走真实路径）
- Evidence:
  - test_agent_runtime_m246.py:
    - `from agent.platform.persistence.session.jsonl_store import JsonlSessionStore` — 用 (B) 层
    - `JsonlSessionStore(base_dir=...)` — (B) 层参数名，(A) 层是 `data_dir=`
    - `manager.create_session(title=..., metadata=...)` — 缺少必填 `workspace_root=`
    - 错误：`TypeError: SessionManager.create_session() missing 1 required keyword-only argument: 'workspace_root'`
  - test_compaction_replay_audit_contract.py:
    - `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` — 用 (C) 层
    - `store.load_session(...)` 直接访问 (C) store
  - test_hooks_query_contract.py:
    - `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` — 用 (C) 层
    - `SessionManager(store=store)` 直造，绕过 SessionService
  - Tests: 3 文件单跑，test_agent_runtime_m246 有 1 failed（TypeError），其余两个尚需确认
  - Entry: N/A（C1 阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 38a705cf (unit 分支 HEAD)
- Commits: C1=<待补>, C2=<待补>, C3=<待补>
- Next: R2 迁移 test_agent_runtime_m246.py

---

### R2 — 迁移 test_agent_runtime_m246.py

- Context: `_make_session_manager()` 用 (B) 层 JsonlSessionStore + 直造 SessionManager，需改走 SessionService 路径
- Decision: 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；session 创建走 `service.create_session(workspace_root=tmp_path)`；去掉 title 参数（SessionService.create_session 接受 title 但测试不依赖 title，workspace_root 是必填）
- Rationale: 迁移目标是走真实 SessionService.create_session → SessionManager.create_session → (A) JsonlSessionStore 路径，metadata 中 workspace_root 由 SessionService 自动 merge，行为等价
- Evidence:
  - Tests: pytest tests/unit/test_agent_runtime_m246.py — 5 passed
  - Entry: 真实 (A) 路径创建 session，LLM mock 接收 user messages，断言行为不变
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 commit
- Commits: C1=<plan commit>, C2=<待补>, C3=<待补>
- Next: R3 迁移 test_compaction_replay_audit_contract.py

---

### R3 — 迁移 test_compaction_replay_audit_contract.py

- Context: 直造 `SQLiteSessionStore` + `SessionManager`，用 `store.load_session()` 验证 CompactionEntry
- Decision: 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；`store.load_session()` 改为 `service.manager.store.load_session()`
- Rationale: `SessionManager.store` 是公开属性（manager.py:36），可直接访问底层 store 做 load_session 断言
- Evidence:
  - Tests: pytest tests/contract/test_compaction_replay_audit_contract.py — 1 passed
  - Entry: 真实 (A) 路径 append_compaction，通过 manager.store.load_session 验证 CompactionEntry
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R2 C3 commit
- Commits: C1=<plan commit>, C2=<待补>, C3=<待补>
- Next: R4 迁移 test_hooks_query_contract.py

---

### R4 — 迁移 test_hooks_query_contract.py

- Context: `_build_client()` 直造 SQLiteSessionStore + SessionManager，传 `create_app(session_store=store, ...)`
- Decision: `store` 改为 `JsonlSessionStore(data_dir=...)`；`SessionManager(store=store)` 改为 `service = SessionService(store=store)` + `AgentRuntime(session_manager=service.manager, ...)`；`create_app(session_store=store, ...)` 保持不变（store 仍是 (A) 实例）
- Rationale: `create_app` 已接受 JsonlSessionStore（M1 已修 app.py:46 类型签名），store 传入无需变量名改变
- Evidence:
  - Tests: pytest tests/contract/test_hooks_query_contract.py — 2 passed
  - Entry: 真实 HTTP 路径验证 hooks 契约形态
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R3 C3 commit
- Commits: C1=<plan commit>, C2=<待补>, C3=<待补>
- Next: R5 全套 pytest tests/ 不回归验证

---

### R5 — 全套 pytest tests/ 不回归验证

- Context: 3 个文件迁移完成后，验证整套测试不新增失败
- Decision: 跑 `pytest tests/ -x --ignore=tests/e2e -q`，对比 baseline ~207 failed 无新增
- Evidence:
  - Tests: <待补>
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R4 C3 commit
- Commits: C3=<待补>
- Next: 合并到 unit 分支
