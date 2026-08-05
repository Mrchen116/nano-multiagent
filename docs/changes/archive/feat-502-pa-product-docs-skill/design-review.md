# Design Review: feat-502-pa-product-docs-skill

## Round 1

### Metadata

- reviewer: `/root/feat_502_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 恒为 full；本轮从首文档、全部 delta、canonical specs 与生产入口重新建立完整 inventory。`
- started_at: `2026-08-05T12:13:56+08:00`
- completed_at: `2026-08-05T12:18:54+08:00`
- duration: `4m 58s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- 首文档：`spec.md` 的 6 条澄清、5 个 Requirement、17 个 Scenario、范围与非目标。
- 技术方案：全部 5 条决策、接口/数据流、风险/回退、review runbook 与唯一 milestone `feat-502-M1`。
- delta-spec：Gateway 的 1 条 ADDED + 1 条 MODIFIED Requirement；IM 的 1 条 ADDED Requirement；`kernel` / `cli` 的 no-delta 声明。
- canonical specs：`docs/specs/gateway/agent-capabilities.md`、`docs/specs/im/agents-nodes.md`、`docs/specs/kernel/skills.md` 及各包入口。
- 生产路径：`personal_assistant.main → gateway.process_lifecycle.run_gateway → builtin_skills.bootstrap → compose_gateway/build_pa_kernel → Kernel`，以及 `Kernel.list_skills → upstream_reporter → IM capabilities/create/detail → session runtime`。

### 现状断言核实台账

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| 包内资源与 package data | `pyproject.toml:50-58` 将 `src/` 设为 package root 并包含 `personal_assistant = ["builtin_skills/**"]`；`src/personal_assistant/builtin_skills/__init__.py` 使资源树成为真实 package。 | 成立 |
| 生产安装 owner | 产品入口在 `src/personal_assistant/main.py:93-113` 把 foreground 交给 `process_lifecycle.run_gateway`，后台也生成同一 foreground child；`src/personal_assistant/gateway/process_lifecycle.py:135-147` 在构建 runtime 前调用 installer。 | 成立 |
| 当前 installer 是 missing-only | `src/personal_assistant/builtin_skills/bootstrap.py:16-55` 枚举直接子目录，目标 `SKILL.md` 已存在时跳过，否则 `copytree`；这正是 delta 要替换的 current 行为。 | 成立 |
| `gateway.bootstrap` 同名实现不是生产安装 owner | `src/personal_assistant/gateway/bootstrap.py:27-64` 仍有旧 installer，但生产入口只由 `process_lifecycle.py:22,39-55,143` 引用 `personal_assistant.builtin_skills.bootstrap`；`gateway.runtime` 对该模块的生产使用是 channel start/stop。 | 成立；design 明确不改它是正确边界 |
| PA 全局 skill root 进入 Kernel | `src/personal_assistant/product.py:39-55` 把 `~/.nanoassistant/skills` 放在首个 deployment root；`src/personal_assistant/product.py:381-434` 经 `agent.sdk.build_kernel(skill_search_roots=...)` 装配。 | 成立 |
| skill 发现与 `skill_view` | canonical `docs/specs/kernel/skills.md:14-46` 规定候选注入和 `skill_view` 只加载命中的 `SKILL.md`；实现 `src/agent/platform/tools/builtins/skill_view.py:92-187` 也只读取 `skill.location`。 | 成立；并暴露 R1-C1 |
| 全局 skill 自动投影为默认项 | `src/personal_assistant/reporter/upstream_reporter.py:112-142` 仅对 `~/.nanoassistant/skills` 下的 location 标 `default_on=true`，`145-202` 将结果用于 node/agent capabilities。 | 成立 |
| 新建页消费 capability defaults | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:31-36,374-403` 从 `default_on=true` 物化默认 skills/tools；服务端无字段时也由 `src/IM/api/routes/nodes.py:244-263` 解析 node defaults。 | 成立 |
| 默认/显式 skills 的 runtime 语义 | `src/personal_assistant/gateway/session_composition.py:54-82` 将非空 skills 投影为白名单、空集合投影为 `None`（默认发现）；`src/IM/frontend/src/features/chat/components/slash-candidates.ts:37-51` 使用相同语义。 | 成立 |
| skill 刷新不改 profile | installer 调用发生在 config load 后、runtime build 前，只写全局文件树；profile 的 skills 通过 session projection/IM config sync 单独流动。design 未引入 profile 写入接口。 | 成立 |
| 工具白名单可关闭文件工具 | canonical `docs/specs/gateway/agent-capabilities.md:82-100` 要求 `tool_allowlist` 为真白名单，并明确允许禁用 `read`；实现 `src/personal_assistant/product.py:362-378` 原样投影白名单。 | 成立；决策 3/5 没有把该约束闭合，见 R1-C1 |
| current 产品文档来源 | `README.md` 提供默认使用入口，`docs/product/` 定义产品原则，`docs/operations/` 定义启动/排障，`docs/specs/{gateway,im}/` 定义可观察 current behavior；design 的来源边界与 `docs/README.md` authority 路由一致。 | 成立 |
| 架构红线 | 本方案只改 `personal_assistant` 自有资源/installer，继续经 `agent.sdk` 装配；IM 只消费 capabilities/profile，无 PA↔IM import 新边。 | 成立 |

### 决策核实台账

| 决策 | 拍板 / 自洽 / spec 驱动 / 现状约束 | 结论 |
|---|---|---|
| D1 内置目录所有权 | 精确限定为当前包中含 `SKILL.md` 的直接子目录，完整替换目录、保留非内置名称、绝不写 profile；直接覆盖 `spec.md:64-85,140-147`。与 current root/discovery seam 一致。 | 成立 |
| D2 逐 skill 刷新事务 | staging、backup、切换、失败恢复、继续其他项与日志暴露均已拍死；delta `gateway/agent-capabilities.md:48-70` 有对应可观察契约，接口返回成功项也闭合 caller。 | 成立 |
| D3 短 SKILL + 三份 references | 内容分区和维护 owner 已拍死，但实际正文只存在 references，而现有 `skill_view` 只能返回 `SKILL.md`。一个只启用产品 skill + `skill_view` 的合法 Agent 读不到正文。 | **不成立 — R1-C1** |
| D4 本机 / 现场 / 远端来源优先级 | 离线默认、现场核实、官方远端、不可用降级、范围外路由均对应 `spec.md:87-136`；未引入专属网络依赖。 | 成立（受 R1-C1 的本机手册可达性阻断） |
| D5 复用现有 IM 选择链 | global-root default、创建默认、非空显式 allowlist、关闭/重开都可由现有 capability/profile/session 链表达；无 UI/API 新 seam。只声明 `skill_view` 为调用前提也与 gateway delta 一致，但没有声明或解决 references 所需的第二个工具。 | **不成立 — R1-C1** |

### spec 约束核实台账

| Requirement / Scenario | design 落点与本轮证据 | 结论 |
|---|---|---|
| R1 / 新建 Agent 默认启用 | D5；全局 location 经 reporter 标 `default_on`，create page 物化默认值；IM delta Scenario 1。 | 覆盖 |
| R1 / 默认 skill 集合的既有 Agent 获得手册 | D5 的空/default 发现；session projection 空集合→`None`；包资源在 runtime build 前刷新。 | 覆盖，回答能力受 R1-C1 阻断 |
| R1 / 升级不改写显式选择 | D1/D5 不写 profile，非空 allowlist 不补手册；Gateway/IM delta 均钉住。 | 覆盖 |
| R1 / 用户关闭与重新开启 | D5 复用 IM 保存后的 session skill 白名单；IM delta Scenario 3。 | 覆盖 |
| R2 / 升级刷新全部内置 skills | D1/D2 以当前包目录为替换单元并清除旧额外文件；Gateway MODIFIED delta。 | 覆盖 |
| R2 / 本地修改被产品版本替换 | D1 的 PA 托管所有权与完整替换直接覆盖。 | 覆盖 |
| R2 / 非内置用户 skill 不变 | D1 只枚举当前包声明的名称；Gateway delta Scenario 3。 | 覆盖 |
| R2 / 刷新不改变 Agent 选择 | installer 只写资源 root；D1/D5 明确不写 profile。 | 覆盖 |
| R3 / 任一 PA 对话入口问产品问题 | D3/D4 设计单个共享 PA skill，所有 channel 复用同一 session capability；Gateway ADDED delta Scenario 1。 | **未真正闭合 — R1-C1** |
| R3 / 普通任务不触发 | D3 frontmatter 精确触发 + D4 分类，真实 LLM reviewer 旅程验证；Gateway ADDED delta Scenario 2。 | 覆盖 |
| R3 / 范围外问题 | D3/D4 明确 coding CLI、Kernel、开发流程只说明边界/路由；Gateway ADDED Requirement 正文保留边界。 | 覆盖 |
| R4 / 基础问答无需联网 | D3 随包内容 + D4 默认本机 reference；验收以工具轨迹确认不调 web。 | **未真正闭合 — R1-C1** |
| R4 / 最新版或升级差异 | D4 只在明确询问时查官方仓，并区分远端/本机；Gateway ADDED delta Scenario 4。 | 覆盖 |
| R4 / 远端不可用 | D4 退回已安装手册并声明边界；Gateway delta Scenario 4 的 AND。 | 覆盖（退回内容受 R1-C1 阻断） |
| R5 / 当前配置或运行状态 | D4 仅在工具可用时核实并区分规则/观察；Gateway delta Scenario 5。 | 覆盖 |
| R5 / 现场与说明书不一致 | D4 要求实际观察优先、明确区分，不用默认值冒充事实。 | 覆盖 |
| R5 / 手册与现场均无答案 | D4 明确无法核实时限定不确定性；Gateway delta Scenario 5 的 AND。 | 覆盖 |
| 范围与全部非目标 | 不建帮助站/UI/MCP，不改通用 Kernel skill contract，不引入基础联网依赖；仅 D1 改 PA 托管资源供给。 | 不越界 |

### delta-spec 核实台账

| Delta 条目 | canonical 锚点 / 用法 / THEN 视角 | 结论 |
|---|---|---|
| Gateway ADDED `PA 产品说明书按需回答产品问题` | 是对 Gateway 用户表面的平行新增，落在语义最窄的 `agent-capabilities.md`；5 个 Scenario 以用户可观察回答/工具轨迹为 THEN，未写内部函数。内容覆盖 PA 问答、普通任务、离线、远端和现场证据边界。 | 用法成立；其 Scenario 1 只给定 skill + `skill_view`，因此进一步证明 R1-C1 是设计冲突 |
| Gateway MODIFIED `PA 内置 skill 启动自举` | 精确锚定 canonical 同名 Requirement；原 Lark allowlist/静态 ingress/event 场景均保留，旧“同名不覆盖”场景被目标态刷新语义取代，并新增刷新、用户 skill、失败和 profile 不变场景。 | 成立 |
| IM ADDED `PA 产品说明书 skill 可默认启用和关闭` | 是普通 capability item 上新增的产品语义，不修改现有 API/schema；3 个 Scenario 分别覆盖创建默认、既有显式选择、关闭/重开，消费者视角为浏览器用户。 | 成立 |
| kernel / cli no spec delta | 方案声明不改 Kernel 发现/读取/统计及 coding CLI；代码落点和决策没有跨入二者。 | 成立；也意味着不能假定 `skill_view` 会新增 reference 读取能力 |

### Milestone 核实台账

| Milestone | 拆分 / 范围 / 两轨退出 | 结论 |
|---|---|---|
| `feat-502-M1 product-docs-skill` | 单 milestone，installer、手册、契约和真实问答属于同一端到端价值闭环；不存在横切式并行拆分。范围列出生产资源/installer、聚焦测试、canonical specs 与 delta；`[reviewer]` 覆盖 5 个 Requirement 全场景，`[worker]` 覆盖同步事务、package data、capability/prompt 和精确命令。 | 结构成立；R1-C1 修正后需把“只有 `skill_view`、没有 `read` 的合法工具白名单”纳入可达性退出标准，或由修订后的资源形态消除该组合依赖 |

### 整体判断

- 上层架构总览清楚地表达“包资源 → Gateway 启动刷新 → 全局 root → Kernel/capabilities → IM/session”，D1/D2/D4/D5 的方向可快速审核。
- 接口和刷新数据流闭合；production owner、runtime build 顺序、default projection 与 profile 白名单均有真实 caller。
- 文档没有 TBD、模板残留、命名漂移或横切 milestone；runbook 的 `e2e-up/down`、`.e2e-ports.env`、`.gateway.pid/.log` 与当前脚本一致，并明确隔离 HOME。
- 问答数据流在 `skill_view → SKILL.md → reference` 处断开：第二跳依赖 `read`，但 spec/delta 与工具白名单契约没有保证它存在。这不是实现细节，而是核心内容可达性的接口缺口。

### 架构进攻

| 角度 | 主动检查与证据 | 发现 |
|---|---|---|
| 归属 | installer 放在 PA 包资源 owner，启动副作用留在 foreground lifecycle；capability/default 仍在 Gateway/IM 既有边界，未把 PA 文件系统职责推给 IM 或 Kernel。 | 归属合理，无反向依赖 |
| 该不该存在 | 删除新增 helper/MCP/文档服务后，现有 skill seam 已足以承载产品手册；D1 的 transaction 是“完整替换且失败不残缺”的直接需要，单 skill/三主题分区也不是为假想多态预造抽象。 | 无多余模块；但 references 作为正文唯一载体在当前工具契约下不可独立存在，见 R1-C1 |
| 深还是浅 | `skill_view` 的稳定接口只隐藏并返回一份 `SKILL.md`；D3 把真正能力放到接口之外的 references，导致“已成功调用 skill”仍不能取得手册。长期代价是每个验收/故障都要同时推理 skill 与 tool 白名单，且默认配置测试会掩盖关闭 `read` 的真实失效。 | **R1-C1** |
| 治本还是补丁 | 复用 global root 并改变其托管所有权，直接解决升级残留；没有另建 managed root 或在 IM 写特例。来源优先级也正面区分本机/现场/远端。 | 刷新方案治本；问答内容可达性需在 design 层正面解决，不能靠“默认通常有 read”兜底 |

### Issues

- [R1-C1][CRITICAL] [决策 3 / 决策 5 / 问答主流程 / feat-502-M1]: 方案把产品说明正文全部放在三份 `references/*.md`，`SKILL.md` 只保留触发与路由（`design.md:93-104,129-168`），但 current Kernel 的 `skill_view` 契约和实现只返回 `SKILL.md`（`docs/specs/kernel/skills.md:40-46`; `src/agent/platform/tools/builtins/skill_view.py:92-187`）。同时 Gateway 的稳定契约允许用户禁用 `read`，会话只得到显式 `tool_allowlist`（`docs/specs/gateway/agent-capabilities.md:82-100`; `src/personal_assistant/product.py:362-378`），而 feat-502 的 Gateway delta 核心场景只要求产品 skill + `skill_view`（`specs/gateway/agent-capabilities.md:9-13`）。因此一个合法 Agent 可以发现并成功调用 `nanoassistant-docs`，却只能拿到路由说明、无法读取任何产品正文；基础离线问答和默认 skill 集合场景会实质失败。若不修，worker 只能自行猜测是扩大 `SKILL.md`、强绑 `read`、还是偷偷改 Kernel，三种实现会产生不同且可能越界的架构。请在 design 拍死一种与 spec/non-goal 自洽的内容可达契约，并同步 milestone 的验证组合。

### Recommendations

- [R1-R1] 优先让 `skill_view` 单次返回的 `SKILL.md` 自身足以完成承诺的基础产品问答，把 references 降为启用文件工具后的可选深挖；若作者选择强依赖 `read`，则必须先调整 spec/delta、IM/tool 选择语义和相应非目标，不能只在实现或测试里隐式补上。

### Author Resolutions

- `R1-C1`: **accepted**. 核对 current `SkillViewTool.max_result_size_chars = 50_000`、`skill_view` 只返回命中 `SKILL.md` 全文，以及 Gateway 允许显式关闭 `read` 的契约后，确认 references 会造成内容可达缺口。已修订 `design.md` 决策 3、决策 4、内部接口、问答时序、风险、Reviewer Runbook 与 M1 退出标准：手册正文全部内置于单份 `nanoassistant-docs/SKILL.md`，并低于 50,000 字符；不依赖 references 或 `read`；真实旅程和聚焦测试都覆盖“只开启该 skill + `skill_view`”组合。spec 和 delta-spec 已要求该组合，无需改动。

## Round 2

### Metadata

- reviewer: `/root/feat_502_design_reviewer`
- review_mode: `delta`
- mode_reason: `R1-C1 的修订改变了产品手册的资源形态，并有界传播到来源决策、接口/时序、风险、runbook 与 M1；spec、delta、生产 owner、刷新架构和选择契约未变，影响范围可完整枚举，无需升级 full。`
- started_at: `2026-08-05T12:25:42+08:00`
- completed_at: `2026-08-05T12:26:51+08:00`
- duration: `1m 9s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 重查历史项：`R1-C1` 及其 Author Resolution。
- changed atoms：决策 3、决策 4、`nanoassistant-docs/SKILL.md` 接口、问答时序、手册漂移风险、Reviewer Runbook、`feat-502-M1` 范围与两轨退出标准。
- 波及链：`skill_view` 当前读取/序列化/结果预算 → 显式 tool allowlist → 基础离线问答 spec/delta → 真栈与会话级退出标准。
- retained_from: Round 1 — `spec.md` 与全部 delta 未改；D1/D2 的刷新架构、D5 的 IM 选择链、生产 wiring、其他 spec 台账和未受影响的架构进攻证据均未因“references → 单份 SKILL.md”失效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted；将正文收敛到单份自包含 `SKILL.md`，取消 references/read 依赖，并补齐无 `read` 的测试与真栈旅程。 | `design.md:93-101` 明确单文件完整手册、只需 `skill_view`、低于结果预算且拒绝 references；`103-110` 把已安装来源改为该 `SKILL.md`；`130,161-163` 的接口和时序均只剩一次 `skill_view`。current `SkillViewTool` 在 `src/agent/platform/tools/builtins/skill_view.py:92-187` 读取并返回命中 `SKILL.md`，不再存在第二跳。 | closed |

### Changed Atoms 核实

| changed atom | 本轮动作与证据 | 结论 |
|---|---|---|
| D3 资源形态 | 对照 current `skill_view`：`src/agent/platform/tools/builtins/skill_view.py:97,165-187` 读取整份文件并声明 50,000 字符预算；`design.md:95-101` 让同一文件同时承载触发和完整手册，明确无 `read` 依赖。 | R1-C1 的内容可达缺口已从设计根部消除 |
| D3 容量边界 | 结果预算实际作用于序列化后的工具结果：`skill_view.py:194-203` 将 name/content/location 序列化，`src/agent/core/agent/loop.py:814-841` 再交给 compressor，`src/agent/core/tools/result_budget.py:52-75` 超限才压缩。M1 不仅检查正文低于 50,000，还要求会话级证明返回“未截断的完整手册”，覆盖了 JSON 包装开销，未只依赖文件字符数假设。 | 完整、可验，无需改 Kernel contract |
| D4 来源优先级 | `design.md:103-111` 已把稳定问答来源从 reference 改为 `skill_view` 返回的完整 `SKILL.md`；现场与远端分支保持 Round 1 已核实的边界。 | 与 `spec.md:89-119` 及 Gateway delta `:9-29` 一致 |
| 接口与问答时序 | `design.md:130` 的资源接口是自包含手册；`161-163` 从 `skill_view(nanoassistant-docs)` 直接得到完整手册并回答，没有悬空 reference caller。 | 数据流闭合 |
| 风险与维护 | `design.md:183` 将漂移 owner 改为同一 `SKILL.md`；未新增源码仓运行时依赖、MCP 或 helper。 | 未扩需求/架构边界 |
| Reviewer Runbook | `design.md:198-207` 要求真栈观察实际 `skill_view`，并显式设置 skills 仅 `nanoassistant-docs`、tools 仅 `skill_view`、不含 `read`；基础离线问答仍以无 web 工具轨迹验证。 | 直接复现并关闭 R1-C1 的合法配置组合 |
| M1 范围与退出标准 | `design.md:215` 将资源范围收窄为单份 `SKILL.md`；`[reviewer]` 走无 `read` 真实模型旅程，`[worker]` 以会话级聚焦测试证明完整未截断，再保留 capability/default/profile 与 installer 门禁。 | 单 M1 垂直闭环仍成立，两轨可验 |

### 上下游影响

- 上游 spec/delta 已经只承诺“产品 skill + `skill_view`”即可回答（Gateway delta `:9-13`），本轮修订直接实现该前提，不需要改写需求。
- 下游 Kernel、IM、Gateway capability schema 均不变：内容搬回 `SKILL.md` 后复用已有 `skill_view` 深接口，不强制补 `read`，也不改变真白名单契约。
- installer 仍以整个内置目录为替换单元；从“一个 SKILL + 三份 references”缩为“一个 SKILL”不会使 D1/D2 的事务、失败恢复或非内置保护证据失效。

### 架构进攻（受影响角度）

| 角度 | 本轮攻击 | 结论 |
|---|---|---|
| 该不该存在 | 删除三份 references 后，调用方不再需要第二种读取工具；方案也没有为此新增 helper/MCP、强制工具联动或 Kernel 特例。 | 单份资源是满足现有接口的最小结构，无多余间接层 |
| 深还是浅 | 一次 `skill_view` 现在隐藏“定位版本化手册 + 取得完整内容”的全部复杂度，接口结果足以直接回答；容量由真实序列化路径和未截断测试把守。 | 从 Round 1 的浅两跳改为闭合的一跳深接口 |
| 治本还是补丁 | 修订没有靠“默认通常启用 read”或测试配置兜底，而是让核心内容在唯一稳定读取面上可达，同时保留用户关闭任意工具的白名单语义。 | 治本，未留下补丁债 |
| 归属 | 手册仍属于 PA 包资源，Kernel 只执行既有通用 `skill_view`；没有跨包职责迁移。 | retained_from: Round 1 — 归属与依赖方向未变化 |

### Issues

- None.

### Recommendations

- None.

## Post-review product decision: progressive references

本文件前述 R1-C1 与 Round 2 结论记录当时“即使显式关闭 `read`，仅凭 `skill_view` 也必须完整回答”的需求前提。PR review 中用户随后明确撤销该前提，并要求进一步采用 OpenAI 的 skill 写法：正常 PA Agent 保留默认 `read`，产品说明书不为关闭 `read` 的配置提供正文副本或兼容路径。

因此，R1-C1 在旧前提下的分析仍作为历史审计保留，但不再约束最终资源形态。最终设计改为：

- `SKILL.md` 只承载触发、回答规则、来源边界和主题路由；
- 七份一层 `references/*.md` 承载互不重复的专题正文，并全部由入口直接链接；
- `skill_view` 加载入口，默认启用的 `read` 只加载当前问题所需的 reference；
- Gateway delta 的问答场景同步要求产品 skill、`skill_view` 与 `read`，不改变用户仍可显式关闭任何工具的真白名单契约。

该产品决策不改变 D1/D2 的托管目录、事务刷新、跨进程锁或失败恢复设计；整个 skill 目录仍是安装器的原子替换单元。最终验证证据记录在 `verification.md` 和 `acceptance.md` 的 post-review revision 段落。
