# refactor-461-M1 — Progress

## Baseline

- 首次 untouched 全量 `pytest -m "not e2e"`：`1 failed, 3495 passed, 1 skipped, 23 deselected`；唯一失败为范围外 `test_competing_handlers_relay_and_ack_only_the_durable_winner`。
- Orchestrator 在 main 与 milestone worktree 各连续复跑该测试 8 次，合计 16/16 通过；按其继续条件再次运行 untouched 全量，结果 `3496 passed, 1 skipped, 23 deselected`（110.29s）。当前只证实一次瞬态失败，不纳入 M1 实现范围。

## R1 — 收口 Gateway lifecycle 配置与迁移备份

- Status: TODO

## R2 — 删除 runtime subprocess/health seam 并保持 lifecycle 行为

- Status: TODO

## R3 — 清理 active 入口残留并完成真栈验收

- Status: TODO
