# gateway/routing-delivery.md (delta for feat-796)

## MODIFIED Requirements

### Requirement: 群聊新消息按各 Agent 的接收策略触发，控制命令按目标生效

两种模式先按协作范围过滤，再处理命令和优先级：处于「团队公开」（`team`）的 Agent 可接收所参与群的消息；处于「私有」（`owner_only`）的 Agent 仅接收同主人私密专属群（仅含主人本人及同主人名下 Agent）的消息，不接收任何含外部成员群聊的消息。下述群背景自动带入、按群创建 Session、普通正文/过程气泡及 `/new` 的重开效果适用于 `single_thread`；global 将可见更新存入 Inbox，仅有效实时触发推进唤醒，不自动摄取正文；命中的 global Agent 对 `/new` 在原聊天明确答复不支持。全局模式对应行为以 [global-agent](global-agent.md) 为准。

允许接收该群消息时，私聊、真实提及、回复或引用本 Agent 及时触发，普通群消息累计到下次高优或十分钟。触发后仍可按相应工作模式保持静默。裸 `/stop` 与内置 Web IM 群聊中的精确裸 `/new` 独立于普通消息策略：前者中断实际触达的活动 Agent，后者按各 Agent 的工作模式处理。`/compact`、`/compact <关注点>` 和 `/effort <level>` 仍须明确指向目标 Agent。

#### Scenario: 团队协作与专属私密群下未点名的普通群消息作为背景
- **GIVEN** 一个 `single_thread` Agent 在其有权接收的群中（「团队公开」群，或「私有」下的同主人私密专属群）
- **WHEN** 群里来了一条未提及或回复该 Agent 的普通消息
- **THEN** 暂存为该群背景。同群下一条高优或十分钟先到者使其取得积压；忙时在下一次模型请求前取得，空闲时有积压才启动。跨群正文分隔，同批只交付一次，且不将该群会话劫持绑定为主人心跳主会话。

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
- **GIVEN** 一个含 single_thread Agent 的内置 Web IM 群聊，其中该 Agent 有权接收该群消息
- **WHEN** 用户发送精确的裸 `/new`
- **THEN** 每个 single_thread Agent 分别重开自己的群会话并在原群确认；Global Agent 反馈不支持重置并保留其原工作上下文
- **AND** 重开后，面向该 single_thread Agent 的普通消息不携带其旧群会话上下文

#### Scenario: 群聊压缩仍需明确目标
- **GIVEN** 一个有权接收该群消息的 Agent 在某群聊中
- **WHEN** 用户发送未 @该 Agent、也非回复该 Agent 的 `/compact` 或 `/compact <关注点>`
- **THEN** Gateway 不压缩该 Agent 的群会话，也不发送控制确认
- **WHEN** 用户通过结构化 mention、文本 `@Agent` 或回复该 Agent 发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Gateway 只在被指向 Agent 的群会话上执行命令，并在同一群返回控制确认

#### Scenario: 群聊推理档位始终需要明确目标
- **GIVEN** 群内一个或多个 Agent 有权接收该群消息
- **WHEN** 用户发送指向 Agent A 的 `/effort <level>`，Gateway 向参与者 fan-out relay
- **THEN** 只有 Agent A 处理该命令；其他 Agent 不创建会话、不改写 session effort，也不把命令交给模型

### Requirement: 内核中的产品工具可把 Agent 产出的消息投递到目标会话

以下工具显式指定目标、权限校验和真实投递结果适用于两种模式。当前群来源的复核适用于 single_thread；global 按其目标群已接收范围复核，无隐含当前聊天。全局模式对应行为以 [global-agent](global-agent.md) 为准。

内核中运行的产品工具(如 `send_message`)可把 Agent 产出的消息投递到另一目标会话;模型参数 `target` 使用聊天成员的短 `user_id` 或短 `conversation_id`，人和 Agent 均以 `user_id` 联系。外部 Inbox 在镜像尚未同步时返回的临时 `local:` 目标也可原样用于回复，Gateway 在同步恢复后解析到原聊天。Gateway 经 live IM 连接路由到目标会话,目标直聊不存在且符合该 Agent 可见与协作范围时创建、已存在则复用;当发送方 Agent 处于「私有」（`owner_only`）且目标为外部同事、他人 Agent 或含外部成员的会话时，IM 明确拒绝并返回私有范围限制说明；IM 连接不可用时返回明确错误而非静默丢弃。

#### Scenario: IM 在线时投递成功并回执
- **GIVEN** Gateway 的 IM 连接已激活且目标符合发送方 Agent 的协作范围（「团队公开」或「私有」下的主人及同主人内部会话）
- **WHEN** 工具发起投递 `{target, text}`
- **THEN** 消息经 IM 连接投递到目标会话,投递返回 `ok=True` 与目标会话标识

#### Scenario: 私有助手向外部目标投递被明确拒绝
- **GIVEN** 发送方 Agent 处于「私有」（`owner_only`）
- **WHEN** 工具尝试向外部同事、他人名下 Agent 或含外部成员的会话发起投递
- **THEN** 投递被拒绝且不产生对外消息，返回明确说明该助手仅允许与主人及主人名下助手通信的错误信息

#### Scenario: IM 连接不可用时返回明确错误
- **WHEN** IM 连接缺失或未连接时收到投递请求
- **THEN** 投递返回 `ok=False` 并附带错误说明(不静默丢消息)

#### Scenario: 缺必填字段时拒绝投递
- **WHEN** 投递请求缺 `text` 或 `target`
- **THEN** 投递返回 `ok=False` 与字段校验错误

#### Scenario: 当前群工具发送遇到尚未采纳的新消息
- **GIVEN** 当前群运行的发送工具准备向同群投递正文
- **WHEN** 该运行在投递提交前接受了本轮尚未采纳的新消息
- **THEN** 工具明确回报正文未发送、需要结合新消息继续处理，不产生群发言；之后仍由原运行按原回复规则继续
- **AND** 网络失败保留原错误语义，不把未发送当成功回执

### Requirement: 通知遵循已有 Agent 群接收策略及忙闲处理

复用现有消息／Inbox 与执行机制，群内可见不等于所有 Agent 立即执行。分配通知是可由负责人接手的交办信息，读取并领取后才表示开始推进。

#### Scenario: 协作范围不同的 Agent 同群
- **WHEN** 含外部成员的群内改派消息 @ A 和 B，A、B、C 处于团队公开，D 处于私有（或仅在同主人私密专属群中与主人协作）
- **THEN** 含外部成员群的聊天提醒仅向团队公开成员按范围送达（A、B 被明确指向，C 的普通聊天消息按批次处理，D 不在含外部成员群接收聊天）；在仅含主人及同主人名下 Agent 的私密专属群中，私有 Agent 正常按群提及与批次策略接收提醒。任务原件及面向负责人的任务控制仍依其专有授权和触发规则。

#### Scenario: 空闲、忙碌、离线与取消当前执行
- **WHEN** 应处理通知的 Agent 空闲、忙碌或离线
- **THEN** 分别采用主动触发、排队等待合适处理时机、保留待处理通知；不等用户必须再次发话，也不把已投递显示成已开工。
- **AND** `/stop` 保持取消当前执行的语义；后续有效任务消息仍按既有群策略触发处理，不新增持久停止或等待真人恢复的状态。
- **AND** 不另开一个冲突执行，不把整张任务图或依赖关系自动变成任务调度器。

#### Scenario: 重投与权限撤回
- **WHEN** 相同任务系统消息因断线恢复重投，或目标已不具备群接收资格
- **THEN** 同一有效输入不会重复交办；投递前复核资格，无资格者不因旧任务回执继续收到内容。
- **AND** 系统消息保留系统来源，不能冒充真人指令或新增删除授权。

### Requirement: 话题回复只把关注者及时叫醒

有权接收群消息的群里（「团队公开」群，或「私有」Agent 所在的同主人私密专属群），未关注、未被 @、也未被引用的话题回复不中继。它不进入该 Agent 的群背景，也不在十分钟后并入下一次运行。私聊话题仍按私聊新消息及时到达。「私有」Agent 不在含外部成员的群中接收群话题；创建者及同主人名下 Agent 与它的私聊话题和同主人私密专属群中的已关注/被点名话题正常及时到达。

#### Scenario: 未关注的群话题
- **GIVEN** 有权接收该群消息的 Agent 没有关注这条群话题
- **WHEN** 话题里出现没有 @ 它、也没有引用它的回复，无论发送者是人还是 Agent
- **THEN** 不创建运行，群背景和十分钟积压里也没有这条消息

#### Scenario: 已关注或被点名
- **WHEN** 话题回复来自该 Agent 在有权接收群中已关注的话题，或 @ 了它，或引用了它
- **THEN** 按现在的高优路径及时叫醒，并把话题根和这条回复交给该聊天现有的 session
- **AND** 它随后要人看见的话写回这个话题，不另写一条主时间线消息

#### Scenario: 私有档位下的内部与外部话题边界
- **WHEN** 外部会话话题尝试指向一个「私有」Agent，同时创建者（或同主人 Agent）在私聊话题或同主人私密专属群话题里 `@` 该「私有」Agent
- **THEN** 外部话题不叫醒它，而创建者私聊话题与同主人专属群话题正常到达并建立初始话题关注
