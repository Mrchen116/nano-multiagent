# gateway/routing-delivery Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。原有 Scenario 完整保留，作用域由各 Requirement 开头的模式限定确定。

## MODIFIED Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 Agent 身份解析与未知 Agent 拒绝适用于两种模式；global 的入站持久接受后交 Inbox，不预建等待主模型回复的聊天消息。

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待主模型返回和自动整理上下文三类“活着但安静”的窗口都有周期性 liveness 心跳，看门狗不再以“无业务输出事件”判卡死；等待用户权限决策的窗口则完全豁免于 idle 看门狗超时。只有该轮收到 `permission_resolved` 或判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

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
- **WHEN** 等待时长超过判定窗口(即使用户离开、关闭 IM 页面、其间没有 liveness 心跳到达)
- **THEN** 该轮不被 idle 看门狗取消;用户随后批准则工具正常执行、该轮继续推进,不报「relay idle for 120s」
- **AND** 一旦用户做出决策、内核发出 `permission_resolved`,正常 idle 看门狗立即恢复,决策后的卡死/断连仍会被捕获

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(抛 `LookupError`),不创建会话也不执行

### Requirement: Gateway 为已接收的普通消息维持可见恢复交付

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 未摄取正文留在持久 Inbox，恢复其信号与主上下文，不创建按原聊天自动投递的恢复 batch。

Gateway 在非用户终态前已接受、但尚未进入模型上下文的普通消息，必须在 Kernel 给出可验证的恢复 batch 后继续由原聊天交付；恢复的最终文本一次发送，已接受消息各自只收到一次 terminal delivery status。

#### Scenario: 真中断前已接收的插话由同一聊天继续交付
- **GIVEN** Agent 的当前 run 确实因非用户原因终止，且 Gateway 已接受一条尚未进入模型上下文的普通消息
- **WHEN** Kernel 创建并结算该消息的关联恢复 batch
- **THEN** Gateway 在原聊天接收恢复 run 的结果并一次完成该普通消息
- **AND** 用户不必重发，也不会收到超时或重复回复

#### Scenario: 无法验证或无法创建恢复 batch 时明确收口
- **GIVEN** Gateway 正在等待已接受普通消息的恢复 batch
- **WHEN** Kernel 明确结算为无 successor/无法恢复，或后继 descriptor 与已接受消息不匹配
- **THEN** Gateway 只将尚未恢复的消息收口为失败并释放会话
- **AND** 不把无关 run 的输出投到原聊天，也不无限等待

#### Scenario: 显式控制命令不进入恢复
- **GIVEN** 某会话有活动 run 或正在等待恢复的已接受普通消息
- **WHEN** 用户发送精确 `/stop` 或精确 `/new`
- **THEN** Gateway 分别保持既有停止或重开语义，并抑制已知恢复 run 的可见输出
- **AND** 其他自然语言文本仍按普通消息处理，不触发停止或重开

### Requirement: 群聊只在被 @提及 / 回复 Agent / 明确的全群控制命令时触发 Agent

MENTION/ALWAYS 和命令实际触达范围适用于两种模式。以下群 buffer 自动带入、按群创建 Session、普通正文/过程气泡和 `/new` 重开的 Scenario 适用于 `single_thread`；global 将可见更新存入 Inbox，仅有效实时触发推进唤醒，不自动摄取正文；命中的 global Agent 对 `/new` 在原聊天明确答复不支持。全局模式对应行为以 [global-agent](global-agent.md) 为准。

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
- **THEN** Gateway 为群内每个 Agent 分别切换到新的 Kernel session，并在同一群显示各 Agent 的控制确认
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

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 命令路由与入站幂等仍通用；global 的 `/new` 拒绝不重置主上下文。

Gateway 在已路由的 direct chat，或明确指向 Agent 的 group chat 中，把精确的 `/new` 作为当前 Gateway session 的新会话命令。命令确认留在原聊天，既有可见历史不删除；后续普通消息使用新的 Kernel session。若原 session 正在执行，Gateway 先撤销并收敛旧 run 的所有尚未完成用户可见输出，再中断它；已排队但尚未提交的旧输入不能在新会话执行，旧 run 的 stream、final reply 或 external mirror 也不得在新会话确认之后抵达。`/new` 之外带有额外文本的 slash 消息按普通用户消息处理。

#### Scenario: `/new` 保留可见历史并切换后续上下文
- **GIVEN** 用户与某 Agent 已在一个 direct chat 中进行多轮对话
- **WHEN** 用户发送精确的 `/new`
- **THEN** 原聊天显示开始新会话的确认，既有可见消息仍可阅读
- **AND** 后续普通消息由新的 Kernel session 处理，不携带旧会话上下文

#### Scenario: 运行中开始新会话
- **GIVEN** 当前 Gateway session 有正在执行或已接受但尚未提交的用户工作
- **WHEN** 用户发送 `/new`
- **THEN** Gateway 中断已执行的旧 run，丢弃未提交的旧输入，并确认旧操作已停止且新会话已就绪
- **AND** 不再向该聊天投递旧 run 的 stream、final reply 或 external mirror，也不把旧输入提交到新 Kernel session
- **AND** 若旧 run 已有 provisional bubble，Gateway 在新会话确认前将其以无正文的终态关闭或丢弃

#### Scenario: 重放同一入站 `/new` 不重复切换会话
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/new`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的新会话结果和控制确认
- **AND** 不创建第二个 Kernel session，也不因第二次切换丢弃第一次切换后的用户输入

#### Scenario: 新会话发布失败不吞掉旧 run 输出
- **GIVEN** 当前 Gateway session 的 old run 已产生一条尚未投递的 stream、terminal reply 或 external mirror
- **AND** 用户发送 `/new` 后，Gateway 已临时暂停该 old run 的可见输出
- **WHEN** 新 Kernel session 无法持久发布为当前 binding
- **THEN** Gateway 保持原 binding 与后续上下文，不发送“已开始新会话”确认
- **AND** 暂挂的 old run output 以原 identity 恰好一次恢复投递，old run 后续输出仍可见

### Requirement: 用户可安全地手动压缩当前 Agent 会话

以下按聊天寻址及 `/new` 切换的 Scenario 适用于 `single_thread`；global 将相同 focus、幂等、FIFO 预留、失败不改上下文和来源反馈作用于主 Session。消息被读入/提交的执行不得越过压缩预留边界，接收 Inbox 本身不被阻塞。全局模式对应行为以 [global-agent](global-agent.md) 为准。

Gateway 在已路由的聊天中把精确的 `/compact` 和 `/compact <关注点>` 作为当前 Kernel session 的手动压缩命令。非空关注点仅指导这次摘要保留重点；它不作为普通用户 turn 写入会话。无论当前 session 是否有 active 或 queued work，Gateway 都接受该命令并立即预留其 FIFO 位置：在此前工作完成后执行压缩，且后续普通消息不得越过该压缩边界。若 `/new` 在已排队的压缩执行前切换会话，Gateway 不在新会话上执行该旧压缩，并在同一聊天说明其未执行。Gateway 在同一聊天明确区分成功、无需压缩、未执行和失败；失败不得改变调用前上下文。其他 slash 文本按普通用户消息处理。

#### Scenario: 空闲会话按关注点压缩
- **GIVEN** 当前聊天已有可压缩的历史，其中含认证方案和未完成事项
- **WHEN** 用户发送 `/compact 保留认证方案与未完成项`
- **THEN** Gateway 在原聊天确认已按该关注点压缩
- **AND** 随后的 Agent run 可从压缩摘要延续认证方案和未完成事项，关注点本身不成为一条普通 user message

#### Scenario: 当前没有可压缩会话
- **GIVEN** Gateway 尚未为当前聊天建立 Kernel session，或已有 session 但没有新的可压缩历史
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 在原聊天说明无需压缩
- **AND** 不为该 no-op 创建空 Kernel session，也不改变已有会话上下文

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
- **THEN** Gateway 切换到新 Kernel session，且不在新会话或旧会话执行该先前排队的压缩
- **AND** Gateway 在原聊天说明该压缩请求未执行

#### Scenario: 重放同一入站压缩不产生第二个压缩边界
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/compact <关注点>`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的压缩结果和控制确认
- **AND** 当前 Kernel session 不产生第二个 compaction record，关注点不作为重放 identity

### Requirement: /stop 控制命令中断当前运行

命令语法、实际触达范围和原聊天反馈适用于两种模式。以下“当前运行/会话”在 single_thread 指聊天绑定，在 global 指实际触达 Agent 的主工作上下文；global 控制记录归工作轨迹，停止不清 Inbox，也不新增对子任务的级联停止。全局模式对应行为以 [global-agent](global-agent.md) 为准。

终端用户发 `/stop`(支持 `/stop`、`@agent /stop`、`/stop @agent` 形式)可中断该会话当前活动运行;无活动运行时返回友好提示而非报错。

#### Scenario: /stop 中断正在执行的运行
- **GIVEN** 某会话有一轮正在执行
- **WHEN** 用户向该会话发 `/stop`
- **THEN** 当前运行被中断,用户收到「已停止当前操作。」,该 /stop 动作记入会话历史

#### Scenario: 无运行时 /stop 返回友好提示
- **WHEN** 某会话当前无活动运行而用户发 `/stop`
- **THEN** 用户收到「当前没有正在执行的操作。」,不抛错

#### Scenario: 群聊裸 /stop 不受 @ 提及门控限制
- **GIVEN** 群里某 Agent `group_reply_policy=MENTION` 且正在运行
- **WHEN** 用户发裸 `/stop`(不 @ 任何 Agent)
- **THEN** 该 `/stop` 仍送达群内 Agent 并中断正在运行的那个;当前无运行的 Agent 不受影响、不在群里发任何反馈(幂等无副作用)

### Requirement: Agent 正在回复时，用户仍能继续发消息并被及时采纳

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 忙时接收至 Inbox，由主 Agent 自主读取，不强制把新正文注入安全边界。

用户不必等 Agent 把当前这条回复彻底做完，就能再发消息；Agent 会尽快把新消息纳入考虑，而不是把它晾到当前回复结束之后才理。

#### Scenario: Agent 忙着做事时插一句，很快被采纳
- **GIVEN** Agent 正在回复用户的上一条消息（在一步步做一件要花点时间的事）
- **WHEN** 用户在它还没回复完时又发一条消息
- **THEN** Agent 很快把这条新消息纳入考虑并据此调整方向，而不是等当前这件事整个做完才理它

#### Scenario: 插话不打断 Agent 手头正在做的事
- **GIVEN** Agent 手头有一件事正在做（哪怕这件事很慢、在重试）
- **WHEN** 用户在此期间插一句
- **THEN** Agent 手头这件事照常做完，这条插话在它做完手头这步之后才被采纳（不被硬生生打断）

#### Scenario: 连发多条，按发送顺序全部被听到
- **GIVEN** Agent 正在回复用户
- **WHEN** 用户在它回复完之前一连发了好几条消息
- **THEN** 这些消息按发送先后全部被 Agent 纳入考虑，不丢、不乱序

#### Scenario: Agent 空着时发消息，照常回复
- **GIVEN** Agent 当前没有在回复任何东西
- **WHEN** 用户发一条消息
- **THEN** Agent 照常开始回复，和一直以来一样

#### Scenario: 群里插话，发言人身份和上下文不丢
- **GIVEN** 一个群聊里 Agent 正在回复
- **WHEN** 某个成员在它回复期间插一句
- **THEN** Agent 看到的这条插话仍带着「谁说的」以及群里该有的上下文，和平时在群里收到消息一样（群聊体验不变）
- **AND** 即使几个成员几乎同时插话，每条插话各自的「谁说的」和上下文都完整保留，不会互相串掉或丢失

### Requirement: 对插话的回复出现在插话下方，并随 Agent 做事逐步显示

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 的过程与轮次归工作页，聊天仅显示显式发出的消息。

#### Scenario: 对插话的回复排在插话下方，并随做事逐步显示
- **GIVEN** Agent 正在回复用户，会话里已经有它这条回复
- **WHEN** 用户在它回复期间又发一条消息
- **THEN** Agent 针对这条新消息的回复出现在这条新消息**下方**（按发送先后排），并随 Agent 一步步做事在那里逐步显示出来，直到给出最终回复
- **AND** 用户发这条新消息**之前** Agent 已经在说/在做的那部分，仍留在上一条回复里，那条回复正常结束

### Requirement: 实际配置边界最终可靠同步到 Web IM

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 采用新配置的事实归主 Session 的工作轮次，使用工作记录的持久同步，不伪造聊天/用户消息锚点；纯展示变化和保存失败仍不产生边界。

当既有聊天的一轮新回复首次采用不同的有效运行配置时，Gateway 为该聊天和首条用户消息产生稳定、可重试的配置边界事实。IM 暂时离线或 Gateway 重启不会永久丢失该事实；重复投递不会产生重复边界。外部 channel 的业务回复不因 IM 暂时离线而被阻塞，恢复后其 Web IM 影子聊天补齐边界，外部平台不收到伪造消息。边界只携带定位、幂等和代次证明所需的非敏感身份。

#### Scenario: Web IM 新回复采用新配置
- **GIVEN** 既有 Web IM 聊天的有效运行配置已改变
- **WHEN** 首条用户消息真正开始使用新配置
- **THEN** Gateway 把配置边界关联到该聊天和该用户消息，供 IM 持久显示

#### Scenario: IM 断线后最终补齐唯一边界
- **GIVEN** Gateway 已实际采用新配置，但 IM 连接暂时不可用
- **WHEN** IM 连接恢复，或 Gateway 在恢复前重启
- **THEN** 同一配置边界最终投递成功且至多显示一次

#### Scenario: 外部 channel 不等待 Web IM 标记
- **GIVEN** 用户在外部 channel 的既有对话中触发新配置，IM 暂时离线
- **WHEN** Agent 完成回复
- **THEN** 回复照常发回外部 channel
- **AND** IM 恢复后影子聊天补齐原用户消息、Agent 回复与其前唯一配置边界，外部 channel 不收到边界文本

#### Scenario: Gateway 在影子同步中断后恢复
- **GIVEN** 外部消息已进入本地可恢复同步流程，IM 写入某一步后 Gateway 尚未记录成功
- **WHEN** Gateway 重启并重放同一外部事件
- **THEN** IM 复用同一影子聊天、用户消息和 Agent 回复，配置边界仍唯一且锚点正确

#### Scenario: 纯展示变化与保存失败不产生边界
- **WHEN** Agent 只发生展示信息变化，或配置保存没有成功
- **THEN** Gateway 不产生实际运行配置边界

### Requirement: 会话映射与实际运行配置状态持久化，进程重启后续接不丢历史

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 按 Agent 持久绑定唯一主 Session，已读取的不同聊天内容可在该上下文关联使用；不迁移旧聊天绑定或合并旧历史。

Gateway 持久化聊天与内核会话的绑定及该聊天实际采用的运行配置身份。配置更新不删除绑定；同一聊天在原内核会话应用最新配置。进程重启后恢复同一绑定、历史与实际配置状态。升级前没有配置身份的旧绑定惰性建立基线，不因部署升级产生虚假配置提示。

#### Scenario: 重启后同一通道会话续接原内核会话
- **GIVEN** 某通道聊天已绑定内核会话并跨过一次配置更新
- **WHEN** Gateway 重启后同一聊天再来消息
- **THEN** 恢复原内核会话及实际配置状态，保留配置边界两侧历史，不退回旧配置

#### Scenario: Agent 配置更新不删除休眠聊天绑定
- **GIVEN** 同一 Agent 有多个已持久化聊天，其中一些休眠
- **WHEN** Agent 运行配置更新
- **THEN** 这些绑定均保留；休眠聊天在自己下一次新回复时才采用最新配置

#### Scenario: 旧绑定首次恢复不产生虚假边界
- **GIVEN** 升级前绑定没有持久运行配置身份
- **WHEN** 升级后首次恢复并继续该聊天
- **THEN** Gateway 建立兼容基线并延续原会话，不仅因软件升级产生“Agent 配置已更新”边界

#### Scenario: 不同聊天保持隔离
- **GIVEN** 同一 Agent 有直聊、群聊和外部 channel 多个独立聊天
- **WHEN** 配置更新后各自继续
- **THEN** 每个聊天只延续自己的历史和配置边界，不读取其他聊天内容

#### Scenario: 未知会话键返回空绑定
- **WHEN** 查询从未绑定的会话键
- **THEN** 返回空绑定且无副作用

### Requirement: 内核中的产品工具可把 Agent 产出的消息投递到目标会话

以下工具显式指定目标、权限校验和真实投递结果适用于两种模式。当前群来源的复核适用于 single_thread；global 按其目标群已接收范围复核，无隐含当前聊天。全局模式对应行为以 [global-agent](global-agent.md) 为准。

内核中运行的产品工具(如 `send_message`)可把 Agent 产出的消息投递到另一目标会话;`to` 为稳定业务标识 (`user_id` / `agent_id` / `conversation_id`)。Gateway 经 live IM 连接路由到目标会话,目标直聊不存在则创建、已存在则复用;IM 连接不可用时返回明确错误而非静默丢弃。

#### Scenario: IM 在线时投递成功并回执
- **GIVEN** Gateway 的 IM 连接已激活
- **WHEN** 工具发起投递 `{text, to, from_session_id}`
- **THEN** 消息经 IM 连接投递到目标会话,投递返回 `ok=True` 与目标会话标识

#### Scenario: IM 连接不可用时返回明确错误
- **WHEN** IM 连接缺失或未连接时收到投递请求
- **THEN** 投递返回 `ok=False` 并附带错误说明(不静默丢消息)

#### Scenario: 缺必填字段时拒绝投递
- **WHEN** 投递请求缺 `text` 或 `to`
- **THEN** 投递返回 `ok=False` 与字段校验错误


#### Scenario: 当前群工具发送遇到尚未采纳的新消息
- **GIVEN** 当前群运行的发送工具准备向同群投递正文
- **WHEN** 该运行在投递提交前接受了本轮尚未采纳的新消息
- **THEN** 工具明确回报正文未发送、需要结合新消息继续处理，不产生群发言；之后仍由原运行按原回复规则继续
- **AND** 网络失败保留原错误语义，不把未发送当成功回执

### Requirement: 后台任务完成后 Gateway 把 Agent 回复中继回原 IM 对话

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 的后台结果与主 Agent 综合正文归工作轨迹；只有显式发言进入聊天，不按最后聊天自动回传，也不另复制一份 Inbox 通知。

用户让 Agent 后台执行长任务后，主轮先回复已启动；任务结束时，Gateway 把消费该 `<task-notification>` 后产生的普通 Agent 回复投递回原 IM 对话。既有 background Bash 继续以第二条文本回复送达。对内置 Web IM 的后台 subagent / Workflow，回复还携带与 notification 同源的结构化后台返回，让用户核对原始 result 或 error 与来源；对不提供内部过程时间线的外部 IM，继续只投递普通文本。重复投递经稳定 identity 去重，不产生重复消息或重复后台返回。

#### Scenario: 后台 Bash 完成后用户在 IM 对话收到包含结果的第二条回复
- **GIVEN** 用户经 IM 直聊让 Agent 后台执行一个命令（如 `run_in_background: sleep 30 && echo X`）
- **WHEN** 主轮返回“已启动”，任务在后台完成
- **THEN** 用户在同一 IM 对话收到第二条 Agent 回复，内含后台任务输出（如“X”）
- **AND** 本 unit 不要求该 Bash 回复增加结构化后台返回过程项

#### Scenario: 后台 Agent 完成后 Web IM 收到正文与可归因返回
- **GIVEN** 用户经 Web IM 让 Agent 以 `run_in_background=true` 派发一个 subagent
- **WHEN** 主轮已返回“已启动”，subagent 稍后完成并由 parent 生成综合回复
- **THEN** 用户在同一对话收到第二条普通 Agent 回复
- **AND** 该回复同时携带 subagent 的 task/agent identity、status、未经主 Agent 改写的 result/error、usage、duration 与 output artifact

#### Scenario: 后台 Workflow 使用相同投递通路
- **GIVEN** 用户经 Web IM 启动一个 Workflow
- **WHEN** Workflow completed、failed 或 stopped，parent 生成综合回复
- **THEN** Gateway 用相同消息 sidecar 携带 Workflow task/run identity、terminal value、usage、diagnostics 与 resume hint
- **AND** 不把 terminal 当作 launch ToolCall 的后续更新

#### Scenario: 后台 Workflow 终态 continuation 使用原 parent session runtime
- **GIVEN** Workflow 所属 parent session 的持久 runtime 选择了特定 model 与 effort，且该 session 在终态通知到达时没有 active run
- **WHEN** Gateway 因该通知启动普通综合回复
- **THEN** continuation 使用原 parent session 持久化的 model 与 effort
- **AND** 不回落到进程默认模型，也不借用其他 session 的 runtime

#### Scenario: 外部 IM 保持普通文本回复
- **WHEN** 同一后台返回来自飞书等外部 channel
- **THEN** Gateway 仍把主 Agent 的普通文本回复发回原聊天
- **AND** 不新增外部卡片、raw XML 或 Web 专用过程字段

#### Scenario: Gateway 重启不产生重复的后台回复
- **GIVEN** 某后台任务回复及其结构化返回已投递到 IM 对话
- **WHEN** Gateway 重启后同一 task 的事件被重放
- **THEN** 该对话中不出现重复的第二条回复，同一消息中也不出现重复后台返回

### Requirement: agent 回复失败时即时反馈真实原因

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 global 在对应工作轮次显示真实失败/中断状态，节点断连时显示不可确认或离线；不为此创建聊天失败气泡。

当一轮 agent 回复因故无法完成时,Gateway 即时把该条回复在消息级翻为失败态并附带可读的真实失败原因, 归属到对应 agent。该即时反馈不依赖 IM 的 idle 看门狗;看门狗仅在「整个节点失联、无法发出任何反馈」时作为最后兜底。

#### Scenario: run 失败即时翻为失败态
- **GIVEN** 用户向某 agent 发了一条消息,该 agent 开始回复
- **WHEN** 这一轮回复在中途失败(例如超长会话腾挪后仍无法继续)
- **THEN** 该条回复在数秒内翻为失败态,携带可读的真实失败原因,并归属到该 agent
- **AND** 用户无需等待约两分钟才看到一句笼统的「relay idle」超时提示

#### Scenario: 节点失联时看门狗仍兜底
- **GIVEN** 一条 agent 回复处于进行中
- **WHEN** 整个节点失联、无法发出任何终态反馈
- **THEN** IM 的 idle 看门狗在静默窗口后仍把该回复兜底翻为失败,避免其永久停在进行中

### Requirement: 内置当前群运行在发言提交前复核已接受消息

本条当前群上下文、插话和过程分段规则及 Scenario 适用于 `single_thread`。global 没有隐含当前群，其显式发送执行独立的目标群复核。全局模式对应行为以 [global-agent](global-agent.md) 为准。

仅内置普通群运行启用；普通正文、同群发送工具及回到该群继续运行的后台结果采用相同规则。复核只处理已按原策略被当前运行接受的新消息，不新增静默许可、触发条件或冲突暂停。

#### Scenario: ALWAYS 群中的新更正进入回复
- **GIVEN** Agent 正准备根据周四安排回复，另一 Agent 未提及它便更正为周五
- **WHEN** 当前运行按 ALWAYS 接受更正，原正文尚未提交
- **THEN** 原正文保持未发送，Agent 有机会依据更正重新回复或解释分歧；只有原规则允许时才能静默

#### Scenario: 真人补充多模态消息
- **WHEN** 当前群运行准备回复时接收到用户的文本或图片更正
- **THEN** 在公开旧正文之前结合完整新输入继续处理，不丢发言人或图片

#### Scenario: 无新消息与提交后到达
- **WHEN** 发言提交前没有尚未采纳的新输入，或新消息在提交后才被接受
- **THEN** 发言正常发送；后到消息依原插话规则处理，不撤回已提交回复

#### Scenario: 原规则与排除入口保持
- **WHEN** 未 @ 的消息只进入 MENTION 背景缓冲，或用户使用 Open chat 单聊、外部渠道、跨群主动通知
- **THEN** 保持各自既有行为，不扩大唤醒范围，也不附加当前群复核交互

#### Scenario: 后台返回后继续回复
- **GIVEN** 后台任务或 Workflow 的结果回到当前群的运行
- **WHEN** 模型基于结果准备正文期间，该运行又接受新消息
- **THEN** 与普通回复一样在提交前复核；原始工具返回仍按 Process 展示，不冒充正式发言

#### Scenario: 连续更新及显式控制
- **WHEN** 复核期间又接收更新，或用户执行 /stop、/new
- **THEN** 新更新继续遵守发言前复核；停止和新会话保持原有语义，不复活未发旧稿，不引入冲突次数后的暂停或强发
