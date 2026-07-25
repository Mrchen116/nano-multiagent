# Verification Report: feat-474

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 |
| Correctness | 11/11 |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: `M1-agent-type-ergonomics/tasks.md` 全部 4 个 Roadpoint（R1-R4）均标 `[DONE]`，4/4 complete。逐条核实证据（非只看标记）：
  - R1（内置类型目录模块）: `src/agent/platform/tools/subagent_types/__init__.py` 已新增，`tests/unit/agent/tools/test_subagent_types.py` 14 用例覆盖 resolve/deny/文案。
  - R2（kernel 三态扩展 + runtime 窄口）: `_SessionSubagentControl.create_subagent`（`src/agent/sdk/kernel.py:130-180`）已贯通 `tool_allowlist`/`prompt_seed`，`skills` 三态不折叠；`AgentEngine.resolve_active_enabled_tool_names`（`src/agent/core/agent/runtime.py:998-1031`）已新增。
  - R3（`AgentTool` 瘦身 + 类型集成）: `src/agent/platform/tools/builtins/agent.py` schema 已删 `load_skills`/`category`/`timeout_seconds`，`_create_subagent_session` 已接入类型目录 + 父工具求交。
  - R4（真实入口验收 + 收尾）: `progress.md` R4 段记录三条真实旅程（默认可写 / Explore 只读被验证 / 未知类型精确报错文案），窄测试与全量门禁证据齐全；本轮复核未发现 worktree 内遗留 scratch 产物（`git status --porcelain` 干净）。
- Spec 覆盖：spec.md 三条 Requirement（调用更轻 / 三类型可区分 / 未知类型失败可理解）+ 附加的「后台超时与插话行为保持产品语义」共 4 条 Requirement、11 条 Scenario，逐条核实见下方 Correctness 表，均有对应实现，无缺失。
- Prototype / Reference 覆盖：design.md 无「## 前端原型」段，本 unit 不改前端；N/A。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 最少参数即可新建子 agent（默认 general-purpose） | `agent.py:230-253`（`run`→`resolve_agent_type(None)`→`DEFAULT_AGENT_TYPE_NAME`） | `test_agent_tool.py::test_default_omitted_type_resolves_general_purpose_with_full_parent_tools` | covered |
| 旧仪式字段不再被要求（load_skills/category/timeout_seconds 已删，多传即失败） | `agent.py:176-218`（schema `required=[description,prompt]`，`additionalProperties:false`） | `test_agent_tool_schema.py::test_agent_tool_schema_freezes_public_surface`；通用校验机制见 `test_tool_validation_errors.py` | covered |
| 默认 general-purpose 能改代码类工作 | `subagent_types/__init__.py:54-71`（`disallowed_tools=frozenset()`）；真实验证见 `progress.md` R4 旅程 1 | 单测 + R4 真实入口（子 agent 真写文件、主 agent 读回校验） | covered |
| Explore 只读探索，不能改仓库 | `subagent_types/__init__.py:74-91`（deny 含 write/edit/agent/skill_manage）；真实验证见 R4 旅程 2 | `test_agent_tool.py::test_read_only_types_drop_write_edit_agent_skill_manage`；R4 用 `bash ls` 独立确认文件未创建 | covered |
| Plan 只读出方案，不能改仓库 | 同上（`_PLAN` 同 deny 集） | 同上（参数化覆盖 Explore/Plan） | covered |
| 主 agent 能知道有哪些类型可选（含默认） | `agent.py:141-166`（`_build_description` 动态列 whenToUse + 缺省） | `test_agent_tool_schema.py::test_agent_tool_description_lists_built_in_types_and_default` | covered |
| 未知类型名失败并列出可用类型 | `subagent_types/__init__.py:135-156`（`resolve_agent_type` 抛 `ToolError` 含 `Available agents: …`） | `test_subagent_types.py::test_unknown_or_wrong_case_names_fail_with_available_agents`；`test_agent_tool.py::test_unknown_or_wrong_case_type_fails_with_available_agents`（含 `control.created==[]` 验证零副作用）；R4 旅程 3 真实验证精确文案 | covered |
| 错误大小写按未知类型失败（如 `explore`） | 同上（`_BY_NAME` 精确匹配，区分大小写） | 同上（parametrize 含 `explore`/`PLAN`/`general_purpose`） | covered |
| 前台过久仍自动转后台，且不可调超时参数 | `agent.py:33`（`_DEFAULT_FOREGROUND_BUDGET=120.0` 常量）+ schema 无 `timeout_seconds` 字段 | `test_agent_tool.py::test_foreground_timeout_hands_off_and_watcher_completes`（既有回归，行为未退化）+ schema freeze 测试确认字段已删 | covered |
| 运行中仍可向子 agent 插话（agent_id 续跑不重建类型配置） | `agent.py:428-495`（`_run_continuation`/`_resume_subagent` 全程不调用 `resolve_agent_type`，只读已持久化配置） | `test_agent_tool.py::test_running_continuation_requires_live_delivery`、`test_terminal_continuation_resumes_same_conversation`（既有回归） | covered |
| 子 agent skills 不宽于父（三态不折叠） | `kernel.py:170`（`skills=tuple(skills) if skills is not None else None`，不再 `if skills else None`）；`agent.py:650`（`skills=parent_session.skills` 原样传） | `test_kernel_create_subagent.py::test_skills_three_states_pass_through_without_folding`；`test_agent_tool.py::test_child_skills_mirror_parent_without_folding`（parametrize None/()/非空） | covered |

无 WARNING 级偏离；无缺测试；未见测试堆积（新增测试均对应新行为，无跨层重复断言同一逻辑——`tasks.md` 测试策略已显式规避）。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: 内置类型目录归属 platform，定义含 core `PromptSlotSeed`，禁 platform import `agent.sdk` | 是 | `subagent_types/__init__.py:8-13`（docstring 分层约束）+ import 仅 `agent.core.*`；`tests/contract/test_platform_no_sdk_imports.py` 机械守卫，实测通过 |
| 决策 2: Explore/Plan 相对父有效工具 deny-list 求交；general-purpose 显式写满（禁 `None`→registry 全量） | 是 | `agent.py:630-637`（`_create_subagent_session` 始终产出显式 `list`，从不回传裸 `None`）；`_READ_ONLY_DENY={write,edit,agent,skill_manage}`（`subagent_types/__init__.py:27`） |
| 决策 3: 类型角色文案经 core `PromptSlotSeed` 写入，不继承父产品四槽 | 是 | `_seed()` 只产 `PromptSlotSeed(head=..., body=...)`（`subagent_types/__init__.py:46-51`）；`create_subagent` 内部控制面直写 `NewSession.prompt_seed`，不经 sdk `PromptSlots`（`kernel.py:144-149` 注释 + 176 行实现） |
| 决策 4: 子 session 继承父 `skills`，不再提供 load_skills 覆盖；修三态折叠 bug | 是 | `agent.py:650`（`skills=parent_session.skills`）；`kernel.py:170` 三态不折叠；单测覆盖见 Correctness 表 |
| 决策 5: `subagent_type` 为可选 string（非 schema enum）；description 列 whenToUse；未知类型失败含 Available agents | 是 | `agent.py:192-198`（schema `subagent_type` 为纯 `string` 类型，无 enum）；`_build_description()` 动态拼装 |
| 决策 6: 单 M1 一次交付 | 是 | 本 unit 仅 1 个 milestone 目录 `M1-agent-type-ergonomics/`，与 design Milestone 表一致 |
| 分层：`platform → core`，禁 `platform → sdk` | 是 | 同决策 1 证据；`AgentEngine.resolve_active_enabled_tool_names` 落点在 core（`runtime.py:998`），sdk 只做委派（`kernel.py:182-191`），无反向依赖 |
| 依赖方向 / 模块边界（§4.3 架构自洽） | 是 | 未见产品包（CLI/Gateway）直接 import `agent.core`/`agent.platform` 内部；全量 `tests/contract` 套件（含既有 `test_agent_sdk_boundary_contract.py`/`test_core_no_platform_imports.py`）在全量跑中通过 |
| 复用 vs 平行（§4.3） | 是 | 未新造执行通道；扩展既有「session 配置决定工具集 + prompt slots」机制（`tool_allowlist`/`prompt_seed`/`skills` 均为 `NewSession` 既有字段），符合 design"本变更沿用的既有模式" |

### Prototype / Reference Contract

N/A（design.md 无「## 前端原型」段；本 unit 不改前端，产品消费侧无独立契约增量）。

## 补充：全量回归基线

- 窄测试：`pytest tests/unit/agent/tools/test_subagent_types.py tests/contract/test_platform_no_sdk_imports.py tests/unit/agent/test_kernel_create_subagent.py tests/unit/agent/test_runtime_active_enabled_tools.py tests/unit/agent/tools/test_agent_tool.py tests/unit/test_agent_tool_schema.py -q` → 53 passed
- 全量基线：`pytest tests/unit tests/contract -q -m "not e2e"` → 3162 passed（与 `progress.md` R3/R4 记录的基线数一致，无回归）
- `ruff check` 改动文件（`subagent_types/__init__.py` / `agent.py` / `kernel.py` / `runtime.py`）→ All checks passed
- worktree 复核未见未提交的残留（`git status --porcelain` 干净）

## Issues

（无发现。台账无 CRITICAL / WARNING / SUGGESTION。）

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

无。
