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
- Commits: C1=`accdc87c1`；C2=`8a4efbf32`；C3=`dbf6aab5a`。
- Next: R2 补慢 workspace ownership 校验的并发红测与两阶段原子协议。

## R2 — Binder workspace 校验两阶段并发协议

- Context: `Kernel.get_session()` 是同步 SDK seam，实际经 `SessionDirectory.get()` / `JsonlTranscript.load_config()` 扫描整份 JSONL。原 `resolve()` 在 binder 单一 `threading.Lock` 和 async event-loop 线程内执行它，导致无关 Agent 的 resolve / invalidate 既争用全局锁，又无法获得 event-loop 执行机会。
- Decision: `resolve()` 先在短锁内 capture repository candidate、binding revision 与 Agent generation；随后用 `asyncio.to_thread()` 在锁外验证 workspace；返回后重新取得短锁，对账 catalog current、generation、candidate kernel-session identity 与 binding revision，再决定 refresh commit、旧操作 ephemeral return 或重试新 candidate。
- Rationale: workspace guard 仍是每次 reuse 的权威校验；慢 I/O/JSONL 解析不占全局锁或 event loop。config publish / invalidate 穿过校验时，旧请求可继续使用其已捕获且校验通过的旧 session，符合 D2；但只有 guard + candidate 都 current 才能 repository bind，符合 D3 的 stale-write 禁令。
- Evidence:
  - Tests: R2 红测修复前 `2 failed`，两次都只能在慢校验 1 秒 fail-safe 结束后观察到 `validation_finished=True`；实现后 binder/repository/config-sync/fork/reuse/size focused suite `42 passed in 2.78s`。
  - Entry: `GatewaySessionBinder.resolve()` 公共 async interface 以可控真实线程阻塞模拟长 transcript：agent-A 校验未释放时 agent-B resolve 返回原 session，agent-C invalidate 完成；publish/invalidate 同 Agent 后旧 resolve 返回旧 session 但 repository 保持空，下一次 resolve 仅写入 v2 workspace session。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py` 两条永久回归；全仓 `pytest -q -m "not e2e"` 为 `3398 passed, 1 skipped, 20 deselected, 16 warnings in 107.86s`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退实现提交 `59f4eb393` 即恢复 R2 红测状态；无 schema/key/data migration。
- Commits: C1=`53a17e49e`；C2=`59f4eb393`；C3=本提交。
- Next: M7 完成，进入 rebase/unit 集成；不修改 canonical specs（design 明确 gateway delta-spec 为 none）。

## Milestone Validation

- `ruff check src tests`: passed。
- `pytest -q -m "not e2e"`: `3398 passed, 1 skipped, 20 deselected, 16 warnings in 107.86s`。
- 文件大小：`test_gateway_session_binder.py` 372 行；`test_gateway_session_binder_concurrency.py` 148 行；均小于 400 行。
- `git diff --check`: passed。
- 运行时服务：N/A；本 milestone 未启动端口、IM、Gateway 或其他常驻进程，无资源需回收。
