# refactor-463-M7 — Progress

## 根因取证

- `PersistentSessionBindingStore.drop_agent()` / `bindings_for_agent()` / `find_direct_by_agent()` 将外部 Agent/channel 标识直接拼入参数化 `LIKE` pattern；参数化只防 SQL 注入，不会取消 `_` / `%` 的 pattern 语义，因此相似 id 会被错误查询或删除。
- `GatewaySessionBinder.resolve()` 在单一 `threading.Lock` 内调用同步 `Kernel.get_session()`；该 SDK 路径经 `SessionDirectory.get()` → `JsonlTranscript.load_config()` 遍历 JSONL。锁覆盖磁盘扫描，且同步调用发生在 async resolve 的 event-loop 线程，既串行化所有 binder 操作，也阻塞无关协程。
- D2/D3 约束：旧 snapshot 已开始的操作可以完整使用旧 revision；但 publish / invalidate 之后，任何旧 reuse/create 结果都不得重新写入 repository。修复需把慢校验拆成 capture → validate → recheck/commit 两阶段，而不是移除 workspace guard。

## R1 — SQLite binding 字面值隔离

- Context: SQLite 参数绑定不会取消 `LIKE` 的 `_` / `%` pattern 语义；`bindings_for_agent()` 是 binder invalidation 的真实 repository 入口，因此错误集合会让 binder 精确 `drop(key)` 删除相似 Agent 的 row。
- Decision: 用统一 `_literal_like_pattern()` 以 `!` 作为 SQLite `ESCAPE` 字符，先转义 escape 自身，再转义 `%` / `_`；`drop_agent()`、`bindings_for_agent()`、`find_direct_by_agent()` 全部复用，只有 conversation-id 段保留通配。
- Rationale: 统一 helper 防止三个查询点规则漂移；保持现有 `LIKE` 查询、schema、key 与 reply-context 格式，修复限定在 identifier 解释语义。
- Evidence:
  - Tests: 红测在修复前稳定得到 2 failures（`team_a` 删除 `teamXa`；canonical lookup 将 `web_relay/team_a` 命中 `webXrelay/teamXa`）；修复后 `test_gateway_session_binder.py` + `test_persistent_session_binding_store.py` + size contract 为 `28 passed`。
  - Entry: 真实 `PersistentSessionBindingStore` 经 `GatewaySessionBinder.invalidate_stale()` 与 `find_canonical_direct()` 公共接口验证；目标 `_` / `%` Agent row 被删除，相似 id row 保留，channel/agent canonical lookup 返回 exact binding。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_session_binder.py::{test_persistent_invalidation_treats_agent_wildcards_as_literals,test_persistent_canonical_lookup_treats_channel_and_agent_as_literals}`，28 passed focused suite。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退实现提交 `8a4efbf32` 即恢复 R1 红测状态；无数据迁移。
- Commits: C1=`accdc87c1`；C2=`8a4efbf32`；C3=本提交。
- Next: R2 补慢 workspace ownership 校验的并发红测与两阶段原子协议。

## R2 — Binder workspace 校验两阶段并发协议

- 状态：DOING
- Next：提交可控慢校验并发红测。
