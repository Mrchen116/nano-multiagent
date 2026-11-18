# gateway/routing-delivery Specification (delta for feat-774)

## MODIFIED Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

聊天路由先应用协作范围。下列聊天触发和回发场景以消息已获准送达为前提。

本条以下按聊天绑定、处理和自动展示的规则及 Scenario 适用于 `single_thread`。全局模式对应行为以 [global-agent](global-agent.md) 为准。 Agent 身份解析与未知 Agent 拒绝适用于两种模式；global 的入站持久接受后交 Inbox，不预建等待主模型回复的聊天消息。

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待主模型返回和自动整理上下文三类“活着但安静”的窗口都有周期性 liveness 心跳，看门狗不再以“无业务输出事件”判卡死；等待用户权限决策同样依赖持续 liveness。只有判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾；`permission_resolved` 是审批结束事件，不是运行失活。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行, 最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话轮次串行、不同会话并行
- **WHEN** 一个会话已有回复在执行，其他会话也收到消息
- **THEN** 同一会话中需要另起回复的消息按序处理，其他会话可独立推进。当前轮次采纳新输入的时机见[忙时插话](#requirement-agent-正在回复时用户仍能继续发消息并被及时采纳)。

#### Scenario: 失去 liveness 后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行,但在判定窗口(120 秒)内既无业务事件也无任何 liveness 心跳,另一条需要独立回复的消息仍在等待
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

### Requirement: 群聊新消息按各 Agent 的接收策略触发，控制命令按目标生效

两种模式先按协作范围过滤，再处理命令和优先级。下述群背景自动带入、按群创建 Session、普通正文/过程气泡及 `/new` 的重开效果适用于 `single_thread`；global 将可见更新存入 Inbox，仅有效实时触发推进唤醒，不自动摄取正文；命中的 global Agent 对 `/new` 在原聊天明确答复不支持。全局模式对应行为以 [global-agent](global-agent.md) 为准。

团队协作下，私聊、真实提及、回复或引用本 Agent 及时触发，普通群消息累计到下次高优或十分钟。触发后仍可按相应工作模式保持静默。裸 `/stop` 与内置 Web IM 群聊中的精确裸 `/new` 独立于普通消息策略：前者中断实际触达的活动 Agent，后者按各 Agent 的工作模式处理。`/compact`、`/compact <关注点>` 和 `/effort <level>` 仍须明确指向目标 Agent。

#### Scenario: 团队协作下未点名的普通群消息作为背景
- **GIVEN** 一个使用团队协作的 single_thread Agent 在群中
- **WHEN** 群里来了一条未提及或回复该 Agent 的普通消息
- **THEN** 暂存为该群背景。同群下一条高优或十分钟先到者使其取得积压；忙时在下一次模型请求前取得，空闲时有积压才启动。跨群正文分隔，同批只交付一次。

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

#### Scenario: Web IM 群聊裸 `/new` 按各 Agent 工作模式处理
- **GIVEN** 一个含 single_thread Agent 的内置 Web IM 群聊，其中该 Agent 使用团队协作
- **WHEN** 用户发送精确的裸 `/new`
- **THEN** 每个 single_thread Agent 分别重开自己的群会话并在原群确认；Global Agent 反馈不支持重置并保留其原工作上下文
- **AND** 重开后，面向该 single_thread Agent 的普通消息不携带其旧群会话上下文

#### Scenario: 群聊压缩仍需明确目标
- **GIVEN** 一个 团队协作 的 Agent 在某群聊中
- **WHEN** 用户发送未 @该 Agent、也非回复该 Agent 的 `/compact` 或 `/compact <关注点>`
- **THEN** Gateway 不压缩该 Agent 的群会话，也不发送控制确认
- **WHEN** 用户通过结构化 mention、文本 `@Agent` 或回复该 Agent 发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Gateway 只在被指向 Agent 的群会话上执行命令，并在同一群返回控制确认

#### Scenario: 群聊推理档位始终需要明确目标
- **GIVEN** 群内一个或多个 Agent 使用团队协作
- **WHEN** 用户发送指向 Agent A 的 `/effort <level>`，Gateway 向参与者 fan-out relay
- **THEN** 只有 Agent A 处理该命令；其他 Agent 不创建会话、不改写 session effort，也不把命令交给模型

### Requirement: /stop 控制命令中断当前运行

聊天控制仅对当前协作范围内的输入生效。

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
- **GIVEN** 群里某 Agent 使用团队协作 且正在运行
- **WHEN** 用户发裸 `/stop`(不 @ 任何 Agent)
- **THEN** 该 `/stop` 仍送达群内 Agent 并中断正在运行的那个;当前无运行的 Agent 不受影响、不在群里发任何反馈(幂等无副作用)

### Requirement: 内置当前群运行在发言提交前复核已接受消息

本条当前群上下文、插话和过程分段规则及 Scenario 适用于 `single_thread`。global 没有隐含当前群，其显式发送执行独立的目标群复核。全局模式对应行为以 [global-agent](global-agent.md) 为准。

仅内置普通群运行启用；普通正文、同群发送工具及回到该群继续运行的后台结果采用相同规则。复核只处理已按原策略被当前运行接受的新消息，不新增静默许可、触发条件或冲突暂停。

#### Scenario: 群内已接受的高优更正进入回复
- **GIVEN** Agent 正准备根据周四安排回复，另一 Agent 回复它的原消息，更正为周五
- **WHEN** 当前运行已接受该高优更正，原正文尚未提交
- **THEN** 原正文保持未发送，Agent 有机会依据更正重新回复或解释分歧；只有原规则允许时才能静默

#### Scenario: 真人补充多模态消息
- **WHEN** 当前群运行准备回复时接受了面向它的文本或图片更正
- **THEN** 在公开旧正文之前结合完整新输入继续处理，不丢发言人或图片

#### Scenario: 无新消息与提交后到达
- **WHEN** 发言提交前没有尚未采纳的新输入，或新消息在提交后才被接受
- **THEN** 发言正常发送；后到消息依原插话规则处理，不撤回已提交回复

#### Scenario: 原规则与排除入口保持
- **WHEN** 未 @ 的消息仅在普通背景批次中积累，或用户使用 Open chat 单聊、外部渠道、跨群主动通知
- **THEN** 保持各自既有行为，不扩大唤醒范围，也不附加当前群复核交互

#### Scenario: 后台返回后继续回复
- **GIVEN** 后台任务或 Workflow 的结果回到当前群的运行
- **WHEN** 模型基于结果准备正文期间，该运行又接受新消息
- **THEN** 与普通回复一样在提交前复核；原始工具返回仍按 Process 展示，不冒充正式发言

#### Scenario: 连续更新及显式控制
- **WHEN** 复核期间又接收更新，或用户执行 /stop、/new
- **THEN** 新更新继续遵守发言前复核；停止和新会话保持原有语义，不复活未发旧稿，不引入冲突次数后的暂停或强发

### Requirement: 通知遵循已有 Agent 群接收策略及忙闲处理

复用现有消息／Inbox 与执行机制，群内可见不等于所有 Agent 立即执行。分配通知是可由负责人接手的交办信息，读取并领取后才表示开始推进。

#### Scenario: 协作范围不同的 Agent 同群

- **WHEN** 改派消息 @ A 和 B，A、B、C 处于团队协作，D 仅限本人
- **THEN** 聊天提醒按范围送达，A、B 被明确指向，C 的普通聊天消息按批次处理，D 不接收群聊天。任务原件及面向负责人的任务控制仍依其专有授权和触发规则。

#### Scenario: 空闲、忙碌、离线与取消当前执行

- **WHEN** 应处理通知的 Agent 空闲、忙碌或离线
- **THEN** 分别采用主动触发、排队等待合适处理时机、保留待处理通知；不等用户必须再次发话，也不把已投递显示成已开工。
- **AND** `/stop` 保持取消当前执行的语义；后续有效任务消息仍按既有群策略触发处理，不新增持久停止或等待真人恢复的状态。
- **AND** 不另开一个冲突执行，不把整张任务图或依赖关系自动变成任务调度器。

#### Scenario: 重投与权限撤回
- **WHEN** 相同任务系统消息因断线恢复重投，或目标已不具备群接收资格
- **THEN** 同一有效输入不会重复交办；投递前复核资格，无资格者不因旧任务回执继续收到内容。
- **AND** 系统消息保留系统来源，不能冒充真人指令或新增删除授权。
