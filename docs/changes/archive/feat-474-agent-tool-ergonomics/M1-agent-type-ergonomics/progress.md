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
- Rollback: `git revert fc9326db1`
- Commits: fc9326db1
- Next: R4 — 真实入口验收 + 收尾

## R4 — 真实入口验收 + 收尾

- Context: §0.3 要求新功能至少一条真实入口验证；design Runbook 建议用 Coding CLI 或 Web IM 对话
  真实调用 `agent` 工具。R1-R3 已用单测覆盖内部逻辑，本 R 补一条跨真实 LLM 的端到端确认。
- Decision: 在 worktree 内用 `PYTHONPATH=src python3 -m coding_cli.main --text "<中文自然语言指令>"`
  （真实 LLM，本地代理 `kimiCoding:K2.6`，`http://127.0.0.1:4000`）跑三个旅程：
  1. 不传 `subagent_type`（默认）派前台子 agent 写文件 → 子 agent 真的写入并被主 agent 读回，
     presentation 显示 `"subagent_type": "general-purpose"`。
  2. `subagent_type=Explore` 派前台子 agent 尝试写文件 → 子 agent 自陈"没有 write/edit 工具"，
     主 agent 额外用 `bash ls` 确认文件确实未被创建。
  3. 显式传不存在的 `subagent_type=oracle` → 工具调用 `status=failed`，`error` 精确等于
     `"Agent type 'oracle' not found. Available agents: general-purpose, Explore, Plan"`，
     主 agent 原样转述。
- Rationale: 三条旅程精确对应 spec 三条核心 Requirement（轻量派发默认类型 / 类型能力可区分 /
  未知类型失败可理解），且都跑过真实 LLM + 真实 Kernel + 真实文件系统，不是 mock 出的假设行为。
  按 TESTING_GUIDE §6，这属于一次性验收证据（终端记录），不落 `test_*.py`（已有的 unit 层覆盖同一
  逻辑的确定性回归，二者不重复）。
- Evidence:
  - Tests: `pytest tests/unit tests/contract -q -m "not e2e"` → 3162 passed（收尾门禁，与 R3 相同基线）
  - Entry:
    - 旅程 1（默认 general-purpose 可写）：`tool_end` 显示
      `"subagent_type": "general-purpose"`，子 agent 结果 `content` 确认文件已含
      `FEAT474_DEFAULT_OK`；主 agent 独立 `read` 校验内容一致。终端记录：本节 R4 对应的
      shell 会话输出（未落盘为文件；如需复查可按本段旅程 1 的 prompt 在同环境重跑）。
    - 旅程 2（Explore 只读）：子 agent 原话"没有文件写入/编辑工具...无法写文件"；主 agent
      `bash ls ./feat474_r4_explore_should_fail.txt` 返回 `No such file or directory`，
      证明确实没有写权限，不只是嘴上说没有。
    - 旅程 3（未知类型失败）：`tool_end.status=failed`，
      `error="Agent type 'oracle' not found. Available agents: general-purpose, Explore, Plan"`
      与 R1 单测断言的文案完全一致。
    - 验证后清理：三次旅程产生的 `.nanocode/`（CLI 会话存储）与 scratch 文件
      （`feat474_r4_scratch.txt` 等）已删除，未提交进 worktree。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（跨真实 LLM 的行为已现场验证；不新增 e2e 用例——design 未要求，
    reviewer 阶段会用同类真实旅程独立复验，避免同一逻辑在 worker/reviewer 两层重复固化）
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 本 R 无代码变更（纯验收），无需回退
- Commits: （无新 commit；tasks.md/progress.md 收尾一并提交，见下）
- Next: 本 milestone 已完成；LOGBOOK 无新增沉淀（本期未发现超出既有记录的可复用经验/坑）

## Fix 1 — reviewer 反馈循环小修：续聊误标 general-purpose（§FL 小修快车道）

省略 §2.3 全量六读、§3 tasks.md 模板、§2.4 复用原 worktree 的部分——理由 FL①/②：本 fix
单点、一步到位，改动收敛在 `_AgentPresenter` 一处类 + `_run_continuation`/`_resume_subagent`
两处返回值，未跨 3+ 文件也未超 100 行；已按派单方要求读了 design.md 相关段（决策 5 / 类型解析
时序图）、现有 `agent.py` presenter 实现、`tests/unit/platform/tools/test_presentation*.py`
+ `tests/unit/agent/tools/test_agent_tool.py`。**未跳过 §FL 的红测豁免**——finding 是行为/契约
类改动，先写了红测再修（见下）。

- Context（CONFIRMED finding）: `_AgentPresenter.format_start`/`format_end` 无条件把缺省
  `subagent_type` 展示成 `DEFAULT_AGENT_TYPE_NAME`（general-purpose）。续聊路径
  `agent(agent_id=..., prompt=...)` 通常不传 `subagent_type`，`AgentTool.run` 直接走
  `_run_continuation`——这条路径从不调用 `resolve_agent_type`，真实类型只存在于 registry
  record / JSONL metadata 里。于是 UI 把 Explore/Plan 续聊误标成 general-purpose。
- Decision（治本，未在崩溃点贴补丁）:
  1. presenter 新增 `_resolve_display_type(args, output, is_continuation)`：显式传
     `subagent_type` 时以调用参数为准；新建（无 `agent_id`）缺省 `general-purpose`（保留
     R3 既有行为，反映 `resolve_agent_type` 的真实运行时缺省）；续聊（有 `agent_id`）没有
     显式类型时，优先读 `output["agent_type"]`（真实类型），拿不到就返回 `None`——`detail`
     里不写这个 key，而不是伪造一个类型。
  2. `format_start`/`format_end` 按上述结果决定是否把 `subagent_type` 写进 `detail`；
     `None` 时省略 key（不是空串——省略在前端 `str(undefined) === ""` 语义下渲染效果一致，
     但更诚实地表达"未知"而非"已知为空"）。
  3. `_run_continuation` 的 `message_queued` 分支、`_resume_subagent` 的返回值补
     `"agent_type": record.agent_type or ""` / `agent_type or ""`——三条续聊子路径（运行中
     插话、终态恢复、冷启动从 JSONL 重建）此前都拿到了真实 `agent_type`（分别来自
     `record.agent_type` / `current.agent_type` / `metadata.get("agent_type")`）却从未透传给
     调用方，presenter 因此拿不到真值只能瞎猜。这一步是"更好"选项（README 里 reviewer 给的
     第 3 条修法）：数据本来就在手边，补一个字段传递不破坏分层（`AgentTool` 内部方法间传递，
     不涉及 `agent.sdk`/`agent.core` 边界）。
- Rationale: 与 §0.1 一致——根因是"续聊路径从不解析类型，presenter 却假装它解析了"，不是展示层
  拍脑袋加个 if。选"读真实值优先、拿不到就不展示"而非"续聊一律留空"，是因为数据已经在
  `_run_continuation` 内部唾手可得，多传一个字段的成本远低于继续让 UI 展示空白。
- Evidence:
  - Tests:
    - 红：新增 5 个 presenter 用例（`test_start_continuation_without_subagent_type_omits_it`
      / `test_end_continuation_without_real_type_omits_it` /
      `test_end_continuation_uses_real_type_from_result` 等，见
      `tests/unit/platform/tools/test_presentation.py::TestAgentPresenter`）+
      3 个 `AgentTool` 返回值断言（`tests/unit/agent/tools/test_agent_tool.py` 里
      `test_terminal_continuation_resumes_same_conversation` /
      `test_running_continuation_message_queued_carries_real_agent_type`（新增）/
      `test_cold_continuation_rehydrates_through_control`）——改动前跑本组用例，3 个
      presenter 断言 + 3 个 `KeyError: 'agent_type'` 全红，确认失败点=缺失能力。
    - 绿：`pytest tests/unit/platform/tools/test_presentation.py
      tests/unit/platform/tools/test_presentation_golden.py
      tests/unit/agent/tools/test_agent_tool.py -q` → 90 passed（含既有 golden 用例
      `test_format_start_golden[agent-...]` 不变——新建路径缺省展示不受影响）。
    - 全量基线：`pytest tests/unit tests/contract -m "not e2e" -q` → 3168 passed，无回归。
  - Entry: N/A——presenter 是纯格式化层（无 I/O、无跨进程），行为已被
    `tests/unit/agent/tools/test_agent_tool.py` 里真实 `AgentTool.run()`（非 mock 内部逻辑，
    只 fake 了 runner/registry 边界，与既有测试体系一致）串起 registry→presenter 的完整数据
    流覆盖；本 fix 范围内无需另起真实 LLM/浏览器旅程（R4 已验证过同一 `agent` 工具的真实入口
    可用性，本 fix 不改变工具的功能行为，只改展示层怎么读已有数据）。
  - Frontend State Matrix: N/A（未改前端代码；已确认 `AgentCard`
    `str(detail.subagent_type)` 对 `undefined` 返回 `""`，省略 key 与旧的空串展示效果一致，
    不需要前端改动或新增前端测试）。
  - Browser QA: N/A
  - E2E/Regression: N/A（见上，单测已覆盖数据流全链路，跨层不重复）
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert 7282438f7`
- Commits: 7282438f7
- Next: 本 fix 完成，无后续动作
