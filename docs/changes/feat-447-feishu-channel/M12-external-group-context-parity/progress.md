# feat-447-M12 — Progress

## Startup

- Context: M12 starts from `origin/unit/feat-447` after M10/M11 are merged. Scope is restricted to Feishu mention parsing, external group context parity, config/channel diagnostic warnings, and focused tests.
- Decision: Split into R1 mention parsing/metadata, R2 external group buffer/drain, R3 diagnostic warning plus live/non-e2e verification.
- Rationale: These roadpoints map directly to the three failure modes in design.md: deleted mention content, disconnected group buffer identity, and platform configs that only deliver @Bot events.
- Evidence:
  - Baseline: `pytest -m "not e2e"` -> 3250 passed, 1 skipped, 22 deselected, 20 warnings in 155.21s.
  - Read context: `spec.md`, `design.md`, `AGENTS.md`, `LOGBOOK.md`, `docs/TESTING_GUIDE.md`, current Feishu/Pipeline code and tests.

## R1 — Mention 正文保真与结构化 metadata

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R2

## R2 — External group buffer key 与纯 @ drain

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3

## R3 — 普通群消息投递能力 warning/health 诊断与收尾验收

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
  - Live Critical: TODO
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: Milestone complete
