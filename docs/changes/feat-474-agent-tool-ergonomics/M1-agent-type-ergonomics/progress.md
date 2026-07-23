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

## R1 — 内置类型目录模块

- Context: `AgentTool` 需要一个不依赖 `agent.sdk` 的内置类型目录（general-purpose/Explore/Plan），
  给出 deny-list + 角色 prompt seed，供后续 R3 编排。
- Decision: 新增 `src/agent/platform/tools/subagent_types/__init__.py`：
  `SubagentTypeDefinition`（name/when_to_use/disallowed_tools/role_prompt_seed）、
  `resolve_agent_type`（缺省 general-purpose，未知/大小写不对抛 `ToolError` 含
  `Available agents: general-purpose, Explore, Plan`）、`apply_tool_deny`（保序求差）、
  `format_available_agents`、`iter_agent_types`。角色文案用 core `PromptSlotSeed`/
  `PromptSlotText`（head=身份，body=角色指引，Explore/Plan 含 READ-ONLY 段），语义参考
  `cc-subagent-system-prompts/*.md` 改写 nano 工具名，非逐字抄。
- Rationale: 与 design 决策 1（platform 内置目录 + core PromptSlotSeed）/ 决策 2（deny-list 求交，
  起步 DENY = write/edit/agent/skill_manage）/ 决策 3（专属四槽，不继承父产品 prompt）/ 决策 5
  （description 列 whenToUse + 未知类型失败文案）一致。同时补 `tests/contract/test_platform_no_sdk_imports.py`
  ——现有 `test_core_no_platform_imports.py` 只守 core 不导 platform/sdk，没有对称守 platform 不导
  sdk 的契约；本期新增模块首次让 platform 直接消费 core 类型，需要这条方向守卫防未来回归。
- Evidence:
  - Tests: `pytest tests/unit/agent/tools/test_subagent_types.py tests/contract/test_platform_no_sdk_imports.py -q` → 14 passed；
    `pytest tests/unit tests/contract -q -m "not e2e"` → 3139 passed（全量基线，无回归）
  - Entry: N/A（本 R 是纯内部模块，无独立入口；真实入口验证见 R4）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯逻辑单测已覆盖；跨层不重复）
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert 4dc7d5ef2`
- Commits: 4dc7d5ef2
- Next: R2 — kernel `create_subagent` 三态扩展 + runtime 窄口
