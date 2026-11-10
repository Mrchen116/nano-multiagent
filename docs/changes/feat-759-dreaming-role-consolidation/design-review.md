# feat-759 独立设计审查

## Round 1

- Reviewer / target：`design_review`，独立 `change-design-reviewer`。受审对象为 `develop`（`9490424a1`）工作区的 [首文档](spec.md)、[设计](design.md)、[Gateway delta](specs/gateway/agent-capabilities.md) 和 [M1 骨架](M1-role-and-consolidation/.gitkeep)。
- Review mode：`full`。首轮 Gate 2，检查全部三个目标、实际装配、关键决策、消费和恢复边界、delta、milestone 与验收准备。并入 `agent-context-review` 设计模式。
- Started at：`2026-11-10T19:15:13+08:00`。
- Completed at：`2026-11-10T19:18:45+08:00`。
- Duration：`3m 32s`。
- Verdict：**Issues Found · 0 CRITICAL / 3 WARNING**。

### 覆盖与证据

- **前台角色约定。** Node 在正常产品进程内按 Agent 配置与会话绑定启动运行时，运行时注册 `KnowledgeRuntime`，由其挂接 `DocumentMemory` 的请求装配。现有文档记忆按同主体查固定工作区，角色入口改用当前 Session 精确绑定可以保留普通 child 的记忆入口；原生 fork 的父前缀可以沿用。由宿主按缺失时创建占位文件、由根 Agent 普通工具写入经确认的正文，可复用现有工作区与文件能力。角色位于正式记忆目录之外，Dreaming 的暂存写路径也无需扩大。主动询问、逐次确认、跨请求刷新及数据与维护指令分开在方案中有落点。多方确认和工具受限的消费边界见 R1-W1、R1-W3。[Node 接线](../../../apps/node/src/main.ts#L163) · [运行时注册](../../../packages/dsh-integration/src/index.ts#L224) · [知识装配](../../../packages/dsh-integration/src/knowledge/runtime.ts#L52) · [文档装配和目录限制](../../../packages/dsh-integration/src/knowledge/document-memory.ts#L29) · [原生文件语义](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L57) · [fork 现行契约](../../specs/gateway/agent-capabilities.md#scenario-fork-子-agent)
- **后台整合。** Dreaming 从固定工作区准备暂存文件，通过独立空种子维护会话提交模型输入。其装配会过滤普通 Persona 和动态上下文，把只读角色快照放入整合的显式业务输入可避开这层过滤，纳入现有预算测量，并用已有的维护会话 `history` 找回；`source_history` 仍用于被允许的业务来源。现有来源目录可回查本批所含的 task summary 及其被证明的后代，不能任意读取未在目录中的旧任务。若原证据不可达，本轮根据已有可靠证据保留例外、并存解释或未知项，与首文档限定“有足够依据”一致。提炼继续保存任务事实，整合按角色挑长期可复用结论、条件和来源，历史保留关键经过，职责和保存方式仍为两阶段。[Dreaming 输入与预算](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L228) · [维护会话与过滤](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L32) · [业务来源回查范围](../../../packages/dsh-integration/src/knowledge/dreaming-history.ts#L19) · [当前提示](../../../packages/dsh-integration/src/knowledge/dreaming-prompts.ts#L65)
- **重组及首页。** 当前宿主已经检查暂存目标路径、既有文件的完整读取和版本，差异计划只写 Markdown，首页排在正文后。移除正文变更对首页差异的强制要求、复用现有 8,000 UTF-16 code units 装配上限校验新的首页，可以支持正文单独更新，并让合格的新首页仍能直接进入日常请求。旧超限首页有路径回查，允许按相关批次收敛。保存与 Git 回执、来源水位和无变化处理仍由宿主负责。正文页合并的应用顺序见 R1-W2。[计划生成](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L123) · [前台首页阈值](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L152) · [应用与进度](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L378)
- **参考与职责。** 逐项核对 OpenClaw 从主动谈话到写入身份文件的示例及实际 bootstrap 路由，Codex 对任务保真、后续不同任务的检索价值与适用范围的写法，以及 memoryrepo 的搜索、去重、移除失效条目、修复链接和短首页。Anthropic Organizer 公开示例另提供先写入并读回目标、再把原页缩成链接的具体做法。现有 DSH 原生文件与角色装配、Nano 来源准入、既有 Dreaming 计划分别承担其职责。角色确认复用对话规则，知识重组复用整合 prompt 和宿主计划，不需要增加 Dreaming 阶段、审批产品实体或第二个正式记忆写者。上述参考证实相关提示和运行接线，Nano 效果仍由隔离真实模型对照判断。[OpenClaw 模板](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/docs/reference/templates/BOOTSTRAP.md#L14) · [OpenClaw 调用](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/src/agents/pi-embedded-runner/run/attempt-bootstrap-routing.ts#L36) · [Codex 提炼](../archive/feat-676-role-memory-dreaming/input/codex-memory-v2-8fdf647295/stage_one_system_v2.md) · [Codex 整合](../archive/feat-676-role-memory-dreaming/input/codex-memory-v2-8fdf647295/consolidation_v2.md#L8) · [memoryrepo 整合与调用](https://github.com/supermemoryai/memoryrepo/blob/54f7ff3065df8af687dc5c04a4bb17d6611e5fd1/src/server/memory.ts#L60) · [Anthropic Organizer](https://github.com/anthropics/claude-cookbooks/blob/ce8b2629efe8b24048b127b4c79af1e9cbab93d4/managed_agents/example_data/memory_distill/prompts/organizer_system.md#L11)
- **Delta、milestone 和前置。** Gateway 是正确 canonical target，MODIFIED 的六个旧 Scenario 逐一对比均保留，新增场景覆盖角色使用、长期提炼和正文重组。角色新增契约尚需补齐 R1-W1、R1-W3 的可观察行为。三个目标共享根装配与整合试验，同一个串行 M1 及仅含空 `.gitkeep` 的骨架合适。Review runbook 复用支持 `--profile daily` / `--wt` 的隔离入口，给出了凭据与测试绑定检查点、脱敏或合成素材、同模型基线对照和请求/回执证据。多方对话沿用现有 IM 交付，没有待对齐的新客户端界面，无 prototype 或 must-match 条目。按需初始化角色文件和自然批次整理不需要一次性部署迁移。[Gateway canonical](../../specs/gateway/agent-capabilities.md#dreaming-按交流与任务经历组织记忆) · [M1 与 runbook](design.md#runbook-for-reviewer) · [隔离环境](../../development/worktree-runtime.md#固定日常验收模板)

本轮证据为当前源代码、产品入口接线、文档及上游原件。下列 WARNING 是设计缺口，实际请求、工具行为及模型整理结果由实施阶段观察。未启动服务、未生成或清理运行资源。

### Issues

**R1-W1 · 共享角色约定缺少可识别的确认人和实际提议绑定。** **CONFIRMED（设计）**。接口第 1 条只说“真实、适用的用户”，仅对 PA 指出 owner。独立 Agent 的 ROLE 影响此后所有聊天和 Dreaming，而 Inbox 的独立 Agent 行只呈现真人类型、发送者及目标，未标出这位发言者是否有权决定该 Agent 的全局角色。现行产品有负责管理 Agent 的绑定账号，`SessionBinding.ownerId` 在宿主存在；一条普通 IM 消息的真实来源本身只证明谁说了什么。PA 也需要同时识别 owner、participant 和提议实际所指，owner 观察消息依然可能是写给别人。若按真实对话者即可确认解读，某群成员能把该群临时分工改成全局职责。反之，只写“适用”也可能让模型拒绝完成所有首次确认。修订时在设计和 delta 确认独立 Agent 适用主体及其模型可见识别来源，明确 PA 沿用参与及实际收件人规则。Global 的提议用既有公开交付，并依据同一实际聊天内已送达提议和适用用户的回复匹配，避免以私有草稿或另一聊天的“可以”写入。确认继续由 prompt 约束。M1 加入普通协作者、PA observer 或无关聊天回复的反例以及一次有效确认。[受审接口](design.md#接口与数据流) · [Inbox 投影](../../../packages/personal-assistant/src/inbox.ts#L450) · [产品绑定](../../../packages/dsh-integration/src/index.ts#L83) · [设备管理归属](../../specs/im/agents-nodes.md#设备绑定把节点归属到当前用户) · [跨聊天现行契约](../../specs/gateway/global-agent.md#scenario-多聊天提议与简短回复) · [PA 和发送来源规则](../../../packages/dsh-integration/src/policy/sources.ts#L16)

**R1-W2 · 合并后的链接可能先保存，原有内容先于迁入页丢失。** **CONFIRMED（设计）**。设计允许旧正文压缩为指向主页面的链接，同时沿用原计划顺序和失败恢复，只规定首页排最后。实际计划按正文路径字典序排列，宿主逐页保存后记录回执，失败时停止。例：`knowledge/a.md` 压成指向 `knowledge/z.md` 的链接，前者先成功，后者版本冲突或写入失败。若冲突使计划退役，原有条件或证据会从当前 Wiki 中消失，链接也可能指向不存在的页。暂存区已具备完整内容不保证正式库保存顺序。保持写操作一种，明确先保存承接相关内容的正文，再收缩旧页或改写依赖它的导航，或者约束本批只生成依赖已保存内容的链接。用第二页保存失败的隔离案例验证原有知识仍可读。公开 Organizer 示例提供同一行为的写法，可作为现有设计引用的具体补充。[重组和应用设计](design.md#接口与数据流) · [当前排序](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L132) · [逐文件应用](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L378) · [冲突退役](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L177) · [Organizer 的目标先行规则](https://github.com/anthropics/claude-cookbooks/blob/ce8b2629efe8b24048b127b4c79af1e9cbab93d4/managed_agents/example_data/memory_distill/prompts/organizer_system.md#L17)

**R1-W3 · 用户确认后的写入保证缺少现有工具受限分支。** **CONFIRMED（契约与设计）**。设计用普通文件工具，且要求不变更现有权限，但首文档和 delta 仍以“用户同意”直接推出成功保存。实际根 Agent 可使用显式白名单，包含空集，原生文件工具并非固定 Global 沟通工具；当写工具未开或动作被既有规则拒绝，宿主依然能生成占位并让模型提出确认，模型却没有普通保存路径。若只按当前成功契约验收，会把这类 Agent 误报为已保存或促使实现绕开权限。设计及 delta 写清允许且成功才生效，工具缺失、拒绝或失败时维持旧文件并告知用户结果。补一项真实受限工具场景，确认后仍未保存，后续请求和 Dreaming 仍消费旧值或占位。复用已有权限与结果语义即可。[首文档验收](spec.md#验收标准) · [角色 delta](specs/gateway/agent-capabilities.md#scenario-首次确认或修改约定) · [根会话工具白名单](../../../packages/dsh-integration/src/capabilities.ts#L38) · [设置现行契约](../../specs/im/agents-nodes.md#toolcatalog)

### Recommendations

- **R1-R1。** 在设计的 OpenClaw 引用同时标注实际 bootstrap 路由，并写明它只说明待初始化的用户交互适合做引导。OpenClaw 完整模式会阻止普通首回复先于引导处理，Nano 已确认普通任务照常进行与后续继续询问。两者的触发和答复次序可以据此清楚区分。[OpenClaw 路由](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/src/agents/pi-embedded-runner/run/attempt-bootstrap-routing.ts#L36) · [OpenClaw 引导提示](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/src/agents/bootstrap-prompt.ts#L1)

### Author Resolutions

- **R1-W1 — accepted.** Inbox 实际提供作者与 target，产品绑定提供可信节点主人，PA 另有主人、参与和实际收件人语义。按 [设计接口](design.md#接口与数据流)匹配同一实际聊天中的已送达提议和确认回复，首文档、delta 和验收方法同步。
- **R1-W2 — accepted.** 现行应用在文件保存失败时停止，冲突时可能退役计划。按 [重组决定](design.md#3-借鉴-memoryrepo把更新和清理都写成-dreaming-的职责)，跨正文缩减前先从正式库读到已有的承接内容，仍只在暂存的内容保留原页副本，现有应用顺序可复用。增加隔离失败验证。
- **R1-W3 — accepted.** 复用普通工具及回执，成功才成为新约定。首文档、[角色 delta](specs/gateway/agent-capabilities.md#scenario-未确认或未保存)和验证方法补入工具缺失、拒绝或保存失败。
- **R1-R1 — accepted.** 已在 [第一项决定](design.md#1-借鉴-openclaw-的主动开场和落盘顺序)补充 OpenClaw 实际路由，以及 Nano 普通任务照常处理的行为。

## Round 2

- Reviewer / target：`design_review`，同一独立 `change-design-reviewer`。受审对象为 `develop`（`9490424a1`）工作区的修订后 [首文档](spec.md)、[设计](design.md)、[Gateway delta](specs/gateway/agent-capabilities.md) 和 M1 证据安排。
- Review mode：`delta`。复核角色确认的身份来源及失败语义、跨页迁移的保存边界，以及三项修订在契约和证据安排中的投影。修订改变了有界行为。角色文件位置、正式记忆写入归属、Dreaming 提炼及预算恢复、主要装配路径和 milestone 结构沿用 `retained_from: Round 1`。
- Started at：`2026-11-10T19:20:37+08:00`。
- Completed at：`2026-11-10T19:21:51+08:00`。
- Duration：`1m 14s`。
- Verdict：**Approved · 0 CRITICAL / 0 WARNING**。

### 历史问题闭环

- **R1-W1 · closed。** Author 采用独立 Agent 所在节点的绑定主人，复用 PA 主人、实际参与及收件人语义。Node 实际 Global 装配的 `ownerId` 来自节点用户 ID。SingleThread 的产品绑定也持有该值，真实输入的 sender ID 进入宿主标记的 `actorId`。Nano IM Inbox 已提供真实的 `sender.id`、类型与目标，PA 另有 `is_owner` 和 `delivery`。修订明确角色上下文提供绑定身份，并用可信真人来源核对实际作者。Global 复用已送达提议和同一实际聊天的明确确认，验证覆盖有效确认、非绑定协作者、PA observer 与另一聊天的简短回复。实施阶段从实际 provider 请求核对直接消息的可信来源是否能与绑定身份关联，宿主已存 `actorId` 本身只证明来源可用。[设计接口](design.md#接口与数据流) · [Node 用户绑定](../../../apps/node/src/main.ts#L492) · [Global 会话绑定](../../../packages/personal-assistant/src/global-agent.ts#L139) · [SingleThread 绑定与直接输入](../../../packages/personal-assistant/src/single-thread.ts#L100) · [直接输入来源](../../../packages/personal-assistant/src/single-thread.ts#L200) · [Inbox 来源](../../../packages/personal-assistant/src/inbox.ts#L450) · [跨聊天现行契约](../../specs/gateway/global-agent.md#scenario-多聊天提议与简短回复)
- **R1-W2 · closed。** Author 将可缩减的范围限于本批从正式库完整读到主要页已承接的内容和依据。接收页内容尚只在暂存时，原页保留独有信息。实际维护工具已有正式库只读、暂存可写的路径，可在普通编辑前完成这项判断。用 R1 的 `a.md` / `z.md` 反例复核，`z.md` 如仅是暂存写入，`a.md` 会保留相关内容，现有逐页应用顺序和失败恢复可复用。已保存目标可在后续相关批次支持旧页收缩。delta 和验收安排均要求在接收页保存失败时原页可读。[重组决定](design.md#3-借鉴-memoryrepo把更新和清理都写成-dreaming-的职责) · [已有工具边界](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L73) · [宿主逐页回执](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L378) · [重组 delta](specs/gateway/agent-capabilities.md#scenario-按主题重组已有知识)
- **R1-W3 · closed。** Author 在设计与 delta 明确普通文件工具实际保存成功才激活新约定。现有白名单、拒绝及失败语义均适用。模型在受限或失败时报告未保存，主会话后续请求和 Dreaming 使用旧值或占位。审查表新增工具关闭或失败的隔离反例，纳入同一 M1 的权限与应用证据。[设计接口与审查安排](design.md#接口与数据流) · [失败 delta](specs/gateway/agent-capabilities.md#scenario-未确认或未保存) · [现有工具选择](../../../packages/dsh-integration/src/capabilities.ts#L38)
- **R1-R1 · adopted。** OpenClaw 参考补齐实际 bootstrap 路由，设计明确 Nano 在未完成角色澄清时照常处理普通任务。闭环依据沿用 R1 已核对的模板与运行路由。[参考决定](design.md#1-借鉴-openclaw-的主动开场和落盘顺序)

### 覆盖与证据

核对了三个决策从实际产品入口、可信模型来源和文件工具，到首文档、delta 及 M1 证据方法的影响。现有六个 canonical Scenario 继续保留。受审方案沿用现有 IM 确认、Dreaming 两阶段及宿主写入，角色确认和整理策略由 prompt 表达。本轮依据实际源码和修订文档做设计判断，未启动服务或模型。

### Issues

无。

### Recommendations

无新增。
