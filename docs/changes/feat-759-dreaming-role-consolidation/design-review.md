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

## Round 3

- Reviewer / target：`design_review`，同一独立 `change-design-reviewer`。受审对象为 `develop`（`07ad36c33`）工作区新增人工编辑需求后的 [首文档](spec.md)、[设计](design.md)、[Gateway delta](specs/gateway/agent-capabilities.md)、[IM delta](specs/im/agents-nodes.md) 和 M1 退出标准。
- Review mode：`full`。用户增加一种正式写入入口，新增 IM、Node、DSH 和两端配置界面契约并扩大 M1。复核全部受影响的职责、数据流、消费者与验收安排。两阶段 Dreaming 的既有提炼、重组、来源资格、预算、恢复及正式文档保存继续引用 `retained_from: Round 2` 与其 R1 证据。
- Started at：`2026-11-10T19:28:04+08:00`。
- Completed at：`2026-11-10T19:30:55+08:00`。
- Duration：`2m 51s`。
- Verdict：**Issues Found · 0 CRITICAL / 2 WARNING**。

### 覆盖与证据

- **真实入口与职责。** 现有配置入口先验证登录身份、空间与 Agent 主人，现有文件型设置走 IM 到当前 Node 的认证 RPC。RPC 校验回包连接和消息类型，配置当前读取另有 profile 与连接代次的返回前复核。ROLE 可以沿用这条路径，继续由 Node 定位目标运行时、DSH 读写固定文件，不让 IM 直读节点工作区。设计将正文留在宿主文件，不放到公开资料、配置版本或离线快照，GET 无副作用。有效连接、当前绑定与已证实保存应是返回正文或成功的前置；缺失、不可用和超时保持独立状态。实际跨分区工作区归属见 R3-W1。[现有控制入口](../../../apps/im-server/src/control-routes.ts#L101) · [在线与当前绑定校验](../../../apps/im-server/src/agent-settings.ts#L22) · [RPC 回包相关性](../../../apps/im-server/src/node-rpc.ts#L61) · [Gateway 连接校验](../../../apps/im-server/src/gateway.ts#L400) · [Node 文件型设置入口](../../../apps/node/src/main.ts#L317)
- **共享版本和角色消费。** 设置保存以本次读取的文件版本提交，DSH 的显式 `createIfAbsent` 或 `replaceIfVersion` 与现有文件能力相容。聊天继续通过普通文件工具读取后写入，现行观察策略使用文件读取时的版本，并在过期时要求重读；因此可以检测配置页写在聊天读取之后的竞争。聊天在新的人工内容改变原提议依据时重新核对，改变拟写入文本才需要再次确认。管理者显式保存授权该次人工写入；普通配置保存、角色草稿与源证据互相独立。主 Agent 下一请求读取当前值，新整合批次取新快照，进行中的整合继续用原快照，清空则恢复主动澄清。当前批次的业务回查和正式记忆写边界均保留。实施证据应能观察到与聊天交叉写入造成的过期文件结果，超时重读表示当时可确认的文件状态。[受审数据流](design.md#接口与数据流) · [当前文件版本写入](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L208) · [普通工具已挂载观察策略](../../../packages/dsh-integration/src/knowledge/document-memory.ts#L29) · [当前维护范围](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L73)
- **配置体验。** 检查了最近的归档真实 Web 设置画面中的文件读取、上次确认提示、普通配置区，以及当前 Web/iOS 控件和状态接线。把角色项放在自定义指令附近，分别说明用途，局部显示保存结果、最新版本和未保存草稿，可以沿用现有信息层级与输入组件。设计已给出决定性的操作与状态，无需另做界面原型。两端各有本地表单、保存和回退行为，原生体验取证缺口见 R3-W2。画面证据为既有功能基线，本轮未观察 ROLE 界面或执行新的保存旅程。[Web 基线画面](../archive/bugfix-644-agent-offline-settings/review-evidence/r2-history-body.png) · [Web 基线回归](../archive/bugfix-644-agent-offline-settings/regression.md#历史正文与时效补证) · [Web 普通保存与退出](../../../src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx#L2080) · [iOS 表单与状态](../../../src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift#L59)
- **Delta 和 M1。** IM 配置的消费者契约正确锚定 agents-nodes，Gateway 行为增量继续描述主会话及 Dreaming 的下一消费时点。没有移除 Dreaming 原有六个 canonical Scenario。保留单一串行 M1 合适，Web 的管理权限、保存、清空、断线、版本冲突及后台采用已进入验收计划。扩展后的工作区边界与 iOS 实际交互需补入 M1。隔离服务、测试账号及模型仍按原 runbook 准备，本机明确选用完整 Xcode 后可用 Xcode 26.4.1 和 iOS 26.4 模拟器 runtime。本轮未启动服务、模拟器或模型。[IM 目标](../../specs/im/agents-nodes.md) · [Gateway 目标](../../specs/gateway/agent-capabilities.md) · [M1](design.md#milestones) · [iOS 隔离工程入口](../../../src/IM/ios/README.md#模拟器测试)

### 历史问题闭环

R1-W1/W2/W3 继续关闭。聊天确认人与同一实际交流的约束不变，人工入口采用已授权管理者的明确保存。跨页退休约束继续以正式库为依据。对话普通文件工具失败仍须如实报告，人工入口使用独立 RPC 回执。

### Issues

**R3-W1 · 跨分区的 ROLE 文件归属缺少可执行的权威判断。** **CONFIRMED（设计）**。第 5 条把拒绝共享工作区写在转发至 DSH 后的宿主解析描述中，未说明哪个位置拥有完整 Agent 配置，或同一资格如何供 API 和运行消费共用。Node 启动时只给每个 DSH 进程传入该分区的 `partition.agents`，PA 与普通 Agent 分区不同。现有 `DocumentMemory.forConfig` 只看该进程已打开的库。Node 自定义工作区解析也允许配置已存在的目录。两个 Agent 若解析到同一真实工作区，在首次聊天前或分属不同分区时，两边都可能把同一 `ROLE.md` 当作本 Agent 独享文件，修改一个角色就改变另一个 Agent 的长期职责。明确由能看到整台节点配置的 Node 依据已解析路径核对文件归属，相关 ROLE 写入与运行消费采用同一判定，或给出已有的等价权威来源。Node 已有跨配置的 canonical 路径比较可参考，编辑无需复用目录删除所需的删除见证。M1 加入跨分区或尚未建会话的两个配置共享同一路径的用例，验证不能通过设置或运行装配串用角色。[设计接口](design.md#接口与数据流) · [分区初始化](../../../apps/node/src/main.ts#L163) · [分区定义](../../../apps/node/src/runtime-partitions.ts#L47) · [本进程库判定](../../../packages/dsh-integration/src/knowledge/document-memory.ts#L59) · [Node 配置与已存在路径](../../../apps/node/src/configuration.ts#L130) · [Node 跨配置比较](../../../apps/node/src/configuration.ts#L170)

**R3-W2 · iOS 新的独立保存和冲突交互缺少客户端验收证据。** **CONFIRMED（验收安排）**。IM delta 承诺 iOS 可以就地保存 ROLE、保留冲突草稿并和普通配置独立。设计只要求 Web 实际操作，iOS 做编译及泛称“相关回归”。当前 iOS 普通配置由 SwiftUI 顶部 Save、自己的草稿与冲突状态、离开保护共同控制，ROLE 又将增加另一组保存与冲突状态。共用 API 无法验证点顶部 Save 时不会提交角色，或者重读冲突时角色草稿仍在并可再次明确保存。M1 至少补一次隔离 iOS 模拟器的连续操作，覆盖独立保存和重开确认，以及冲突重读时保留草稿。完整权限、来源、离线及模型矩阵仍可在 Web、API 和 runtime 复用。没有需要增加的原型门禁。[IM 契约](specs/im/agents-nodes.md) · [现有 iOS 草稿和冲突状态](../../../src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift#L24) · [iOS 保存与离开](../../../src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift#L103) · [平台证据方法](../../../.agents/skills/frontend-experience-review/references/prototype-and-runbook.md#验证平台与深度) · [现有 M1](design.md#milestones)

### Recommendations

- **R3-R1。** 首文档将“首次填入和后续修改都由主 Agent 完成”限定为对话内更新，与用户后续增加的人工编辑入口统一。[首文档角色维护](spec.md#角色约定的维护与使用)

### Author Resolutions

- **R3-W1 — accepted.** 运行时分区只拥有各自的 Agent；整节点的配置和已准备工作区由 Node 掌握。按[人工编辑数据流](design.md#接口与数据流)，设置和两个运行消费者共用 Node 的 canonical workspace 归属判断，以既有本机 stdio 与分区校验交付。加入 PA 与普通分区同一工作区、首聊前后均不串用的用例。
- **R3-W2 — accepted.** 按[审查安排](design.md#本次审查安排)补 iOS 模拟器的独立保存、重开、普通保存不提交角色和冲突草稿保留。共享权限及后台采用沿用 Web、API 与 runtime 证据。
- **R3-R1 — accepted.** 首文档把主 Agent 更新规则限定为对话内更新，人工入口保留独立确认方式。

## Round 4

- Reviewer / target：`design_review`，同一独立 `change-design-reviewer`。受审对象为 `develop`（`07ad36c33`）工作区的 R3 修订。
- Review mode：`delta`。两项有界修订明确了既有人工入口下的内部归属接线和原生验收证据。重新检查跨分区数据流及其三处消费者、iOS 旅程、M1 和首文档语义。外部 API、其余 IM 和 Gateway delta、主要写入语义与 milestone 划分未变，`retained_from: Round 3` 的未受影响证据继续有效。
- Started at：`2026-11-10T19:32:55+08:00`。
- Completed at：`2026-11-10T19:33:42+08:00`。
- Duration：`47s`。
- Verdict：**Approved · 0 CRITICAL / 0 WARNING**。

### 历史问题闭环

- **R3-W1 · closed。** Author 将工作区归属判断放在拥有完整配置及预备工作区的 `NodeConfiguration`。实际 Node 通过 `resolve` 记录已准备的 canonical 路径，现有跨配置检查同时可看当前配置及预备目录。方案借用 realpath 判定，无需目录删除见证。设置接口在转发前判断归属，主 Agent 与 Dreaming 用同一 Node 判定。现有 `RuntimePartitions` 注册宿主回调时按请求 Agent 所在分区检查来源，stdio 已支持 DSH 发起 Node 回调。该接口只需返回本 Agent 的角色资格，角色正文及固定路径继续由所属 DSH 分区读取。对照 R3 的 PA 与普通 Agent 共用真实目录案例，两个分区都可在首聊前得到不可用，前台跳过角色文件初始化、注入与指导，后台新批次也不消费。设计加入用实际配置复现的反例，覆盖设置和会话启动后的模型请求。原有文档记忆及 Dreaming 批内快照仍各按自己的契约处理。[修订数据流](design.md#接口与数据流) · [预备 canonical 路径](../../../apps/node/src/configuration.ts#L145) · [整节点配置检查](../../../apps/node/src/configuration.ts#L170) · [分区来源校验与回调注册](../../../apps/node/src/runtime-partitions.ts#L194) · [实际 Node 回调示例](../../../apps/node/src/main.ts#L505)
- **R3-W2 · closed。** Author 在设计和 runbook 补入对同一隔离 IM 的原生模拟器操作。独立保存后重开、普通配置保存不提交角色草稿、版本冲突后读取最新值并仍保留原草稿，分别对应 SwiftUI 自己的状态及顶部保存按钮。审查表写明实测范围，M1 要求保留模拟器操作证据。权限和后台采用沿用 Web、API 与 runtime 的验证计划。R3 已核对完整 Xcode 与 iOS runtime 可用，修订将其明确为验收前置。[审查安排](design.md#本次审查安排) · [隔离运行入口](design.md#runbook-for-reviewer) · [M1](design.md#milestones) · [iOS 顶部保存](../../../src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift#L103)
- **R3-R1 · adopted。** 首文档已把主 Agent 首次填入及后续更新限定为对话场景，管理者仍通过配置页的显式保存确认。[首文档](spec.md#角色约定的维护与使用)

### 覆盖与证据

两项修订保留 R2 已审过的聊天身份、提议与回复匹配、写入失败处理及跨页重组边界。复核了本机 Node/DSH 调用入口和修订后的验收前置。新角色 RPC、出站模型请求和 iOS 实际保存行为留待实施验证，本轮未启动服务、模型或模拟器。

### Issues

无。

### Recommendations

无新增。

## Round 5

- Reviewer / target：`design_review`，同一独立 `change-design-reviewer`。受审对象为 unit worktree `codex/feat-759-dreaming-role-consolidation`（`b6f3ce423`）的 [首文档](spec.md)、[设计](design.md)、[Gateway delta](specs/gateway/agent-capabilities.md) 与 M1 批次提交增量。
- Review mode：`full`。用户更改批次保存的核心职责、成功判据及恢复语义，并增加 M1 验收结果。本轮复核整条整合链路与用户约束，ROLE 设置、归属、前台消费和 iOS 验收沿用 `retained_from: Round 4`，提炼及相关证据沿用 R1 至 R4。
- Started at：`2026-11-10T20:02:39+08:00`。
- Completed at：`2026-11-10T20:05:08+08:00`。
- Duration：`2m 29s`。
- Verdict：**Issues Found · 0 CRITICAL / 3 WARNING**。

### 覆盖与证据

- **产品装配与提交职责。** 当前 `KnowledgeRuntime` 实例化 `Dreaming` 和文档库。整合在独立、受限的原生会话使用暂存工作目录，正常结束后返回宿主应用；现有 `MemoryDocuments.apply` 在单页保存后自动记录一个 Git 版本。把真实批次提交放在仅整合 Agent 可发起的固定 `git_commit` 工具，普通编辑继续只写暂存，宿主继续验证并负责正式文件发布，可以表达用户指定的动作和安全边界。工具应以成功提交、无需提交或失败的实际结果反馈；同一个原生 handle 的宿主反馈可使用既有系统来源和 `followup`，保持批次及角色快照。该内部反馈不需要新增 Work 轨迹或修改投影。每次正常结束仍由宿主独立查正式仓，Git 成功或一次普通模型结束均不能单独推进来源。[产品组装](../../../packages/dsh-integration/src/knowledge/runtime.ts#L53) · [隔离会话](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L31) · [现有 followup](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L104) · [逐页版本记录](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L199) · [现有最终回执](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L422)
- **契约与证据。** Gateway 是合适的消费者契约位置，提炼 JSON、取消不进位、来源范围、无信号以及不新增私有 `finish` 都保留。当前设计仍保护完整读取、文件哈希、首页上限、跨页保留证据、ROLE 与正式库隔离。测试计划已包含多页同一 commit、遗漏提交后的同会话反馈、清洁无变化成功及取消，尚缺下列实际失败链路。现有隔离栈、真实模型对照、Web/iOS 设置路径和 M1 的单一串行结构继续适用。证据来自源码、文档和隔离临时 Git 仓的小复现。未启动产品、服务、模拟器或模型，临时 Git 仓已清理。[新 Gateway 场景](specs/gateway/agent-capabilities.md#scenario-提炼输出与整合批次-git-提交) · [审查安排](design.md#本次审查安排) · [M1](design.md#milestones)

### 历史问题闭环

R1 至 R4 的 ROLE 相关问题维持关闭。此前跨页保护继续保留，批次提交改动未改正式库是单一 Dreaming 写入者的边界。

### Issues

**R5-W1 · 同会话继续编辑时，现有应用基准无法接受本批自己的前一次发布。** **CONFIRMED（设计）**。当前暂存 manifest 在 `prepare` 中只写一次。计划用它作为每页 `beforeHash`，正式库仅接受该哈希或目标 `afterHash`。R5 允许同批先把某页 A 发布成 B，再因正式库仍脏而将状态交还同一个 Agent。若 Agent 依据反馈将暂存页 B 改为 C，按原 manifest 计算会拿 A 校验当前正式库 B，当作外部版本冲突。当前仅测补提交原有差异也可能掩盖该缺口。设计明确第二次及后续发布使用宿主实际保存的已验证版本作基准，部分保存时只更新已保存页，保留对第三方版本的冲突保护。续步不提前把验证、Git 和来源水位标成完成。M1 验证同一 handle 在一次正式发布后再次修改同一页并提交，覆盖已应用一部分时保留真实回执的情形。[R5 应用与反馈](design.md#整合-agent-提交和宿主检查) · [manifest 写入](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L336) · [固定基准](../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts#L132) · [第三版本拒绝](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L209)

**R5-W2 · 正式仓脏状态必须进入准入，且必须显式检查未跟踪文件。** **CONFIRMED（设计及命令复现）**。设计要求验证既有脏仓可触发整理，未明确它如何影响当前早退出。现有 `needsVerification` 只比较来源代次和 Markdown 文件哈希，运行在没有新交流/任务材料且不需验证时直接返回。若真实 index 有 staged 变化而工作树 Markdown 内容未变，或只有未跟踪非 Markdown，旧判定不会启动任何整合会话。首次版本记录失败后，已有单页 basis 也可能与脏工作树一致。另在隔离 Git 仓复现 `status.showUntrackedFiles=no` 时，裸 `git status --porcelain` 返回空，显式 `--untracked-files=all` 才得到 `?? knowledge.md`。设计需用真实正式仓状态参与准入和退出，退出检查显式纳入未跟踪文件，命令失败保持未确认。允许处理的 dirty 交给同会话，非记忆路径或不能安全提交的状态走明确阻塞或失败并保留文件，避免已知不可处理项永久唤起同一会话。M1 至少覆盖无新来源但 Git 状态脏及未跟踪检查。[R5 准入与检查](design.md#整合-agent-提交和宿主检查) · [文件 hashes 判定](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L161) · [初次版本失败与 basis](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L79) · [无来源提前返回](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L208)

**R5-W3 · 新的批次 Git 提交未接上原有来源保护的执行边界。** **CONFIRMED（设计）**。现有来源刷新、文件写入及单页版本记录通过同一文档库串行边界协调，`apply` 在该边界内验证来源代次、取消和目标哈希，并在返回前写 Git。R5 把提交移到多页发布之后，仅说明它在同一个工具调用内；多次异步文件发布之间，来源可以被撤销或 Agent 被停用。若直接在发布返回后提交，宿主在最终检查发现过期之前已经把撤销来源派生内容写入 Git。现有单页 Git 也隔离了普通 index 中其他路径。指定 `git_commit` 复用文档库的串行与来源校验边界，在真正提交时核对来源代次、取消状态和已验证正式文件，并且提交仅包含被授权的 Markdown 路径，不顺带带上其他预暂存内容。正式仓最终干净与业务进度仍在同批正常结束后由宿主确认。为发布后、commit 前撤销来源增加隔离证据。[R5 提交接口](design.md#整合-agent-提交和宿主检查) · [来源同步与串行发布](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L182) · [隔离 index](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L238) · [来源失效契约](../../../packages/dsh-integration/src/knowledge/dreaming-history.ts#L36)

### Recommendations

- **R5-R1。** 将首文档场景中「Work 中」改为同一原生整合会话，并注明沿用现有 Work 轨迹。用 native Session ID、宿主反馈、Git commit 和来源水位核对本批结果，可直接遵循用户排除 Work 轨迹改动的约束。[首文档用户场景](spec.md#用户场景)

### Author Resolutions

- **R5-W1 — accepted.** 真实发布成功后按路径推进本会话基线。允许同一 Agent 收到 dirty 结果后再次编辑已发布页面，回归验证包括这种后续修改及首次发布的实际文件状态。
- **R5-W2 — accepted.** 准入与完成都读取正式仓真实 Git 状态，显式启用全部未跟踪项。状态反馈回到同一 Agent，无法由现有 Markdown 能力处理的剩余路径会阻止成功。
- **R5-W3 — accepted.** 提交在文档串行边界核对来源、取消、实际文件版本和 Git index 路径范围。只有 Agent 的工具调用执行提交，干净核对和来源推进保留独立宿主检查。
- **R5-R1 — accepted.** 验收沿用现有轨迹与会话 ID，首文档改为直接描述同一整合会话。

## Round 6

- Reviewer / target：`design_review`，同一独立 `change-design-reviewer`。受审对象为 feat-759 unit worktree（`b6f3ce423`）在 R5 后的 [提交与检查](design.md#整合-agent-提交和宿主检查)、[验收安排](design.md#本次审查安排) 和 [首文档](spec.md#用户场景) 修订。
- Review mode：`closure`。修订闭合 R5 三项缺口与一项建议，未扩张用户范围、外部契约或阶段划分。其他设计与验收证据沿用 `retained_from: Round 5`。
- Started at：`2026-11-10T20:06:37+08:00`。
- Completed at：`2026-11-10T20:06:50+08:00`。
- Duration：`13s`。
- Verdict：**Approved · 0 CRITICAL / 0 WARNING**。

### 历史问题闭环

- **R5-W1 · closed。** Author 规定每页真实保存成功后推进该页验证基线，其他路径失败时保留成功部分。R5 反例中，首次发布 A→B 后，同一 handle 再从 B 修改成 C，校验以实际已保存的 B 为基准，第三方修改仍冲突。独立的 Git 完成和来源水位只在宿主确认正式仓干净后推进。审查安排加入同一会话再次编辑已发布正文并补交的用例。[修订数据流](design.md#整合-agent-提交和宿主检查) · [现有按路径回执与版本保护](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L199)
- **R5-W2 · closed。** Author 明确真实 Git 差异独立于新来源成为整合准入，补上当前 `needsVerification` 和无来源早返回之间的缺口。正式仓退出检查指定 `--untracked-files=all`，覆盖 R5 临时 Git 仓复现的全局或仓级配置隐藏未跟踪项。宿主将实际状态反馈给同一会话，仍不可处理的路径返回阻塞并保留内容。审查安排明确包含无新来源的脏仓。[修订数据流](design.md#整合-agent-提交和宿主检查) · [现有准入分支](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L208)
- **R5-W3 · closed。** Author 将实际提交纳入现有文档串行边界，核对来源代次、运行许可、取消、真实文件版本和 index 范围，再仅提交获准的 Markdown。该边界与现有来源同步可直接复用；单页保存回执和 Agent 发起的 Git 回执分开，宿主最终仍检查干净状态和来源后才进位。实施验证中用发布后、提交前撤销来源落实“未通过检查”分支，并核对真实 Git HEAD 与来源水位，避免仅靠工具返回判断。[修订数据流](design.md#整合-agent-提交和宿主检查) · [来源同步的串行边界](../../../packages/dsh-integration/src/knowledge/memory-documents.ts#L182)
- **R5-R1 · adopted。** 首文档改用同一 Dreaming 整合会话描述继续处理。现有轨迹与会话 ID 可以提供证据，Work 轨迹变更不在本次范围。[首文档用户场景](spec.md#用户场景)

### Issues

无。

### Recommendations

无新增。本轮只审查修订后的设计，实际提交、会话续写及来源变更由实施阶段验证。
