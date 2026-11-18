# feat-774 · Agent 协作范围与分级收件技术设计

对应 [已确认需求](spec.md)。一个端到端 M1 交付两个收件范围、两种工作模式、配置切换和存量迁移。

## Changelog

## 现状分析

**涉及范围。** IM 的普通发帖经 Messaging.enqueueRelays，其他入口还走 Gateway.relayMessage；RelayDelivery 重连前复查 relayEligible。PA 另有中心持久观察流、pa.source.admit 和节点 recoverPersonalObservations。飞书普通 Agent 从 ExternalChannels 直接进入产品，PA 飞书先镜像到 IM，再以中心观察事件为输入。Node 的 main.ts 是这些路径及配置生效的组装处。仅在 needsAttention 里改一个布尔值，挡不住已写 Inbox 的输入、命令或重复观察路径。

**既有约束。** IM 拥有会话成员、原发送者和授权来源，Channels 拥有平台事件解析；产品包拥有收件、期限和交付；DSH 仅由 dsh-integration 使用公开接口接入。协作范围约束新的聊天收件，聊天历史查询、已有工作、心跳、定时、任务的独立授权和工具权限各沿用原契约。源已撤销时沿用原有撤销处理。

**可复用能力。** InboxStore 已把原文、未读、通知快照和回执分开，GlobalAgent 的 inbox 系统 steer 可唤醒空闲根，也可合并到忙碌根的下一步。已有十分钟机制只扫描 PA observer，且使用 onlyIfIdle。SingleThread 的 group_background 按 Agent 和会话存储，takeGroup 转入可恢复 inputs，但当前缺少期限，高优走 followup。Web 与 iOS 都有现成的 Agent 设置选择器，选项与 Node 当前真实执行的两档并不一致。

**相关历史。** bugfix-687 明确观察来源和权限，bugfix-693 合并实际下一步的 Inbox 提醒，bugfix-732 引入可直接读取的会话摘要。延续原文与提醒分离、原生可恢复交付、按需读取；修改批次选择和背景到期时机。PA 入站审核的成本独立跟踪。[Issue #533](https://github.com/Mrchen116/nano-multiagent/issues/533)

## 架构总览与关键决策

1. **先判断能否收，再决定何时提醒。** product-contracts 导出同一个纯函数，输入为协作范围和各来源已核实的事实，返回 skip、high 或 background。坚持由来源解释身份与目标，IM 和节点复用判定，PA 不信任调用方自报主人。立即通知、阻塞发言前复核、允许执行命令是三个判断，不能共用一个 attention 位。观察主人可高优，但不会据此阻塞 PA 对外发送或授权执行命令。
2. **按已有模型上下文划定批次。** Global 和 PA 用一个根的 Inbox，single_thread 用同一 Agent 的单个聊天。共用分类、十分钟常量与截止规则，各自复用现有持久收件结构。现有工作模式选择保持独立；协作范围不创建新 Agent 模式。
3. **收紧设置是收件边界。** 用户已确认「停止递送积压」。设置生效时清退所有尚未交给模型、且在新范围外的输入。已经发出的模型请求继续完成，已进入先前请求的历史与真实聊天记录保留。切回团队后从新消息开始。编辑成功须晚于清退和生效确认。

## 接口与数据流

### 配置从创建到生效

统一公开字段 `collaboration_scope`，取 `team`、`owner_only`。新建省略时为 team；编辑省略沿用已存值；显式非法值拒绝。节点内映射为 collaborationScope。移除 group_reply_policy 的表单、API、共享 canonical/fingerprint、IM profile/seed、节点 YAML 和 live 配置、运行时 attention 配置及 PA 创建工具 schema。旧 NO_REPLY 配置和模型决定保持静默时输出的 NO_REPLY 文本是两个独立契约，保留后者。创建/编辑 Web、iOS、PA 首次创建、PA 代建及节点本地创建种子都走统一默认。PA 简化首次创建沿用默认，随后可在设置修改。设置沿用原选择器和保存反馈，字段标题「协作范围」，选项「团队协作」「仅限本人」，帮助文字说明谁的私聊可达；改选「仅限本人」时同时说明尚未递送的团队消息会跳过，切回后也不会补发；单会话/全局工作模式仍决定上下文边界。

沿用 agent_config_operations 的 profile_version、节点 configuration.prepare/persist/apply、状态恢复和 node.register 快照。新字段参与 canonical fingerprint。协作范围是节点当前收件配置，旧运行的模型配置 revision 不能使旧范围继续接收聊天。中心 queued/sent relay 的资格复查、配置待确认及断线重放须与节点一致；以每次收紧时持久的操作/版本边界识别旧工作，重新放开避免旧封包复活。其他配置项的修改不撤销有效批次。新库及新配置直接使用新数据模型；一次性历史转换见[部署提示词](deployment-prompt.md)。

### 身份事实与优先级

| 来源和条件 | 仅限本人 | 团队协作 |
|---|---|---|
| 创建者本人直接给 Agent 的一对一聊天 | high | high |
| 其他身份发给 Agent 的私聊 | skip | high |
| Agent 自己参与的群，结构化 @ 它、回复/引用它或明确提交给它的交互卡 | skip | high |
| PA 看到他人发给主人的私聊、@ 主人、回复/引用主人的消息（含 PA 与主人共同参与的群） | skip | high，标明发给主人 |
| 主人主动向他人发言，普通群动态，或仅作为可见背景的聊天 | skip | background |
| 不在当前来源权限内、PA 自身回声 | skip | 沿用原来源排除 |

- IM 在线普通发帖、卡片、Agent fan-out 和恢复共用从实际会话、成员、发送者及持久 reply_to/interaction_reply 派生的事实。真实 @ 使用会话内可解析目标 ID，区分 explicit mentions 与回复/卡片目标。PA 使用绑定的 owner_user_id；普通 Agent 用登录创建者的稳定用户身份（常规注册 user.id=owner_id；历史非同值按绑定真人查证）。同租户、同节点、显示名、代发身份及 owner 对其他 Agent 私聊的只读观察资格均不能证明消息是创建者亲自发给此 Agent。PA 旁观 direct 必须验证私聊另一端就是主人，不能以 sender 不是主人推导收件人。优先剔除自身回声与仅历史回填，再判断范围。共同群里同时命中 PA 与主人只计一条。
- PA observation enqueue/read 与 pa.source.admit 使用同一 message/sourceFacts 建立范围、参与关系、实际目标；保留 is_owner 的原有「谁发出」语义。以同一原消息 ID 合并 participant relay 和 observation，显式区分 addressed_to=agent/owner/both 与 delivery=participant/observer。普通非主人 participant 的输入审核仍在准入前走原流程。失败/重审恢复重新执行范围判断；被范围排除的观察事件结束消费，不能拖住后续事件。
- 飞书从 SDK 原事件保留实际 mention.open_id、parent_id、平台消息 ID，与该 app 的 Bot、已绑定 owner_open_id 比对。被引用作者由同一 app/chat 的已发送 outputs.platform_id、已收 inbound 的平台 ID 确定；本地没有时按真实 parent_id 读取平台原消息核实作者。取不到原作者时保留普通背景，其余明确的 @/私聊继续高优。原生飞书只收平台有权投递的消息。镜像写入的来源事实随认证 Gateway 写入，PA 的中心流和本地直接入口使用相同事实；Web 在影子会话真正输入时使用实际 Web 作者。history(contextOnly) 是补历史，不能自己发起高优或定时唤醒。team 沿用原渠道自动绑定。owner_only 须另有可核验的创建者声明：在现有、仅创建者可管理的飞书渠道配置中，允许显式登记本人在该 app 的 open_id；以经过认证的配置写入者、agent、app_id 和该 open_id 为一条身份对应。节点与 PA 中心通过现有 manifest 的管理配置使用同一值，换 app 即失效。provider_runtime.owner_open_id 是历史自动发现值（包括群内首次发言的同事），不能初始化这项声明，也不能通过团队模式切换或运行时 metadata 上报覆盖它。仅限本人且无声明时 Web 主人私聊照常可用，外部来源继续镜像，飞书私聊不进入 Agent。已有渠道管理页在需要私人飞书收件时提供这个身份字段，独立于两档协作选择。私人渠道的入站、PA sourceFacts/ownerConversation、回送目的地与主人特权判断统一使用声明。隔离验证同事先在群内自动绑定、随后收紧、未声明与声明创建者后双方分别私聊。
- 同步用户可见聊天与投给 Agent 要分开。过滤在创建目标 relay、观察和收件人的回执行之前；在节点 acceptRelay、controlText、飞书 reaction、group_background 与模型提交前同样生效。保留原群聊消息及其他合法收件人。中心过滤后的直聊存为正常聊天记录，不生成待回复占位；仅因范围不收的 Agent 不进入群已读分母。在途旧 relay 用节点可重试的明确 skipped 结果结清，IM 将目标投递记为 cancelled 并清理尚无送达证据的收件人，不伪造已送达/已读。命令先过范围，团队内 /stop、/new 及定向命令保持各自规则；系统任务上下文仍走既有专用投影，聊天副本不借任务事件重复触发。

### Global 与 PA 的合并提醒

1. 已准入的聊天消息立即入 Inbox，区分可唤醒的高优、计入期限的普通消息与只供主动读取的上下文。扩展现有 inbox 行和 background_wakes。以每条准入后的未通知记录及首个背景的本机准入时间定界；忙碌、后到、重启均不重置 deadline。审核可能乱序结束，不能用入库 seq 的单一最大值跳过尚未准入的旧行。
2. 高优到达或最早期限到达，进入同一个按 Agent 串行的 wake。事务冻结已准入、未读、当前有权的消息集合、摘要及稳定 inputId；原有 notification.seqs 与 summary 扩展为覆盖及恢复凭据。将首批「新且未通知」的行标成同一准备中批次，在 durable ACK 后记录该批已通知。ACK 丢失先 lookup 原 inputId；重启扫描准备中批次和到期记录。ACK 只防重复提醒；真正送达和读完正文继续分别依据模型有效响应与已摄取片段。高优与 timer 同时触发只拿同一批一次；新增行安排下一批。已主动完整读完的行不单独唤醒。
3. 统一向 native session 提交系统来源 channel=inbox、mode=steer，去掉 PA 到期分支的 onlyIfIdle。多个通知在 native 下一步前积累，沿用 pending inbox 合并，替代旧提醒的快照须覆盖仍有效的未读来源与回执映射。回执只推进最终真实出站请求覆盖的原消息，不能把仅排队或已撤销的条目算作送达。高优到来会带出此前普通消息；已通知仍未读的来源可随下一次真实提醒出现，但不会自行再启动同一批。禁用、删除、来源撤销、断线后恢复沿用现有生命周期和来源检查。

### 模型实际看到的内容

Consumer 为 Global/PA 主模型。沿用一条 Inbox 系统提醒、可直接读取的 target、按需 read/check。普通 Global 保留会话名称、类型、未读数、实际 @ Agent 数；PA 额外保留参与或旁观，以及本批有无直接找主人／Agent 的事实，避免把「有人找主人」误解为受托执行。每个来源增加 latest_message_at。取同一快照内有权且未读消息原始发送时间的最大有效瞬间；Web 取 IM 持久原消息时间；飞书从 SDK 原事件 create_time 严格提取正数毫秒值，独立保存可空的原始发送时间并贯穿 external.sqlite3、认证镜像、中心观察及 Inbox。external.ts 为展示补写的 Date.now() 不参与排序。旧飞书消息仅在 source_timestamp 或同一原平台事件保有可信时间时采用；不能区分补值则未知。每组至少一条有可信时间时取已知最大值；按 Agent 所属用户时区输出带偏移的 ISO 时间，无时区用 UTC。无可靠原始时间时用 null，不用抵达时间冒充。按时间降序，未知在末尾，同时间固定按 target。冻结后重试不漂移。inbox check 同样投影；通知排序不改变 read 的原消息顺序、触发优先级或十分钟的准入时钟。

下例省略固定系统前言。现状两行均无时间，目标版本的 PA 可直接比较两个聊天，也能看出「小林找主人」未 @ PA。字段值为模拟数据。

```json
{"sources":[
  {"target":"chat_b","name":"你 ↔ 小林","conversation_type":"direct","unread":2,"mentions":0,"delivery":"observer","addressed_to":"owner","latest_message_at":"2026-11-18T14:37:00+09:00"},
  {"target":"chat_a","name":"产品群","conversation_type":"group","unread":12,"mentions":1,"delivery":"participant","addressed_to":"agent","latest_message_at":"2026-11-18T14:32:00+09:00"}
]}
```

### SingleThread 按聊天交付

- 沿用 group_background，以 agent_id + 规范会话 ID 管理最早期限。外部聊天的影子别名归到同一聊天。首条普通消息入缓冲即可 ACK 传输；不创建空模型轮。计时器、重启扫描必须能发现尚未创建 session 的群。真实高优和到期都进同一个会话串行出口；同一事务把选中原消息、触发原因及稳定批次 ID 转入现有 inputs 的持久 handoff，再移出缓冲。保留原消息 ID 对应的去重、回执、图片、引用、真实作者和入口。高优前带出的范围仅限该会话。
- 使用一个原生提交承载该次交付，避免循环 inject 每条背景期间模型先行跨步。由 single-thread.ts 复用其现有逐消息内容构建器构造有边界、依时间标识原作者的上下文块，附件随原消息映射；高优触发时保留该条实际 sender/source/messageId 作当前输入，其余逐条标注为背景，审批上下文只把真实当前人类原话作为该输入的直接来源。纯到期批次以 nano-system 触发，正文逐条保留真实来源，不合成为主人指令。原消息追踪通过批次成员到同一 native inputId/turn 的映射完成，不伪造多个原生请求。lookup/恢复/投递/已读/更正复核依据该映射；idle 可启动，busy 用 steer 在下一步交付，保留控制信号、pending 权限和静默 NO_REPLY。外发的目标、触发源以实际高优触发者或到期批次最近的真实来源为准，同一 shadow 的 Web 原发与飞书原发仍可辨别；普通背景不会仅因到期而强制公开回复。

### 切换时停止积压

收紧成功是「下一次模型请求还能看见什么」的界线。沿用配置操作 ID，prepare 阶段按目标 Agent 暂停新的聊天提交与清退竞争，不阻塞无关 Agent；apply 时将新范围与取消旧积压的决定持久化。中心作废旧的待派 relay、尚未消费的观察消息事件；节点将超范围 Inbox/待审、group_background、未提交 inputs、准备中通知、旧控制及 external 待投的**聊天递送**置为终态。保留创作者私聊；含多来源的旧摘要重新投影，剩余部分用新 ID 交付。中心在配置落库事务中将此次收紧前遗留的目标任务标作终态；中心写入与节点保存之间在途的旧版本由有效配置版本及最近收紧边界拒收。再次开放只能接收此后产生的流量。投递完成标志需区分传输、模型送达、原文已读、范围取消。

DSH 已接受的输入与 Inbox 工具结果可能已写 native history，provider 尚未收到。锁定版本的 buildRequest 会冻结请求，llm/stream 的 next() 无参数。模型输入的改写落在公开 Session surface：dsh-integration 启动时通过 ctx.sessions.registerMessageProjection 注册本插件的撤销事件，沿用原生 image-offload 插件的注册/回放模式；按原 session 事件序号投影新的不可变消息，保留 message ID、角色、toolCallId 和可复原日志。产品负责裁定哪些原消息被取消，运行时只把这个已持久化决定映射到原生输入及工具结果。pre-step/inbox.remove 先撤掉尚未进入 surface 的候选。最终 llm/stream 仅放行或拒发整个冻结请求。

- **找到载体。** 按 sessionId 和输入 ID 登记 Global notice、单会话批次成员。Inbox read/check 按 toolCallId 登记已返回的来源、原消息及图片，复用 Inbox 的 frozen snapshot、reads 和 attachment source，给 check 保存同类来源清单。工具返回前登记，使并发工具结果也能撤销。输入取消和「已实际交给 provider」的证据持久化，独立于历史追加、工具完成和已读回执。
- **请求与配置成功定序。** 每 Agent 在最终放行入口与配置 apply 之间设读写边界。收紧先关闭新放行。已获得旧范围放行权并调用 adapter 的请求，让其完成交接，等首次可证明 provider 已接收的响应数据或请求终止，再报告配置生效；本地流开始标记不足为证。无需等待整个 Agent 轮次或正在执行的工具完成。还在 prepareRequest、工具返回与下步之间或尚未取得放行权的请求，按新范围投影后再发。已真实发出的请求正常完成。如果交接时崩溃且证据不足，按未交付处理，先恢复收紧操作。
- **投影与原生重建。** 收紧时以及每次最终放行前，根据真实未交付成员检查本次 request 与当前 session surface。即使 user/message 在 apply 后才从旧 decision.messages 追加，也会在此命中。对每条需要撤回的新载体按序号 append 一次带稳定身份的原生 projection 事件并 flush；重启恢复先重放投影再允许发请求。纯投影解释器以事件里的允许成员和原始消息为输入，对混合批次、check 摘要及 read 的文本和图片分别保留仍允许的块；全撤的 user 消息变为中性占位，工具结果保留同一 toolCallId 的空结果。投影不修改原始审计事件；替代后的摘要与回执冻结集合对齐，不把旧范围里的消息推进为送达。
- **已冻结的旧请求不调用 next()。** 即便 surface 已刷新，正在 waterfall 里的旧对象仍不可发送。若另有合法工作，listener 给该本地 attempt 返回带专用原因的 error finish，不产生 provider 调用；同一 Agent 的 agent/request-error 钩子优先识别该原因，在投影已持久化且原步骤有可继续工作时返回公开的 {kind:'retry'}。锁定的原生 loop 回到 prepareRequest/buildRequest，使用 session 的最新 surface，firstAttempt=false 不重复 append 用户输入或执行工具。以已应用投影代次与实际请求成员校验重建结果，通过才执行正常 next()；同一未修复状态不反复 retry。普通模型错误走原处理。若本轮唯一触发原因已撤销，使用现有会话取消和静默收尾，节点不发布错误气泡。先于 apply 已获放行的旧请求按上段交接顺序结算。
- **证据与恢复。** product 的已取消 inputId/toolCallId 记录、native surface 已应用事件和真实 provider 交付证据分别持久化；切回 team 不删除取消记录。恢复以原事件/操作 ID 查重。llm/stream 调用 next() 前核对当前允许成员和摘要映射；仅对真实请求的有效响应推进相应收件回执，本地重建的 error finish 不触发回执、耗量、provider fallback 或对外失败。合法主人私聊与独立任务继续；申请历史查询仍走既有来源权限。
- **精确验收窗口。** 在 pre-step 通过而 prepareRequest 尚未结束时挂起；另一次让 Inbox read/check 已返回带图片的团队或混合来源但下步尚未发出。在两个窗口分别保存、重启、切回，核对后续实际 provider body（含工具结果及附件）、无关工作和请求计数。让另一请求由 provider 接收且响应未完成，检查它正常结束。无交接证据的请求不得与收紧成功并行放行。

## 本次审查安排

| 问题 | 阶段和方法 | 可复用定位 |
|---|---|---|
| 谁有权进入、何时只提醒一次、实际请求长什么样 | 设计及实现做 Context 审查；真实组装入口录制隔离 provider 请求，配合有门控的忙碌工具和可控时钟。分别标记模拟 provider、真实传输和产品界面证据。 | packages/personal-assistant/tests/{personal-attention,inbox,global-agent,single-thread}.test.ts，packages/dsh-integration/tests/inbox-delivery.test.ts |
| 两入口配置信息有没有丢失，用户能否据此选对收件范围 | Web/iOS 原有表单各走创建、保存、重开；PA 首次与代建检查默认。受限用户与群成员走真实 IM，不从 HTTP 成功推断模型收到了。 | src/IM/frontend/src/features/settings/agents、src/IM/ios/NanoIM/Features/Agents，tests/e2e/critical_paths |
| 是否减少逐条提示，期限、重投和切换是否兑现 | 对固定的连续 20 条低优+1 条高优计数聊天触发的请求及模型实际可见通知，区分独立审核和正在运行的其他请求。重复覆盖同刻 timer/高优、断连 ACK、恢复、源撤销、乱序准入、混合摘要清退与切回。 | 原始请求、Inbox/Work 对账和同一消息的回执 |
| 迁移是否保留原数据并可恢复 | 设计审查和隔离旧库/配置副本演练，含不完整迁移与重试。 | 本 unit 的 deployment-prompt.md |

## 契约层增量

[IM 配置](specs/im/agents-nodes.md)、[会话回执](specs/im/conversations-messages.md)、[PA 消息](specs/im/personal-agent.md) 分别拥有配置接口、分母与 PA 观察说明。[Gateway 路由](specs/gateway/routing-delivery.md) 定义单会话交付与命令边界，[Global](specs/gateway/global-agent.md) 定义摘要与批次，[PA](specs/gateway/personal-agent.md) 定义主人优先级和来源，[外部渠道](specs/gateway/external-channels.md) 定义平台身份及镜像，[配置快照](specs/gateway/service-lifecycle.md) 对齐公开字段。current 在实现验收后归并。

## 风险、回退与一次性部署迁移

切换时最容易漏掉的两处为中心持久重投和已经进入原生下一步队列的输入；二者须在隔离环境用真实请求取证。飞书的私聊 owner 与群引用按平台身份核实，普通群消息可用性受 Bot 实际订阅权限约束。迁移以目标版本、备份和旧配置操作状态为前提；恢复时配套恢复旧二进制和数据。[部署提示词](deployment-prompt.md)

## Runbook for Reviewer

| 服务 | 停止 | 启动 | 可用判据 |
|---|---|---|---|
| 隔离 IM、Node、DSH 子进程及 Web | `./scripts/e2e-down.sh` | 实施 worktree 内 `./scripts/e2e-up.sh --profile daily` | 加载本 worktree 的 .e2e-ports.env，GET 本地 IM_PORT 的 /health，管理页显示本轮节点在线 |
| 真实飞书通道专项 | 同上 | 上一栈退出后 `./scripts/e2e-up.sh --feishu` | 专用 E2E Bot 绑定在线，具备群普通消息投递和被引消息读取能力，使用同一测试群及主人/非主人账号 |

使用 daily 的隔离 P/E/Q 和 PA、两个群、一个 single_thread；按需通过真实创建入口补齐身份。iOS 使用模拟器接入同一隔离 IM。请求证据先用本机 dev_host 的 llm_logs 定位，或使用隔离可记录请求的 provider；不提交真实用户文本。受控时钟覆盖精确截止点，真实栈至少一组无后续触发的到期旅程及跨聊天高优旅程。飞书使用专用凭据与 listener，缺少外部资源时明确记录实际覆盖，SDK 事件夹具只证明传输适配。部署仅做迁移所需读写及有限只读核对。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 实现并验证两档协作范围 | 无 | 单组 | apps/im-server、apps/node、packages/{product-contracts,channels,personal-assistant,dsh-integration}、Web/iOS 设置、测试及随包配置 | **[reviewer]** 两端默认 team 并能切换；私密范围只达创建者，积压清退；团队私聊、@、引用、卡片、PA 旁观、跨群或同群批次、到期忙闲、最新时间均有与 spec 场景对应的真实入口和模型可见证据。**[worker]** 身份矩阵、无跨会话原文、实际定时和切换竞态、ACK/重启去重、pre-step 后与工具结果窗口、飞书自动绑定与创建者不同、缺失或无效的原始时间经镜像为 null、快照时间及回执、配置持久化、隔离迁移/重试/恢复通过；检查发言前复核、系统任务与专用命令，跑窄测试、TS 构建和运行时依赖契约。 |
