# gateway (personal_assistant) - Routing and Delivery Specification

> 对齐: feat-517, bugfix-525
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

入站触发、运行中插话、回复定位、会话映射、产品投递工具和用户可见失败反馈的 Gateway 契约。

## Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道(外部 IM 或内置 Web IM)收到一条入站消息时,Gateway 依次决策:路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标,不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待 LLM 返回这两类"活着但安静"的窗口都有周期性 liveness 心跳,看门狗不再以"无业务输出事件"判卡死;等待用户权限决策的窗口则完全豁免于 idle 看门狗超时 (用户可能离开、关闭页面、心搏链路也可能延迟或丢失),只有该轮收到 `permission_resolved` 或判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

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

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀
- **GIVEN** 某轮已发起一个需要授权的工具,正等待用户在权限卡片上决策
- **WHEN** 等待时长超过判定窗口(即使用户离开、关闭 IM 页面、其间没有 liveness 心跳到达)
- **THEN** 该轮不被 idle 看门狗取消;用户随后批准则工具正常执行、该轮继续推进,不报「relay idle for 120s」
- **AND** 一旦用户做出决策、内核发出 `permission_resolved`,正常 idle 看门狗立即恢复,决策后的卡死/断连仍会被捕获

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(抛 `LookupError`),不创建会话也不执行

### Requirement: 群聊只在被 @提及 / 回复 Agent / 明确的全群控制命令时触发 Agent

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

Gateway 在已路由的聊天中把精确的 `/compact` 和 `/compact <关注点>` 作为当前 Kernel session 的手动压缩命令。非空关注点仅指导这次摘要保留重点；它不作为普通用户 turn 写入会话。Gateway 只在当前 session 无 active 或 queued work 时执行压缩，并在同一聊天明确区分成功、无需压缩、忙碌和失败；失败不得改变调用前上下文。其他 slash 文本按普通用户消息处理。

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

#### Scenario: 忙碌或失败时上下文不变
- **GIVEN** 当前 session 有 active 或 queued run
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 提示等待当前操作完成或先使用 `/stop`，且不调用压缩
- **GIVEN** 当前 session 空闲但手动压缩无法生成或持久提交摘要
- **WHEN** 用户发送 `/compact`
- **THEN** Gateway 报告压缩未完成，后续运行仍使用压缩前上下文

#### Scenario: 重放同一入站压缩不产生第二个压缩边界
- **GIVEN** Gateway 已成功处理一个带稳定入站 identity 的 `/compact <关注点>`
- **WHEN** 外部 provider 或 relay 重放同一条入站消息
- **THEN** Gateway 复用第一次的压缩结果和控制确认
- **AND** 当前 Kernel session 不产生第二个 compaction record，关注点不作为重放 identity

### Requirement: /stop 控制命令中断当前运行

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

#### Scenario: 对插话的回复排在插话下方，并随做事逐步显示
- **GIVEN** Agent 正在回复用户，会话里已经有它这条回复
- **WHEN** 用户在它回复期间又发一条消息
- **THEN** Agent 针对这条新消息的回复出现在这条新消息**下方**（按发送先后排），并随 Agent 一步步做事在那里逐步显示出来，直到给出最终回复
- **AND** 用户发这条新消息**之前** Agent 已经在说/在做的那部分，仍留在上一条回复里，那条回复正常结束

### Requirement: 配置更新不改变正在进行的回复与被其采纳的插话

Gateway 为正在进行的回复保持其开始时的 Agent 运行配置。配置更新期间到达、且成功被当前回复采纳的插话继续属于同一配置代次；只有随后真正开始的新回复使用最新配置。

#### Scenario: 回复进行中修改配置
- **GIVEN** Agent 正在使用配置 A 回复
- **WHEN** 用户把 Agent 更新为配置 B
- **THEN** 当前回复继续使用 A，下一轮新回复使用 B

#### Scenario: 配置更新后的插话进入当前回复
- **GIVEN** 当前回复使用配置 A，Agent 已更新为 B
- **WHEN** 用户插话被当前回复采纳
- **THEN** 该插话与当前整轮继续使用 A，不在同一轮中混入 B

### Requirement: 实际配置边界最终可靠同步到 Web IM

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

### Requirement: 后台任务完成后 Gateway 把 Agent 回复中继回原 IM 对话

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

### Requirement: self-evolution 维护过程不作为 Agent 聊天文本投递

Gateway 只把含非空真实更新对象的 self-evolution structured result 作为既有 system notification 投递；飞书触发时，该产品化更新通知按普通消息的触发源路由在原 chat 显示一行等价 Bot 文本。review side-chain 的 prompt、工具过程、完成确认、无更新说明与失败文本均属于后台维护信息，不形成内部 IM 或外部 channel 的普通 Agent 消息。该隔离不改变普通后台 Agent 明确面向用户产生结果的投递语义。

#### Scenario: memory review 完成后只显示 structured notice

- **GIVEN** 用户的一轮正常聊天触发后台 memory review
- **WHEN** review 保存 memory 并生成完成确认
- **THEN** 用户只收到正常 Agent 回答与既有 memory-updated system notification；飞书触发时原 chat 收到同一结果的一行 Bot 通知
- **AND** 不收到 review prompt、工具状态或完成确认的普通聊天气泡

#### Scenario: 无更新或失败的 review 保持私有

- **WHEN** self-evolution review 得出无需更新或执行失败
- **THEN** 用户不收到 `Nothing to save.`、错误文本或其他 side-chain 回复
- **AND** 该后台结果不改变前台回答的完成状态
- **AND** 没有成功的 memory/skills 写操作时不产生 system notification

#### Scenario: 普通后台 Agent 结果继续投递

- **WHEN** 非 self-evolution 的后台 Agent 按既有语义产生用户可见文本
- **THEN** Gateway 继续把该文本投递到原内部 IM 或外部 channel

### Requirement: agent 回复失败时即时反馈真实原因

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

### Requirement: PA 在 workspace 产品目录保留可读聊天副本

Gateway 在每个 PA 会话的 user 或 assistant 文本进入其持久化投递路径时，向 `<workspace_root>/.nanoassistant/chat_history/<conversation-id>.jsonl` 追加一个简化 JSONL 条目。条目保留 `ts`、`role` 与文本 `content`，供用户在 workspace 中查看；它不替代内核 session transcript，也不作为会话恢复的唯一来源。Gateway 不在 workspace 根新建 `chat_history/`。

#### Scenario: 用户与助手文本写入 PA 产品目录
- **GIVEN** 一个 PA Agent 的 workspace 为代码仓目录，且用户完成一轮有 assistant 文本回复的聊天
- **WHEN** Gateway 持久化该轮的简化聊天副本
- **THEN** user 和 assistant 条目写入该 workspace 的 `.nanoassistant/chat_history/`，每项含 `ts`、`role`、`content`，workspace 根没有新建 `chat_history/`

#### Scenario: 可读聊天副本不替代会话恢复记录
- **WHEN** Gateway 在已有简化聊天副本后恢复该会话
- **THEN** 仍从内核 session transcript 恢复上下文，而非把简化 JSONL 当作唯一恢复来源
