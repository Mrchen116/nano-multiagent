# refactor-459-M3 — Progress

## 基线

- `pytest -m "not e2e"`: 3474 passed, 2 skipped, 22 deselected（2026-07-11）。
- 边界确认: 当前 agent-message caller 必须显式传 `caller_owner_id=None`；不推断 owner，不 repair 历史 conversation，不新增 orphan-owner 产品断言，不修 issue #128。

## R1 — 建立 Gateway conversation persistence interface

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence:
  - Tests: 待实施。
  - Entry: 待实施。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待实施。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 待实施。
- Commits: 待实施。
- Next: R1 C1 红测。

## R2 — 收口 handler 并完成真栈恢复验收

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence:
  - Tests: 待实施。
  - Entry: 待实施。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待实施。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 待实施。
- Commits: 待实施。
- Next: R1 完成后开始。
