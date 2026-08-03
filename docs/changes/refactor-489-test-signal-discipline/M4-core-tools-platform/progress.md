# refactor-489-M4 — Progress

## 启动记录

- Baseline: `unit/refactor-489@8d6cfb3e8`；M4 slice `658 passed, 1 warning`。
- Baseline command: 用 zsh array 选取 `tests/unit/platform` 与排除 M2/M3/M5--M8/M13 语义归属后的 root `tests/unit/test_*.py`，执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q`。
- 调试说明: 首轮命令误用 zsh 特殊参数名 `path`，循环赋值污染 `PATH`，造成 6 个 `bash` 子进程假失败；改用普通变量后同一测试集全绿，确认不是仓库基线缺陷。
- Scope clarification: orchestrator 确认 `tests/unit/test_curator.py` 归 M3、`tests/unit/test_text_runner.py` 归 M8，M4 不修改；跨 slice 替代保护只能引用当前基线已存在且可运行的测试，不能依赖尚未合入结果。

## R1 — 清除布局、迁移终态与历史 golden

- Context: M4 同时存在 event 子集重复、platform `__module__`/legacy-root 迁移终态，以及与 current presenter tests 逐字段重复的历史 golden。
- Decision: 删除 2 个 event unit 子集、4 个 platform location 文件与 1 个 presenter migration golden；不新增替代测试。
- Rationale: event 集合已由当前 contract 精确拥有；内部 home/退役 root 没有独立产品风险；presenter 的 summary/detail/emoji/cap 已由当前行为测试直接覆盖。
- Evidence:
  - Claim: 删除历史断言后，event/hook contract、SDK/import boundary 与 presenter 用户可见结果仍受保护。
  - Baseline: `unit/refactor-489@8d6cfb3e8`，M4 slice `658 passed`。
  - Method: 删除前后均运行现有替代保护；删除后扩大到 `tests/unit/platform/tools`。
  - Result: PASS；4 个 contract 文件 `6 passed`，platform tools `57 passed`，`git diff --check` 通过。
  - Locator: `tests/contract/test_core_events_contract.py`、`tests/contract/test_hooks_contract.py`、`tests/contract/test_agent_sdk_boundary_contract.py`、`tests/contract/test_core_no_platform_imports.py`、`tests/unit/platform/tools/test_presentation.py`、`test_presentation_cap.py`。
  - Limit: 本轮只证明现有替代 seam；不评估 M2 对 contract 文件的后续处置。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q <上述 4 个 contract>` → `6 passed`；`... pytest -q tests/unit/platform/tools` → `57 passed`。
  - Entry: N/A（零产品行为的测试资产重构；current contract 与 presenter seam 是验证入口）。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 保留的自动化 regression 如 Locator；无新用例。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交可恢复 7 个历史测试文件。
- Commits: 本提交（SHA 以 Git history 为准）。
- Next: R2 收敛 AutoMode 与 permission gate，同时保留安全与 fail-closed seam。

## Promotion Candidates

None.
