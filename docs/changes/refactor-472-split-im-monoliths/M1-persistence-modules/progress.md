# refactor-472-M1 — Progress

## 基线

- 已阅读 motivation、design、项目约定、IM 长青契约与测试规范。
- `PYTHONPATH=src pytest -m "not e2e"` 基线正在运行；完成结果在 R1 记录。

## R1 — 锁定最终 package 边界与导入契约

- Context: 本次重构必须 replace-don't-layer，最终结构不允许旧 module 或聚合 re-export 继续成为事实入口。
- Decision: 先以 architecture contract 固定 package、私有 primitive 和禁止旧入口的可观察结构，再迁移 concrete importer。
- Rationale: contract 的失败可证明当前缺失的是最终边界，不把后续实现细节锁进测试。
- Evidence:
  - Tests: 待执行。
  - Entry: N/A；本 roadpoint 为内部 architecture contract，HTTP 入口回归在 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/contract/test_im_persistence_seam_contract.py`，待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C1 commit。
- Commits: C1=待提交，C2=待提交，C3=待提交。
- Next: 写入 red contract 并确认只因最终 package 尚未实现而失败。
