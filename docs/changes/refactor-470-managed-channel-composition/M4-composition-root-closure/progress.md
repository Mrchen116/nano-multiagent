# refactor-470-M4 — Progress

## 启动记录

- 测试基线根因：M4 worktree 没有独立 `.venv`，因此 `.venv/bin/pytest` 为不存在路径（exit 127）；仓库根的共享 `.venv` 存在。后续以 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest` 在 M4 worktree 运行，不改环境或产品代码。
- Design 修订：无。

## R1 — 固化 composition root 边界与对账基线

- Context: M4 的成功不是仅移动 `main.py`，而是删除 test-only service locator 并保证 38 个基线引用逐一可审计。
- Decision: 以 `rg -l 'personal_assistant\\.main|from personal_assistant import main' src tests scripts` 的 38 文件作为基线，按真实 owner、入口保留、命令字符串/测试说明三类对账；contract 只守用户可观察的入口边界，不测试私有实现。
- Rationale: owner migration 可保持现有行为回归价值，并避免把一次性迁移路径做成脆弱测试。
- Evidence:
  - Tests: 基线运行中；共享 `.venv` 已定位。
  - Entry: R3 完成前待验。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: R2/R3 完成前待验。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 删除本 milestone 分支的 R1 变更。
- Commits: C1=pending, C2=pending, C3=pending。
- Next: 基线完成后写入 C1 contract 与 38-file 对账结论。
