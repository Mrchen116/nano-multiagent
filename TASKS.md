# TASKS (Current Milestone: M9)

## [DONE] R9.1 skills 自动发现 + system prompt 注入 + /skill 改写
- Steps:
  - 新增四类红测覆盖：`<available_skills>` 注入、空 skills 不注入、`/skill` 改写与 runtime 主链路（Red）
  - 实现 `skills/registry.py`：扫描并解析 `SKILL.md` 元数据（`name/description/location/base_dir`）
  - 实现 `skills/workspace.py`：按 `CODEX_HOME` 与工作区目录解析可见 skills
  - 实现 `skills/formatter.py`：生成含 read/路径解析指导的 `<available_skills>` 片段
  - 在 `agent/prompting.py` 注入 skills 段（仅 skills 非空时）
  - 实现 `agent/skill_commands.py` 并在 `AgentRuntime.run` 接线改写 `/skill:name [args...]`
  - 跑目标测试与 `pytest -q` 全量验收
  - 回填历史占位：`R8.2 C3=4fac5ba`
- Expected Tests:
  - `tests/unit/test_agent_prompting.py`
  - `tests/contract/test_skill_commands_contract.py`
  - `tests/integration/test_agent_runtime_skill_command_integration.py`
  - `tests/e2e/test_skill_command_message_sync_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R9.1 hash 与证据
  - 不进入 M10+（compaction/task/SSE）

## Milestone M9 状态
- R9.1 提交链已闭环：`c71191c` -> `ae706e2` -> `(this docs commit)`。
- `skills` 自动发现与 `/skill` 改写能力已接入 runtime 主链路。
- 范围严格限定在 M9，未进入 M10+。
