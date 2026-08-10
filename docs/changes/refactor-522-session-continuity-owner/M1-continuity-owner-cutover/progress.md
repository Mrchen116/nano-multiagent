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

## Next

M1 已完成，集成到 `unit/refactor-522` 后交 independent reviewer。

## Reviewer Feedback Fix 1 — `/compact` 回归与 subprocess 回收

- Context: verifier R1 W1 缺已有 binding 的 no-op / failure Gateway 回归；S1 指出 stage-A 在 barrier 前失败会泄漏 subprocess。
- Decision: 仅补两个 Gateway 行为测试，并让 stage-A 在 `finally` 中 terminate/wait、超时 kill/wait；现有 production 已满足目标行为，未修改 production。
- Evidence:
  - Mutation Red: 临时破坏 no-op 与异常分支后，新用例 `2 failed`，分别命中错误成功回复与异常外泄；恢复原实现后 `2 passed`。
  - Regression: `test_gateway_stop_command.py` → 23 passed；覆盖 no-op binding 不变、失败友好回复、稳定 operation replay 只执行一次、后续普通消息继续原 session。
  - E2E: 原 90s 门禁基线 1 passed in 28.52s；共享主机高负载下以 `--timeout=300` 完整重跑 1 passed in 63.05s；一次 barrier 超时还确认新增 `finally` 回收 stage-A，无残留进程。
  - Gates: non-E2E 基线 3182 passed；避开同机并发门禁后的串行全量 3184 passed；Ruff check/format-check 与 `git diff --check` 全绿。
- Process: 按 §FL 省略 §3 tasks 模板，理由是反馈自包含、3 个文件内且单 commit 可回退；reviewer 仍独立复验。
- Rollback: revert 本 fix commit；production 行为未改。
- Commits: 本 fix commit。

## Reviewer Feedback Fix 3 — Grounding 与 baseline

- Context: change-code-review 确认 shadow anchor/promotion crash window、浅 private store surface 与 boundary backlog 累计反序列化三项问题；runtime probe 已确认根因，未调用 systematic-debugging。
- Design check: 远端 IM anchor 返回后先幂等 promotion、再记录 saga anchor，符合 binder 独占 continuity persistence 与 test-only crash barrier 决策；旧反向磁盘态通过显式 recovery seam 收敛，不改 schema 或 production composition boundary。
- Process: 反馈横跨 crash E2E、production owner 与测试 seam，超过 §FL 的单点/三文件判据，因此升级回既有 tasks roadpoints；仍保持单 feedback commit 可整体回退，不启动 worker 自验角色。
- Baseline:
  - 同 HEAD `ff2de7c8` 已有独立 non-E2E 全量证据 `3184 passed`。
  - 本轮共享主机 full xdist baseline：`10 failed, 3174 passed`；失败仅为 40ms heartbeat watchdog 一项与 Feishu subprocess 5s readiness/crash cases，伴随两个 xdist worker 非正常退出。
  - 同范围串行复跑：`2 failed, 14 passed`；仍仅为同一 40ms watchdog 与第二 listener 5s readiness。orchestrator 结合当时 host load >160、并行多套 pytest/真实服务，判为资源竞争并放行；不修改 production 或测试内部 timeout。
  - C1/C2/C3 直接相关 focused baseline：binder/persistence/outbox/delivery/shadow/composition/admission `95 passed`。

## Reviewer Feedback Fix 3 — Red → Green

### F3-R1 — Shadow anchor/promotion crash recovery

- Red: unit ordering regression observed `[False]` rather than `[True]`, proving the promotion callback ran only after saga anchor commit. The exact A/B subprocess journey independently reached the barrier with `promotion_committed=true` but `saga_anchor_absent=false` and failed before process termination.
- Decision: after IM returns the remote anchor, promote the pending boundary transaction first and then commit the saga anchor. Recovery first asks binder for pending shadow saga identities and idempotently promotes any already-anchored legacy row before replaying missing anchors.
- Compatibility: no DB path/schema/table/serialization change. The explicit recovery seam converges both durable split states: new `promotion committed / saga anchor absent`, and legacy `saga anchor committed / pending promotion present`.
- Green: exact cross-process journey `1 passed in 52.28s`; A was terminated at the new promotion/anchor barrier, B reused the IM idempotency key and emitted exactly `boundary-1` and `boundary-legacy` once each, retained one user anchor per external chat, and left no pending shadow boundary saga.

### F3-R2 — Private store surface deletion

- Red: deletion contract found `drop`, `drop_agent`, and `pending_boundaries`; AST ownership contract found two ordinary quarantine tests in addition to the two accepted race fault-injection tests reaching `binder._repository`.
- Decision: delete the three unused private methods; move bind/get/restart/reverse lookup assertions to `GatewaySessionBinder`; observe quarantine through the public terminal `Idle` outcome and non-redelivery, retaining one direct private compatibility test only for on-disk quarantine serialization/transaction semantics.
- Green: focused deletion, ownership, public restart/reverse lookup and private compatibility set passed. Repository access in ordinary tests is absent; the two named race fault injections remain the only binder-private reaches.

### F3-R3 — O(N) boundary drain

- Red: draining 32 durable intents materialized 528 rows (`32 + ... + 1`) because every ACK selected/deserialized the entire remaining backlog.
- Decision: retain the binder `Ready/Wait/Idle` + outcome seam while the private query uses the existing eligibility/order clauses with `LIMIT 1` and `fetchone()`.
- Green: the same deterministic regression materialized exactly 32 rows. Existing retry-zero fairness and ACK/retry/quarantine regressions remained green.

### Focused gates

- Four exact red regressions: `4 failed` with the expected ordering, deletion, ownership and `528 != 32` assertions; no incidental failure.
- Immediate green set: `14 passed`.
- Expanded binder/persistence/concurrency/outbox/delivery/shadow/control/recovery/composition/admission/Gateway-control suite: `123 passed`.
- Live-proxy restart test collected but skipped because `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` was not enabled; no unit timeout was relaxed.
- Full-run execution caveat: after host load fell from >160 to about 11, the first unsharded serial run reached 74% with one failure and was externally terminated with exit 143 before pytest could summarize. No production/test timeout was changed. A bounded shard rerun identified the sole failure as the new subprocess helper exceeding the 400-line test-file contract (`439` lines), not a runtime failure.
- Structure correction: extracted file-backed subprocess doubles to a 94-line test-only support module; the launcher became 360 lines. The exact size contract plus subprocess journey then passed together (`2 passed in 40.23s`).
- Complete serial non-E2E collection was rerun without concurrency in five bounded shards to avoid the execution-session SIGTERM ceiling: `588 + 657 + 951 + 605 + 377 = 3178 passed`. The six-test reduction from the prior `3184 passed` HEAD is exactly the intended removal/merge of shallow private-store bind/get/drop/reverse-lookup duplicates; no test timeout was relaxed.
- Final gates: full-repository Ruff check passed; Ruff format-check reported 879 files formatted; documentation integrity passed for 222 maintained Markdown sources / 67 required routes; `git diff --check` passed.
