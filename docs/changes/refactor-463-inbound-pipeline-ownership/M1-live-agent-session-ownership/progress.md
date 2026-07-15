# refactor-463-M1 — Progress

## 启动基线

- Context: refactor-461 已由 PR #197 合入，unit/local/remote 均基于 `a6c04258183b89867df6f08f6dcedf125989daf0`。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3337 passed, 1 skipped`（39.56s）。
- Leader alignment: M1 必须覆盖 create、internal-dispatch IM ack、session-fork await 三类 post-await stale guard；live 证据必须落本目录并明确展示动态配置下一轮、重启续接、cron canonical direct 与 `send_message` 正确历史。

## R1 — 收回 live Agent snapshot 所有权

- Context: 旧 live Agent 状态是 pipeline 内可变 dict；配置发布者与各消费者只能靠共享对象身份协同，且旧测试用 `__new__ + _agents` 固化私有布局。
- Decision: 新增 concrete `LiveAgentCatalog` 与 frozen `LiveAgentSnapshot`；publish 在短锁内递增 revision、复制完整 mapping 并原子替换，features 在入口防御性复制为只读 mapping。R1 只建立独立 owner 与公开 interface，不提前把 pipeline/main 切成半套 wiring；生产消费者在 R3 一次切换。同步删除/迁移直接拼 pipeline 私有 metadata builder 的重复测试，保留 `handle_inbound()` → `create_session` 的公开行为覆盖。
- Rationale: 单独先落 owner 可让 R1 在全量绿色基线上独立回退，避免 catalog 已替换 pipeline 而 composition root 仍读 `_agents` 的中间双 interface；copy-on-write 使任何 reader 持有完整旧 snapshot 或完整新 snapshot，不会观察逐字段 mutation。
- Evidence:
  - Tests: `pytest -q test_agent_catalog.py test_inbound_pipeline_session_metadata.py test_session_metadata_features_wiring.py test_heartbeat_cron_vars_injection.py` → 18 passed；`ruff check src tests` → passed；`pytest -m 'not e2e' -n 4 --dist worksteal` → 3335 passed, 1 skipped（31.82s）。
  - Entry: Catalog 公开入口测试覆盖 initial/get/require/publish/is_current/values_snapshot，含并发 reader 只观察完整 `(title, model, heartbeat)` 旧/新组合；产品 metadata 仍经真实 `InboundPipeline.handle_inbound()` 到 fake Kernel `create_session` 验证 features/custom prompt。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `tests/unit/personal_assistant/test_agent_catalog.py` 为永久 revision/copy-on-write 回归；R1 是独立纯状态 owner，真 Gateway 入口证据统一在 R3 切线后执行，避免验证未使用模块。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `a0fbcd482` 恢复为无 catalog owner；C1 可独立保留为红测或连同回退。
- Commits: C1=`e8bcb06df`；C2=`a0fbcd482`；C3=本次 docs commit。
- Next: R2 C1 binder interface 与 create-await stale-write 红测。

## R2 — 收回 Gateway session binding 所有权

- Context: 既有 `SessionBindingStore` / SQLite store 同时被 pipeline、scheduler、runtime delivery、fork 与 internal dispatch 当业务 service 使用；配置 publish 跨 `create_session`、IM ack 或 fork await 时没有统一 stale-write guard。
- Decision: 新增 concrete `GatewaySessionBinder`，repository 只保留存储 adapter；Binder 用 process-local binding revision + per-agent invalidation generation 管理 reuse/create writeback，旧 snapshot 在 create await 后变 stale 时仍返回本轮可用的 ephemeral binding、但不持久化。新增 typed `BindingWriteGuard` / `ConversationBindingRequest` / `ConversationBindResult(bound|stale)`，供 external await 前捕获、await 后统一校验。内存/SQLite adapter 增加 exact drop、按 Agent 枚举与 canonical direct 查询，未改表结构和序列化。
- Rationale: revision 约束“哪版配置拥有这行 binding”，generation 使 eager invalidation 同时否决已经跨 await 的旧写回；semantic bind 由 binder 返回 typed stale，而不是让 internal dispatch/fork 自己理解 repository 与锁。
- Evidence:
  - Tests: `pytest -q test_gateway_session_binder.py test_persistent_session_binding_store.py test_heartbeat_session_binding.py` → 32 passed；`ruff check src tests` → passed；`pytest -m 'not e2e' -n 4 --dist worksteal` → 3340 passed, 1 skipped（35.95s）。
  - Entry: `GatewaySessionBinder.resolve()` 公开入口覆盖持久化 session reuse + reply refresh、完整 snapshot create、跨 await publish/invalidate 后 stale create 不写 repo；`bind_conversation()` 覆盖 pre-await guard stale、reverse 与 canonical lookup。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_session_binder.py`；真实 Gateway 消费者尚未切线，统一在 R3 完成后运行真栈，避免双 owner 中间态。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `fd9328713` 删除 binder 与 repository adapter 扩展；现有生产路径仍完整使用旧 store，因此可原子回退。
- Commits: C1=`ea6237abc`；C2=`fd9328713`；C3=本次 docs commit。
- Next: R3 C1 锁定 internal-dispatch ack/fork-await stale、consumer public wiring 与 architecture guard。

## R3 — 切换全部生产消费者并证明真实入口

- Context: pipeline、internal dispatch、fork、heartbeat/cron、runtime delivery、kernel shim 与 composition root 仍各自知道 live Agent dict 或 binding repository；`main.py` 还在构造后写 `pipeline._*` callback。真实重启路径又暴露出相同 IM mirror reconcile 也会 bump revision 并误删 durable binding。
- Decision: 所有生产消费者统一注入同一个 `LiveAgentCatalog` 与 `GatewaySessionBinder`；每次操作捕获一个 snapshot，并在 `create_session()`、internal-dispatch IM ack、session fork 三类外部 await 后用同一 snapshot/generation guard 拒绝 stale write。将 `IMAgentConfigSync` 与 `IMShadowConversationSync` 迁入独立模块；composition root 一次性构造完整 pipeline，不再 post-wire 私有字段。config reconcile 先持久化，完全相同 config 不 publish、不 invalidate。
- Rationale: Catalog/Binder 成为唯一业务 owner 后，消费者只需理解 snapshot/bind 语义，不再同时学习 repository schema、私有 dict 与 invalidation 顺序；no-op reconcile 保留 restart binding，同时真实配置变化仍用单调 revision 主动失效旧行。
- Evidence:
  - Tests: `ruff check src tests` → passed；`pytest -m 'not e2e' -n 4 --dist worksteal` → 3346 passed, 1 skipped（33.22s）。新增 catalog、binder、config no-op、internal-dispatch ack stale、fork-await stale 与 architecture ownership 回归均包含在全量门禁。
  - Entry: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 ... pytest -xvs test_create_agent_via_im_critical_path.py` → 1 passed（9.48s）；最终 C2 上 restart + cron 三条关键路径 → 3 passed（62.07s）。
  - Durable E2E: `evidence/live-stack.md` 保存公开 IM journey、SQLite binding/API 与 session JSONL 对账；覆盖动态 Agent 下一轮、重启暗号续接、cron canonical direct、`send_message` 两个 conversation key 共用同一 Kernel session 并连续追加历史、未知 Agent 400 且 binding `0 → 0`。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `574da3ca6` 恢复旧消费者、内联 config/shadow 与 post-wiring；C1 `52669e470` 可随同回退。无 schema migration。
- Commits: C1=`52669e470`；C2=`574da3ca6`；C3=本次 docs commit。
- Next: 合并到 `unit/refactor-463`，由 orchestrator 进入 M2。
