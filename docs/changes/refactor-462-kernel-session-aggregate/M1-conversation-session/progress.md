# refactor-462-M1 — Progress

## Baseline

- Context: M1 是一次性 session ownership cutover；必须先证明 main 基线稳定，避免把既有失败误归因到重构。
- Decision: 使用仓库共享 `.venv` 跑完整非 e2e 测试与 ruff 格式门禁。
- Rationale: 与项目 CI 的 Python job 一致，同时避免新建环境造成依赖漂移。
- Evidence:
  - Tests: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e'` → `3496 passed, 1 skipped, 23 deselected`。
  - Entry: N/A（实现前基线）。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: N/A（实现前基线）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: N/A（尚未修改产品代码）。
- Commits: plan commit 待提交。
- Next: R1 C1 为 Transcript/Directory/Prompt seed/lifecycle 写最终 interface 红测。

## R1 — Transcript、Directory 与核心 session 数据模型

- Status: TODO

## R2 — ConversationSession 接管 turn/compact/fork transaction

- Status: TODO

## R3 — KernelExecutor、RunsRegistry 与 subagent 控制面

- Status: TODO

## R4 — SDK composition cutover、旧 seam 删除与真实入口签收

- Status: TODO
