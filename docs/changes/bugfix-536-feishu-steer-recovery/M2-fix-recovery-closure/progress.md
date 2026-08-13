# bugfix-536-M2 — Progress

## R1 — 基线与失败边界定位

- Context: Round 1 verifier 已确认 adopted successor 的 non-completed/no-suffix 分支可遗留 active marker；产品回归在两个独立 Web IM 直聊中确认精确 `/new` 后旧口令仍可见。
- Decision: 从 `dc3173750` 建立独立 M2 worktree；先追踪 `SessionRunCoordinator`、`GatewaySessionBinder` 和 Kernel transcript，再为两条路径建立最窄红测。
- Rationale: `/new` 已创建 fresh Kernel session，必须继续辨别 binding 回写与会话外输入，不能以提示词掩盖用户可见契约。
- Evidence:
  - Tests: M1 aggregate baseline `159 passed in 13.75s`。
  - Entry: 已确认 `/new` 的入口是 exact parser → `new_session` → `prepare_reset` → `publish_reset`；recovery failure 在 nested no-suffix 返回后抛出时只清理原 predecessor。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；后续用隔离 Web IM 真栈做运行时验收。
  - E2E/Regression: 两条 Round 1 报告已读；红测和真栈结果待 R2/R3 追加。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 删除 M2 的提交即可回到 `dc3173750`。
- Commits: pending

## R2 — 收口无 suffix 的失败 successor

- Context: `test_failed_adopted_successor_without_suffix_releases_session` 在基线失败：`run-2` 已成 active owner，nested handoff 因没有新 suffix 返回 `None`，外层仅按 root `run-1` 清理，`is_session_busy()` 仍为真。
- Decision: 仅在 nested handoff 确认没有可接管 suffix 后，由 recovery owner 用 `claim.run_id` 关闭 active marker；有 suffix 的 nested handoff 原样继续。
- Rationale: successor 的 active ownership 只能由知道 successor identity 的 recovery coordinator 收口；提前关闭会丢失其可能的 re-handoff suffix。
- Evidence:
  - Tests: 红测在基线失败（`is_session_busy('web_relay:recovery:agent-a')` 为真）；修复后 `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py tests/integration/test_session_run_coordinator_recovery.py` 为 `9 passed in 2.33s`。
  - Entry: root/follower 各发一次 failed，active/busy 清空，后续 ordinary message 新提交并回 `ordinary reply`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 保留 correlated successor、suffix adoption、`/stop`、`/new`、shutdown recovery cases，均在 focused suite 内通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 即恢复 `dc3173750` 行为。
- Commits: pending

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | code-test-CI | N/A | M2 是已批准设计内的行为修复。 |
