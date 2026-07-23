# feat-474-M1 — Progress

## 范围确认（§2.5）

已读完 design.md / spec.md / delta specs（tools-hooks / skills / background-tasks / prompts）/
AGENTS.md / TESTING_GUIDE.md / 现有 `AgentTool` / `_SessionSubagentControl` / `AgentEngine` /
`session/types.py` / `session/directory.py` / 既有测试 `test_agent_tool.py` /
`test_agent_tool_schema.py` / `test_runtime_tool_allowlist_enforcement.py`。

范围 = design.md Milestone 表 `feat-474-M1` 行：`src/agent/platform/tools/builtins/agent.py`；新增
`src/agent/platform/tools/subagent_types/`；`src/agent/sdk/kernel.py`（`create_subagent` + 父有效
工具窄口）；`src/agent/core/agent/runtime.py`（窄口实现，供 kernel 委派）；相关单测。

**明确排除**：`docs/specs/kernel/*.md`（canonical，归 orchestrator 归并）与
`docs/changes/feat-474-agent-tool-ergonomics/specs/kernel/*.md`（delta，design-author 已写定）—— 按
派单方指示不由 worker 改动；对外行为变化在下面各 R 段记录，供 orchestrator 归并参考。

无待澄清歧义，design 决策 1-6 对本 milestone 边界描述清晰，按 tasks.md R1-R4 开始实施。
