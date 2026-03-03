# TASKS (Milestone: M31)

- Test command: `pytest -q`
- Branch: `milestone/M31`
- Milestone status: `RUNNING`
- Refactor boundaries:
  - Must keep unchanged: `ToolSpec.input_schema` 数据结构、工具调用执行路径、system prompt placeholder 与 skills 注入机制。
  - Allowed to change: `src/nano_multiagent/agent/prompting.py` 的工具展示文案与 prompt 相关测试、里程碑文档。

## [TODO] R31.1 调整 Available tools 展示并同步测试断言
- Acceptance:
  - system prompt 的 `Available tools` 区段只保留 `- <name>: <description>` 行，不再输出 `input_schema`。
  - prompt 文本中不出现 `input_schema` 字样。
  - 仅调整展示层；工具执行契约（`ToolSpec` 结构与运行时调用）保持不变。
  - runtime placeholders（`AVAILABLE_TOOLS` / `SKILLS_SECTION` / 时间 / cwd）填充行为保持不变。
  - 与 prompt 相关的 unit/contract/integration 测试断言更新并通过。
- Tests Plan:
  - `unit`: 选择，覆盖 `build_prompt_messages` 的工具展示文案变化与无 `input_schema` 约束。
  - `contract`: 选择，覆盖 system prompt 模板契约不含 `input_schema`。
  - `integration`: 选择，覆盖 runtime 填充后 system prompt 不含 `input_schema` 且仍含工具列表。
  - `e2e`: 不新增专门用例；全量门禁已包含相关 e2e，避免重复覆盖。
- Expected Tests:
  - `pytest -q tests/unit/test_agent_prompting.py tests/contract/test_system_prompt_contract.py tests/integration/test_prompt_runtime_fill_integration.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS` 记录决策、证据、回滚点、提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO
