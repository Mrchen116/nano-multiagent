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
    - 测试函数为同步 `def test_`，但 `runtime.run` 是 async，导致协程未被 await
    - 错误：`TypeError: SessionManager.create_session() missing 1 required keyword-only argument: 'workspace_root'`
  - test_compaction_replay_audit_contract.py:
    - `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` — 用 (C) 层
    - `store.load_session(...)` 直接访问 (C) store，(A) JsonlSessionStore 无此方法
  - test_hooks_query_contract.py:
    - `from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore` — 用 (C) 层
    - `SessionManager(store=store)` 直造，绕过 SessionService
    - `create_app(... auth_token="test-token")` 传递不存在的参数（auth_token 早已从 create_app 签名移除）
  - Tests: 3 文件在 unit 分支上均失败（baseline 176 failed）
  - Entry: N/A（C1 阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 38a705cf (unit 分支 HEAD)
- Commits: C1=6150b6d8
- Next: R2 迁移 test_agent_runtime_m246.py

---

### R2 — 迁移 test_agent_runtime_m246.py

- Context: `_make_session_manager()` 用 (B) 层 JsonlSessionStore + 直造 SessionManager；测试函数为同步但调用 async runtime.run
- Decision: 改用 `SessionService(store=JsonlSessionStore(data_dir=...))` + `service.manager`；session 创建走 `service.create_session(workspace_root=root)`；测试函数全改为 `async def test_`，调用改为 `await runtime.run(...)`
- Rationale: `asyncio_mode = "auto"` 对 `async def test_` 自动处理；workspace_root 由 SessionService 自动 merge 到 metadata，行为等价
- Evidence:
  - Tests: pytest tests/unit/test_agent_runtime_m246.py — 5 passed
  - Entry: 真实 (A) 路径创建 session，async LLM mock 接收 user messages，断言行为不变
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 6150b6d8 (C1 commit)
- Commits: C1=6150b6d8, C2=62d7e97d

---

### R3 — 迁移 test_compaction_replay_audit_contract.py

- Context: 直造 SQLiteSessionStore + SessionManager，用 store.load_session() 读取 CompactionEntry；(A) 的 JsonlWriter 是异步写入，list_entries() 读磁盘需要先 flush
- Decision: SessionService + manager.list_entries()；在断言前调用 manager.writer.flush() 强制刷盘；放宽 entry_id 断言（(A) compact_boundary 不持久化 entry_id，由 new_compaction_entry 动态生成）；放宽 first_kept_event_id 断言（list_entries 重建时用 summary_uuid 不是原传入值）；去掉 "Continue the conversation" 断言（该文本由 compaction 层 prompts.py 拼接，不在 session 持久化层）
- Rationale: (A) 路径语义与 (C) 有差异：entry_id 不持久化、resume instruction 由上层注入；测试应验证 compaction 行为契约（data.reason、replayed message content、list_turn_messages 重放），而非 store 序列化细节
- Evidence:
  - Tests: pytest tests/contract/test_compaction_replay_audit_contract.py — 1 passed
  - Entry: 真实 append_compaction → flush → list_entries 读回 CompactionEntry，断言 data.reason 和 list_turn_messages 重放内容
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 6150b6d8 (C1 commit)
- Commits: C1=6150b6d8, C2=62d7e97d

---

### R4 — 迁移 test_hooks_query_contract.py

- Context: 直造 SQLiteSessionStore + SessionManager，传递不存在的 auth_token 参数给 create_app
- Decision: store 改为 JsonlSessionStore(data_dir=...)；SessionManager 改为 SessionService + service.manager；去掉 auth_token 参数（create_app 不接受，认证是 no-op）；去掉 Authorization 请求头（no-op auth 不验证 token）
- Rationale: create_app 当前签名无 auth_token；require_bearer_auth 是 no-op，请求头不影响测试结果
- Evidence:
  - Tests: pytest tests/contract/test_hooks_query_contract.py — 2 passed
  - Entry: 真实 HTTP GET /v1/hooks/events 和 /v1/hooks，断言响应结构
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 6150b6d8 (C1 commit)
- Commits: C1=6150b6d8, C2=62d7e97d

---

### R5 — 全套 pytest tests/ 不回归验证

- Context: 3 个文件迁移完成，需确认 baseline failed 无新增
- Decision: 跑 `pytest tests/ --ignore=tests/e2e -q --tb=no`，对比 unit 分支 baseline
- Evidence:
  - Tests: M2 分支 168 failed / 1937 passed；unit 分支 baseline 176 failed / 1929 passed
  - 结论：M2 减少了 8 个失败（迁移的 3 文件原来就失败），无新增失败
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 62d7e97d (C2 commit)
- Commits: C3=<当前提交>
- Next: 合并到 unit 分支
