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

## R2 — kernel `create_subagent` 三态扩展 + runtime 窄口

- Context: 旧 `_SessionSubagentControl.create_subagent` 只传 `skills`+`metadata`，`tool_allowlist`/
  `prompt_seed` 完全没有贯通口子；且 `skills=tuple(skills) if skills else None` 会把父显式传入的
  空序列 `()` 悄悄折叠成 `None`（= 加宽成父默认），与 design 决策 4 冲突。父有效工具解析需要一个
  不依赖 runtime 私有 `_resolve_session_available_tools_from_config` 的公开窄口。
- Decision:
  1. `create_subagent` 新增 `tool_allowlist: Sequence[str] | None = None` / `prompt_seed:
     PromptSlotSeed | None = None` 参数，贯通到 `NewSession`；`skills` 改为 `tuple(skills) if
     skills is not None else None`（三态不折叠）。
  2. 新增 `_SessionSubagentControl.list_parent_enabled_tool_names()`，委派到 `AgentEngine` 新公开方法
     `resolve_active_enabled_tool_names(session_id)`——镜像 `resolve_run_model` 的 `_active_state`
     contextvar 读取模式：只在被解析 session 的活动 turn 内调用才有效（正是 `AgentTool` 运行时的场景），
     未匹配则 raise（调用方不变量违反，不静默返回默认值）。
- Rationale: 与 design 决策 4（三态不折叠）、"父有效工具解析(推荐取法)"（`control.directory.get
  (control.ref)` 读持久化 `tool_allowlist`；`None` 时经窄口读活动 turn 已解析集合）一致；`resolve_
  active_enabled_tool_names` 复用 `resolve_run_model` 已验证过的 contextvar 读取范式（bugfix-443
  同款），不新造一套状态读取机制。
- Evidence:
  - Tests:
    - `pytest tests/unit/agent/test_kernel_create_subagent.py -q` → 8 passed（三态 skills / 显式
      tool_allowlist 含空 / 省略默认 None / prompt_seed 持久化 / 省略默认空 seed / parent 不匹配报错）；
      手动验证：临时回退 kernel.py 改动重跑，3 个用例按预期红（`unexpected keyword argument
      'tool_allowlist'/'prompt_seed'` + skills 三态用例之一），确认测试先红后绿
    - `pytest tests/unit/agent/test_runtime_active_enabled_tools.py -q` → 7 passed（None/显式/空
      allowlist 三态 + 非活动 run 内调用报错）；先红后绿（`AttributeError: no attribute
      'resolve_active_enabled_tool_names'`）
    - `pytest tests/unit tests/contract -q -m "not e2e"` → 3151 passed（全量基线，无回归）
  - Entry: N/A（本 R 是 sdk/runtime 内部控制面，无独立入口；真实入口验证见 R4）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯逻辑/内存态单测已覆盖）
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert 78d0c3fa1`
- Commits: 78d0c3fa1
- Next: R3 — `AgentTool` 瘦身 + 类型集成

## R3 — `AgentTool` 瘦身 + 类型集成

- Context: R1/R2 备好了类型目录和 kernel 三态贯通口子，本 R 把 `AgentTool` 接上：schema 瘦身、
  类型解析、父有效工具求交、prompt_seed/skills 传递。
- Decision:
  1. schema 删 `load_skills`/`category`/`timeout_seconds`；`required=[description, prompt]`；
     `additionalProperties: false` 保留；description 由 `_build_description()` 动态拼装类型目录的
     `when_to_use` + 缺省行为，扩类型不用手改文案。
  2. `run()` 先 `_validate_new_agent_args`（现在只剩 description/prompt 非空校验）→ 再
     `resolve_agent_type(...)`（未知/大小写不对立即抛错，早于生成 `agent_id`/建 session，零副作用失败）
     → 按 `run_in_background` 分派，`type_definition` 贯穿 `_run_background`/`_run_foreground`/
     `_create_subagent_session`。
  3. `_create_subagent_session` 读 `control.directory.get(control.ref)` 拿父持久化
     `tool_allowlist`/`skills`；`tool_allowlist is not None` 直接用，否则经
     `control.list_parent_enabled_tool_names()`（R2 窄口）取活动 turn 已解析集合；对结果套
     `apply_tool_deny(parent_tools, type_definition.disallowed_tools)`；`skills` 原样传父值；
     `prompt_seed=type_definition.role_prompt_seed`。
  4. 删 `_normalize_skill_names`/`_resolve_agent_name`/`_resolve_timeout_seconds`（连带用途一起消失）；
     presenter 的 `subagent_type` 展示位由裸字符串改为省略时兜底 `general-purpose`（透明展示实际生效类型，
     而非空串——连带更新 `test_presentation.py`/`test_presentation_golden.py` 两处 golden 断言）。
- Rationale: 与 design 决策 5（description 列 whenToUse + 缺省，不进 schema enum，未知类型失败早于副作用）
  一致；"已删除仪式字段不可再传"验收标准复用现有 `_validate_args`/`additionalProperties` 通用机制
  （`test_tool_validation_errors.py` 已通用覆盖该机制本身，本层只需冻结 schema 形状，不重复断言同一逻辑——
  遵守 TESTING_GUIDE §4 跨层不重复）。
- Evidence:
  - Tests:
    - `pytest tests/unit/agent/tools/test_agent_tool.py tests/unit/test_agent_tool_schema.py -q` →
      27 passed（默认 general-purpose 全量父工具、Explore/Plan 去 write/edit/agent/skill_manage、
      父 `tool_allowlist=None` 经窄口兜底、未知/错大小写类型失败含 Available agents 且不创建任何
      session、skills 三态原样透传、类型专属 prompt_seed 含 READ-ONLY、schema 形状冻结、description
      列出三类型）
    - `pytest tests/unit tests/contract -q -m "not e2e"` → 3162 passed（含两处 presentation golden
      更新：`subagent_type` 缺省展示位从空串改为 `general-purpose`，反映实际生效类型，无功能回归）
    - `ruff check` 全部改动文件 → All checks passed
  - Entry: 见 R4（真实入口验收）
  - Frontend State Matrix: N/A（本 milestone 不改 IM 前端；已确认 `IM/frontend/src` 无
    `load_skills`/`category`/`subagent_type` 耦合）
  - Browser QA: N/A
  - E2E/Regression: N/A（本 R 行为已被 unit 层覆盖；跨进程/真实 LLM 验证放 R4，遵守
    TESTING_GUIDE §4 不跨层重复断言同一逻辑）
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 待提交后填 commit hash（见下）
- Commits: 待补
- Next: R4 — 真实入口验收 + 收尾
