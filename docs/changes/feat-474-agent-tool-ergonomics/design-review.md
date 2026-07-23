# Design 评审: feat-474

**结论**: Issues Found

> **作者跟进（2026-07-23）**: 已按下方 CRITICAL/WARNING 改写 `design.md` 与 `specs/kernel/*`（PromptSlotSeed 分层、skills MODIFIED+继承 ADDED、background-tasks 锚既有通知 Requirement、旧字段 `additionalProperties: false`）。本文件保留首轮评审台账；是否放行以再跑一轮 design-review 为准。

**核实台账**（逐条核过的承重原子；结论附证据，不是打勾）:

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `AgentTool` 是本期主改 / 生产派发入口 | 从 `build_kernel` 正向追 wiring | ✓ `build_kernel` → `register_builtin_tools` → `AgentTool(wiring=…)`（`src/agent/sdk/kernel.py:666` + `src/agent/platform/tools/builtins/__init__.py:57`）；CLI/PA 均经 `build_kernel`（`coding_cli/product.py:144`、`personal_assistant/product.py:423`）。新建/前台/续跑均进 `AgentTool.run`（`agent.py:223-235`） |
| 现状: `create_subagent` 只传 `skills`+`metadata`，不传 `tool_allowlist`/`prompt_seed` | 读 sdk 控制面实现 | ✓ `_SessionSubagentControl.create_subagent` 签名仅 `workspace_root/skills/metadata/parent_session_id`；`NewSession(...)` 未传 `tool_allowlist`/`prompt_seed`（`src/agent/sdk/kernel.py:130-147`） |
| 现状: `skills` 空序列被折叠成 `None` | 读折叠表达式 | ✓ `skills=tuple(skills) if skills else None`（`kernel.py:143`）；`AgentTool` 侧还有 `skills=load_skills if load_skills else None`（`agent.py:598`）——`[]`/`()` 都会变成「全开 skills」语义 |
| 现状: `NewSession` 已有 `tool_allowlist`/`prompt_seed`/`skills` | 读 core 类型 | ✓ `src/agent/core/session/types.py:128-137` |
| 现状: `tool_allowlist is None` → 落默认全套工具，故类型无法换工具集 | 从 runtime 解析路径追 | ✓ `_resolve_session_available_tools_from_config`：`None` → `_default_tool_ids` 或 registry 全量（`runtime.py:1111-1117`）；子 session 经 `create_subagent` 未写 allowlist → 恒 `None` → 可比父更宽。注：引擎构造未见传入 `default_tool_ids`，生产父会话通常在 `create_session(enabled_tools=…)` 已写显式名单（CLI `DEFAULT_ENABLED_TOOLS` / PA `resolve_enabled_tools`），但子会话仍掉回全量——与 design「洞」断言一致 |
| 现状: `RuntimeRunner` 跑子 turn，本期几乎不动 | 追 background wiring | ✓ `wiring.py:76-77` 生产装 `RuntimeRunner`；`AgentTool` 经 `wiring.subagent_runner.start/start_foreground` 调用；无平行「测试专用」子 agent runner 替代生产路径 |
| 现状: 产品只许 import `agent.sdk` | 对 SPEC / contract | ✓ `SPEC.md` §5；`tests/contract/test_agent_sdk_boundary_contract.py` 文档不变量 `platform ↛ sdk` |
| 现状: 子模型继承父 run；不引入 `model` | 对照代码 + spec 非目标 | ✓ `agent.py:289-301` / `350` 传 `model=control.resolve_run_model()`；spec 非目标含 CC `model` |
| 现状: 120s 前台预算、`agent_id` 续跑、`<task-notification>` 语义在 | 读 AgentTool | ✓ `_DEFAULT_FOREGROUND_BUDGET = 120.0`（`agent.py:27`）；续跑 `_run_continuation`（`401+`）；超时转后台 `async_launched`（`355-381`） |
| 现状: `subagent_type` 基本是标签；`load_skills` 硬校验 | 读校验 / metadata | ✓ `_resolve_agent_name` 只产出字符串写入 metadata（`855-862`）；`_validate_new_agent_args` 强制校验 `load_skills` 同源 + 要求 category/type 二选一（`636-665`）；无按类型换工具/prompt |
| 现状: 契约层与代码一致（标签 vs 真类型冲突） | 对 canonical | ✓ `docs/specs/kernel/background-tasks.md:105` 仍写「传齐 description + subagent_type / category」；`skills.md:136-140` 仍有 `load_skills` 校验 Scenario——与本期目标冲突，需 delta |
| 决策 1: 目录放 platform；定义形状含 deny + role slots | 拍死?自洽?分层? | ✗ 拍死了归属与形状，但与接口段 `create_subagent(prompt: PromptSlots)` 叠加后，隐含 **platform 构造 sdk.PromptSlots** 的反向依赖（见架构进攻）。单条「放 platform」合法，组合后撞 `platform → core` / `sdk → core+platform` |
| 决策 2: deny-list ∩ 父有效工具；GP 显式写满；起步 DENY 集 | 拍死?有据? | ✓ 拍死 B + DENY=`{write,edit,agent,skill_manage}`；与「子不得比父更宽」+ CC 同构；Bash 保留+提示约束已写风险 |
| 决策 3: 不继承父产品 slots；类型文案 head+body | 拍死? | ✓；对齐 CC 专用人格；走既有 PromptSlots/seed 语义 |
| 决策 4: 子 skills 继承父配置；修三态 | 拍死?数据流? | ✓ 语义拍死；父配置可读路径存在：`control.directory.get(control.ref)` → `Session.skills`（`directory.py:124-135`，`models.py:24-25`）。须修 `create_subagent` 折叠（已点名） |
| 决策 5: 可选 string + description 列类型；未知失败 + Available agents | 拍死? | ✓；对齐澄清 Q5/Q8/Q9 |
| 决策 6: 单 M1 | 拆分举证? | ✓ 粘在同一创建路径；拒绝横切；合理 |
| 风险表: 旧字段忽略或校验失败「实现选一并测」 | 拍死? | ✗ 显式 A/B 未拍死。现 schema `additionalProperties: False`（`agent.py:209`）——删掉 properties 后仍传旧字段会走哪条，worker/验收可能打架 |
| spec Req: agent 调用更轻 / 去掉赘余传参 | design 落点? | ✓ 决策 4/5 + 对外表面表 + M1 退出标准 |
| spec Scenario: 最少参数默认 general-purpose | 覆盖? | ✓ 决策 5 + 序列图缺省 |
| spec Scenario: 旧仪式字段不再被要求 | 覆盖? | ✓ schema 删除三字段；required 仅 description+prompt |
| spec Req: 三种真类型可区分（GP/Explore/Plan） | 覆盖? | ✓ 决策 2+3 + 目录三类型 |
| spec Scenario: 主 agent 能知道可选类型 | 覆盖? | ✓ description 列出 whenToUse + 缺省 |
| spec Req: 未知/错大小写失败可理解 | 覆盖? | ✓ 决策 5；大小写敏感字面量 |
| spec Scenario: 前台过久转后台且不可调超时 | 覆盖? | ✓ 保留常量预算；删 `timeout_seconds` |
| spec Scenario: 运行中 agent_id 插话 | 覆盖? | ✓ 「续跑不改配置」+ 行为不变 |
| 澄清 Q1–Q9 | 不冲突? | ✓ 均有对应决策；Q7 子→主边推为非目标 |
| 非目标: 子→主推、claude*、verification、model/isolation、自定义目录、SendMessage 拆分 | 越界? | ✓ design 未做；决策 1 显式不预埋可注入 registry |
| delta `tools-hooks.md` ADDED 真类型轻量派发 | 锚 canonical?用法?THEN? | ✓ 平行新增行为，ADDED 合适；THEN 为消费者可观察（工具说明/工具集合/失败文案）；无内部符号 |
| delta `tools-hooks.md` MODIFIED/REMOVED | — | ✓ 无整段替换/删除；注明既有 detail-prompt Scenario 保持 |
| delta `background-tasks.md` MODIFIED 前台隔离 | 锚标题?保留 Scenario? | ✓ 锚定「派生子 agent 的前台执行与内核 run 隔离」；两 Scenario 保留并改 WHEN 措辞 |
| delta `background-tasks.md` MODIFIED「超预算自动转后台（模型不可调超时）」 | 锚 canonical? | ✗ canonical **无此 Requirement 标题**；能力散落在既有「前台 subagent 超预算转后台…」等 Scenario（`background-tasks.md:46-47`）。放在 MODIFIED 下会让机械归并「替换同名条目」找不到锚；「不可调超时」语义可能落空或与旧 Scenario 双轨 |
| delta `skills.md` REMOVED load_skills Scenario | 用法对吗? | ✗ 被删的是 Requirement「同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致」下的**一条 Scenario**（`skills.md:136-140`），不是整 Requirement。写成 REMOVED + 自造标题 → 归并按名删除会 miss，旧 Scenario 残留，与「不再有 load_skills」矛盾 |
| delta `skills.md`：继承父 skills 的新行为 | 有 Scenario 吗? | ✗ 仅有「由 tools-hooks / 会话配置覆盖」散文；`tools-hooks` ADDED 也未写 skills 继承。对外可见行为变化缺契约锚 |
| delta `prompts.md` ADDED 类型 PromptSlots | ADDED 合适?THEN? | ✓ 平行新能力；THEN 为装配后 slots 可观察内容；主语为消费者/子会话 |
| gateway/im/cli no spec delta | 合适? | ✓ 产品只消费内核 `agent` 行为，无独立产品契约增量 |
| M1 垂直切片 / 退出两轨 | 横切?可验? | ✓ 单垂直切片；`[reviewer]` 对齐 spec 场景；`[worker]` 含三态/deny/文案；范围文件无并行冲突 |

**架构进攻**（四角度逐个走；每条发现带具体长远代价）:

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 决策 1（目录在 platform）+ 接口 `create_subagent(prompt: PromptSlots)` + AgentTool 编排 | ✗ 组合后要求 **platform**（`AgentTool` / `subagent_types`）产出 **sdk.PromptSlots**。分层硬规则是 `platform → core`、`sdk → core+platform`（`SPEC.md` §5）；platform 现无任何 `agent.sdk` import。不改→ worker 按字面 `from agent.sdk import PromptSlots` 写入 platform，撞分层/未来 contract；或每人自造平行 slots 类型，与 `Kernel.create_session` 的 `_to_prompt_seed` 路径漂移。应拍死：目录/AgentTool 只用 core `PromptSlotSeed`（或结构化 duck），`create_subagent` 在 sdk 内转 seed；**不要**让 platform 依赖 `PromptSlots` |
| 该不该存在 | 新增 `subagent_types/` 目录模块 | ✓ 删除测试：长文案 + 三类型 + 共用 `format_available_agents` 若内联进 `agent.py` 会撑爆工具文件（决策 1 拒 C 成立）；非假想多态工厂 |
| 深还是浅 | `resolve_agent_type` / `apply_tool_deny` 小函数 | ✓ 走完无存活发现——薄封装换来单测与 AgentTool 编排清晰，非重造 runner |
| 治本还是补丁 | 走 session `tool_allowlist`+`prompt_seed` 而非新执行通道 | ✓ 治本：复用既有会话配置扩展点，堵住「子 `None`→全量」洞；非在 AgentTool 上叠特例 runner |

**Issues**（按 CRITICAL > WARNING 排序）:

- [CRITICAL] [决策 1 + 接口与数据流 / `create_subagent`]: 目录与 `AgentTool` 落在 platform，却把子 session 提示参数写成 sdk 的 `PromptSlots`。不改→ worker 极易在 platform 反向 import `agent.sdk`，违反 `SPEC.md` 分层；或复制一套不兼容的 slots 结构。请改接口契约为：platform 目录产出 core `PromptSlotSeed`（或等价 duck）；`create_subagent` 接受 seed / duck 并写入 `NewSession.prompt_seed`（与 `_to_prompt_seed` 同构），仅公共 `create_session` 继续暴露 `PromptSlots`。

- [CRITICAL] [delta `specs/kernel/skills.md` REMOVED]: 把既有 Requirement 下的单条 Scenario「子 agent 的 load_skills 校验与 list_skills 同口径」写成整段 REMOVED，且标题是自造名，未锚定「同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致」。不改→ 收尾机械 REMOVED 删不掉真条目，canonical 残留 load_skills 校验契约，与本期删参实现并存矛盾。应改为 **MODIFIED** 该 Requirement 全文，删除该 Scenario、忠实保留其余 Scenario。

- [WARNING] [delta `specs/kernel/background-tasks.md`]: 「前台子 agent 超预算自动转后台（模型不可调超时）」挂在 MODIFIED，但 canonical 无同名 Requirement；「不可调超时」是参数面增量。不改→ 归并找不到替换锚，Scenario 可能落空或与既有超预算通知 Scenario 双轨。建议改为 ADDED，或 MODIFIED 真正承载超预算语义的既有 Requirement，并并入 AND「无法经参数改超时」。

- [WARNING] [决策 4 / delta 覆盖]: 子 agent skills **继承父会话配置**是消费者可观察行为变化，但 delta 无对应 Scenario（skills 散文甩给 tools-hooks，tools-hooks 也未写）。不改→ 收尾 canonical 不记载继承语义，日后被当成实现细节改掉且无契约挡住。建议在 `skills.md` 或 `tools-hooks.md` ADDED/MODIFIED 一条可观察 Scenario。

- [WARNING] [风险与回退]: 「旧调用方仍传 `load_skills`/`category` → 忽略或校验失败（实现选一并测）」未拍死。不改→ worker 与 reviewer 对验收期望不一致（现网 schema 为 `additionalProperties: False`）。建议在对外表面表拍死一种（推荐：随 `additionalProperties: False` 校验失败，与删字段一致）。

**Recommendations**（不阻断门禁，作者自行取舍）:

- `Kernel.create_session` 同样存在 `skills=tuple(skills) if skills else None`（`kernel.py:989`）。本期主路径是 `create_subagent`，可不扩 scope；若关心父会话「零 skill」三态，可另开或顺手注明「已知同源折叠，非本 unit」。
- 父 `tool_allowlist is None` 时「取父 turn 已解析工具名」在生产少见（父通常已有显式 enabled_tools），但建议在接口段补一句推荐取法（例如经 control 暴露与 runtime 同源的解析，或对 `None` 展开为当前 registry 可见名再 deny），减少 worker 探私有 `_resolve_session_available_tools_from_config` 的冲动。
- 调研笔记写 CC 类型列表多在 system 附件；design 选 description 列举仍满足 spec「准备使用工具时能获知」，无需为「更像 CC 附件」再扩 scope。

---

**给作者**: 先修 2 条 CRITICAL（PromptSlots 分层落点 + skills delta 用法），并建议顺手收 3 条 WARNING；改完可再跑一轮 design-review。修到台账无 ✗、进攻无存活发现后，再交给 `change-orchestrator`。
