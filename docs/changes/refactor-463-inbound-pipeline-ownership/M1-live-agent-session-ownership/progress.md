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

- Context: 待开始。
- Decision: 待完成。
- Rationale: 待完成。
- Evidence: 待完成。
- Rollback: 待完成。
- Commits: 待完成。
- Next: R1 完成后开始。

## R3 — 切换全部生产消费者并证明真实入口

- Context: 待开始。
- Decision: 待完成。
- Rationale: 待完成。
- Evidence: 待完成。
- Rollback: 待完成。
- Commits: 待完成。
- Next: R2 完成后开始。
