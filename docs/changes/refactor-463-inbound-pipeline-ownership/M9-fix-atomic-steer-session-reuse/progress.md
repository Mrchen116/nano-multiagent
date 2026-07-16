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

## R2 — O(1) stable binding reuse

- Context: M7 已把 `Kernel.get_session()` 的 JSONL 扫描移出 binder 全局锁和 event loop，但每条稳定消息仍无条件重扫随对话增长的 transcript。Repository row 不携带 workspace/revision schema，重启后的首次接管仍必须读取 Kernel session 才能防止复用 legacy/mismatched workspace。
- Decision: Binder 为每个 `session_key` 记录 process-local verified ownership fingerprint：kernel session id、Agent id/revision、binder generation 与 workspace root。首次持久化 row 接管仍走权威 `get_session()`；同 fingerprint 的稳定复用直接进入 O(1) recheck/refresh。创建新 session 可直接登记 ownership；conversation rebind、invalidation、candidate/revision 变化清除缓存，重启因新 binder 天然重新验证。
- Rationale: 缓存只保存本进程已经证明过的 immutable ownership facts，不写入 SQLite，也不代替 catalog current、generation 或 repository candidate identity recheck。这样性能优化不改变 stale operation 可用旧 snapshot、但不得 stale writeback 的 D2/D3 语义。
- Evidence:
  - Tests: C1 修复前稳定为 `1 failed, 4 passed`，第二次相同 `resolve()` 产生第二次 `get_session()`；实现后 binder/repository/config-sync/fork/internal-dispatch/restart owner chain `53 passed`。
  - Entry: `GatewaySessionBinder.resolve()` public interface 首次访问 persisted binding 后，第二次相同 revision/workspace 的 validation count 保持 1；重新构造 binder 后 count 增至 2，证明进程重启不会信任旧内存 provenance。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py::test_stable_reuse_validates_once_per_binder_process_ownership`；同文件 publish/invalidate 慢校验竞态、既有 workspace mismatch、persistent restart 与 semantic bind 回归全部通过。全仓 `pytest -m "not e2e"` 为 `3421 passed, 1 skipped, 20 deselected`，耗时 104.21 秒。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退实现提交 `e053b317b` 即恢复 R2 红测状态；无 schema/key/data migration。
- Commits: C1=`631ad4809`；C2=`e053b317b`；C3=本提交。
- Next: M9 roadpoints 完成，进入 rebase/unit 集成；canonical specs 无 delta。

## Milestone Validation

- `ruff check .`: `All checks passed!`。
- 聚焦 R1 owner/SDK/coordinator suite：`50 passed`；聚焦 R2 binder owner chain：`53 passed`。
- `pytest -m "not e2e"`: `3421 passed, 1 skipped, 20 deselected, 16 warnings in 104.21s`。
- Test size contract：passed；新增 `test_session_run_coordinator_steer_identity.py` 66 行，扩展的 binder concurrency 文件 180 行，均低于 400 行。
- `git diff --check`: passed。
- 运行时服务与 LLM：N/A；本 milestone 未启动端口、服务或代理，未触碰用户在 4000 端口的 LLM proxy。
