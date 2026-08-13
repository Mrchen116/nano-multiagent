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

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | code-test-CI | N/A | M2 是已批准设计内的行为修复。 |
