# feat-759 Dreaming 角色背景、长期整合与记忆重组 — 技术方案

> 对齐 [首文档](spec.md)

## Changelog

## 现状分析

### 涉及范围

- [主会话装配](../../../../packages/dsh-integration/src/agent-config.ts)已按产品根、普通 child 和 fork 分配 Persona 和职责。[DocumentMemory](../../../../packages/dsh-integration/src/knowledge/document-memory.ts)在 native request 装配文档记忆，以可信配置及产品绑定解析工作区，按次读取首页。首页超过 8,000 UTF-16 code units 时给路径而省略正文。
- [Dreaming](../../../../packages/dsh-integration/src/knowledge/dreaming.ts)沿用合格 Global 原文、任务摘要、当前首页及按需回查。两个阶段使用隔离子会话，[维护请求](../../../../packages/dsh-integration/src/knowledge/dreaming-agent.ts)过滤掉前台 Persona 等提示，只提供 PA/专家类别。其暂存应用计划目前只支持写入，正文有变化时强制首页也有内容变化。
- [现行提示](../../../../packages/dsh-integration/src/knowledge/dreaming-prompts.ts)的提炼已按 Codex 保留任务脉络。整合复述了部分任务保真要求，同时要求短首页和主题/历史分层，对既有页面重组的触发和操作写得较弱。
- Web 的 [Agent 配置](../../../../src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx)与 iOS 的 [AgentConfigView](../../../../src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift)都有管理者专用入口及文本编辑控件。现有 `custom_prompt` 随配置版本保存。工作区文件另有 [HEARTBEAT.md 读取](../../../../apps/im-server/src/control-routes.ts#L448)先核实管理归属、再由节点访问的接线。

### 既有约束

依据 [现行 Agent 契约](../../../specs/gateway/agent-capabilities.md)和 [Context 规范](../../../development/agent-context-engineering.md)，来源资格、当轮纠正、任务状态、普通工具授权和文件保存回执继续由各自机制决定。正式记忆仍由 Dreaming 写入。普通 child 职责与 fork 的父前缀复用保持现有契约。

### 可复用能力

复用文档记忆的可信工作区解析、产品根会话绑定、文件工具、请求动态上下文，以及 Dreaming 既有预算和恢复、只读来源回查、暂存读取核对、路径检查、文件版本冲突处理和保存回执。角色文件是该工作区的单份独立数据。

### 相关历史

[feat-676](../feat-676-role-memory-dreaming/spec.md)明确了两类材料、唯一记忆写者、当前主题与历史分层。禅和 PA 的检查样本及证据限制见[首文档](spec.md#本轮调查依据与限制)。

## 架构总览

管理者在 Agent 配置页直接维护 `.nanoassistant/ROLE.md`，主 Agent 也能在对话确认后维护同一文件。主会话装配读取它以开展工作，Dreaming 整合在每批启动时读取它以选择和组织知识。两阶段输入及记忆文件暂存校验沿用既有接线，正式库 Git 提交由整合会话显式发起。

## 关键决策

### 1. 借鉴 OpenClaw 的主动开场和落盘顺序

[OpenClaw BOOTSTRAP.md 第 14 行起](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/docs/reference/templates/BOOTSTRAP.md#L14)先自然对话、用户难以回答时提供建议，了解之后更新身份文件，完成后撤下引导。其[实际路由](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/src/agents/pi-embedded-runner/run/attempt-bootstrap-routing.ts#L36)区分待引导的输入。Nano 沿用主动发起、对话后落盘的写法，并允许普通任务照常进行。Nano 自己的规则是先提出拟写入文本、获得明确同意后再写入。对现有 Agent 同样适用。未确认期间保留占位提示，在之后合适的真人交互中继续主动问，当前任务照常执行。PA 使用现有身份绑定，仅询问其长期帮助目标、职责和有实际需要的分工。独立 Agent 对齐职责、长期目标及相关服务对象与协作边界。

角色约定为简短 Markdown，按职责适用性记录，建议整份不超过 2,000 UTF-16 code units。主 Agent 提议时压缩措辞并请用户确认。主 Agent 装配请求时发现角色文件超限或读取失败，当轮先尝试读取指定文件，再向有权维护的用户私下说明检查结果和修复办法。超限且读得到原文时，主 Agent 提出保留原意的精简稿，和维护者核对，获得明确确认后保存并回读。只有已确认的空态触发角色澄清。Dreaming 用系统角色定义和已有 Persona 继续。配置 Persona 可补充背景，已确认文件提供当前用户约定，冲突的职责含义由主 Agent 与用户厘清。配置和宿主权限保有其各自效力。

#### 配置页直接编辑同一份角色文件

Web 和原生 iOS 的现有 Agent 配置页在“自定义指令”附近提供独立的“角色约定”文本编辑项，沿用各端现有表单。说明只需能区分长期职责与一般行为指令，以及何时生效。使用“保存角色约定”就地提交，和整页配置各有自己的草稿及保存结果。真人管理者主动保存即为确认。未设置时显示可填写的空态，保存空白回到主 Agent 的主动澄清状态，宿主占位提示只在运行侧使用。使用同一 2,000 UTF-16 code units 上限，超限给出提示并保留草稿。该入口沿用现有信息层级和编辑控件，设计期无需另做原型。

### 2. 沿用 Codex 从保真材料中提炼可复用知识的判断

[Codex stage one](../feat-676-role-memory-dreaming/input/codex-memory-v2-8fdf647295/stage_one_system_v2.md)已是当前提炼的来源，保留其现有输入与输出。[Codex consolidation 的开头及检索提示规则](../feat-676-role-memory-dreaming/input/codex-memory-v2-8fdf647295/consolidation_v2.md#L8)以未来会做相关但不同的事来衡量信息价值，保留适用范围与原始指向，并压缩价值下降的条目。把现有整合 prompt 中关于完整任务脉络的措辞收窄：材料负责保真，主题页写给以后会用到知识的 Agent，留下有助于判断与行动的结论、条件、例外和来源；历史页只保留可解释结果、变化或复查依据的关键节点，利用已有摘要或原始记录定位详细经过。单次明确规则仍可在其原范围保留。用职责选择价值，证据仍来自现有来源链。

### 3. 借鉴 memoryrepo，把更新和清理都写成 Dreaming 的职责

采用 [memoryrepo 的 dreamInstructions](https://github.com/supermemoryai/memoryrepo/blob/54f7ff3065df8af687dc5c04a4bb17d6611e5fd1/src/server/memory.ts#L68)及 [CONVENTIONS](https://github.com/supermemoryai/memoryrepo/blob/54f7ff3065df8af687dc5c04a4bb17d6611e5fd1/src/server/memory.ts#L41)中实际对应的写法：

- 先读当前首页并搜索相关页面，再决定归入哪里。更新已有主题，合并重复内容，改写已变化的现行认识，删掉已失效的条目，修正相关链接。遇到冲突先回查原证据，按作者、范围、时间与证据质量区分并存条件和真正的更正。
- 告诉 Dreaming 首页正文会在日常请求中直接进入模型上下文，按“还不知道下一件任务时，Agent 是否就需要知道”选择事实，给主题详情留下语义清楚的相对链接。沿用模型自行判断的内容选择和现有物理装配上限。压缩膨胀首页时先把仍有用的细节和来源移入主题页。
- 改动聚焦本批可判定的内容。有更新时正文先于首页保存。首页仍准确就保留原文。沿用现有 Markdown 相对链接、普通文件编辑和宿主应用计划。优先就地重写主要页面。跨页移动时，沿用 [Anthropic Organizer 先写目标、再收缩原页的写法](https://github.com/anthropics/claude-cookbooks/blob/ce8b2629efe8b24048b127b4c79af1e9cbab93d4/managed_agents/example_data/memory_distill/prompts/organizer_system.md#L17)。Nano 用正式库作为已保存依据：只有本轮从正式库完整读到主要页面已承接对应有效内容与来源，才在暂存中缩减原页或把它变成短链接。若承接内容只存在于本批暂存，原页保留这部分信息，下次相关批次可精简；本轮仍可改写主题现行认识、删除已明确失效条目、合并页内重复和维护首页。
- 用现有 `source_history` 或合格 IM 只读补查替代上游回查工具。依据现有边界处理删除请求与单轮例外。memoryrepo 的前台正式记忆写入和提交工具各自属于其项目结构。

以上为对应行为的参考源。Anthropic Cookbook 公开的 Analyzer/Organizer 用于对照其知识重组思路，Nano 的实现仍在同一个现有整合阶段。上游源码证实 prompt 写法和调用位置，Nano 的效果由隔离真实模型试验判断。

## 接口与数据流

1. **前台根请求。** 在文档记忆装配以当前 session 的产品绑定限定角色文件消费者，保持现有普通 child 的记忆入口。用既有工作区解析取 `.nanoassistant/ROLE.md`。首个实际绑定根请求以原生文件能力创建缺失的提示占位符，使用仅文件缺失才创建的语义，重复装配不得覆盖已确认内容。检查或预览没有绑定时不写盘。根会话规则使用 PA 已有的主人绑定，独立 Agent 使用本产品会话绑定的节点主人 `SessionBinding.ownerId`。在角色上下文给模型区分确认人所需的绑定身份。直接输入用可信真人来源的 `actorId`，Global 使用当前 Inbox 实际消息的作者和 target，Nano IM 的 `sender.id` 与绑定身份比对；PA 还须是 `is_owner` 且为发给 PA 的 participant 消息。其他渠道仅在现有来源能证实同一身份时采用，不从显示名、外部镜像或观察上下文猜测身份。只在适合与确认人交流时主动询问。
   Global 复用[跨聊天提议与简短回复的契约](../../../specs/gateway/global-agent.md#scenario-多聊天提议与简短回复)，以实际发送成功的提议和同一实际聊天中确认人的明确回复匹配拟写入的文本；直接会话以真实对话的先后和回复内容匹配。引用、历史片段、草稿和其他 Agent 的提议不能替代当次确认。角色更新走当前可用且有权限的普通读写工具。写入工具不可用、拒绝或保存失败时明确报告未保存，现行约定仍以实际文件为准。确认条件只写入 prompt，权限沿用已有工具路径。
2. **前台更新与恢复。** 每个根请求在动态上下文显示当前文件内容、路径和占位状态，确认后同一聊天下一请求及其他根会话读取新值。文件读取错误要能区分未初始化与不可读，不替用户推断角色。角色是用户约定的数据，文件正文与宿主角色维护规则分开装配。保留 fork 原生前缀的继承规则，在根角色指导中限定只有主 Agent 对真实用户执行询问和修改；普通 child 和隔离维护子会话不装配这段指导。
   主 Agent 加载首页时复用 8,000 个 UTF-16 码元上限。超限时以 Markdown 块或列表项的完整结束位置截取原文前缀，附省略提示和完整路径。Dreaming 的首页输入及保存判定沿用原逻辑。
3. **后台整合。** 为每个整合批次调用主 Agent 的公开 systemPrompt 装配接口，复用实际生效的产品身份、Global 工作方式（含主 Agent/subagent 分工）及 PA 角色段落；同时从固定主体工作区读取已确认 ROLE 和有效配置 Persona。三类背景分开标注，在现有预算测量前提供给隔离整合请求。它们用于理解记忆所属 Agent 的未来工作与信息价值，不作为 Dreaming 自身的执行指令。不复制工具 schema、动态记忆快照或 Skills 目录。空白或占位只表明约定尚待澄清，历史对话不得替它转正。把快照作为实际整合输入的一部分，可通过现有 `history` 恢复；同批继续时使用该快照，新批重新取值。提炼请求仍聚焦任务事实。角色数据不加入来源目录、进度水位或维护写路径。
4. **应用。** 宿主比较暂存 Markdown 版本生成现有文件计划，移除“正文有变化就必须改首页”的条件。保留已存在文件的完整读取及资格核对，首页实际变化时沿用其最后应用顺序。复用装配阈值校验新写入首页，避免新产出退化为路径提示。老的超限首页仍可读取并在本轮有机会时缩小；正文计划不因该旧页仍超限而失败。文件版本冲突和来源资格检查沿用现有保护。跨正文迁移暂存阶段保留尚未保存到接收页的独有内容，因此接收页保存失败仍能从原页读取。
5. **人工编辑。** IM 提供固定 Agent 目标的 `GET/PUT /im/v1/agents/:agent_id/role`。复用管理配置的主人与空间校验、当前节点连接和绑定复核，以及 Node RPC 请求/回执，`no-store`，不把正文放进公开资料、配置 JSON、IM 离线快照或 `profile_version`。Node 使用同一份工作区归属判定后，将固定读写请求按 `agentId` 路由到对应 DSH 分区。已配置但尚未开启首个聊天也可使用；GET 只读，区分未设置、不可用和有内容。DSH 复用固定角色路径及文件能力，核对工作区与受信配置一致，拒绝路径越界。客户端不传路径。
   **工作区归属。** Node 的 `NodeConfiguration` 从整台节点实际配置和已准备的工作区查验目标 Agent 的文档记忆模式及 canonical workspace 归属。用 [现有跨配置路径比对](../../../../apps/node/src/configuration.ts#L170)的 realpath 规则，遇到多个 Agent 指向同一真实工作区则该角色文件不可用。无需目录删除见证，也无需等待建立会话。Node 配置 API 调用该判定。主 Agent 请求装配与 Dreaming 新批次取角色快照也通过现有分区校验的本机 stdio 请求，以可信 `agentId` 向 Node 读取同一判定，不在分区各自推断。判定失败时跳过角色文件的初始化、注入和更新指导，普通工作与现有文档记忆按各自契约继续。
6. **保存与采用。** 设置页提交 Markdown 和读取时的角色文件版本，DSH 使用同一文件系统的 `createIfAbsent` 或 `replaceIfVersion`。角色版本只绑定此 Agent 的工作区及该文件，写入成功后返回已保存内容与新版本。正常聊天写入沿用现有文件读取与更新语义，主 Agent 发现人工编辑已改变提议依据时先重新核对，需改变拟写内容时再次确认。版本冲突时只刷新并展示最新内容，保留草稿，由用户核对后主动决定；节点离线或读取失败时保留本页草稿及本页已确认的内容，恢复后先读取当前版本，超时也以重读为准。普通配置保存不覆盖角色文件。下一次主 Agent 请求和新开始的整合批次从现有装配读取已保存值，进行中的整合保留其已有角色快照。

### 整合 Agent 提交和宿主检查

1. 整合继续编辑现有暂存副本。每次整合 Agent 调用专用 `git_commit`，或正常结束时，宿主检查本次暂存差异、来源、读取证据和目标版本，并把验证过的 Markdown 保存到正式库。新首页仍受现有上下文上限约束。保存先于 Git 提交，相关文件保持真实保存回执。每次真实成功写入后更新该路径的已验证基线，即使同一批的其他路径保存失败也保留成功部分。同一会话收到状态反馈后再编辑同一页，按实际已保存版本校验。
2. `git_commit` 只在该整合 Agent 可用，带提交说明。在同一次工具调用内先完成上述发布，再针对正式库中已核对的记忆 Markdown 用真实 Git 暂存、提交。提交进入既有文档串行边界，核对当前来源代次、运行许可、取消信号、已验证的正式文件版本和实际 Git 路径。只暂存获准的正式 Markdown 路径，确认 index 范围后执行提交。普通宿主应用仅写文件，版本记录关联 Agent 发起的提交。提炼及主 Agent 的能力范围维持原有契约。没有工作区差异时无需空提交。
3. 有可见 Git 差异时，即使没有新来源也启动整合。每次整合正常结束后，宿主执行正式库的 `git status --porcelain --untracked-files=all` 检查。如仍有变更，将状态与文件路径作为宿主反馈交给同一个 native 整合会话，再等待它正常结束并重复检查。失败、取消、无法校验的文件状态或来源撤销不能登记成功。恢复新批次时检查实际工作区与来源，保留已保存的变更供该 Agent 处理，无需宿主代为提交或重放旧暂存计划。正式库干净且文件与来源检查通过后，记录提交与保存结果，随后推进本批来源。
4. 在已有检查链路内验证正式库既有脏文件会触发整理。对于当前机制无法处理的非记忆路径，将实际状态交给同一会话。若状态仍无法处理，返回阻塞并保留变更供人工检查。提交工具只处理正式库内的记忆 Markdown。维护工作区和角色文件均在正式库之外。

## 本次审查安排

| 必须回答的问题 | 能力与阶段 | 证据方法 |
|---|---|---|
| 角色在该出现的消费时点生效，前台与后台保持各自职责 | 设计与实施 Agent Context 审查 | 从产品绑定入口捕获实际 provider 请求，核对角色首次、确认后、同 Agent 另一聊天、普通 child/fork、整合与提炼、换窗恢复。用非绑定协作者、PA observer、另一聊天短回复以及角色文件工具关闭或失败作反例，检查前台与后续整合仍用原值。 |
| 管理者能从配置页独立编辑同一份角色约定 | 设计与实施配置体验、代码与 Agent Context 审查 | 从隔离 Web 配置真实读写并重开，验证 PA 与独立 Agent、未初始化、角色修改后主 Agent/Dreaming 采用、清空、普通配置互不保存、文件版本冲突和断线恢复。用真实 API 验证非管理者访问被拒，两个不同运行分区的 Agent 在均未打开首聊且实际配置指向同一工作区时，设置页和之后的主 Agent/Dreaming 均不串用角色。用隔离 iOS 模拟器验证独立保存后重开、普通保存不提交角色草稿、版本冲突重读时仍保留角色草稿；共享权限和后台采用证据沿用 Web、API 与 runtime。 |
| 正式仓 Git 提交与来源进度对应 | 实施及代码审查 | 从 native 整合实际执行观察多页同一 commit、一次遗漏提交后同一会话收到真实 status、再次编辑已发布的正文并补交、无新来源时检查已有 Git 差异、无变更直接成功、取消或未通过检查时进度保留。 |
| 提炼保真、整合可重组，首页对后续 Agent 仍可直接消费 | 独立设计审查、实施评测及代码审查 | 用同一脱敏样本与同一模型分别跑现行和新 prompt，含禅式长期协调经验与 PA 式个人目标/例外。比对真实读写、计划回执、合并后的证据链、首页装配，以及正文独立写入、无变化、接收页写入失败后原页仍可读。 |

## 契约层增量

[Gateway Agent capabilities 增量](specs/gateway/agent-capabilities.md)，归并目标为[现行 Agent capabilities](../../../specs/gateway/agent-capabilities.md)。

[IM Agent 配置增量](specs/im/agents-nodes.md)，归并目标为[现行 Agents 与 Nodes](../../../specs/im/agents-nodes.md)。

## 风险与回退

重组容易抹去适用范围。回查后合并，仍有独立依据的条件、例外与历史保留。角色约定可能与旧记忆和 Persona 矛盾，按来源和当前用户沟通处理，旧记忆不能自行成为新角色约定。回退版本后已有角色文件保留在原处，正式记忆继续使用已有 Markdown 格式和版本记录。

## 一次性部署迁移

无。既有工作区按需生成占位，现有文档在后续正常整合中按主题处理。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 Node/Gateway 与配套 IM | `./scripts/e2e-down.sh --wt "$REVIEW_WT"` | `./scripts/e2e-up.sh --profile daily --wt "$REVIEW_WT"` | 确认 readiness、测试 workspace、两个 Agent 的绑定及本地测试模型可请求 |

**Review 驱动方式** 从隔离 IM 分别与 PA、独立 Agent 发起对话，从 Web 设置验证角色编辑，用现有维护入口触发整合。捕获出站请求和文件回执，用定向 runtime 测试覆盖失败、恢复及写入边界。比对内容质量时使用脱敏样本或合成副本，记录模型、版本及两次输入。用 [iOS 工程的模拟器入口](../../../../src/IM/ios/README.md#模拟器测试)启动与同一隔离 IM 对接的原生客户端，验证局部保存与冲突恢复。

**验收前置** `REVIEW_WT` 指向本轮独占的绝对目录，按 [隔离环境文档](../../../development/worktree-runtime.md)检查测试模型凭据和工作区。已有 provider 捕获可复用时记录代码版本与证据位置。iOS 使用本机完整 Xcode 和隔离模拟器，审查阶段确认 Xcode 26.4.1 与 iOS 26.4 runtime 可用；模拟器目标指向本次隔离 IM。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-role-and-consolidation | 角色约定、同轮记忆重组与批次提交 | 无 | 串行 | `packages/dsh-integration/`、现有记忆指导资产、`apps/{node,im-server}/`、Web/iOS Agent 配置与相关测试 | [reviewer] 用户能经配置页直接修改角色，或在对话中补齐和确认角色约定，主 Agent 与 Dreaming 分别正确消费。配置页显示真实保存结果且保留冲突草稿。任务保真与长期提炼在对照样本中可分别观察，旧 Wiki 实际被重组，首页适合注入，必要时只更新正文。[worker] 保留实际请求/暂存/回执证据及同模型对照；覆盖 PA/专家、配置页权限与冲突、未确认与后续更新、普通 child/fork、恢复、预算、证据与应用边界、实际整批 Git 提交与同会话重试，保留 iOS 模拟器独立保存、重开和冲突保留草稿的操作证据。 |
