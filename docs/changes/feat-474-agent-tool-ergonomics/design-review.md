# Design 评审（第二轮）: feat-474

**结论**: Approved

> 对照首轮 Issues：PromptSlotSeed 分层、skills MODIFIED+继承 ADDED、background-tasks 锚「通知」Requirement、旧字段 `additionalProperties: false`、父 tools 窄口取法——均已在当前磁盘版 `design.md` + `specs/kernel/*` 闭合。本轮重新追生产路径与 delta 锚点，台账无未化解 ✗，四角度进攻无存活发现。

**核实台账**（逐条核过的承重原子；结论附证据，不是打勾）:

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `AgentTool` 是本期主改 / 生产派发入口 | 从 `build_kernel` 正向追 wiring | ✓ `build_kernel` → `register_builtin_tools(..., wiring=background_task_wiring)`（`src/agent/sdk/kernel.py:666`）→ `AgentTool(wiring=wiring)`（`src/agent/platform/tools/builtins/__init__.py:57`）；CLI/PA 均经 `build_kernel`（`coding_cli/product.py:144`、`personal_assistant/product.py:423`）。新建/前台/续跑均进 `AgentTool.run`（`agent.py:223-228`） |
| 现状: `create_subagent` 只传 `skills`+`metadata`，不传 `tool_allowlist`/`prompt_seed` | 读 sdk 控制面 | ✓ 签名仅 `workspace_root/skills/metadata/parent_session_id`；`NewSession(...)` 未传 allowlist/seed（`src/agent/sdk/kernel.py:130-147`） |
| 现状: `skills` 空序列被折叠成 `None` | 读折叠表达式 | ✓ `skills=tuple(skills) if skills else None`（`kernel.py:143`）；`AgentTool` 另有 `skills=load_skills if load_skills else None`（`agent.py:598`） |
| 现状: `NewSession` 已有 `tool_allowlist`/`prompt_seed`/`skills` | 读 core 类型 | ✓ `src/agent/core/session/types.py:128-137` |
| 现状: `tool_allowlist is None` → 落默认全套，子可比父更宽 | 从 runtime 解析追 | ✓ `_resolve_session_available_tools_from_config`：`None` → `_default_tool_ids` 或 registry 全量（`runtime.py:1111-1117`）；子经 `create_subagent` 未写 allowlist → 恒 `None` |
| 现状: `RuntimeRunner` 跑子 turn，本期几乎不动 | 追 background wiring | ✓ `wiring.py:76-83` 生产装 `RuntimeRunner`；无平行「仅测试」子 agent runner 替代生产路径 |
| 现状: 产品只许 import `agent.sdk`；platform ↛ sdk | 对 SPEC / contract + Grep | ✓ `tests/contract/test_agent_sdk_boundary_contract.py:14`；`src/agent/platform/**` 无 `agent.sdk` import |
| 现状: 子模型继承父 run；不引入 `model` | 对照代码 + spec 非目标 | ✓ `agent.py:289-301` 传 `model=control.resolve_run_model()`；spec 非目标含 CC `model` |
| 现状: 120s 前台预算、`agent_id` 续跑、`<task-notification>` 语义在 | 读 AgentTool | ✓ `_DEFAULT_FOREGROUND_BUDGET = 120.0`（`agent.py:27`）；超时转后台 `async_launched`（`355-381` 一带）；续跑 `_run_continuation` |
| 现状: `subagent_type` 基本是标签；`load_skills` 硬校验 | 读校验 / metadata | ✓ `_resolve_agent_name` 只产字符串（`855-862`）；`_validate_new_agent_args` 强制 `load_skills` + category/type 二选一（`636-665`） |
| 现状: 契约层与代码冲突（标签 / load_skills） | 对 canonical | ✓ `background-tasks.md:105` 仍写「subagent_type / category」；`skills.md:136-140` 仍有 load_skills Scenario——需本 unit delta |
| 现状: 父 `tool_allowlist`/`skills` 可读 | 追 directory.get | ✓ `control.directory.get(control.ref)` → `Session` 含 `skills`/`tool_allowlist`（`directory.py:124-135` + `models.py:24-27` + `_session_from_config` `272-281`） |
| 现状: schema 已 `additionalProperties: false` | 读 schema + 校验器 | ✓ `agent.py:209`；未知字段走校验失败（`registry.py:581-591`）——删 properties 后仍传旧字段会失败 |
| 决策 1: 目录放 platform；定义含 deny + `PromptSlotSeed`；禁 sdk `PromptSlots` | 拍死?分层? | ✓ 拍死归属与形状；明确 core `PromptSlotSeed`、禁止 platform import `agent.sdk.PromptSlots`（design 决策 1 + 接口段 + M1 退出标准）——首轮 CRITICAL 已闭合 |
| 决策 2: deny-list ∩ 父有效工具；GP 显式写满；起步 DENY | 拍死?有据? | ✓ DENY=`{write,edit,agent,skill_manage}`；修「子可比父更宽」洞；Bash+提示约束已写风险 |
| 决策 3: 不继承父产品 slots；类型文案 head+body 经 seed | 拍死? | ✓；与决策 1 分层一致 |
| 决策 4: 子 skills 继承父；修三态 | 拍死?数据流? | ✓；父可读 + 修 `create_subagent` 折叠；注明 `create_session` 同源折叠本期不扩 |
| 决策 5: 可选 string + description 列类型；未知失败 + Available agents | 拍死? | ✓；对齐澄清 Q5/Q8/Q9 |
| 决策 6: 单 M1 | 拆分举证? | ✓ 粘在同一创建路径；拒绝横切 |
| 接口: `create_subagent` 扩 `tool_allowlist`/`prompt_seed`/`skills` 三态 | 数据流闭合?分层? | ✓ seed **直接**写 `NewSession.prompt_seed`；公共 `create_session` 仍经 `PromptSlots`→`_to_prompt_seed`（`kernel.py:345-362`）；platform 不碰 sdk |
| 接口: 父有效工具窄口取法 | 拍死?可实施? | ✓ 三步：`directory.get` → 非空元组直用 → `None` 走 control 窄口（如 `list_parent_enabled_tool_names()`），禁止 AgentTool 依赖私有 `_resolve_*`。空元组 `()` 未单独点名，但 `is not None` 自然读法即可；见 Recommendations |
| 风险表: 旧字段校验失败 | 拍死? | ✓ 对外表面表 + 风险表拍死 `additionalProperties: false` → 校验失败；tools-hooks ADDED Scenario「已删除的仪式字段不可再传」对齐——首轮 WARNING 已闭合 |
| spec Req: agent 调用更轻 / 去掉赘余传参 | design 落点? | ✓ 决策 4/5 + 对外表面表 + M1 退出 |
| spec Scenario: 最少参数默认 general-purpose | 覆盖? | ✓ 决策 5 + 序列图缺省 |
| spec Scenario: 旧仪式字段不再被要求 | 覆盖? | ✓ schema 删三字段；required 仅 description+prompt；多传失败 |
| spec Req: 三种真类型可区分（GP/Explore/Plan） | 覆盖? | ✓ 决策 2+3 + 目录三类型 |
| spec Scenario: 主 agent 能知道可选类型 | 覆盖? | ✓ description 列出 whenToUse + 缺省 |
| spec Req: 未知/错大小写失败可理解 | 覆盖? | ✓ 决策 5；大小写敏感字面量 |
| spec Scenario: 前台过久转后台且不可调超时 | 覆盖? | ✓ 保留常量预算；删 `timeout_seconds`；background-tasks MODIFIED 并入 |
| spec Scenario: 运行中 agent_id 插话 | 覆盖? | ✓ 「续跑不改配置」+ 行为不变 |
| 澄清 Q1–Q9 | 不冲突? | ✓ 均有对应决策；Q7 子→主边推为非目标 |
| 非目标: 子→主推、claude*、verification、model/isolation、自定义目录、SendMessage | 越界? | ✓ design 未做；决策 1 显式不预埋可注入 registry |
| delta `tools-hooks.md` ADDED 真类型轻量派发 | 锚?用法?THEN? | ✓ 平行新增，ADDED 合适；THEN 消费者可观察；含「已删除字段不可再传」 |
| delta `tools-hooks.md` MODIFIED/REMOVED | — | ✓ 无整段替换/删除；注明既有 detail-prompt Scenario 保持 |
| delta `background-tasks.md` MODIFIED「通知」Requirement | 锚标题?保留 Scenario?并入不可调超时? | ✓ 锚定 canonical 既有标题「后台任务完成后发起 session 收到结果通知，跨 workspace 可靠」（`docs/specs/kernel/background-tasks.md:14`）；五条 Scenario 忠实保留；正文 +「超预算转后台」Scenario 并入「无法经参数自定义前台预算」——首轮 WARNING 已闭合 |
| delta `background-tasks.md` MODIFIED「派生子 agent…隔离」 | 锚?Scenario? | ✓ 锚定既有标题；WHEN 改为 description+prompt、可选 type（去掉 category） |
| delta `skills.md` MODIFIED「preview/list/runtime 一致」 | 锚?删 Scenario?保留其余? | ✓ 锚定既有标题（`skills.md:122`）；归并说明删 load_skills Scenario；其余三条 Scenario 保留——首轮 CRITICAL 已闭合 |
| delta `skills.md` ADDED 继承父 skills | 有可观察 Scenario? | ✓ ADDED Requirement + Scenario「子会话 skills 与父会话一致且不更宽」——首轮 WARNING 已闭合 |
| delta `prompts.md` ADDED 类型角色指引 | ADDED?THEN? | ✓ 平行新能力；THEN 为装配后 slots 可观察内容（消费者 PromptSlots 语义）；实现落点为 core seed（design 已写明） |
| gateway/im/cli no spec delta | 合适? | ✓ 产品只消费内核 `agent` 行为 |
| M1 垂直切片 / 退出两轨 | 横切?可验? | ✓ 单垂直切片；`[reviewer]` 对齐 spec；`[worker]` 含三态/deny/文案/additionalProperties/platform 无 sdk import；范围无并行冲突 |
| 整体: 给人层可读 / 接口闭合 / 无 TBD | 通读 | ✓ 总览+图+决策结论可扫；数据流闭合；Changelog/Unit branch/Runbook 齐；无常驻新服务且给了可选重启命令 |

**架构进攻**（四角度逐个走；每条发现带具体长远代价）:

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 决策 1+3+接口：目录/`AgentTool` 在 platform，seed 类型，`create_subagent` 接 seed | ✓ 走完无存活发现——platform 只产/传 core `PromptSlotSeed`；sdk 内部控制面直写 `NewSession.prompt_seed`；公共面仍 `PromptSlots`→`_to_prompt_seed`。无 platform→sdk 反向依赖，不撞分层硬规则 |
| 该不该存在 | 新增 `subagent_types/` 目录模块 | ✓ 走完无存活发现——删除测试：长文案+三类型+共用 `format_available_agents` 内联进 `agent.py` 会撑爆工具文件（决策 1 拒 C）；非假想多态工厂 |
| 深还是浅 | `resolve_agent_type` / `apply_tool_deny` / 父工具窄口 | ✓ 走完无存活发现——薄封装换编排清晰；窄口避免 AgentTool 探 runtime 私有方法；非重造 runner |
| 治本还是补丁 | 走 session `tool_allowlist`+`prompt_seed` 而非新执行通道 | ✓ 走完无存活发现——复用既有会话配置扩展点，堵住「子 `None`→全量」洞；非在 AgentTool 上叠特例执行通道 |

**Issues**:

（无。首轮 2 CRITICAL + 3 WARNING 均已闭合；本轮无新升级项。）

**Recommendations**（不阻断门禁，作者/worker 自行取舍）:

- 父有效工具取法可再点一句：`tool_allowlist is not None`（含空元组 `()`）即用持久化名单，仅 `None` 走窄口——与 skills 三态措辞对称，避免字面「非空」误导。
- `Kernel.create_session` 同源 skills 折叠（`kernel.py:989`）已注明本期不修；若日后父会话「零 skill」三态也要严，另开即可。

---

**给 orchestrator**: 台账无 ✗、进攻无存活发现 → **可进 `change-orchestrator`**，按单 M1 `feat-474-M1` 派 worker。
