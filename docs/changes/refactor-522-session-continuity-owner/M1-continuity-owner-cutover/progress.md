# refactor-522-M1 — Progress

## Baseline

- Context: 开始单 M1 原子 cutover 前确认 unit branch 与现有行为健康。
- Evidence: `python -m pytest -n auto -m 'not e2e' -q` → 3181 passed, 26 deselected, 36 warnings。

## R1 — Binder 独占 SQLite persistence

- Context: `session_keys.py` 同时公开内存/SQLite store、全局实例和 helper，普通 caller/test 需要选择 persistence adapter。
- Decision: `GatewaySessionBinder(db_path=...)` 内建 `_SQLiteSessionBindingStore`；普通测试使用 `:memory:`，durability 测试使用临时文件；删除 20 余方法的私有 repository protocol、dead Kernel HTTP 字段/setter 和全部公开 store/helper。
- Rationale: continuity 的 session、runtime、boundary、control、supersession 状态共享事务和恢复约束，公开 adapter 只会泄漏存储步骤；SQLite 已是本地可替代实现。
- Evidence: deletion test 断言旧四个 public symbol 不存在；repository symbol search 在 production 仅余 binder 对 private SQLite 的单点引用；binder/persistence/concurrency focused suite 包含重建 binder、legacy migration、事务与 race 保护。
- Rollback: revert implementation commit；SQLite 路径、表和序列化未变，不需要数据回迁。
- Commits: `675efd6fc`。

## R2 — Boundary 两步 transition 与 composition cutover

- Context: composition 和 outbox 曾绕过 binder 持有 raw store，dispatcher 直接学习 ready/ack/error/defer/deadline 五个存储动作。
- Decision: binder 提供 `next_boundary_dispatch()` 的 Ready/Wait/Idle plan 和 `complete_boundary_dispatch()` 的三类 outcome；retry policy 固定在 binder construction；shadow promotion 也经同一 binder。
- Rationale: remote send/ACK 分类继续属于 dispatcher，durable retry/quarantine transition 归 continuity owner，双方不再共享 SQLite vocabulary。
- Evidence: focused outbox/delivery/composition/control tests 79 passed；retryable zero-delay regression 证明新 loop 需保持原 batch fairness，ready query 调整为未延期 row 优先、再按 deadline/rowid，回归后全绿。
- Rollback: revert implementation commit；wire payload、matching ACK 与 deterministic rejection 分类未改。
- Commits: `675efd6fc`。

## R3 — Durable compatibility 与产品行为回归

- Context: 约 40 个测试文件直接构造 store，容易在迁移时绕开真实 SQLite recovery 语义。
- Decision: fixture/caller 全部改经 binder intent；仅 binder-owned persistence compatibility test 触达 private SQLite，保留现有六表、WAL、`BEGIN IMMEDIATE`、reply-context JSON 与 legacy-column migration。
- Rationale: replace-don't-layer 能让 `/new`、FIFO `/compact`、superseded run、reverse lookup 与 restart 测试覆盖 production owner，而不保留 compatibility façade。
- Evidence: focused 79 passed；真实 `personal_assistant.main` isolated stack 的 Gateway-only restart journey 1 passed in 36.42s，重启后同 conversation 能复述随机 sentinel；非 E2E 全量 3182 passed、36 warnings。
- Rollback: revert implementation commit；durable schema/data contract 原样兼容。
- Commits: `675efd6fc`。

## R4 — Cross-process partial recovery 与全量收口

- Context: 单进程测试不能证明 durable commit 后进程丢失时 pending shadow boundary 与 pending external `/new` handoff 的联合恢复。
- Decision: 新增 test-only A/B subprocess launcher、真实隔离 IM、共享两个 SQLite 文件和 file-backed barrier/ledger；A 在 durable commit 与 external send block 后被 parent 终止，B 重建 production owners 并重复 recovery 验证幂等。
- Rationale: barrier 仅存在于 remote test adapter，不扩 production composition、env hook 或 failpoint；ledger 和真实 IM history 同时验证用户可见唯一性。
- Evidence: partial-recovery critical path 1 passed in 20.42s；同一 boundary anchor/applied boundary、external confirmation、IM `/new` 及终态各一次，后续普通消息使用 reset 后 session；new-file size contract 与先前时序回归各自隔离重跑 2 passed；Ruff check 全绿、878 files formatted、`git diff --check` 全绿。
- Rollback: 删除三个 test-only launcher/test 文件；production 无测试开关。
- Commits: `7a02d5326`。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| Canonical `/compact` drift merge | unit orchestrator | 按 worker 派发不修改 canonical docs 或 delta specs；implementation 已由 FIFO admission tests 证明 | non-E2E full suite + unit design delta |
