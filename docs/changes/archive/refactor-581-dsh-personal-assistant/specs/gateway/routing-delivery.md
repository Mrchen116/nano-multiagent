# gateway/routing-delivery Specification (delta for refactor-581)

## MODIFIED Requirements

### Requirement: PA 为每条真人消息固定模型侧发生时间与实际入口

Gateway 对来自内置 Web IM 或外部 Channel 的真人消息，在不改变用户可见正文的前提下，为送入 Agent 的每条新 user message 固定一个稀疏 context envelope。时间优先采用 Channel 提供的消息发生时间；来源没有合法时间时，采用 Gateway 同步接受该消息时一次固定的接收时间；两者都按 Gateway 启动时确定的 PA 本地时区呈现。入口按该条消息实际经过的 Channel 标为 `Web IM` 或 `Feishu`，不从共享 shadow conversation 推断，也不附加 Direct/Group、Bot ID、chat ID、host 或 IP。

同一消息在 group buffer、normal submit、active steer、retry 和 history replay 中复用同一个固定 envelope；本 requirement 不改变 active steer 的接受、消费、持久化、失败处理或恢复语义。群聊继续保留既有 `[sender]`；模型侧新增 context 不写入 IM message body，也不进入 PA workspace 中供用户查看的简化聊天副本。PA 顶层会话的 system prompt 只保留稳定 timezone，不再把 session 创建时刻称为当前时间；动态时间只随新真人 user message 追加。Heartbeat、cron、subagent 与内部通知不获得真人消息 envelope；没有选择该行为的 Coding CLI 保持既有 prompt/message semantics。

#### Scenario: 长会话中的新消息各自保留发生时间
- **GIVEN** 用户在同一 PA 会话的不同时间先后发送两条真人消息
- **WHEN** 后一条消息进入 Agent context
- **THEN** 两条消息各自携带固定的发生时间，Agent 可判断先后与时段
- **AND** system prompt 不把会话创建时刻继续表述为当前时间

#### Scenario: 来源时间优先且缺失时固定 Gateway 接收时间
- **GIVEN** 一条消息带有合法 Channel occurrence time，另一条没有合法来源时间
- **WHEN** Gateway 为两条消息建立 model context
- **THEN** 第一条采用 Channel occurrence time，第二条采用各自进入 Gateway 时一次固定的 receipt time
- **AND** 后续 buffer、retry 或 replay 不重新读取当前时钟

#### Scenario: 飞书历史补拉沿用消息原发生时间
- **GIVEN** Gateway 在一条飞书群触发消息前通过 provider history API 补拉到先前漏收的真人消息，且该历史消息带合法 create time
- **WHEN** 补拉消息进入 group buffer 并随触发消息提供给 Agent
- **THEN** 该消息采用 provider create time，而不是本次补拉或触发发生的时间

#### Scenario: 同一 shadow context 按逐消息实际入口标注
- **GIVEN** 飞书聊天与 Web IM shadow conversation 共享同一 DSH session
- **WHEN** 用户先从飞书发送消息，随后从 Web IM 继续
- **THEN** Agent 看到前一条来自 `Feishu`、后一条来自 `Web IM`
- **AND** 两条消息都不因 conversation 的外部来源属性而被标成同一入口

#### Scenario: 群聊延续 sender 语义但不重复 chat type
- **GIVEN** Web IM 或飞书群聊中有多名参与者发送消息
- **WHEN** buffered 与当前消息一起进入 Agent context
- **THEN** 每条新消息同时保留实际 Channel、固定时间与既有 `[sender]`
- **AND** envelope 不额外输出 Direct/Group 或内部 routing identity

#### Scenario: model envelope 不污染用户可见正文
- **WHEN** 用户在 Web IM、飞书或 shadow conversation 查看、复制或搜索消息
- **THEN** message body 仍是用户原文，不含模型侧 time/Channel prefix

#### Scenario: workspace 可读聊天副本保持既有正文语义
- **WHEN** PA 将一次真人 user input 写入 `.nanoassistant/chat_history/`
- **THEN** user content 不含新增 time/Channel envelope
- **AND** 群聊仍可保留变更前已有的 `[sender]` 投影

#### Scenario: 功能启用前的旧历史不补造 context
- **GIVEN** 既有 transcript 或 group buffer row 没有可靠 occurrence time/actual Channel marker
- **WHEN** 功能启用后继续原 conversation
- **THEN** 旧内容保持原样，不用当前时间或当前入口补 stamp
- **AND** 此后新收到的真人消息开始使用固定 envelope

#### Scenario: 非 PA 真人入口保持现状
- **WHEN** Coding CLI、heartbeat、cron、subagent 或内部通知继续产生消息
- **THEN** 它们不获得本 requirement 的 time/Channel envelope
- **AND** 退役 Coding CLI 不再参与消息处理；heartbeat、cron、subagent 与内部通知保留各自的可信 message source/time 格式

### Requirement: 入站消息按四步决策路由并回发原通道原目标

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。 Agent 身份解析与未知 Agent 拒绝适用于两种模式；global 的入站持久接受后交 Inbox，不预建等待主模型回复的聊天消息。

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待主模型返回和自动整理上下文三类“活着但安静”的窗口都有周期性 liveness 心跳，看门狗不再以“无业务输出事件”判卡死；等待用户权限决策同样依赖持续 liveness。只有判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾；`permission_resolved` 是审批结束事件，不是运行失活。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行, 最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话串行、跨会话并行
- **GIVEN** 同一会话已有一轮在执行,另有一条属于不同会话的消息同时到达
- **WHEN** 两条消息先后进入 Gateway
- **THEN** 同一会话的消息排进串行 FIFO 队列、前一轮结束后才消费下一条;不同会话的消息并行推进,互不阻塞

#### Scenario: 失去 liveness 后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行,但在判定窗口(120 秒)内既无业务事件也无任何 liveness 心跳,后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败,随后消费后一条消息,不得让该会话永久阻塞

#### Scenario: 执行静默长命令期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在执行一个耗时远超判定窗口、其间无标准输出的命令
- **WHEN** 命令持续在执行(有周期性 liveness 心跳)
- **THEN** 该轮不被看门狗取消,命令跑完结果正常返回

#### Scenario: 等待 LLM 返回期间不被 idle 看门狗误杀
- **GIVEN** 某轮长时间等待 LLM 返回但连接活着(有周期性 liveness 心跳)
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被看门狗误判卡死

#### Scenario: 自动整理上下文期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在自动整理过长上下文且摘要仍正常推进（有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** Gateway 不把该轮误判为 idle 超时
- **AND** 该轮后续普通消息连同已有上下文照常进入对话并得到正常回复

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀
- **GIVEN** 某轮已发起一个需要授权的工具,正等待用户在权限卡片上决策
- **WHEN** 用户离开或关闭页面，但运行时仍持续发出该轮的 liveness 心跳
- **THEN** 该轮不被 idle 看门狗取消；用户随后批准则工具正常执行
- **AND** 审批等待与其他执行阶段使用同一 liveness 判据；运行时死亡、断连或心跳停止仍会超时，不因一张旧权限卡永久免检

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(返回明确错误),不创建会话也不执行

#### Scenario: 同群跨账号输入保持真实身份
- **GIVEN** 不同账号与该 Gateway 的 Agent 共同参与一个 IM 群
- **WHEN** 群内不同的人按既有规则向该 Agent 发消息或插话
- **THEN** 消息保留实际发送者，按同一聊天和 Agent 执行上下文处理，回复回到该群；不会因发送者不是 Gateway 管理者而另建会话或忽略输入。

### Requirement: Gateway 为已接收的普通消息维持可见恢复交付

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。 global 未摄取正文留在持久 Inbox，恢复其信号与主上下文，不创建按原聊天自动投递的恢复 batch。

Gateway 在非用户终态前已接受、但尚未进入模型上下文的普通消息，必须在 执行运行时给出可验证的恢复 batch 后继续由原聊天交付；恢复的最终文本一次发送，已接受消息各自只收到一次 terminal delivery status。

#### Scenario: 真中断前已接收的插话由同一聊天继续交付
- **GIVEN** Agent 的当前 run 确实因非用户原因终止，且 Gateway 已接受一条尚未进入模型上下文的普通消息
- **WHEN** 执行运行时创建并结算该消息的关联恢复 batch
- **THEN** Gateway 在原聊天接收恢复 run 的结果并一次完成该普通消息
- **AND** 用户不必重发，也不会收到超时或重复回复

#### Scenario: 无法验证或无法创建恢复 batch 时明确收口
- **GIVEN** Gateway 正在等待已接受普通消息的恢复 batch
- **WHEN** 执行运行时明确结算为无 successor/无法恢复，或后继 descriptor 与已接受消息不匹配
- **THEN** Gateway 只将尚未恢复的消息收口为失败并释放会话
- **AND** 不把无关 run 的输出投到原聊天，也不无限等待

#### Scenario: 显式控制命令不进入恢复
- **GIVEN** 某会话有活动 run 或正在等待恢复的已接受普通消息
- **WHEN** 用户发送精确 `/stop` 或精确 `/new`
- **THEN** Gateway 分别保持既有停止或重开语义，并抑制已知恢复 run 的可见输出
- **AND** 其他自然语言文本仍按普通消息处理，不触发停止或重开

### Requirement: 群聊只在被 @提及 / 回复 Agent / 明确的全群控制命令时触发 Agent

MENTION/ALWAYS 和命令实际触达范围适用于两种模式。以下群 buffer 自动带入、按群创建 Session、普通正文/过程气泡和 `/new` 重开的 Scenario 适用于 `single_thread`；global 将可见更新存入 Inbox，仅有效实时触发推进唤醒，不自动摄取正文；命中的 global Agent 对 `/new` 在原聊天明确答复不支持。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。

群聊流量在分配任何内核会话或队列槽**之前**先过 @提及门控。未被点名的群聊消息不触发 Agent 执行;Agent 判断无需回复时输出约定 token(`NO_REPLY`)则不向用户发言。门控策略由各 Agent 的 `group_reply_policy`决定(默认 `MENTION`;`ALWAYS` 则有消息即回)。裸 `/stop` 与内置 Web IM 群聊中的精确裸 `/new` 不受 MENTION 门控：前者只中断正在运行的 Agent，后者为群内每个 Agent 重开各自的共同会话。`/compact`、`/compact <关注点>` 和 `/effort <level>` 仍必须以 mention 或 reply 明确指向 Agent，且不因该 Agent 或其他 Agent 的 `ALWAYS` 策略扩大成群组控制。

#### Scenario: 群聊未被 @提及的消息不触发 Agent
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 群里来了一条既未 @该 Agent、也非回复该 Agent、也非裸 `/stop` 的消息
- **THEN** 不创建内核会话、不发起运行;该消息仅作为后台上下文缓冲到该 Agent 自己的群上下文 buffer, 待该 Agent 下次被点名时随当轮一并带入

#### Scenario: 群聊被 @提及触发并把上下文带入当轮
- **GIVEN** 该 Agent 的群上下文 buffer 里已缓冲了若干条未点名消息
- **WHEN** 群里来了一条 @该 Agent 的消息
- **THEN** Gateway 创建/复用该群会话,把缓冲的消息(各带 `[sender]` 前缀)与当前消息一并提交给内核执行

#### Scenario: 群聊 Agent 输出 NO_REPLY 时不发言
- **WHEN** 群聊一轮运行的最终回复文本为 `NO_REPLY`
- **THEN** Gateway 不把 token 作为正文 delta 投递;若该轮已有用于 running/工具过程的 provisional 气泡则在终态回滚,最终不留下消息行、列表摘要、未读数或桌面通知

#### Scenario: 群聊 Agent 互相 @ 的 fan-out 回复输出 NO_REPLY 时不发言
- **GIVEN** 群聊里 Agent A 的回复 @ 了 Agent B,把 B 拉起(agent-to-agent fan-out),或某 Agent 的后台任务在群聊会话产生回复
- **WHEN** 被拉起的 Agent 判断无需接话,输出 `NO_REPLY`(或心跳静默 token `HEARTBEAT_OK`)
- **THEN** Gateway 对该 fan-out / 后台投递同样抑制,用户在群里看不到 `NO_REPLY` 字面量,该消息也不落库
- **AND** 静默 token 不作为 Agent 发言继续 fan-out,其他 Agent 的群上下文 buffer / run 不得收到该 token

#### Scenario: Web IM 群聊裸 `/new` 为每个 Agent 重开会话
- **GIVEN** 一个 `group_reply_policy=MENTION` 的内置 Web IM 多 Agent 群聊
- **WHEN** 用户发送精确的裸 `/new`
- **THEN** Gateway 为群内每个 Agent 分别切换到新的 DSH session，并在同一群显示各 Agent 的控制确认
- **AND** 后续面向每个 Agent 的普通消息不携带该 Agent 先前的群会话上下文

#### Scenario: 群聊压缩仍需明确目标
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 用户发送未 @该 Agent、也非回复该 Agent 的 `/compact` 或 `/compact <关注点>`
- **THEN** Gateway 不压缩该 Agent 的群会话，也不发送控制确认
- **WHEN** 用户通过结构化 mention、文本 `@Agent` 或回复该 Agent 发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Gateway 只在被指向 Agent 的群会话上执行命令，并在同一群返回控制确认

#### Scenario: 群聊推理档位始终需要明确目标
- **GIVEN** 群内一个或多个 Agent 的 `group_reply_policy=ALWAYS`
- **WHEN** 用户发送指向 Agent A 的 `/effort <level>`，Gateway 向参与者 fan-out relay
- **THEN** 只有 Agent A 处理该命令；其他 Agent 不创建会话、不改写 session effort，也不把命令交给模型

### Requirement: 用户可用文本命令切换当前 Agent 会话

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。 命令路由与入站幂等仍通用；global 的 `/new` 拒绝不重置主上下文。

Gateway 在已路由的 direct chat，或明确指向 Agent 的 group chat 中，把精确的 `/new` 作为当前 Gateway session 的新会话命令。命令确认留在原聊天，既有可见历史不删除；后续普通消息使用新的 DSH session。若原 session 正在执行，Gateway 先撤销并收敛旧 run 的所有尚未完成用户可见输出，再中断它；已排队但尚未提交的旧输入不能在新会话执行，旧 run 的 stream、final reply 或 external mirror 也不得在新会话确认之后抵达。`/new` 之外带有额外文本的 slash 消息按普通用户消息处理。

#### Scenario: `/new` 保留可见历史并切换后续上下文
- **GIVEN** 用户与某 Agent 已在一个 direct chat 中进行多轮对话
- **WHEN** 用户发送精确的 `/new`
- **THEN** 原聊天显示开始新会话的确认，既有可见消息仍可阅读
- **AND** 后续普通消息由新的 DSH session 处理，不携带旧会话上下文

#### Scenario: 运行中开始新会话
- **GIVEN** 当前 Gateway session 有正在执行或已接受但尚未提交的用户工作
- **WHEN** 用户发送 `/new`
- **THEN** Gateway 中断已执行的旧 run，丢弃未提交的旧输入，并确认旧操作已停止且新会话已就绪
- **AND** 不再向该聊天投递旧 run 的 stream、final reply 或 external mirror，也不把旧输入提交到新 DSH session
- **AND** 若旧 run 已有 provisional bubble，Gateway 在新会话确认前将其以无正文的终态关闭或丢弃

#### Scenario: 重放同一入站 `/new` 不重复切换会话
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/new`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的新会话结果和控制确认
- **AND** 不创建第二个 DSH session，也不因第二次切换丢弃第一次切换后的用户输入

#### Scenario: 新会话发布失败不吞掉旧 run 输出
- **GIVEN** 当前 Gateway session 的 old run 已产生一条尚未投递的 stream、terminal reply 或 external mirror
- **AND** 用户发送 `/new` 后，Gateway 已临时暂停该 old run 的可见输出
- **WHEN** 新 DSH session 无法持久发布为当前 binding
- **THEN** Gateway 保持原 binding 与后续上下文，不发送“已开始新会话”确认
- **AND** 暂挂的 old run output 以原 identity 恰好一次恢复投递，old run 后续输出仍可见

### Requirement: 用户可安全地手动压缩当前 Agent 会话

以下按聊天寻址及 `/new` 切换的 Scenario 适用于 `single_thread`；global 将相同 focus、幂等、FIFO 预留、失败不改上下文和来源反馈作用于主 Session。消息被读入/提交的执行不得越过压缩预留边界，接收 Inbox 本身不被阻塞。全局模式对应行为以 [global-agent](../../../../../specs/gateway/global-agent.md) 为准。

Gateway 在已路由的聊天中把精确的 `/compact` 和 `/compact <关注点>` 作为当前 DSH session 的手动压缩命令。非空关注点仅指导这次摘要保留重点；它不作为普通用户 turn 写入会话。无论当前 session 是否有 active 或 queued work，Gateway 都接受该命令并立即预留其 FIFO 位置：在此前工作完成后执行压缩，且后续普通消息不得越过该压缩边界。若 `/new` 在已排队的压缩执行前切换会话，Gateway 不在新会话上执行该旧压缩，并在同一聊天说明其未执行。Gateway 在同一聊天明确区分成功、无需压缩、未执行和失败；失败不得改变调用前上下文。其他 slash 文本按普通用户消息处理。

#### Scenario: 空闲会话按关注点压缩
- **GIVEN** 当前聊天已有可压缩的历史，其中含认证方案和未完成事项
- **WHEN** 用户发送 `/compact 保留认证方案与未完成项`
- **THEN** Gateway 在原聊天确认已按该关注点压缩
- **AND** 随后的 Agent run 可从压缩摘要延续认证方案和未完成事项，关注点本身不成为一条普通 user message

#### Scenario: 当前没有可压缩会话
- **GIVEN** Gateway 尚未为当前聊天建立 DSH session，或已有 session 但没有新的可压缩历史
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 在原聊天说明无需压缩
- **AND** 不为该 no-op 创建空 DSH session，也不改变已有会话上下文

#### Scenario: 忙碌时压缩排队并成为后续消息的 FIFO 屏障
- **GIVEN** 当前 session 有 active 或 queued run
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 接受该命令并预留 FIFO 位置，待此前工作完成后在该 session 上执行压缩
- **AND** 该命令之后到达的普通消息在压缩完成后才执行，不得越过压缩边界
- **GIVEN** 当前 session 空闲但手动压缩无法生成或持久提交摘要
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 报告压缩未完成，后续运行仍使用压缩前上下文

#### Scenario: `/new` 不执行先前排队的压缩
- **GIVEN** 当前 session 有尚未执行的 `/compact`
- **WHEN** 用户在该压缩执行前发送 `/new`
- **THEN** Gateway 切换到新 DSH session，且不在新会话或旧会话执行该先前排队的压缩
- **AND** Gateway 在原聊天说明该压缩请求未执行

#### Scenario: 重放同一入站压缩不产生第二个压缩边界
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/compact <关注点>`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的压缩结果和控制确认
- **AND** 当前 DSH session 不产生第二个 compaction record，关注点不作为重放 identity
