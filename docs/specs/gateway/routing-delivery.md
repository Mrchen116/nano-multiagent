# gateway (personal_assistant) - Routing and Delivery Specification

> 对齐: feat-447
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

入站触发、运行中插话、回复定位、会话映射、产品投递工具和用户可见失败反馈的 Gateway 契约。

## Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道(外部 IM 或内置 Web IM)收到一条入站消息时,Gateway 依次决策:路由到哪个 Agent、用哪个会话、
是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标,不跨通道混发。idle 看门狗按
**liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待 LLM 返回、等待用户权限决策这三类"活着但安静"
的窗口都有周期性 liveness 心跳,看门狗不再以"无业务输出事件"判卡死、也不再为某一类窗口单列特例豁免;只有
在判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行,
  最终 Agent 回复经原通道的出站路由回发到发起会话

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
- **GIVEN** 某轮已发起一个需要授权的工具,正等待用户在权限卡片上决策(其间有周期性 liveness 心跳)
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被 idle 看门狗取消;用户随后批准则工具正常执行、该轮继续推进,不报「relay idle for 120s」

#### Scenario: 路由到未知 Agent 被拒
- **WHEN** 入站消息显式指定一个 Gateway 未注册的 `agent_id`
- **THEN** Gateway 拒绝该路由(抛 `LookupError`),不创建会话也不执行

### Requirement: 群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent

群聊流量在分配任何内核会话或队列槽**之前**先过 @提及门控。未被点名的群聊消息不触发 Agent 执行;Agent
判断无需回复时输出约定 token(`NO_REPLY`)则不向用户发言。门控策略由各 Agent 的 `group_reply_policy`
决定(默认 `MENTION`;`ALWAYS` 则有消息即回)。

#### Scenario: 群聊未被 @提及的消息不触发 Agent
- **GIVEN** 一个 `group_reply_policy=MENTION` 的 Agent 在某群聊中
- **WHEN** 群里来了一条既未 @该 Agent、也非回复该 Agent、也非控制命令的消息
- **THEN** 不创建内核会话、不发起运行;该消息仅作为后台上下文缓冲到该 Agent 自己的群上下文 buffer,
  待该 Agent 下次被点名时随当轮一并带入

#### Scenario: 群聊被 @提及触发并把上下文带入当轮
- **GIVEN** 该 Agent 的群上下文 buffer 里已缓冲了若干条未点名消息
- **WHEN** 群里来了一条 @该 Agent 的消息
- **THEN** Gateway 创建/复用该群会话,把缓冲的消息(各带 `[sender]` 前缀)与当前消息一并提交给内核执行

#### Scenario: 群聊 Agent 输出 NO_REPLY 时不发言
- **WHEN** 群聊一轮运行的最终回复文本为 `NO_REPLY`
- **THEN** Gateway 抑制出站投递,用户在群里看不到任何 Agent 发言

#### Scenario: 群聊 Agent 互相 @ 的 fan-out 回复输出 NO_REPLY 时不发言
- **GIVEN** 群聊里 Agent A 的回复 @ 了 Agent B,把 B 拉起(agent-to-agent fan-out),或某 Agent 的
  后台任务在群聊会话产生回复
- **WHEN** 被拉起的 Agent 判断无需接话,输出 `NO_REPLY`(或心跳静默 token `HEARTBEAT_OK`)
- **THEN** Gateway 对该 fan-out / 后台投递同样抑制,用户在群里看不到 `NO_REPLY` 字面量,该消息也不落库

### Requirement: /stop 控制命令中断当前运行

终端用户发 `/stop`(支持 `/stop`、`@agent /stop`、`/stop @agent` 形式)可中断该会话当前活动运行;无活动
运行时返回友好提示而非报错。

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

### Requirement: 会话映射持久化,进程重启后续接不丢历史

Gateway 把「会话键 → 内核会话」的绑定落盘持久化(SQLite)。进程重启后按会话键恢复映射,续接原内核会话,
聊天历史不丢失;会话键按通道与群聊/直聊维度生成(群聊以 chat 维度、直聊以 user 维度),同一通道会话稳定
命中同一绑定。

#### Scenario: 重启后同一通道会话续接原内核会话
- **GIVEN** 某通道会话已绑定到一个内核会话并持久化
- **WHEN** Gateway 进程重启后,同一通道会话再来一条消息
- **THEN** Gateway 由持久化绑定恢复,续接原内核会话(而非新建),保留先前对话历史

#### Scenario: 未知会话键返回空绑定
- **WHEN** 查询一个从未绑定过的会话键
- **THEN** 返回 `None`(不报错、不副作用)

### Requirement: 内核中的产品工具可把 Agent 产出的消息投递到目标会话

内核中运行的产品工具(如 `send_message`)可把 Agent 产出的消息投递到另一目标会话;`to` 为稳定业务标识
(`user_id` / `agent_id` / `conversation_id`)。Gateway 经 live IM 连接路由到目标会话,目标直聊不存在则
创建、已存在则复用;IM 连接不可用时返回明确错误而非静默丢弃。

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

用户让 Agent 后台执行长任务（`run_in_background`），Agent 立即回复「已启动」后主轮结束；任务完成后，
Gateway 把 Agent 的完成回复投递回触发该任务的原 IM 对话——用户在同一对话看到内含任务结果的第二条
回复。重复投递（如 Gateway 重启后重放）经去重，用户不会看到重复的第二条回复。

#### Scenario: 后台任务完成后用户在 IM 对话收到包含结果的第二条回复
- **GIVEN** 用户经 IM 直聊让 Agent 后台执行一个命令（如 `run_in_background: sleep 30 && echo X`）
- **WHEN** 主轮返回「已启动」，任务在后台完成
- **THEN** 用户在同一 IM 对话收到第二条 Agent 回复，内含后台任务输出（如「X」）

#### Scenario: Gateway 重启不产生重复的后台回复
- **GIVEN** 某后台任务回复已投递到 IM 对话
- **WHEN** Gateway 重启后该回复被重放
- **THEN** 该对话中不出现重复的第二条回复

### Requirement: agent 回复失败时即时反馈真实原因

当一轮 agent 回复因故无法完成时,Gateway 即时把该条回复在消息级翻为失败态并附带可读的真实失败原因,
归属到对应 agent。该即时反馈不依赖 IM 的 idle 看门狗;看门狗仅在「整个节点失联、无法发出任何反馈」时
作为最后兜底。

#### Scenario: run 失败即时翻为失败态
- **GIVEN** 用户向某 agent 发了一条消息,该 agent 开始回复
- **WHEN** 这一轮回复在中途失败(例如超长会话腾挪后仍无法继续)
- **THEN** 该条回复在数秒内翻为失败态,携带可读的真实失败原因,并归属到该 agent
- **AND** 用户无需等待约两分钟才看到一句笼统的「relay idle」超时提示

#### Scenario: 节点失联时看门狗仍兜底
- **GIVEN** 一条 agent 回复处于进行中
- **WHEN** 整个节点失联、无法发出任何终态反馈
- **THEN** IM 的 idle 看门狗在静默窗口后仍把该回复兜底翻为失败,避免其永久停在进行中
