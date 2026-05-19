# M3 — tests-integration: progress.md

## R1 — 基线确认 + tasks 提交

- Context: milestone worktree 从 unit 分支创建，检查 16 个目标文件均存在；baseline 有 87 failed 但都是已知问题（(B)(C) 接口不兼容 (A)）
- Decision: 按 test-migration-plan.md 分 6 个实施 roadpoint（R2-R7），每批 C1 Red → C2 Green → C3 docs
- Rationale: baseline failures 全部来自目标文件使用 SQLiteSessionStore，迁移后自然绿
- Evidence:
  - Tests: `pytest tests/integration/ -q --tb=no` → 87 failed / 69 passed（baseline 记录）
  - Entry: N/A（重构类，行为不变）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 38a705cf（unit 分支基线）
- Commits: C1=TBD
- Next: R2 开始迁移 batch-1
