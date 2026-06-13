# gateway (personal_assistant) Specification

> 对齐: bugfix-404-M3
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本契约层只收 Gateway **对外可观察的行为**——
> 消费者 = 在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的
> 运维者。每条 Scenario 的主语 = 这些外部消费者;Gateway 内部如何把 channel / pipeline / scheduler /
> kernel 接起来不在此层(那在代码 + 归档 design)。跨包架构(包职责、依赖方向、部署拓扑)在
> [`../../SPEC.md`](../../SPEC.md)。

## Purpose

`personal_assistant`(Node Gateway)是个人助手产品的**常驻进程节点网关**:把外部 IM / 内置 Web IM 的入站
消息路由到正确的 Agent、进程内持有 `agent` 内核(经 `agent.sdk`)执行、把结果回发原通道,并跑本地
heartbeat / cron 两套主动机制、与可选的中心 IM 服务做配置同步与状态上报。它运行在用户机器上,通常在 NAT 后面。

它对外承担的可观察职责:① 终端用户在任一通道发消息能被正确的 Agent 处理、回复回到原通道原目标;
② 群聊只在被 @提及 / 回复 Agent / 控制命令时才触发 Agent;③ 运维者用启停命令把它当后台服务管理;
④ IM 服务在线时它主动连出、注册节点、周期心跳、同步配置、中继 Web IM 消息;⑤ IM 服务离线时外部 IM
主路径仍可用(本地自治);⑥ 进程重启后会话映射自动恢复,错过的 heartbeat / cron 周期不补跑回填。

**显式不负责**:不实现 Agent Loop、不直接调 LLM、不管会话持久化(都由内核负责);不做全局用户/组织
管理(IM 服务负责);不提供终端 CLI 交互(coding_cli 负责)。它**只经 `agent.sdk`** 持有内核,禁止
import 内核内部(由 `tests/contract/` 把守)。

## Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道(外部 IM 或内置 Web IM)收到一条入站消息时,Gateway 依次决策:路由到哪个 Agent、用哪个会话、
是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标,不跨通道混发。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway,且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent(显式 `agent_id` → channel/chat 绑定 → 节点默认 Agent),交内核执行,
  最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话串行、跨会话并行
- **GIVEN** 同一会话已有一轮在执行,另有一条属于不同会话的消息同时到达
- **WHEN** 两条消息先后进入 Gateway
- **THEN** 同一会话的消息排进串行 FIFO 队列、前一轮结束后才消费下一条;不同会话的消息并行推进,互不阻塞

#### Scenario: 静默运行失败后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行,但持续 120 秒没有任何内核事件,后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败,随后消费后一条消息,不得让该会话永久阻塞

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

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 以后台常驻进程运行,启动命令尽快返回;`stop` / `restart` 按配置定位并管理该进程;
显式 `--foreground` 仅作 debug/高级模式。单实例 PID 锁防止对同一 config 重复启动。`stop`/`restart`
必须先停止新入站、heartbeat、cron 和 dispatch 生产者,再收拢内核运行,最后关闭 IM/channel 资源;
进行中的操作进入明确终态,终态事件有机会完成投递;关闭阶段的次要错误不得覆盖导致进程退出的最早
真实错误。

#### Scenario: 默认启动后台常驻并尽快返回
- **WHEN** 运维者执行 `python -m personal_assistant.main`(无子命令)
- **THEN** Gateway 在脱离的子进程中后台启动,主命令打印 pid / 健康提示 / 日志路径后尽快返回,
  进程转入常驻服务态

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的后台 Gateway
- **WHEN** 运维者对同一 config 再次发起后台启动
- **THEN** 启动被拒,提示「gateway is already running (pid=…)」并指引先 `stop` 或 `restart`

#### Scenario: stop 终止后台 Gateway 并清理状态
- **WHEN** 运维者执行 `... main stop`
- **THEN** 对应后台进程被优雅终止(超时则升级 SIGKILL),PID/状态文件被清理;若本无运行则报「NOT RUNNING」,
  状态陈旧则报「STALE」

#### Scenario: stop 收拢活动运行后终止 Gateway
- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作,活动操作进入明确终态,内核 Task 被收拢后进程退出,
  日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误
- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因;任何资源关闭失败只作为次要诊断,不替换首因

### Requirement: IM 服务在线时 Gateway 主动连出并保持双向通信

Gateway 始终**主动**向 IM 服务发起 WebSocket 持久连接(因其在 NAT 后,不能被反向连接)。连接上后注册节点、
周期发心跳;经该连接接收下行的 Web IM 消息中继、配置同步、Agent 创建/能力解析、手动 heartbeat 触发。

#### Scenario: 连接后注册节点并周期心跳
- **GIVEN** 配置了 IM 服务地址
- **WHEN** Gateway 启动并连上 IM 服务 WebSocket
- **THEN** 首帧发 `node.register`(携带 node_id、agent 列表与 `agent_workspaces`——agent_id →
  本地 config 解析出的绝对 workspace_root 映射,供 IM 首次落库种子使用;重连重发同帧内容一致),
  随后在线期间周期发 `node.heartbeat`(含 `node_id` / `status=online` / `agent_count`),
  IM 服务据此刷新节点状态

#### Scenario: runtime workspace_root 以本地 config 为准,IM 镜像值不进入 runtime
- **GIVEN** IM 中某 agent profile 的 workspace_root 为路径 A,Gateway 本地 config 为路径 B
- **WHEN** Gateway 同步 agent 配置并处理该 agent 的会话(含 heartbeat)
- **THEN** session / heartbeat 实际读写路径 B,路径 A 不被读写;其余配置字段(system_prompt /
  skills / tool_allowlist / features / custom_prompt 等)仍以 IM 镜像为准同步

#### Scenario: IM 推送 agent.create 时在节点落地工作区并回非空 workspace_root
- **WHEN** IM 服务经下行请求在本节点创建一个 Agent
- **THEN** Gateway 在本地建该 Agent 工作区、注册进 live 路由,并在回包中返回非空 `workspace_root`(绝对
  路径);该 Agent 配置写回本地持久化 config

#### Scenario: IM 请求当前 Agent 配置时返回 live 快照
- **WHEN** IM 服务请求某 Agent 的当前配置
- **THEN** Gateway 返回该 Agent 的 live 配置快照(display_name / system_prompt / skills / tool_allowlist /
  group_reply_policy / default_model / workspace_root / features / custom_prompt)

#### Scenario: IM 经 RPC 请求读取 HEARTBEAT.md 预览内容（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.heartbeat.md.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/HEARTBEAT.md`，回帧 `node.heartbeat.md`（含 content；文件不存在则 content 为空串）；
  IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）

#### Scenario: IM 经 RPC 请求列出 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.jobs.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/.nanoassistant/cron/jobs.json`，回帧 `node.cron.jobs`（含 jobs 列表；文件不存在则 jobs 为空列表）

#### Scenario: IM 经 RPC 请求删除某条 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.delete.request`（含 agent_id / workspace_root / job_id）
- **THEN** Gateway 从 `jobs.json` 中移除匹配 job_id 的条目并回写，回帧 `node.cron.delete`（含 deleted: true/false）；
  job_id 不存在时 deleted 为 false，不报错

### Requirement: 断线后自动重连并补发未确认帧,期间外部 IM 主路径不受影响

WebSocket 断开后 Gateway 自动重连(指数退避,有上限),重连后重发 `node.register`;断开前未收到 ack 的
上行帧在重连后补发,不丢消息。断线期间外部 IM 主路径(通道 → Gateway → 内核)仍可用。

#### Scenario: 重连后补发断线前未确认的帧
- **GIVEN** 一帧 `node.report` 已发出但 socket 在收到 ack 前断开
- **WHEN** Gateway 重连成功
- **THEN** 新连接上先发 `node.register`、再补发那帧 `node.report`,原 payload 不变

#### Scenario: 重连采用指数退避并封顶
- **WHEN** IM 服务持续不可达,Gateway 反复重连
- **THEN** 重连间隔按指数退避增长直到上限(不无限激增、不放弃)

#### Scenario: IM 离线时外部 IM 主路径仍可用
- **GIVEN** IM 服务不可达
- **WHEN** 外部通道来一条入站消息
- **THEN** 该消息照常走通道 → Gateway → 内核 → 回发,Agent 执行不受 IM 离线影响(本地自治)

### Requirement: 首次连新 IM 实例时支持自动确认节点绑定

Gateway 首次连一个尚无 owner 的 IM 节点时需确认绑定。默认打开浏览器让运维者点确认;设
`NANO_MULTIAGENT_AUTO_BIND=1`(或 `--auto-bind`)时 Gateway 自动发确认请求完成绑定,不开浏览器(供
自动化 / CI / e2e)。节点已有 owner 时跳过绑定。

#### Scenario: 设置 auto-bind 后无浏览器自动完成绑定
- **GIVEN** 节点在 IM 侧尚无 owner,且 `NANO_MULTIAGENT_AUTO_BIND=1`
- **WHEN** Gateway 启动并注册该节点
- **THEN** Gateway 自动向 IM 发 `action=confirm` 的绑定请求完成绑定,不打开浏览器

#### Scenario: 未设 auto-bind 时打开浏览器引导绑定
- **GIVEN** 节点尚无 owner,且未设 `NANO_MULTIAGENT_AUTO_BIND`
- **WHEN** Gateway 启动并注册该节点
- **THEN** Gateway 打开绑定 URL 的浏览器,并提示运维者完成绑定

#### Scenario: 节点已绑定时跳过绑定流程
- **WHEN** Gateway 启动时该节点在 IM 侧已有 owner
- **THEN** 不打开浏览器、不发起绑定,直接进入就绪

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

Gateway 提供两套**相互独立**的本地主动行为机制,均完全在本地调度(IM 服务不作调度源),各自由 IM 配置页上
一个 per-agent 开关启停(配置经 IM→Gateway 同步生效):

- **Heartbeat**:周期性"带上下文"唤醒。携带该 Agent 与 owner 的 canonical 直聊上下文。**顶层节律
  (多久唤醒一次)来自 agent 配置 `heartbeat.every`(未配置默认 30m),不来自 HEARTBEAT.md**;
  `HEARTBEAT.md`(Agent 可经对话自管写入)承载任务内容:freeform 任务清单 + 可选 `tasks:` 块的 per-task
  独立频率子节律。活跃时段(activeHours)限制来自配置;无可冒泡内容时回 `HEARTBEAT_OK` 静默、不打扰用户。
- **Cron**:无上下文的定时任务。可挂多条,各在隔离 session 执行(不带对话上下文),由 Agent 经 cron 工具自管
  (注册/查看/删除)。结果文本回发 owner 的 canonical 直聊;用户可就该结果追问,Agent 记得自己汇报过什么。

两套机制**均不补跑积压**:停机/空闲错过多个周期后,恢复只推进到最近一次边界触发一次(不刷屏回填);
已过期的一次性(`at`)任务恢复后不补跑。

Cron 的定时触发和 Agent 手动触发具有同一执行语义:同样的 Kernel 提交、IM 投递、运行历史和
canonical-session awareness;手动触发只改变触发时机并立即返回入队确认。手动触发请求按发起请求的
Agent 身份路由——多 Agent 并存、Agent 在运行期新建、或请求来自 heartbeat / cron 隔离会话时均路由
到正确 Agent,互不串扰。运行历史必须区分 trigger,记录 accepted/running/terminal 状态、Kernel run、
目标会话、结果或错误;仅有最近一次调度时间不构成运行历史。Gateway 关闭时已入队的 cron 投递在 IM
连接关闭前完成收拢。

#### Scenario: 未启用的 Agent 两套机制都不跑
- **GIVEN** 某 Agent 的 heartbeat 与 cron 开关均关闭
- **WHEN** 调度器周期 tick 或工具运行发生
- **THEN** 不为该 Agent 创建任何 heartbeat / cron 运行,cron 工具不获得可用手动运行能力

#### Scenario: 手动运行已有 cron 任务立即入队
- **GIVEN** 某 Agent 已启用 cron,且 workspace 中存在目标 job
- **WHEN** Agent 的 cron 工具请求立即运行该 job
- **THEN** Gateway 校验后接管请求,工具立即返回 accepted 与请求标识,不等待模型任务执行完成

#### Scenario: 手动 cron 与定时 cron 使用同一执行语义
- **WHEN** 手动入队的 cron job 执行完成
- **THEN** 结果按该 job 原规则投递到目标会话、记录运行历史,并写入 canonical session awareness,
  后续用户追问可引用该结果

#### Scenario: 查询 cron 运行历史
- **WHEN** Agent 查询某 job 的运行历史
- **THEN** Gateway 返回手动和定时触发的最新结构化记录,包含触发来源、状态、时间、结果或错误,
  不只返回 scheduler 的 `last_due_at`

#### Scenario: 手动运行未知或不可运行任务
- **WHEN** cron 工具请求不存在或未启用的 job
- **THEN** Gateway 在创建 isolated session 前拒绝请求并返回明确错误,不执行其他任务

#### Scenario: Heartbeat 有内容时带上下文主动冒泡
- **GIVEN** 某 Agent 的 heartbeat 已启用,且当前 tick 有可冒泡内容
- **WHEN** 调度器到点触发该 Agent 的 heartbeat
- **THEN** 在该 Agent 与 owner 的 canonical 直聊里像普通 Agent 消息一样发出,且能引用此前的对话上下文

#### Scenario: Heartbeat 无可行动任务时安静跳过
- **GIVEN** 某 Agent 的 `HEARTBEAT.md` 当前 tick 无可冒泡内容
- **WHEN** 调度器到点触发该 Agent 的 heartbeat
- **THEN** 不发任何用户可见消息(回 `HEARTBEAT_OK` 静默)

#### Scenario: 活跃时段外不唤醒
- **GIVEN** 某 Agent 的 heartbeat 配了 activeHours,当前时刻落在窗口外
- **WHEN** 调度器周期 tick
- **THEN** 不触发该 Agent 的 heartbeat,不打扰用户

#### Scenario: 同一 Agent 多条 cron 任务各自按时触发
- **GIVEN** 某 Agent 挂了多条不同节律的 cron 任务
- **WHEN** 各任务到点
- **THEN** 每条任务独立触发并把各自结果发回 canonical 直聊,互不干扰

#### Scenario: 周期任务错过多个周期不刷屏回填
- **GIVEN** 一个固定间隔的 heartbeat/cron 在 Gateway 停机或空闲期间错过了多个周期
- **WHEN** 调度器恢复
- **THEN** 只在最近一次边界触发一次,不为每个错过的周期各补跑一次

#### Scenario: 过期的一次性任务不补跑
- **GIVEN** 一个一次性(`at`)cron/heartbeat 的触发时刻在 Gateway 停机期间已过
- **WHEN** Gateway 重启后调度器恢复
- **THEN** 该任务被视为错过窗口、不补跑(已执行过的同样不重复)

#### Scenario: Cron 汇报后用户追问,Agent 记得汇报内容
- **GIVEN** 某 Agent 的 cron 任务已执行并把结果发回 canonical 直聊
- **WHEN** 用户在该直聊就此结果追问
- **THEN** Agent 的回复能引用刚发出的 cron 汇报内容(该结果对后续对话轮次可见)

#### Scenario: Heartbeat 顶层节律由配置决定,忽略 HEARTBEAT.md 顶层 every
- **GIVEN** 某 Agent 配置 `heartbeat.every=10m`,其 HEARTBEAT.md 顶层又写了 `every: 15s`
- **WHEN** 调度器评估该 Agent 的 heartbeat 顶层节律
- **THEN** 按 10m 触发;HEARTBEAT.md 顶层 `every:` 不生效(未配置则按默认 30m)

#### Scenario: Agent 配置变更在活连接即时生效,无需重启 Gateway
- **GIVEN** Gateway 与 IM 活连接,owner 在配置页关闭某 Agent 的 heartbeat
- **WHEN** 该变更经 IM→Gateway 同步到达
- **THEN** Gateway 无需重启,数个 tick 内停止该 Agent 的 heartbeat(enable/cadence 等配置变更同理即时生效)

#### Scenario: 断连期间的配置变更在重连对账时收敛
- **GIVEN** Gateway 断连期间 owner 改了某 Agent 的 enable / cadence(增量同步未送达)
- **WHEN** Gateway 重连 IM 并完成全量对账
- **THEN** 该 Agent 的调度行为收敛到 IM 当前真值

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定，能力特性按 requires_tool 联动其工具

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时
Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；为空时取
产品默认工具集（未配置语义）。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动
已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的
`tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 未配置 allowlist 的 Agent 拿到产品默认工具集
- **GIVEN** 某 Agent 的 `tool_allowlist` 为空
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集 = 产品默认工具集

#### Scenario: 启用 cron 能力使 cron 工具进入该 Agent 工具集
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="cron"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `cron` 工具；停用 cron 能力则 `cron` 工具随之移出

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
