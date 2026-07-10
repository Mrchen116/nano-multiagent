# perf-458-M1 — Progress

## Baseline

- Context: 在任何实现前复跑 unit 分支现有门禁，确认不是在红色基线上优化。
- Evidence:
  - Python: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e"` → 3444 passed, 2 skipped, 22 deselected in 149.34s（wall 151.14s）。
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .` 与 `ruff format --check .` → 全绿，769 files already formatted。
  - Frontend: `npm ci && npm run test` → 63 files / 615 tests passed，vitest 13.63s（wall 15.19s）。
- Scope guard: 仅修改 design Milestone 表列出的 workflow、pyproject 和七个测试文件；`src/`、`docs/specs/`、前端源码均不修改。

## R1 — 移除 IM integration 的 live-config 固定等待

- 状态: TODO
- Next: 量取五个目标测试的未优化耗时，提交 Verify 证据。

## R2 — 消除 ShellRunner 与输出上限测试的确定性成本

- 状态: TODO
- Next: R1 完成后量取三条目标测试的未优化耗时，提交 Verify 证据。

## R3 — 接入 xdist、pip cache 与完整门禁

- 状态: TODO
- Next: R2 完成后记录 workflow 缺失能力并接线。
