# feat-349-M5: fix-fork-tool-execution — Progress

## R1 — 失败测试

- Context: fork loop 在 tool_registry=None 时走 tool_registry_unavailable 出口；background_runs.py echo 读错 key 层级
- Decision: 在 test_agent_loop.py 新增 `test_fork_loop_exits_on_tool_registry_none`；在 test_cli_background_runs.py 新增 `test_format_self_evolution_review_reviewed_skills`（复现 wording bug）
- Rationale: 最窄复现路径，直接针对两个根因，不引入新文件
- Evidence:
  - Tests: pytest 两个新 test → 两个 FAILED（Red 确认）
  - Entry: N/A（单元测试阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 3763e609（unit/feat-349 HEAD at start）
- Commits: C1=<pending>
- Next: R2 实现修复

## R2 — 修复实现

- Context: bind_tool_registry 只更新 self._loop，遗漏 self._context_fork._loop；background_runs.py 读错 dict 层级
- Decision:
  1. `runtime.py` `bind_tool_registry`: 同时调 `self._context_fork.bind_tool_registry(tool_registry)`
  2. `context_fork.py` AgentContextFork: 新增 `bind_tool_registry` 方法，委托 `self._loop.bind_tool_registry`
  3. `background_runs.py` `_format_self_evolution_review`: 直接从 `event` 顶层读取 `reviewed_skills`/`reviewed_memory`
- Rationale: 最小修改，不改 AgentContextFork 构造接口，不改 app.py 构造顺序；background_runs 修复直接
- Evidence:
  - Tests: pytest 新增用例 → PASSED；全量 tests/unit/ → PASSED
  - Entry: N/A（单元测试阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: <待 R3 补充>
  - Visual/Interaction: N/A
- Rollback: C1 commit
- Commits: C1=<R1 hash>, C2=<pending>
- Next: R3 文档 + E2E

## R3 — 文档 + 全量回归

- Context: 全量单测 + E2E 验证
- Decision: 跑 pytest tests/unit/ 全量；LC managed 模式 skill_nudge_interval=3，发 3 条消息确认 .nanocode/skills/ 落盘
- Rationale: milestone 退出标准要求 E2E 证据
- Evidence:
  - Tests: <待补充>
  - Entry: <待补充>
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: <待补充>
  - Visual/Interaction: N/A
- Rollback: C2 commit
- Commits: C2=<R2 hash>, C3=<pending>
- Next: 合并到 unit/feat-349，清理 worktree
