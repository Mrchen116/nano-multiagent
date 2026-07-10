# gateway (personal_assistant) - Relay Protocol Specification

> 对齐: feat-447
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

Gateway 与 IM 之间工具调用、附件、终态收口、图片、授权、用量、思考和 fork 委托的中继契约。

## Requirements

### Requirement: Gateway 中继工具调用时执行中即转发参数侧展示

Gateway 把内核工具调用事件中继给 IM 时,工具开始执行的中继帧携带 presenter 在该阶段产出的参数侧展示:
`summary` 经 `output` 字段转发,参数侧 `detail` 原样转发;工具执行结束的中继帧携带含结果的完整展示。
Gateway 纯透传 presenter 字段,不按工具语义增删。

#### Scenario: 工具执行中的中继帧携带参数侧展示
- **GIVEN** 一个其 presenter 在执行开始即产出 presentation 的工具被调用
- **WHEN** Gateway 中继该工具的 `tool_start` 事件给 IM
- **THEN** `tool_call_upserted` 帧携带 presenter 的 `summary`(写入 `output`)与参数侧 `detail`
- **AND** presenter 在执行开始未产出 `detail` 的工具,该帧不含 `detail`

#### Scenario: 工具执行结束的中继帧携带完整展示
- **GIVEN** 同一工具调用执行结束
- **WHEN** Gateway 中继该工具的 `tool_end` 事件给 IM
- **THEN** `tool_call_completed` 帧携带 presenter 的 `summary`(写入 `output`)与含结果的完整 `detail`

### Requirement: 通道中继去重并把多媒体附件透传给内核

Web IM 中继通道对收到的 relay 帧去重(SQLite 落盘,跨重启生效),避免同一消息重复处理;通道把图片等附件
解析为标准结构透传进内核入站,不内置 ASR/OCR 等业务解析。

#### Scenario: 重复 relay 帧只处理一次
- **GIVEN** 中继通道已处理过某 relay 帧
- **WHEN** 同一去重键的 relay 帧再次到达(含进程重启后)
- **THEN** 该帧被去重丢弃,不二次进入入站流水线

#### Scenario: 附件随入站消息透传
- **WHEN** relay 帧携带图片附件
- **THEN** 通道把附件 url(及可选 content_type)放入入站消息元数据,随消息提交给内核,通道层不做内容解析

### Requirement: run 进入终态时对在飞 tool_call 按原因收口

run 进入失败/取消终态(含 idle 看门狗收尸路径)时,Gateway 必须对该轮所有仍处于 running 的 tool_call
经原通道下发一个终态,并标注中断原因,使消费者侧不再有工具停留在「运行中」。中断原因区分两类:工具因自身
deadline(如命令 `timeout`)到点被掐 → 标「执行超时」(耗时过长);run 因 idle 看门狗 liveness 收尸或进程
异常/中断 → 标「已中断」(卡死/中断)。已完成的 tool_call 终态不被改写。

#### Scenario: 工具自身 deadline 命中后在飞工具收口为执行超时
- **GIVEN** 某轮有一个设了自身超时的工具(如带 `timeout` 的命令)已开始执行(已发 tool_start)
- **WHEN** 该工具到达自身 deadline 被掐
- **THEN** 该工具经原通道收到终态,原因标注为「执行超时」,区别于「已中断」

#### Scenario: 看门狗 liveness 收尸后在飞工具收口为已中断
- **GIVEN** 某轮有一个工具已开始执行(已发 tool_start)但该轮在判定窗口内无任何 liveness 心跳
- **WHEN** 该轮被 idle 看门狗判定失去进展并收尸
- **THEN** 该在飞工具经原通道收到终态,原因标注为「已中断」,不再停留运行中

#### Scenario: 异常终止后在飞工具收口为已中断
- **GIVEN** 某轮有在飞工具,run 因进程异常/中断进入终态(非看门狗超时)
- **WHEN** run 进入终态
- **THEN** 该在飞工具经原通道收到终态,原因标注为「已中断」

#### Scenario: 已完成工具不被收口逻辑改写
- **GIVEN** 同一轮里其他工具已正常完成(含执行出错但已返回结果的)
- **WHEN** run 进入终态做在飞工具收口
- **THEN** 这些已完成工具的终态保持不变

#### Scenario: 在飞工具收口仍保留其原始调用参数
- **GIVEN** 某轮有一个工具在飞,其开始执行时已带出原始调用参数(如 bash 的命令与 description)
- **WHEN** run 进入终态对该在飞工具收口(看门狗超时或异常终止)
- **THEN** 下发的终态仍携带该工具的原始调用参数(仅状态改为失败 + 标注原因),消费者据此能看出
  是哪条命令被中断,而非只剩工具名

### Requirement: 用户经 IM 发送的图片被 Agent 看到，且在后续轮次仍可追问

用户在 IM 会话里给 agent 发送图片时，agent 当轮即能基于图片内容作答；在同一会话的后续轮次，用户即便只发文字追问那张图，agent 仍能据其作答。异常图片不致中断会话，图片触发模型错误后会话仍可继续。

#### Scenario: 发图即问，当轮可答
- **WHEN** 用户在一条消息里同时发送一张图片和关于该图的问题
- **THEN** agent 当轮基于图片内容作答，而非表示看不到图

#### Scenario: 上一轮发图，下一轮只发文字仍可追问
- **GIVEN** 用户上一轮发过图片并得到基于该图的回复
- **WHEN** 用户在同一会话下一轮只发文字追问这张图
- **THEN** agent 仍能基于上一轮那张图作答

#### Scenario: 异常图片本轮停下、明确告知用户、可重发
- **WHEN** 用户发送一张异常（超大 / 损坏 / 无法获取）的图片
- **THEN** 本轮即以明确提示作答，说明这张图未送达模型及原因和可操作建议（如换小图重发）
- **AND** 本轮不产生模型对该图的回答（不让 agent 对未送达的图片编造内容），会话不崩溃，用户可重新发送

#### Scenario: 图片触发模型错误后会话仍可继续
- **GIVEN** 用户发送的图片导致了一次模型调用出错
- **WHEN** 用户在同一会话后续发送文字消息
- **THEN** agent 正常回复该文字，会话未因那张图持续失败（不会每轮都因这张图卡住）

### Requirement: Gateway 向 IM 中继的工具调用携带授权决策

Gateway 把内核工具执行事件中继到 IM 时，除既有的 reason 徽标 / emoji / presentation detail 外，
一并透传「该工具调用是否经用户显式授权/拒绝」的标识；自动放行的调用不携带。

#### Scenario: 经用户授权的工具调用被中继
- **WHEN** 内核报出一次经用户允许的工具调用执行
- **THEN** Gateway 中继给 IM 的该工具调用数据携带「经用户授权允许」标识

#### Scenario: 经用户拒绝的工具调用被中继
- **WHEN** 内核报出一次经用户拒绝的工具调用
- **THEN** Gateway 中继的该工具调用数据携带「经用户拒绝」标识

### Requirement: 缓存使用量随 token 用量中继到 IM

#### Scenario: 一轮回复带缓存命中
- **WHEN** 一轮带缓存命中的助手回复经 Gateway 中继
- **THEN** IM 收到的该轮 token 用量里包含命中缓存的输入量与总输入量（不被 Gateway 丢弃）

### Requirement: 整轮多段思考按时序中继到 IM

#### Scenario: 含多段思考的一轮回复
- **WHEN** 一轮带多段思考的助手回复经 Gateway 中继（含只思考、不输出正文的回合）
- **THEN** IM 收到的该轮消息包含全部思考段，且每段带可还原其与工具调用时序的次序信息

#### Scenario: 只思考不输出正文的回合
- **WHEN** 某回合只产生思考、没有正文
- **THEN** 其思考作为该轮过程的一部分中继到 IM，且不因此产生一条空正文消息

#### Scenario: 既无正文也无思考的回合
- **WHEN** 某回合既无正文也无思考
- **THEN** 不向 IM 中继该回合（不产生空消息）

### Requirement: Gateway 受 IM 委托对某 agent 会话按 fork 点 fork 出独立新会话

IM 不持有 conversation↔session 映射、也不直读 Gateway 侧会话日志，故「让分支单聊的 agent 记得历史」由 Gateway 受委托完成。Gateway 收到 IM 的 fork 请求后：复制**源会话在指定 fork 点那一刻所用的上下文视图**（源若已压缩则含当时的压缩摘要；未压缩则为到 fork 点的完整内容），生成一个独立的新会话，并把请求里的新 conversation 预绑定到该新会话——之后该新会话的首条入站消息命中预绑定、agent 带着「与源在 fork 点时一致」的记忆回复。新会话独立：对它的后续追加不回流源会话。

#### Scenario: 受委托 fork 后新会话带源在 fork 点的记忆
- **GIVEN** 一个已有多轮对话的 agent 会话，IM 经 WS RPC 请求对它在某 agent 回复处 fork 出新 conversation
- **WHEN** Gateway 处理该 fork 请求
- **THEN** Gateway 生成一个新会话，其上下文 = 源会话在该 fork 点那一刻所用的视图；新 conversation 被绑定到该新会话；该会话首条入站消息复用此绑定、不另建空会话
- **AND** 用户在新 conversation 继续对话时，agent 表现出对这段历史的记忆

#### Scenario: fork 复刻源在 fork 点的上下文（含压缩态），与源体验一致
- **GIVEN** 源会话在 fork 点之前曾发生过上下文压缩（喂模型时历史被摘要替代）
- **WHEN** Gateway 受委托 fork 该会话到该 fork 点
- **THEN** 新会话复制的是源在该 fork 点的视图（含当时已生效的压缩摘要），与源在该点的记忆一致——不还原压缩前的完整原始历史（不比源记得更多），也不丢失源当时已有内容

#### Scenario: fork 点之后的源历史不进入新会话、两会话独立
- **GIVEN** fork 点之后源会话还有更晚的对话
- **WHEN** fork 完成后用户在新会话与源会话各自继续对话
- **THEN** 新会话不含 fork 点之后的源历史；两会话各自独立演进，互不影响对方记忆

#### Scenario: fork 失败回包让 IM 可回滚
- **GIVEN** Gateway 处理 fork 请求时失败（如源会话绑定缺失、内核 fork 出错）
- **WHEN** Gateway 回复该 WS RPC
- **THEN** 回包标明失败，IM 据此回滚已建的新 conversation；Gateway 不留下半成品绑定
