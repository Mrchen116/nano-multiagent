# refactor-522-M1 — Progress

## Baseline

- Context: 开始单 M1 原子 cutover 前确认 unit branch 与现有行为健康。
- Evidence: `python -m pytest -n auto -m 'not e2e' -q` → 3181 passed, 26 deselected, 36 warnings。

## R1 — Binder 独占 SQLite persistence

- Context: Pending.

## R2 — Boundary 两步 transition 与 composition cutover

- Context: Pending.

## R3 — Durable compatibility 与产品行为回归

- Context: Pending.

## R4 — Cross-process partial recovery 与全量收口

- Context: Pending.

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | code-test-CI | 当前 milestone 尚无跨任务候选 | N/A |
