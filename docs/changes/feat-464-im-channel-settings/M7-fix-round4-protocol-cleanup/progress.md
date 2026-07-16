# M7 — Progress

实现基线：`fb8308ae8ca6fb980fb748b9fb74140385edb8b5`。Baseline focused backend `37 passed`；focused frontend `13 passed`。

## R1 — Status wire owner 与 coalescing race

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

## R2 — 断线 incarnation supersede 与 control correlation

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

## R3 — Legacy backup 安全净化

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

## R4 — Removal 自动成功清理旧反馈

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: error、waiting、empty、missing resource。
  - Browser QA: 延至 R5。
  - E2E/Regression: TODO。
  - Visual/Interaction: 延至 R5。
  - Prototype Comparison: 延至 R5。
- Rollback: TODO。
- Commits: TODO。

## R5 — Targeted browser 与一次性全量门禁

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: TODO。
  - Browser QA: TODO。
  - E2E/Regression: TODO。
  - Visual/Interaction: TODO。
  - Prototype Comparison: TODO。
- Rollback: TODO。
- Commits: TODO。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-deleting` | retry error/waiting 只随 receipt 存在 | TODO | desktop / failed→empty | blocked | 等待 R5 |
| `prototype.html#channels-empty` | 收敛后只显示空态，无旧 alert/notice | TODO | desktop / empty | blocked | 等待 R5 |
