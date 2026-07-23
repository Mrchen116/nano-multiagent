# feat-474-M1: agent-type-ergonomics — Tasks

> 对齐: ../design.md v1（Changelog 2026-07-23 design-review 修订版）

## 目标

`agent` 工具去掉仪式字段（`load_skills` / `category` / `timeout_seconds`），落地三种内置真类型
（`general-purpose` 默认 / `Explore` / `Plan`），未知类型失败并列出可用类型；子 session 显式写入
`tool_allowlist` + 类型 `prompt_seed` + 继承父 `skills`（三态不折叠）；platform 不 import `agent.sdk`。

## 退出标准（抄 design.md Milestone 表本行）

- `[reviewer]` 覆盖 spec：最少参数默认 general-purpose；Explore/Plan 只读；未知/错大小写失败含
  Available agents；无 load_skills/category/timeout_seconds（多传则失败）；前台超时自动转后台仍在；
  agent_id 插话仍在；子 agent skills 不宽于父。
- `[worker]` 最窄相关 pytest 全绿（AgentTool schema/类型解析/deny 求交/skills 三态/未知类型文案/
  additionalProperties）。
- `[worker]` 子 session 新建路径写入显式 tool_allowlist + 类型 PromptSlotSeed + 继承 skills；platform
  无 `agent.sdk` import；续跑不改配置。

## 测试策略

- 被测行为（来自退出标准）：
  1. 最少参数（无 subagent_type/无 load_skills/无 category/无 timeout_seconds）新建成功，默认 general-purpose
  2. schema 不再含 load_skills/category/timeout_seconds；required 仅 description+prompt；additionalProperties=false（多传旧字段即失败）
  3. general-purpose 子 session tool_allowlist = 父有效工具全集（显式列表，不再是 None）
  4. Explore/Plan 子 session tool_allowlist = 父有效工具 − {write, edit, agent, skill_manage}
  5. 未知类型 / 错误大小写（如 `explore`）→ ToolError，消息含 "Available agents: general-purpose, Explore, Plan"
  6. 子 session 继承父 skills 且三态不折叠（None/非空/空序列都原样传递，不再被 `if skills else None` 折叠成 None）
  7. 子 session 写入类型专属 PromptSlotSeed（Explore/Plan 只读指引；general-purpose 通用执行指引），不含父产品 PromptSlots 副本
  8. 续跑（`agent_id` 插话/resume）不重建类型配置，不重新解析 tool_allowlist/prompt_seed
  9. 前台超时仍自动转后台、`agent_id` 插话仍进同一子 agent（存量行为回归，不应退化）
  10. platform 新模块不 `import agent.sdk`（契约层面校验，走 `tests/contract`）
- 已有测试在：
  - `tests/unit/agent/tools/test_agent_tool.py`（扩展：新增类型解析/deny/schema 精简后的用例，改造 fake `_Control`）
  - `tests/unit/test_agent_tool_schema.py`（扩展：冻结新 schema 形状，删除旧字段断言）
  - `tests/unit/agent/test_runtime_tool_allowlist_enforcement.py`（参考模式，不改；新增同构测试验证 `resolve_active_enabled_tool_names` 窄口）
  - 无，新建 `tests/unit/agent/tools/test_subagent_types.py`，理由：新模块（类型目录解析/deny/文案）无既有覆盖文件
  - 无，新建 `tests/unit/agent/test_runtime_active_enabled_tools.py`，理由：`resolve_active_enabled_tool_names` 是 runtime 新增窄口，`test_runtime_tool_allowlist_enforcement.py` 已聚焦另一行为（allowlist 执行期强制），不同断言主题不塞进同一文件避免超 400 行
  - `tests/unit/sdk/`（若存在 kernel create_subagent 相关文件则扩展；否则在 `tests/unit/agent/tools/test_agent_tool.py` 内经 AgentTool 间接覆盖 kernel 三态传递即可，不新建 kernel 专属测试文件——避免为同一行为跨层重复断言）
  - 无，新建 `tests/contract/test_platform_no_sdk_imports.py`，理由：现有 `test_core_no_platform_imports.py` 只守 core 不 import platform/sdk，没有守 platform 不 import sdk 的对称契约；本期新增 `subagent_types/` 首次在 platform 内直接消费 core `PromptSlotSeed`，必须补这条方向守卫防回归
- 落层/目录/marker：`tests/unit/`，无 marker（纯逻辑 + 内存态 AgentEngine/ConversationSession，无真进程/浏览器/真 LLM）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`coding_cli --text` 真实 LLM 调用记录（终端输出，记入 progress.md，不落测试文件）

## Roadpoints

### R1 — 内置类型目录模块

- 步骤：新增 `src/agent/platform/tools/subagent_types/`：类型定义（`name` / `disallowed_tools` / `when_to_use` / `role_prompt_seed: PromptSlotSeed`，import 自 `agent.core.session.types`）；`resolve_agent_type(name) -> Definition`（未知抛 ToolError 含 Available agents）；`format_available_agents()`；`apply_tool_deny(parent_tools, disallowed)`。三类型：`general-purpose`（disallowed=空）、`Explore`/`Plan`（disallowed={write,edit,agent,skill_manage}）。角色文案参考 `cc-subagent-system-prompts/*.md`（改写 nano 工具名，非逐字抄）。
- 验证：新建 `tests/unit/agent/tools/test_subagent_types.py`：resolve 三个已知类型成功；未知类型/错误大小写抛 ToolError 且消息含 Available agents 列表；`apply_tool_deny` 正确求交且保序；`format_available_agents()` 顺序稳定。

### R2 — kernel `create_subagent` 三态扩展 + runtime 窄口

- 步骤：`_SessionSubagentControl.create_subagent` 增加 `tool_allowlist` / `prompt_seed` 参数并贯通 `NewSession`；修 `skills` 三态折叠 bug（`None`/`()`/非空原样传递，不再 `if skills else None`）。`AgentEngine` 新增公开方法 `resolve_active_enabled_tool_names(session_id)`（镜像 `resolve_run_model` 的 `_active_state` 读取模式），供 `_SessionSubagentControl.list_parent_enabled_tool_names()` 委派。
- 验证：扩展 `tests/unit/agent/tools/test_agent_tool.py` 里对 `control.created[...]` 的断言覆盖新参数（经 R3 的 AgentTool 改造后一并跑通）；新建 `tests/unit/agent/test_runtime_active_enabled_tools.py`：仿 `test_runtime_tool_allowlist_enforcement.py` 模式，用真实 `AgentEngine` + `ConversationSession`，工具执行期调用 `resolve_active_enabled_tool_names` 断言与 `tool_allowlist=None`（走默认集合）和显式 allowlist 两种父配置下的返回值一致；未在活动 run 内调用时抛错。

### R3 — `AgentTool` 瘦身 + 类型集成

- 步骤：schema 删 `load_skills`/`category`/`timeout_seconds`；`required=[description, prompt]`；`additionalProperties: false` 保留；description 列出三类型 whenToUse + 默认。`_resolve_agent_name` 改为解析类型目录（缺省 general-purpose，未知抛错）。`_create_subagent_session` 计算父有效工具（`control.directory.get(control.ref)` 读 `tool_allowlist`，非 None 直接用；None 则 `control.list_parent_enabled_tool_names()`）→ 应用类型 deny → 传入 `create_subagent(tool_allowlist=..., prompt_seed=type_def.role_prompt_seed, skills=parent_session.skills)`。移除 `_normalize_skill_names` 校验路径（skill 相关字段已删）。前台预算常量保留，去掉 `timeout_seconds` 入参解析（`_resolve_timeout_seconds` 删除，直接用默认预算）。presenter/description 里的 `load_skills`/`category`/`timeout_seconds` 措辞一并清理。
- 验证：改造 `tests/unit/agent/tools/test_agent_tool.py` 的 fake `_Control`（加 `.directory`/`.ref`，或等价窄口方法）+ `_new_agent_args` 去掉 `load_skills`；覆盖：默认 general-purpose 全量父工具；Explore/Plan 工具集不含 write/edit/agent/skill_manage；未知类型失败含 Available agents；旧字段（`load_skills`/`category`/`timeout_seconds`）再传即 schema 校验失败（经 `builtin_tools()` schema 层，非 `run()` 层——`run()` 不做 schema 校验，由上游 loop 校验，需确认现状校验点并在对应层断言）。更新 `tests/unit/test_agent_tool_schema.py` 冻结新 schema 形状。

### R4 — 真实入口验收 + 收尾

- 步骤：用 `coding_cli.main --text`（真实 LLM，本地代理 `kimiCoding:K2.6`）在 worktree 内实跑：(a) 默认新建子 agent 改一个 scratch 文件；(b) `Explore` 只读探索不改文件；(c) 故意传错类型名验证失败文案。跑窄测试门禁 + 全量单测门禁。补齐 progress.md 每个 R 的证据段。检查是否有 LOGBOOK 沉淀。
- 验证：三个真实入口调用的终端记录（记入 progress.md，不落测试文件）；`<test_command>` 全绿。
