# refactor-489-M1 — Progress

## R1 — 固化唯一处置规范

- 状态: DONE
- Context: 既有规范只要求实现路径变化后回看旧测试，没有定义影响边界、三种处置和删除前提，worker 无法留下可复核的一致结论。
- Decision: 在 `docs/development/testing.md` 的停止条件下增加“受影响的既有测试”小节，并把实际记录格式纳入原有 `tasks.md` 测试策略模板。
- Rationale: 测试规范是测试选择的唯一 owner；skill 只需路由和执行动作，避免三处各自维护完整判据。
- Evidence:
  - Tests: 修改前结构检查显示 `keep`、`rewrite-merge`、`delete`、非全仓台账和精确文本边界均缺失；修改后待 R3 统一校验。
  - Entry: 从 `docs/README.md` → `docs/development/README.md` → `testing.md` 可进入完整处置规则；本 milestone 无产品运行入口。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面文档改动）。
  - E2E/Regression: N/A（不为文档措辞新增永久回归测试）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `cfa2bdb7f`。
- Commits: 本 roadpoint 提交（最终 hash 在后续 roadpoint 汇总）。
- Next: R2 将规范接入 worker 规划、执行与实际任务模板。

## R2 — 接入 worker 与实际模板

- 状态: DOING

## R3 — 校验格式、路由与去重

- 状态: TODO

## Promotion Candidates

None.
