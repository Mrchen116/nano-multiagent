# refactor-489-M12 — Progress

## Baseline

- Context: M12 范围包含 32 个 test 文件、2 个大型重复 helper 和 138 个 collected case；HTTP/WS 跨 seam 保护与 M11 unit/contract 重述、静态 bundle/私有 mapper/helper 自测混杂。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/im_service/integration tests/im_service/e2e` → `137 passed, 1 skipped, 3 warnings in 35.19s`；skip 为可选 frontend `dist/` 缺失触发的静态 bundle 测试。

## R1 — Auth、租户、账户与基础 HTTP 收敛

- Context: 进行中。
- Decision: 进行中。
- Rationale: 进行中。
- Evidence:
  - Tests: 进行中。
  - Entry: 真实 TestClient HTTP；待完成。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待完成。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 commit。
- Commits: 待完成。

## R2 — Message 与 user-stream 实时路径收敛

- Context: 待执行。

## R3 — Agent、Node 与配置 RPC 收敛

- Context: 待执行。

## R4 — Gateway、群聊与共享 harness 收敛

- Context: 待执行。

## R5 — 全量门禁与测试 census

- Context: 待执行。

## Promotion Candidates

None.
