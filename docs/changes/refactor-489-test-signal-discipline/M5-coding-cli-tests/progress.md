# refactor-489-M5 — Progress

## R1 — 完成切片审计与处置计划

- Context: M5 负责 21 个 root CLI test/helper 文件；现状混合了真实入口保护、退役 HTTP/managed 迁移断言、历史文件布局、私有 bridge/phase/Kernel 实现和重复用户路径。
- Decision: 以 current CLI specs 和 `tests/contract/test_cli_sdk_only_contract.py` 为边界 owner，按风险簇完成 keep / rewrite-merge / delete；不建立全仓台账。
- Rationale: 用户入口/公开命令/自动化输出应由 `run_cli` 入口保护，SDK import 由 contract AST seam 保护；文件是否仍不存在、函数住在哪个模块、私有方法如何关闭不构成独立长期风险。
- Evidence:
  - Tests: scoped baseline `163 passed in 0.52s`。
  - Entry: 用 `run_cli` + `_ThresholdBudgetKernelStub(174/200)` 复现：输出只有 assistant/state/usage，没有 current spec 要求的 context budget 或 >=85% `/compact` hint；`commands.py` 调 `print_repl_turn_summary` 未传 kernel。GitHub issue 搜索 `context budget`、`REPL budget hint` 等无结果，按 orchestrator 裁决不创建 issue、不加无 issue xfail。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（终端测试资产重构）。
  - E2E/Regression: N/A（本 milestone 不改产品行为；保留已有 CLI entry regression）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本计划提交。
- Commits: 以 Git history 为准。
- Next: R2 删除退役架构与私有实现保护。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| CLI REPL 未显示 current spec 要求的 context budget 与 70/85/95 hint | `docs/specs/cli/interactive-repl.md` + 后续产品 change unit | `coding_cli.commands._finalize_run_payload` 到 `print_repl_turn_summary` 的用户入口 | `run_cli` 真实入口以 174/200 budget 运行仍无 budget/hint；当前假绿只断言 `echo:hello`；无既有 GitHub issue |
