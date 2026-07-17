# bugfix-468-M2: executor-allowlist-enforcement — Progress

## R1 — executor + runtime allowlist enforcement

- Context:
  - bugfix-468 incident 缺口 2：显式零工具/受限工具会话在执行层无兜底拦截，模型自由发挥的工具调用会被执行。
  - design 决策 3 已定死：runtime 把 session `config.tool_allowlist` 显式（含空）时可用工具名字集传给 `loop.run(tool_execution_allowlist=...)`；为 `None` 时传 `None`。拒绝文案走 `build_reject_message(..., reason="tool '<name>' is not enabled in this session", ...)`，不得用 SUBAGENT_REJECT。
- Decision:
  - `src/agent/core/agent/runtime.py` 的 `_execute_loop` 读取 `self._state().config.tool_allowlist`；显式非 None 时把 `available_tools_override` 的名字集传给 `loop.run(tool_execution_allowlist=names)`，否则传 `None`。
  - `src/agent/core/agent/tool_executor.py` 的 `_is_execution_denied` 拒绝分支把 `build_reject_message` 的 `reason` 改为 `"tool '<name>' is not enabled in this session"`。
  - 测试：扩展 `tests/unit/test_streaming_tool_executor.py` 三类 executor 用例；新建 `tests/unit/agent/test_runtime_tool_allowlist_enforcement.py` 用 `AgentEngine.execute_turn` + `ConversationSession` 验证 runtime 接线。
- Rationale:
  - 复用既有 `_is_execution_denied` / `build_reject_message` 机制，不另起炉灶；fork sidechain 的 `is_subagent` 信号 untouched，维持 feat-440-M2 F6 解耦。
  - 行为上：显式空名单→空 frozenset→全部拒绝；显式名单→名单内执行、名单外拒绝；None→不限制，CLI/kernel 默认会话不变。
- Evidence:
  - Tests: `pytest tests/unit/test_streaming_tool_executor.py::test_empty_allowlist_denies_all_tools_without_side_effects tests/unit/test_streaming_tool_executor.py::test_explicit_allowlist_allows_listed_and_denies_outside tests/unit/test_streaming_tool_executor.py::test_none_allowlist_remains_unrestricted tests/unit/agent/test_runtime_tool_allowlist_enforcement.py -xvs` → 6 passed。
  - Entry: `pytest tests/unit/agent tests/unit/personal_assistant -q` → 1423 passed, 2 warnings（基线 1420 passed，新增 3 个测试）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
    - 用 `scripts/e2e-up.sh` 在 worktree 起隔离栈（IM port 53973，node wt-bugfix-468-M2-7219）。
    - `.gateway-config.yaml` 中 `default-agent.tool_allowlist: []`（显式空名单）。
    - 与 default-agent 建立直聊，发送 "请读取你 workspace 里的 README 文件并告诉我内容。"
    - Agent 回复中明确说明 "当前会话没有启用文件访问工具"；消息 tool_calls 显示 bash/glob/read 均 `failed`。
    - 证据文件落 `M2-executor-allowlist-enforcement/evidence/`：
      - `e2e-messages.json`：完整消息记录（含失败 tool_calls 与回复文本）。
      - `agent-capabilities.json`：default-agent capabilities，可确认 tool_allowlist 生效后的工具集。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert 6f4e934a7` + `git revert f6f0b622a`（按倒序）。
- Commits:
  - C1: `f6f0b622a` test(bugfix-468/M2): allowlist enforcement red tests
  - C2: `6f4e934a7` feat(bugfix-468/M2): wire session tool_allowlist to executor and refine reject reason
  - C3: (this progress + evidence)
- Next: 无，本 milestone 已完成，准备合入 unit/bugfix-468。

