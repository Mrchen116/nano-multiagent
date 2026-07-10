# M1-fix progress — bugfix-422

## R1 — C1 红测

- Context: 锁死三条路径的契约——子 agent 的 LLM 请求层 session id 必须是父 id。
- Decision: 在 `test_agent_tool.py` 的 `_FakeRunner` 记录 `start_calls`（含 `llm_session_id`）；新增前台 spy
  捕获 `runtime.run` 的 `llm_session_id`；`test_agent_background.py` 的 `_RuntimeStub` 记录 `run_calls`。
- Rationale: 单测口径直接断言透传值，比起依赖 proxy 端到端更稳、更快（fix.md Q2）。
- Evidence: 新增 4 例在实现前失败（前台/后台/续传断言 `llm_session_id` 缺失 → None ≠ "parent_1"）。
- Rollback: 删除新增测试。

## R2 — C2 实现

- Context: `runtime.run` / `AgentLoop.run` 已支持 `llm_session_id`，只需把"启动子 agent"链路接通。
- Decision: 新增 `llm_session_id: str | None = None` 形参贯穿 `BackgroundSubagentRunner.start` protocol →
  `RuntimeRunner.start` → `runtime.run`；`run_subagent_lifecycle` 透传；`_NoOpSubagentRunner` 补形参。
  三处调用点（agent.py 前台/后台/续传）传父 session id。
- Rationale: 默认 `None` 向后兼容（无父则 fallback 子本地 id，行为不变）；只动 LLM 请求层，
  `agent_session_id` / `parent_session_id` 维度不变，保住不变量。
- Evidence: `pytest -m "not e2e"` 2727 passed, 2 skipped；`ruff check` / `ruff format --check` 通过。
  实现后修了 3 个集成测试桩（task_stop / auto_background / continuation 的 `_RuntimeStub.run`）补形参。
- Rollback: revert 4 plumbing 文件 + agent.py 三处 + 测试桩形参。

## R3 — C3 文档

- Context: lite 模式回填 fix.md 后两段。
- Evidence: fix.md「修复」「验证」段已填，列出改动文件、commits、测试与回归结论。

## Next

无。三条路径已实现并测试，CI 等价全绿，进入提 PR。
