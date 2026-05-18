# bugfix-357/M1 — Progress

## R1 — C1 红测：新增 multi-roundtrip turn 的 prompt_tokens 回归测试

- Context: 现有测试只覆盖单 LLM call 场景（无 tool call），不能回归住含 tool call 的 multi-roundtrip turn 的错误累加行为。需要先写红测锁住行为边界，再改实现。
- Decision: 更新现有 `test_loop_accumulates_usage_across_multiple_model_calls` 断言为正确语义（prompt=last_value, completion=sum, total=last_prompt+sum_completion）；新增 `test_loop_prompt_tokens_tracks_last_roundtrip_not_sum` 三轮 roundtrip 专项回归。
- Rationale: 两个测试在未修复状态下均红，可精准守护修复语义，防止将来误改回累加。
- Evidence:
  - Tests: 修复前 2 个新测试均 FAILED（`assert 180 == 80`），确认红测有效。
  - Entry: N/A（纯单元测试，无需运行时入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 该 commit 即可恢复到旧断言（单 call 测试不受影响）。
- Commits: 4a07ea94

## R2 — C2 实现：_accumulate_usage 改语义，测试转绿

- Context: `_accumulate_usage` 把 `prompt_tokens` 和 `completion_tokens` 一律累加，导致含 tool call 的 turn 上下文虚高（N 次 roundtrip = N 倍 prompt）。
- Decision: 修改 `_accumulate_usage`：`prompt_tokens` 改为覆盖（取 `update.prompt_tokens`），`completion_tokens` 保持累加，`total_tokens` 重算为 `update.prompt_tokens + accumulated_completion`。同步补充详细 docstring 说明两类 token 不同语义及原因。
- Rationale: `prompt_tokens` 代表上下文快照占用，同一 turn 内每次 roundtrip 发送的是同一份（递增的）history，累加无物理意义；`completion_tokens` 每次 roundtrip 产生独立内容，累加语义正确。`total` 重算保持 context_used + output = total 的同构不变量。
- Evidence:
  - Tests: `pytest tests/unit/test_agent_loop.py::test_loop_accumulates_usage_across_multiple_model_calls tests/unit/test_agent_loop.py::test_loop_prompt_tokens_tracks_last_roundtrip_not_sum` — 2 passed。全量 1557 个单元测试通过，无新增失败（pre-existing 31 failures 与本次改动无关）。
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 该 commit；前端 token chip 无需改动（wire format 不变）。
- Commits: 8df070d5

## R3 — C3 文档：fix.md 补"修复"+"验证"；progress.md 写全

- Context: fix.md 的修复和验证两段空白，progress.md 需要交付完整记录。
- Decision: 回填 fix.md "修复"段（语义变更说明 + 三条规则）和"验证"段（两个回归测试说明）；写本 progress.md 全部 roadpoint。
- Rationale: 文档是 change workflow 的交付物之一，也是将来审查为何 prompt_tokens 不累加的唯一上下文来源。
- Evidence:
  - Tests: N/A（文档变更）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 该 commit（不影响功能）。
- Commits: (this commit)
