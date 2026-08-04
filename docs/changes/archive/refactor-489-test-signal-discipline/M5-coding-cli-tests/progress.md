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
- Commits: `a5154f1fe`。
- Next: R2 删除退役架构与私有实现保护。

## R2 — 删除退役架构与私有实现保护

- Context: 多个 root test 只验证 HTTP/managed 文件已不存在、对象住在哪个模块、bridge 私有别名相等、Kernel 内部关闭方式或无产品调用者的 Rich renderer；`_cli_async_stubs.py` 的 HTTP client stubs 已无消费者。
- Decision: 删除 8 个纯历史/private 测试文件和 `_cli_async_stubs.py`；把 `test_cli_refactor_boundaries.py` 收敛为 README 公开的 release-observability 行为测试（current release-playbook gate 仍引用该路径，故不改名）；删除 managed-mode release playbook 测试；SDK import 风险继续由 contract AST seam 独占。
- Rationale: 这些断言在内部重组时失败，却不增加用户、公开接口或架构风险的独立保护；contract 和 `run_cli` 已是更低、更真实的 seam。
- Evidence:
  - Tests: 清理中 focused suite `65 passed`；最终 scoped suite `79 passed`，相关 CLI contracts `9 passed`。
  - Entry: `test_cli_async_repl_sdk.py` 保留无参启动、Ctrl-C 与生产 `llm-config get`；`test_cli_repl_commands.py` 保留公开命令完整用户旅程。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A。
  - E2E/Regression: N/A（零产品行为变更；入口回归在 root unit/contract）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本轮测试资产清理 commit。
- Commits: `2859535c5`。
- Next: R3 收敛重复入口、render 与 input 覆盖。

## R3 — 将剩余覆盖收敛到当前行为 seam

- Context: 多个文件重复执行同一 stub journey；auto-mode 只测私有 loader/banner；context-budget 阈值测试只断言 assistant echo；输入测试含 150+ 行未使用 HTTP client 和私有 redraw 次数断言。
- Decision: 将 auto-mode 改为 workspace config → `run_cli` → 可见 WARNING；将 text automation 文件改名为 `test_cli_text_mode.py`；合并同 event fixture 的 summary/error 重复用例；保留 steer、NDJSON、resume、非 TTY、工具流和公开命令；删除 context-budget 假绿与无 issue 的替代 xfail；精简共享 Kernel stubs。
- Rationale: 改写后的失败直接对应用户入口或当前 formatter 输出；不会用 helper 绿灯掩盖产品链路未接通，也不把 implementation call graph 当契约。
- Evidence:
  - Tests: 测试从 163 个收敛为 79 个，scoped `79 passed in 0.38s`；相关 CLI contracts `9 passed in 0.63s`；ruff 通过。
  - Entry: 真实 `run_cli` 覆盖无参 REPL/clean close、Ctrl-C、workspace bypass warning、生产 `llm-config get`、斜杠命令、`--text` NDJSON/`--resume`、steer、TTY/非 TTY 和背景 run。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/test_cli_async_repl_sdk.py`、`test_cli_repl_commands.py`、`test_cli_repl_steering.py`、`test_cli_text_mode.py`；focused/scoped 命令全绿。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本轮测试资产清理 commit。
- Commits: `2859535c5`。
- Next: R4 最终门禁、处置对账与范围检查。

## R4 — 最终门禁与范围证据

- Context: 清理后需确认入口保护、SDK contract、文档完整性、静态质量和 milestone 范围同时成立，并确保没有因改名制造 current release-playbook gate 的新路径漂移。
- Decision: 保留 `test_cli_refactor_boundaries.py` 路径（其内容已只剩 current release-observability 行为），因为 current `release_playbook.py` 仍引用该 gate；对全部处置做最终 scope/usage/collection 对账。
- Rationale: 测试内容可以去掉历史断言，但不能在禁止改产品代码的 M5 中新增一个已知路径断裂；最终范围证据也应覆盖删除和 rename 的两端。
- Evidence:
  - Tests: scoped root CLI `79 passed in 0.39s`；CLI contract/错误/隔离 `9 passed in 0.62s`；`ruff check` 通过；`scripts/docs_check.py` 通过（198 maintained Markdown sources / 65 routes）；collect `79 tests`。
  - Entry: `run_cli` 覆盖无参 REPL、Ctrl-C、权限 bypass warning、生产 `llm-config get`、公开斜杠命令、`--text` NDJSON/`--resume`、steer、TTY/非 TTY 与 background run；context-budget 缺口按 R1 证据保持未决且未伪装为绿。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A。
  - E2E/Regression: root CLI 79 + related contract 9 全绿；本 milestone 零产品代码变更，无 live service。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Scope: changed paths 全部匹配 M5 root CLI test/helper 或 M5 产物；所有保留的采集测试文件最多 314 行；`git diff --check` 通过。
- Rollback: 分别回退 `2859535c5`（测试资产处置）和 `a5154f1fe`（计划/证据）。
- Commits: 本收尾提交，SHA 以 Git history 为准。
- Next: M5 完成，合入 `unit/refactor-489`。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| CLI REPL 未显示 current spec 要求的 context budget 与 70/85/95 hint | `docs/specs/cli/interactive-repl.md` + 后续产品 change unit | `coding_cli.commands._finalize_run_payload` 到 `print_repl_turn_summary` 的用户入口 | `run_cli` 真实入口以 174/200 budget 运行仍无 budget/hint；当前假绿只断言 `echo:hello`；无既有 GitHub issue |
| 删除无调用者的 CLI 旧实现 | code-test-CI | `src/coding_cli/release_playbook.py`、`render/repl_live.py`、同步 `input/repl_commands.handle_repl_command` 与 context-budget helper | usage search 显示这些实现无产品调用者；原测试仅保护 managed HTTP 命令、私有字段或未接入 helper，本 milestone 只删除其低信号测试 |
