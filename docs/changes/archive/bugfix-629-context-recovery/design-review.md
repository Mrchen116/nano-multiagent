# bugfix-629 Design Review

## Round 1

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`
- reviewer target: `incident.md`、`design.md`、`specs/gateway/agent-capabilities.md`、`M1-recovery/.gitkeep`
- frozen baseline: Nano `45239680d51dbb94ed2aba1fc95c881aad1cc2b7`；相关生产实现 `be6c1271b`
- plugin baseline: `/Users/czj/Repos/opensource-hub/dsh-context-rollover` 的 `origin/main=621278df757f9c5678bf7d5429b18f0485967885`，通过 `git show origin/main:<path>` 读取，未使用该目录旧 main
- DSH baseline: `/Users/czj/Repos/opensource-hub/deepseek-harness`，HEAD `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；Session/Agent package version `0.2.1-alpha.1`
- review_mode: full
- mode_reason: 首轮 Gate 2；独立核对产品组装、当前实现、公开接口生命周期、需求、delta 和 milestone，不沿用 feat-627 的 Approved
- started_at: 2026-10-21T15:50:08+08:00（正式判定与报告记录起点；前置源码取证已完成）
- completed_at: 2026-10-21T15:51:52+08:00
- duration: 1m44s（正式判定与报告记录；不含前置源码取证）

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

消除高频快照变化和为当前原生 turn 提供 History 入口，能在现有 DSH 公开扩展点内实现。尚有一个会让实施偏离既有能力边界的问题：Skill 是否可发现，与 `skill` 工具是否获准调用是两项独立配置；设计把两者当作同一能力，未闭合已有显式 Skill 调用在受限工具集下的换窗恢复。

### Coverage 与证据

#### 现状与产品组装

- 核对 `packages/dsh-integration/src/workspace-tools.ts:65-85`：无 workspace 路径直接挂载插件，实际 workspace 路径通过 workspace owner/原生 bundle 生命周期挂载，方案不是只改测试中的手工组装。
- 核对 `packages/dsh-integration/src/knowledge/runtime.ts:63-74`：当前确实在发现任意历史 `compaction/end` 后读取 session 用过的 Skill，并每次 assemble 加入全文。设计改为成功压缩后、持续且可按需读取的索引，直接移除了这部分重复全文来源。
- 插件 `src/index.ts` 当前 `CONTEXT_NAME` contribution 同时包含窗口和 `referenceText`，assemble hook 追加 Notes hint；DSH `packages/core/agent-loop/src/runtime-context.ts:114-170` 对完整文本比较，变化后生成完整快照。因而设计去掉每步引用及 Notes 目录的决定与真实根因一致，不是仅降低阈值或移动重复内容。
- 原始事故报告作为既有调查输入阅读，未访问生产私密日志或复跑生产，生产数值沿用报告，不将本轮源码检查表述为新的线上验收。

#### 公开接口与恢复生命周期

- DSH `packages/core/agent-loop/src/agent.ts:267-325` 先写 `turn/start`，再执行 pre-step/claim/assemble；普通输入在同文件约 421 行进入持久日志。已读直接输入与 Inbox tool result 因此可通过对应 `turn/start.seq` 归属；尚未提交的 claimed 输入继续沿现有 decision 路径保留。
- 插件 `src/history.ts` 已以 `snapshotEvents()` 规范化用户、助手和工具记录，并用 `surface.nodes` 排除活动项；增加 turn 字段与精确过滤可以复用现有分页和 `read` 偏移，不需要 Session 私有方法。原始工具结果和 source 保留，Inbox 不被重新标记成人类授权。
- 插件 `src/rollover.ts` 已通过公开 Session append/replace 和 compaction bracket 完整配对提交，checkpoint 是持久消息；在同一事务前生成 body-free turn 导航不改变工具配对、无摘要和 no-tail 约束。正常工作多次换窗时同一 `turn/start.seq` 不变，History 过滤不受 window 边界限制。
- DSH `packages/core/agent-loop/src/index.ts:845-860` 与 `packages/core/session/src/repair.ts:53-97` 显示恢复加载可给被打断的旧 turn 补 `turn/end`。本设计重启恢复依赖已持久化 checkpoint，而不是假设重启后旧 turn 永远 open，这一选择成立。验收仍须检查恢复后的真实内容与交付，不能仅看到一个 open-turn 字段就判完成。
- `agent/turn-stopping` 在最终 `turn/end` 前触发；此时导航不能作为“必有未完成业务”的断言。设计已明确原生边界不推断业务完成，并要求先核对交付避免重复发送，符合该生命周期。

#### 需求、约束与架构判断

- 动态引用改由已有 `get_context_remaining` 和 fallback 提供，Skill 索引留在 Nano knowledge，turn 历史归属与 checkpoint 留在上下文插件；DSH 继续持有请求快照与执行生命周期，职责落点合理。
- 复用 History、原生日志和现有换窗事务，优于新建任务状态存储、摘要器或 context diff 服务；没有发现为本问题新增抽象的必要。一次换窗的有限环境重建仍存在，但设计已要求与逐步增长分别计量。
- 旧 Notes 与新已读任务组合有明确恢复优先级，不把旧 Notes 当作当前状态，不要求用户重复，不删除会话或生产资料。导航本身只证明可定位，设计把实际恢复与交付留给真模型验收，证据边界明确。
- 无客户端交互变化，前端原型和视觉审查不适用。来源、权限、显式回退与受限工具集的主张已核对；其中 Skill 调用权限存在 R1-W1。

#### Delta 与 milestone

- delta 精确修改 canonical `docs/specs/gateway/agent-capabilities.md` 中“无摘要换窗的 workspace 支持持续任务与按需恢复”；原有“多次换窗后继续任务”和“恢复原始细节或说明缺口”两条 Scenario 完整保留，新场景从消费者角度描述结果，没有将 implementation 状态误写为 current。
- 唯一 `M1-recovery` 及 `.gitkeep` 骨架与跨插件/Nano 的单主线修复范围一致，无互相冲突的并行交付面。
- Runbook 明确产品 API 入口、隔离栈、默认预算、旧已完成 Notes + 已读新 Inbox + 保存前压力换窗、七 Skill/六步请求增长检查、多窗和重启/off-on，且明确实际未触发视为未覆盖。milestone 还覆盖 overflow、长内容分页、配对、来源与隔离。可以指导实施和独立产品验收，但 Skill 矩阵需按 R1-W1 补充受限调用配置。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 已选 Skill 不等于可调用 `skill`，仅提供路径索引会丢失现有受限配置的恢复能力

- **位置**：`design.md:41`（关键决策 2）、`design.md:66`、`design.md:83-85`；delta 的“长任务按需恢复 Skill”。
- **证据**：`packages/dsh-integration/src/capabilities.ts:25-30` 用业务 `toolAllowlist` 过滤原生工具，自动保留的仅是四个 context tools；`skill` 和 `read` 不自动获准。相同文件 `89-113` 的人类 `/skill:name` 显式调用则直接通过已选择的 Skill registry 注入正文，无须先开放 `skill` 工具。现有 `packages/dsh-integration/tests/model-policy.test.ts:7-45` 恰好使用 `toolAllowlist: ['workflow']`，通过 `/skill:retained` 载入 Skill，并对插件启用/显式停用两种模式验证压缩后保留正文及重启。
- **具体失败路径**：该已有配置在压缩前可以使用人类明确选中的 Skill；改为仅有名称/路径并要求 `skill` 重读后，工具仍被白名单排除，`read` 也不可用。启用插件时可能通过 History 找回历史正文，但设计没有给这条入口；显式停用插件的摘要模式连 History 都不可用。因此“当前仍可用 Skill”不能仅以 `skills.get` 成功判断可恢复，单纯把原测试改成含索引/开放 `skill` 的测试会掩盖回归。
- **未修后果**：用户未撤销 Skill 选择，却会在换窗或重启后失去其指导；为了让新索引可用而自动开放 `skill`/`read` 又违反保留业务白名单的要求。该问题不要求扩张任务恢复机制，但需要在实现前明确能力边界。
- **闭环要求**：明确“Skill 可用性、工具调用权限、显式人类调用、历史恢复”之间的规则，为已支持的受限配置选定不扩大业务权限的恢复路径或明确的产品契约处理。把上述 `['workflow'] + /skill:retained` 的已有组合保留为回归输入，覆盖插件启用及显式回退，不用默默增加 `skill/read` 白名单消除用例。若改变消费者可观察契约，同步调整 delta；若复用已有允许的入口，应写明索引如何指向它，并验证实际正文被按需取得。

### Recommendations

无额外可选改进；不要求新增任务分类器、状态数据库或修改 DSH。

### 本轮边界

本轮只创建此报告；未修改受审文档、实现、配置或其他 dirty/untracked 内容，未建分支、提交或启动服务。结论是设计审查结论，不是修复完成、真实任务恢复成功或生产部署证明。

### Author Resolutions (R1)

- **R1-W1 accepted**：已核对 DSH tools public `get(name, scope)` 返回 restricted-aware visible definition，以及 Nano 显式 `/skill:name` 不依赖业务 tool allowlist。设计关键决策2改为按该 scope 的 `skill` 能力选择索引或保留既有正文恢复；无能力分支不靠 History、不增权限，启用/回退均成立。Runbook矩阵保留原 `['workflow']` 配置并新增允许 `skill` 的分支；普通步骤无重复由取消高频引用 contribution 保证。更新现状、总览、风险段保持一致。delta仍只要求能恢复及无每步重复，不要求全局移除自动正文，故无需改变产品契约条目。
- 其他结论采纳；未新增任务数据库、分类器或DSH修改。R1报告保留，修订需独立闭环后才实施。

## Round 2

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`（与 R1 相同）
- reviewer target: `design.md` 的 Skill 恢复分支及相关现状/总览/风险/验收矩阵；R1 Author Resolutions
- frozen baseline: Nano `c4cc9275e0614236e794bed66ef07a92b480f8ac`；插件与 DSH 基线沿用 R1
- review_mode: delta
- mode_reason: R1-W1 的解决引入“有重读工具用索引、无重读工具保留正文”的有界行为分支，需复核权限、快照增长和显式回退的影响，故比仅确认措辞的 closure 范围稍宽；其余需求、turn 导航、事务和 milestone 未改变，无需重做 full
- started_at: 2026-10-21T15:54:25+08:00
- completed_at: 2026-10-21T15:55:24+08:00
- duration: 59s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1 已在设计层闭环。修订保留受限工具配置原本具备的 Skill 恢复行为，同时为具备重读能力的会话移除自动全文恢复；两种路径都遵守当前 Skill selection 和工具白名单。

### Coverage 与证据

- **公开能力查询**：独立读取固定 DSH `packages/core/tools/src/index.ts:1156-1232`。`get(name, scope)` 返回 `view(scope).visible`；该视图按 scope 链的 restrictions 过滤继承工具。Nano `ToolSelection` 正是用 `agent.ctx.tools.restrict` 施加业务选择，因此设计使用 `agent.ctx.tools.get('skill', agent)` 能识别本问题中的 `['workflow']` 与允许 `skill` 两种配置，不需要访问私有 registry 或修改 DSH。
- **执行含义**：该查询判断当前 scope 的工具可见能力，不是预先批准任何一次业务动作。DSH 的 PTC presentation 可通过其正常 transport 调用可见工具，原有执行 guards/approval 继续生效；本设计没有绕过这些执行门禁，也没有向 allowlist 添加名称。
- **受限配置与回退**：`design.md` 关键决策 2 明确无 `skill` 能力时保留当前仍获准 Skill 的既有全文恢复，继续由 `skills.get` 过滤。该路径不需要模型调用 `skill`、`read` 或 History，因此对原 `model-policy.test.ts` 的 `['workflow'] + /skill:retained` 及插件显式停用后的摘要模式均有完整内容来源。原生显式调用语义保持。
- **增长与职责影响**：本轮不撤回关键决策 1，引用和 Notes hint 仍不再每步改变插件 contribution。全文分支保留稳定 contribution，DSH 的完整文本比较会抑制未变化快照；真实 Skill 集合、内容或配置变化仍可以触发环境重建。既有有限换窗成本与普通步骤持续增长的区分仍有效，未新增一次性清除标记、缓存状态机或另一套恢复数据库。
- **验证闭合**：关键决策 2 保留受限配置原输入并要求压缩、重启及回退；Runbook 第 4 项明确两种工具能力交叉两种 compaction 模式，受限分支检验正文、业务 schema 和普通步骤增长，可调用分支检验真实读取正文。未通过临时增加工具白名单绕过 R1 用例。
- **delta 契约**：已核对 delta 未改。它要求当前获准 Skill 仍可供任务读取、普通进展不反复追加未变化正文，并未要求所有配置必须去掉自动正文；受限分支保留可读取的现有正文符合消费者结果。无需新增“正文只能通过某工具获得”的产品约束。
- **retained_from: Round 1**：Git diff 确认 `incident.md`、delta-spec、milestone 骨架无变化，设计中 turn_id、History 过滤、checkpoint、compaction 事务、主故障预算与产品入口均未变。R1 对这些路径的源码证据、来源与授权判断、架构职责和验收边界继续有效。

### 历史问题闭环

- **R1-W1 — closed**。
  - Author Resolution：接受 Skill 选择与工具可调用性是不同能力；使用 public scoped `tools.get` 选择恢复方式，并补齐原受限配置回归。
  - 本轮证据：上述 DSH visible view、Nano restrictions、保留全文分支、跨启停与重启矩阵已分别核对；原路径不再依赖不可调用工具或已停用的 History。
  - 结论范围：设计闭环；是否实现正确以及真实模型是否完成任务仍由既定实施与验收门禁证明。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增建议。无需继续为假设边界扩展本单元范围。

### 本轮边界

只向本报告追加 R2，保留 R1 及 Author Resolutions；未修改设计、代码、配置，未提交或运行服务。Approved 不代表实现、CI、真栈验收或生产恢复已经完成。

### Author Resolutions (R2)

接受 R2 结论，无未解决的实质问题；受审设计未继续变更。进入单 milestone 实施，产品任务恢复与交付仍需按 runbook 实测。

## Round 3

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`
- reviewer target: 本轮 `incident.md`、重写后的 `design.md`、delta-spec、M1 范围及退出标准；R1/R2 历史结论
- checkout: `/Users/czj/.codex/worktrees/bugfix-629-context-recovery/nano-multiagent`，branch `codex/bugfix-629-context-recovery`
- baseline: HEAD `9d105ae5d5c79078f8e078b4f1da0076ac70d255` 加本轮冻结的三份未提交文档；HEAD 本身仍含 rc.2 候选实现，不能视作本轮目标已实施
- frozen document SHA-256: `design.md=bb238b732074ecd997aeb1d854a38a91158a400d49b6ecd62bcf500a77cfb071`；`incident.md=4a594145598098aa0de3166301e9a481d0de0a14f5ea6d1c64064b629a74532b`；delta `agent-capabilities.md=d456d597ca68a371bf02c4ba56f45883ead86e9a6caf4d67b43dc662411ee50d`
- review_mode: full
- mode_reason: 用户撤回新模式的额外 Skill 恢复及当前 turn 恢复协议，改变核心恢复方式、History 接口和 milestone 验收语义；不能只依据 R2 closure 放行
- started_at: 2026-10-21T16:48:51+08:00
- completed_at: 2026-10-21T16:51:26+08:00
- duration: 2m35s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本轮设计可以在当前公开接口内按用户指定方式实施并复验。这个结论不证明原事故已经解决：删除当前 turn 特殊导航后，模型是否会从旧 Notes 转向 History 查回最新工作仍须按默认预算实测；失败不能通过恢复被用户撤回的协议来隐藏，也不能将本 unit 标记验收通过。

### Coverage 与证据

#### 用户决定与需求

- 本轮以交接的用户原话为当前范围：“那就按这个 to be 改，去掉新模式下额外的已用 Skill 恢复逻辑。interrupted_turn 先别加，按 Codex 原本的 Notes/History 方式恢复，再验证之前那个故障场景。”设计 Changelog、关键决策 2/4/5、incident 修复方向及 delta 已一致反映该选择。
- 当前未完成任务仍需恢复并完整交付，重复外部副作用仍禁止。用户改变的是恢复方式及验证顺序，并没有授权将失败当成成功；M1 与风险段保持了这个区别。R1 对故障链的既有事实没有因目标变化被删改。
- 不增加任务状态数据库、特殊当前任务提示或最近输入副本；无摘要、无普通对话 tail、无自动 Notes 正文、来源及业务权限边界保持。没有客户端界面变化，视觉原型不适用。

#### 实际组装与公开 owner 判断

- 本轮核对 `packages/dsh-integration/src/agent-config.ts:94-108`、`workspace-tools.ts:65-85`：workspace 插件在实际 Agent preset 内挂载；无 workspace 配置也在该 scope 挂载独立 compaction provider。知识恢复 hook 位于宿主 `KnowledgeRuntime`，将是否贡献内容的判断放在那里，不需要改 PA 或 Channels 的依赖边界。
- `packages/dsh-integration/src/compaction.ts:17-25` 已通过 `this.ctx.get('agentPresets')?.serviceFor(agent, 'compaction')` 将压缩交给该 Agent 的 owner。本轮复用同一公开查询，避免根据日志是否曾经压缩、工具名称或持久化开关猜测当前模式。
- 独立读取固定 DSH `packages/preset/agent-preset-registry/src/index.ts:319-327` 及 `src/mount.ts:98-111`：`serviceFor` 查询 Agent 保留的 preset 组合，返回该组合内实际服务，没有服务时为 undefined。此 API 适用于当前内置无摘要 owner 与停用后回到宿主摘要器的分支。它是服务归属查询，不是所有未来第三方引擎都等同 Codex 模式的证明；本次不扩张到未提出的第三方策略分类。
- 新模式提前返回 assembly 时跳过 references、索引和全文，统计/维护逻辑仍在原职责内。旧摘要分支明确回到原全文行为，因此不会误将 R2 的“可重读则只给索引”继续保留在旧模式。

#### 原生 Skill 目录与受限 History

- 固定 DSH `packages/skill/tool-skill/src/index.ts` 的 catalog pre-step listener 比较当前可见 `skill` 定义、有效 Skill 集合及活动 surface 上目录 digest；`catalogHistory()` 只把仍在 surface 的目录当作可见基线。目录被压缩移出后可重新发布，目录只含名称/描述，不含正文。
- 同包 `tests/tool-skill.spec.ts:631-655` 已有“compaction hides its durable message”后的目录重建测试；`750-764` 明确工具被限制时不发布目录。本轮只阅读这些测试，未执行。设计“根据当前能力重建目录”应按这一原生语义理解：无 `skill` 工具的配置并不被承诺得到完整可调用目录，也不会为了恢复补出虚假目录。
- Nano `capabilities.ts:89-113` 的 `/skill:name` 首次显式调用路径保留，按原输入身份加载并持久化 `skill-invocation` 正文。换窗不应重新触发同一输入；按需 History 查询是恢复旧记录，不是重新发起显式调用。
- 插件原有 `src/history.ts`（`621278df757f9c5678bf7d5429b18f0485967885`）的 `excluded()` 不排除 `skill-invocation` 或普通 tool result，`normalizedItems()` 保留完整正文与 source，`collectHistory()` 只返回离开活动 surface 的项；既有 window/item、搜索、分页和 read offset 足以定位并读回旧 Skill，无须 turn_id。
- `packages/dsh-integration/src/agent-context.ts` 的 context tools 包含 History；`capabilities.ts:25-30` 在受限业务白名单下仍保留这些启用中的内部工具；`policy/approval.ts:100-109` 在 downstream 允许后通过 internal_context 处理，Auto off 不单独阻断它。因此 `['workflow'] + /skill:name` 在新模式下存在不扩权的历史读取路径。显式停用新模式后 History 不再作为恢复前提，旧摘要模式保留全文。
- 恢复出的 Skill 历史是当前 session 的旧证据，不能升级为新的人类授权或绕过当前业务执行限制；本轮没有修改这些强制边界。

#### 换窗、Codex 参考与架构判断

- 移除每步引用和 Notes hint 的动态 contribution 仍直接针对完整 runtime snapshot 累计增长；保留窗口身份、查询引用和换窗 Notes hint 即可，无需另建 projection 或在 DSH 内做 diff。
- 删除 interrupted_turn 与 turn_id 后，History 恢复回到原有工具接口，配对事务、完整日志、Notes 存储和当前 session 范围没有理由改动。候选 rc.2 对新协议的测试/验收不再证明本轮恢复成功，设计已要求撤除和重验。
- 独立抽查 Codex 固定提交 `464add49587a7cb6032d5ab04faa8a1585947853` 的 `core/src/session/mod.rs:4854`、`ext/skills/src/world_state_catalogs.rs:356`、`ext/skills/src/extension.rs:370`、`ext/history-notes/src/extension.rs:115`：窗口重建环境、目录贡献与输入显式 Skill 选择分离；Notes hint 来自有界 backend 响应。后端 hint 生成内容不可见，设计没有将 Nano 的本地提示声明为服务端逐字等价，也没有以参考实现代替事故验收。
- 取消额外知识恢复并复用原生目录，减少了 Nano 与 DSH 重复维护的载荷生命周期；任务恢复继续由 Notes/History 与模型行为承担，符合用户本次选择。其效果存在待实测风险，但没有出现缺失公开接口、不可读取历史或必须突破权限才能实现的设计断点。

#### Delta、milestone 与验收

- delta 仍锚定正确 canonical Requirement，原有多次换窗与原始细节恢复两个 Scenario 保留；新增 Skill 场景明确新模式不重放正文/已用索引、受限配置从 History 恢复，以及停用后旧模式保持。与 R2 的消费者差异已显式记录，没有把新目标当作 current。
- 唯一 M1 改为“Codex Skill 生命周期与原 Notes/History 事故复验”，未增加并行冲突面。rc.3 使用不可变新发布，不覆盖 rc.2；候选包与最终安装一致性是必要验证。
- Runbook 要求真实 Web IM 消息 API、隔离数据、真实 provider 请求及 IM 落库，默认 C/O/B/R、已完成旧 Notes、已读新 Inbox、未保存新 Notes 时压力/overflow、结果只交付一次。触发不了目标路径判未覆盖；误信旧 Notes 判失败；不能靠预定答案、提高 buffer 或秘密恢复特殊提示通过。
- Skill 矩阵覆盖七个大 Skill、六步普通进展、原生目录重建、真实重读、受限 History、正常重启和 off/on。原窗口/item 长记录、来源、配对、fork/session 隔离及 Auto off 等路径保留；依赖被删除字段的旧证据明确失效。足以指导实施与独立验收。

### 历史问题闭环

- **R1-W1 — closed，处理方式按用户新决定替换**。R2 通过“无工具时保留全文”解决缺口，本轮用户明确撤回新模式的该分支；现由启用中的 session-local History 读取原始加载记录，旧摘要模式仍保留全文。公开可访问路径和来源已按上述证据复核，不把已撤回的全文恢复作为本轮门禁。
- R1/R2 的当前 turn 协议判断属于旧目标，本轮不保留其放行效力。此前已读任务恢复能力必须用不带协议的真实请求重新证明。
- 无其他历史未解决 issue；无须改写 R1/R2 原结论。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增建议；按已冻结范围实施和复验，不为假设风险添加被用户撤回的机制。

### 本轮边界

只在该 worktree 的本报告追加 R3，未修改三份冻结受审文档、产品代码、插件、配置或运行数据，未提交、启动服务或执行验收。原事故若复验失败，应报告失败及尚未解决的事实，本轮 Approved 不可用于声称修复完成或部署健康。

### Author Resolutions (R3)

Accepted R3: no unresolved substantive findings. The reviewed design is unchanged. R2 automatic-body fallback and turn-navigation approval are superseded by the explicit user decision. Implementation and real-model acceptance must use the R3 scope; a failed stale-Notes recovery will be reported as failed.

## Round 4

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`
- reviewer target: 原生工具结果压力裁剪接线、预算重算、相关 delta 与同资料复验；R3 实测失败边界
- checkout: `/Users/czj/.codex/worktrees/bugfix-629-context-recovery/nano-multiagent`，branch `codex/bugfix-629-context-recovery`
- baseline: HEAD `35fccff2fdea096aad481c02e683c4176b7319b2` 加本轮冻结 design/delta；其他已有 implementation/verification 修改只读
- frozen SHA-256: `design.md=bc71f63dd616f56f0fb791c6af7d8c68fa8b96bebaf5e954eca0a1856527474f`；delta `agent-capabilities.md=0e572e9ec6e572bf62d2c46e2dda849adec50e1d196a6d9255087d4bbb09584a`
- DSH: clean HEAD `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；另核安装包 `@deepseek-ai/dsh-compaction-tool-result-pruner@0.2.1-alpha.1` 的公开类型
- review_mode: delta
- mode_reason: 用户明确要求接回已有原生裁剪并复验同 25 份资料；变化限于自动压力/overflow 的处理顺序和该事故验收边界，Skill、Notes/History、权限及换窗事务保持 R3 方案，可引用 R3 有效证据
- started_at: 2026-10-21T17:25:21+08:00
- completed_at: 2026-10-21T17:27:46+08:00
- duration: 2m25s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

这是接回当前默认栈已经存在、却被自定义 compaction owner 绕过的原生步骤。接口可用，接线位置与预算重算闭合；同一批工具资料可以用“压力是否被裁剪解除、原任务是否仍在、是否真实交付”判断结果。R3 强制换窗后的任务丢失仍是失败记录，不能被本轮设计或离线裁剪估算改判为通过。

### Coverage 与证据

#### 现状与原生能力

- 已读取 `M1-recovery/implementation.md` 的 R3 pressure distribution and failed recovery：25 个单项低于 spill 阈值的实际结果在同一步累计约 264,885 个估算 token，下一 pre-step 直接换窗，模型读取旧完成 Notes 后没有交付当前 todo。记录明确区分估算量与 provider 实际输入，未把缺少交付的结果记为成功。本轮没有重跑或修改原始会话。
- Nano `packages/dsh-integration/src/compaction.ts:17-19` 在 preset owner 存在时提前返回；插件当前 `src/index.ts:138-152` 直接按 H 选择 pressure，`agent/request-error` 与公开 `compactIfNeeded` 也直接进入原换窗事务。两端组合确实绕过宿主 `BasicCompactionEngine` 的 pruner 调用，不是缺少另一个总量配置器。
- 固定 DSH `packages/compaction/compaction-basic/src/index.ts:290-327` 在 overflow 分支先 prune，在 pressure 达既有阈值后先 prune 并重新 measure，降到阈值以下返回 null。`packages/bundle/base/cordis.patch.yml:407-423` 默认同时组装 spill（12,500 tokens）与 pruner（8192/4096/1024 chars）。它们分别处理单次载荷和压力下活动历史，不能用单项未 spill 推导总量安全。
- 已核安装版本公开 `lib/types/index.d.ts`：`Context.toolResultPruner` 与同步 `pruneSession(session): PruneResult` 均可用；包根 export 声明该能力。设计要求声明公开类型依赖，通过 `ctx.get` 取可选服务，符合现有组合语义，不需要 private import、复制算法或修改 DSH。

#### 调用时机、预算与原有语义

- pre-step 达 W 后调用 pruner，再用同一 assembly/header/pending messages 调用现有 `budget()`，能避免只重算持久 surface 而漏掉尚未落库输入、工具定义或 system 更新。原始批次结果此时已在 session 内，正是原生 pruner 的处理对象；新 claim 仍由原 admission 路径保留。
- 裁剪后再按原 W/H 决定提醒、fallback、换窗；低于 W 不主动裁剪，不增加预算配置。公开 pressure 入口同样先裁剪重算，不能只修 hook 后留下直接入口漏接。设计与新增回归矩阵已覆盖这两条路径。
- provider overflow 保持原来的“恢复事务后由已有 handler 决定重试”路径，只在换窗前接入 native prune；不会把 pressure 的“低于 W 返回”擅自扩张成另一套 provider 重试状态机。此顺序与 BasicCompactionEngine 的 overflow 分支一致。
- 显式 model-requested/manual 不被压力策略替代；裁剪仍超 H 时继续原换窗，无服务时走旧策略。设计没有让原生服务变成所有第三方组合的强制依赖，也没有扩大工具权限。

#### 持久记录、配对与可恢复性

- 固定 DSH pruner `src/index.ts` 的 `pruneSession` 只遍历当前 surface 的 tool/result，保持原 message/source/call 及其余 event data，仅替换 content。每个替换前同步追加 `compaction/prune`，替换项用 `sourceEventSeqs` 指向原项；原始事件保留，正文中段用固定 prune marker 标示。
- `packages/llm/token-meter/src/surface-projection.ts:68-91` 消费相邻 shadow-price 与 replacement，替换立即进入原生计量；重新调用 budget 有实际更新来源，不需要手动减 token 或维护另一套计数状态。
- R3 已核对的 History 根据 active surface 排除当前项；被 prune 移出的完整原项因此可按既有 window/item 搜索/读取，来源不升级，工具配对不需插件自行修补。部分正文仍在活动预览，不等于完整资料；本轮 runbook 已要求模型必要时正常重读并以原资料核对答案。

#### Delta 与验收边界

- 本轮 delta 将新增的“新任务保存前强制换窗”场景改为“大批工具结果造成压力、先裁剪再测量”，保留 canonical 原有多窗继续、原始细节恢复以及 R3 Skill 场景。新增结果对应用户“把 DSH 原生的压力裁剪接回来，别另造一套，再用刚才那25份资料复验”的当前指令；裁剪不足仍沿用既有换窗，并没有声明已解决所有硬溢出恢复。
- `design.md` 的风险段、runbook 与 M1 退出标准均明确保存 R3 失败、不扩大 fixture 强行换窗、不补特殊导航、不把避免一次换窗夸成不可裁剪场景全通过。这个边界成立；后续交付必须保留残余风险，而不能仅以本轮绿色结果关闭此前所有强制换窗恢复主张。
- 离线 `/tmp/bugfix629-r3-pruner-check.json` 明确是已发布 `pruneContent` 对 25 项结果的纯计算，264,885 → 32,450 是估算而非真实请求或模型正确性。设计把它作为接线动机，不作验收证明，证据使用恰当。
- 真栈复验固定相同 25 份内容、默认预算/权限/spill、旧完成 Notes 和真实 Inbox 新任务，要求看到原始批次越线、native prune、新请求仍含当前任务且未发生不必要换窗，以及三项真实待办完整且只交付一次。检查原生事件、provider 请求和 IM 落库，足以区分算法生效、请求保留与业务完成。
- 自动回归覆盖真实发布版 DSH 组合、裁剪后仍超线、低于 W、服务缺席、显式换窗和两个自动入口；原始事件可读也有明确断言。rc.4 新不可变发布及安装 hash 保留，避免把 rc.3 失败版本与最终验收版本混用。

### Retained coverage

`retained_from: Round 3`。本轮未改变新模式跳过 nano-used-skills、原生 Skill 目录、受限 History、原 Notes/History 提示、来源与白名单、无摘要/no-tail、公开配对换窗事务、workspace 生命周期及无客户端变化；沿用 R3 已核源码和架构判断。R3 的 Approved 只证明当时设计可实施，其随后发生的真实失败已经纳入本轮事实，不保留任何不存在的产品验收通过结论。

### 历史问题闭环

- **R1-W1 — closed 保持**：R3 的用户选择与受限 History 路径不变；本轮不恢复已撤回的全文回退或 turn 协议。
- R3 真实事故复验失败不是历史设计 issue ID，保留在 implementation/最终产品报告中；R4 定义新的受约束复验，不回写旧失败。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增建议；按现有 pruner 与已冻结 25 份资料验证，不新增裁剪器、阈值或重试机制。

### 本轮边界

仅追加 R4，未修改冻结 design/delta、产品代码、插件、既有验证记录或原会话；未提交、运行服务或重复实验。Approved 为设计门禁结论，不是 rc.4 已实现、同资料已交付或生产故障已全部关闭的证明。

### Author Resolutions (R4)

Accepted R4 delta review: 0 CRITICAL / 0 WARNING. The frozen design and delta are unchanged. Implement the published DSH pruner at the declared pressure/overflow seams, retain R3 failure as evidence, and validate the unchanged 25-volume fixture through the real product entry. Offline reduction is not product acceptance.

## Round 6

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`
- reviewer target: 仅 R6 Skill/Inbox 原生裁剪接合；不重审 R4/R5，不审产品代码 diff
- checkout: `/Users/czj/.codex/worktrees/bugfix-629-context-recovery/nano-multiagent`，branch `codex/bugfix-629-context-recovery`
- baseline: HEAD `6649dd70c66b1817bf742c44898d1b8dda3105c9` 加本轮冻结的 incident/design/delta 增量
- frozen SHA-256: `incident.md=319e9a797137139d738aa87d2e46ca3f6602df429f2563f97026ef46774f9b05`；`design.md=ea3eb1d20875bf433434475e23c5c9a6e883a7e04da20f8eea4eed92f37446e7`；delta `agent-capabilities.md=9392ff6856398357df58ac5e416ee019dc5710c5ab03eafdfef21acf75e3570a`
- review_mode: delta
- mode_reason: 新增单一消费者生命周期修正，沿用 DSH 原生结果事件、既有显式 Skill 注入和当前来源规则；与换窗任务恢复方案、裁剪算法和 Notes 展示没有新的耦合决定
- started_at: 2026-10-21T18:06:28+08:00
- completed_at: 2026-10-21T18:08:52+08:00
- duration: 2m24s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

从完整、成功且宿主确认 live 的 Inbox 结构化结果一次提取手势，再由原 pre-step 路径按当前 Skill 选择注入，能消除对已裁剪历史文本的 JSON 解析依赖。只传递现有显式调用所需的 `(messageId, skillName)`，没有新增正文副本、持久恢复协议或授权通道。

### Coverage 与证据

#### 已确认的断点与结果观察边界

- `packages/dsh-integration/src/capabilities.ts:95-107` 当前每个 pre-step 遍历 `deriveMessages()`，在检查 invocation ID 前先对标记为 live 的历史工具文本 `JSON.parse`。原生 pruner 保留 call ID，却替换正文中段，所以 dedup 无法阻止已处理过的结果在下一步解析失败。仅 catch 并丢弃会同时掩盖尚未识别的手势，不是所需修复。
- `packages/dsh-integration/src/global-mode.ts:43-62` 将产品结果保留为 `body`，为文本和附件形成 `content`，read 路径完成 `inbox.prepare` 后调用 `recordInbox(agent.id, callId)`，最后返回 `{ body: result, content: admitted }`。因此成功 `tools/result` 观察点已经可以验证宿主 live 标记并读取完整 body，不需另加产品 RPC 或读取持久历史。
- 固定 DSH `packages/core/tools/src/index.ts:190-198,570-576,1665-1713,1885-1900` 将 `tools/result` 定义为 scoped、同步、只读的最终结果观察事件；成功结果的 `value` 是执行本地的 lossless JSON，独立于呈现 content 且不会写入 durable events。文本裁剪并不把该结构化值变成被截断的 JSON 字符串。设计在 observer 中只同步提取和入队，不调用工具或异步读取 Skill，符合该公开契约。

#### 来源、选择与去重

- 入队条件同时要求 `exec.name === inbox`、成功最终结果、所属 Agent 的 `isLiveInbox`，再过滤 `sender.type === user` 与非 partial 消息。这保留了原宿主来源准入，失败结果即使曾进入执行体也不供给手势；`check`、非 live、Agent/system、partial、History/read 或恢复事件不会仅因含有 `/skill:` 文本而升级为新调用。
- `ApprovalSources` 的 live 集合是进程内宿主记录；恢复日志不会重发 `tools/result`，也不会重建新的 live 授权。Agent-keyed 队列不跨 Agent 传递，重启后不从旧正文重新创建待调用手势，符合本次不引入持久恢复协议的限制。
- Skill 正文仍由 accepted pre-step 使用当前 scoped `skills.get` 和 `isUserInvocable` 获取；不能在观察时把当时可用的正文缓存下来绕过后续 selection。直接 nano-human 输入使用同一手势 parser，保留原语法和输入身份。
- 既有 `nano-skill:<messageId>:<name>` invocation ID 仍是持久去重依据；同一条真人消息多次 live read 不会因新 call ID 再注入。已经写入的 invocation 即使随后退出 surface，也可从原生日志识别；无需新增已处理消息数据库。注入继续使用 `skill-invocation` source，不改标为新的 `nano-human`。

#### 队列生命周期与职责

- 队列只承接“工具最终结果已观察，但下一步尚未注入”的短期状态，内容是两项定位信息而不是第二份 Inbox 正文；WeakMap 随 Agent 生命周期释放，属于现有适配器局部职责。
- 设计明确拒绝的 pre-step 不消费队列；accepted 路径才通过原有 selected registry 生成 additions 并使用已有 invocation ID 去重。队列不承担换窗后的任务恢复，也不负责重启重放；这与原 live 来源仅在当前进程成立的范围一致。
- 原生裁剪继续改写模型可见工具文本，R6 不阻止裁剪、不把完整 Inbox 重新注入上下文、不改变裁剪阈值或工具执行权限。修复位置在 Nano 的 Skill 手势消费者，而非 DSH pruner，避免让通用裁剪器理解产品 Inbox 格式。

#### Delta 与验证

- incident 新增 R6 根因与完成条件；design 给出观察、暂存、消费和来源规则；delta 在既有 canonical Requirement 下补充“Explicit Skill gestures survive later tool-history pruning”场景，保留原有场景。三者一致，描述的是当前合法显式手势不因后续裁剪崩溃/重复，没有承诺增加其他来源的自动调用。
- 计划扩展 `packages/dsh-integration/tests/knowledge.test.ts:146-172` 的现有原生 live-Inbox Skill 测试，能复用真实 Global tool、来源登记、原生执行日志和重启路径。长结果低于单结果 spill 阈值、但确实出现 native prune 事件，避免把另一种截断或仅构造字符串当作集成证据。
- 验证连续后续步骤无 JSON 异常且只有一次 invocation，结合真人、Agent、partial 和恢复来源边界，直接对应新增行为。脚本 provider 适合这项确定性集成回归；设计明确不以它替代真实模型任务恢复验收，范围恰当。

### Retained coverage 与历史结论

- `retained_from: Round 4`：公开 pruner、budget 重算、默认阈值、History 可恢复性和权限边界未改。R3 对原生 Skill 目录、无额外已用 Skill 恢复及来源的有效判断保持。R5 Notes 格式校正不是本轮重审对象，本轮不补造其 Gate 2 Round。
- **R1-W1 — closed 保持**：本次不恢复新模式自动正文，也不改变受限 History 路径。
- 本轮修复的是 Skill 消费者解析已裁剪 JSON 的异常，与 R5 真实模型仍读旧 Notes 的失败不同。R6 绿色不能关闭后者，既有任务恢复失败记录须继续保留。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无额外建议；不扩张到其他历史 JSON 消费者、任务协议或权限机制。

### 本轮边界

仅追加 R6 到本报告；未修改冻结受审文档、源码、既有验证记录或 runtime，未提交、运行服务或执行测试。结论是该增量的设计门禁通过，不是 Skill 回归或原任务恢复已经验收完成。
