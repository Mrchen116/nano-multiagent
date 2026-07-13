# refactor-461-M1 — Progress

## Baseline

- 首次 untouched 全量 `pytest -m "not e2e"`：`1 failed, 3495 passed, 1 skipped, 23 deselected`；唯一失败为范围外 `test_competing_handlers_relay_and_ack_only_the_durable_winner`。
- Orchestrator 在 main 与 milestone worktree 各连续复跑该测试 8 次，合计 16/16 通过；按其继续条件再次运行 untouched 全量，结果 `3496 passed, 1 skipped, 23 deselected`（110.29s）。当前只证实一次瞬态失败，不纳入 M1 实现范围。

## R1 — 收口 Gateway lifecycle 配置与迁移备份

- Status: DONE
- Context: `KernelConfig` 把六项死连接/HTTP 字段与三项仍控制 Gateway supervisor 的 timing 混在一起；任意 config 被 canonical save 裁掉 `kernel:` 前必须可恢复原字节。
- Decision: 以 `GatewayLifecycleConfig` / `LocalConfig.gateway` 承载三项 timing；parser 对新旧 mapping 逐字段取值，新值优先；死字段完全忽略。save 仅写非默认 `gateway:`，检测磁盘顶层 `kernel:` 后排他创建 `<config>.pre-refactor-461.bak`，保存原字节与权限，内容一致复用、冲突/IO 失败中止覆盖。
- Rationale: 兼容只停留在 parser edge，不把旧 schema 包装回 runtime；确定性 per-file backup 独立于默认 config 的 timestamp retention，覆盖默认、自定义与 worktree config。
- Evidence:
  - Tests: C1 新增 6 个行为测试均按预期失败；Green 后 `test_local_store.py` 47 passed；config 与受影响 fixture consumers 共 102 passed；narrow ruff check/format 全绿。
  - Entry: 真实文件 load → save → reload 路径验证旧 timing 迁到 `gateway:`，自定义路径生成原字节 migration backup；完整 operator CLI/config save 将在 R3 Runbook 验收。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_local_store.py` 覆盖默认、旧值迁移、逐字段优先级、死字段忽略、backup 创建/权限/复用/冲突阻断；无 e2e marker。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `5244f1e3` 可移除 R1 Green，恢复旧 config runtime。
- Commits: C1=`5244f1e3`, C2=`bc5e8d2f`, C3=本 docs commit。
- Next: R2 删除 runtime manager/health/state interface，并以 PID/start confirmation 测试锁定行为。

## R2 — 删除 runtime subprocess/health seam 并保持 lifecycle 行为

- Status: TODO

## R3 — 清理 active 入口残留并完成真栈验收

- Status: TODO
