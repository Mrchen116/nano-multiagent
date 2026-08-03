# refactor-489-M11 — Progress

## R1 — 公开契约与认证 helper 收敛

- Context: M11 基线覆盖 61 个范围文件、424 个 pytest case；同一行为同时存在 repository、service、route 与 contract 断言，需要先确立公开 contract owner。
- Decision: 以 `docs/specs/im/` 的 HTTP/WebSocket 可观察行为为保留标准，从 contract 与 route-shape tests 开始审计。
- Rationale: 先固定外部边界，后续才能安全删除下层重复，同时避免把 durable ACK、owner isolation 或稳定错误语义误判为实现细节。
- Evidence:
  - Tests: 基线 `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/IM tests/im_service/unit tests/im_service/contract` → `424 passed, 13 warnings in 23.38s`。
  - Entry: N/A；本 milestone 零产品行为变化，公开 contract pytest 是 design 指定入口。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/contract/**` 与相关 route tests；实施后补结果。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 的测试删改 commit 即可恢复原测试集合。
- Commits: 待完成。

## R2 — schema 与 repository 持久化保护收敛

- Context: 待执行。
- Decision: 待执行。
- Rationale: 待执行。
- Evidence:
  - Tests: 待执行。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 commit。
- Commits: 待完成。

## R3 — Gateway、relay 与实时状态持久化保护收敛

- Context: 待执行。
- Decision: 待执行。
- Rationale: 待执行。
- Evidence:
  - Tests: 待执行。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R3 commit。
- Commits: 待完成。

## R4 — 全量门禁与测试 census

- Context: 待执行。
- Decision: 待执行。
- Rationale: 待执行。
- Evidence:
  - Tests: 待执行。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 文档可随对应实现 commit 回退。
- Commits: 待完成。

## Promotion Candidates

None.
