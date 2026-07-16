# M9 Progress

## 2026-07-16 — Planning

- Round 4 issue fingerprint `steer-identity-switch` 首次出现：SDK 先缓存 A，再按 session 二次查 active 并可能注入 B，最终却返回 A。
- Round 4 issue fingerprint `binder-reuse-ohistory` 首次出现：M7 已把扫描移出锁与 event loop，但稳定 reuse 仍每轮重放完整 JSONL。
- 正确修复边界：steer 原子性在 registry/SDK 源头闭合；binder 以 process-local provenance 缓存完成首次权威接管，不修改持久化 schema。

## R1 — Atomic expected-run steer

- Context: Gateway coordinator 的 active marker 与 Kernel registry 的 active run 是两个并发观察点。旧实现由 SDK 先读出 A，再让 registry 按 session 二次读取；若 A terminal 后 B 接管，pending message 会进入 B，但 SDK 返回 A，导致 follower lifecycle/history 归属错误。
- Decision: `RunsRegistry.try_inject_pending_message()` 在 registry lock 内完成 expected-run compare、controller terminal admission 与实际 run id 返回；public `Kernel.try_steer(expected_run_id=...)` 透传该 marker。Coordinator 只传自己持有的 marker，并拒绝任何不一致的 SDK 返回身份。
- Rationale: 原子性由 active-run 真正 owner 闭合，不依赖 Gateway transition lock 覆盖 Kernel 内部换代。旧 `inject_pending_message()` 保留为 bool compatibility façade，但复用同一个原子 primitive，不形成第二套判定。
- Evidence:
  - Tests: C1 在修复前稳定为 `4 failed, 2 passed`：registry/SDK 三处缺 expected-run 契约，coordinator 传入值为 `None`；实现后 registry + SDK contract + coordinator admission/terminal + real-Kernel integration 共 `50 passed`。
  - Entry: `Kernel.try_steer()` public SDK seam 以 stale expected run 调用返回 `None`；`SessionRunCoordinator.dispatch()` public interface 在 A marker / B registry-active 的确定性切换下不登记 follower，等待 A terminal 后只 submit 一个 fallback run。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/agent/runs/test_runs_registry_executor.py::test_expected_run_injection_never_targets_replacement_active_run`、`tests/contract/test_kernel_sdk_behavior_contract.py::test_try_steer_rejects_stale_expected_run_identity`、`tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py`；全仓 `pytest -m "not e2e"` 为 `3420 passed, 1 skipped, 20 deselected`，耗时 106.85 秒。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退实现提交 `85b777891` 即恢复 R1 红测状态；无持久化或协议迁移。
- Commits: C1=`78dd19183`；C2=`85b777891`；C3=本提交。
- Next: R2 为稳定 binding reuse 增加权威读取计数红测，并落 process-local verified ownership provenance。
