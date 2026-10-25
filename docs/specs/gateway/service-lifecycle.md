# gateway (personal_assistant) - Service Lifecycle Specification

> 对齐: feat-596
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

同源首次安装、空节点设置、后台服务管理、IM 长连接、断线恢复和节点绑定的 Gateway 契约。

## Requirements

### Requirement: macOS Gateway 的登录自启意图和稳定运行环境由本地配置拥有

`gateway.autostart` 选择 Gateway 是否在当前 macOS 用户登录后自动运行，缺省值为
`true`；`gateway.environment` 提供手工后台运行和登录自启共同使用的稳定运行环境。
配置变更只在下一次有效启动或 `restart` 时应用，显式 `--foreground` 不修改登录服务。

#### Scenario: 缺省配置默认开启登录自启
- **GIVEN** macOS Gateway 配置没有写 `gateway.autostart`
- **WHEN** 运维者在 Gateway 已停止时执行默认启动，或执行 `restart`
- **THEN** Gateway 在当前用户的登录服务下运行，启动结果明确显示登录自启和意外退出恢复已启用

#### Scenario: 显式开启登录自启
- **GIVEN** macOS Gateway 配置设置 `gateway.autostart: true`
- **WHEN** 运维者在 Gateway 已停止时执行默认启动，或执行 `restart`
- **THEN** Gateway 在当前用户的登录服务下运行，启动结果明确显示登录自启和意外退出恢复已启用

#### Scenario: 显式关闭登录自启
- **GIVEN** macOS Gateway 配置设置 `gateway.autostart: false`
- **WHEN** 运维者在 Gateway 已停止时执行默认启动，或执行 `restart`
- **THEN** 当前 Gateway 仍以普通后台方式运行，启动结果明确显示登录自启已关闭
- **AND** 当前用户下一次登录时不会因此配置自行启动 Gateway

#### Scenario: 登录自启关闭未完整应用时不虚报成功
- **GIVEN** macOS Gateway 配置设置 `gateway.autostart: false`
- **WHEN** 运维者执行有效的默认启动或 `restart`，但原登录服务无法停止或其持久定义无法删除
- **THEN** 命令返回非零且不显示登录自启已关闭
- **AND** 产品不启动可能与旧登录服务竞争的普通后台 Gateway

#### Scenario: 只编辑配置不改变当前运行方式
- **WHEN** 运维者修改 `gateway.autostart`，但尚未在停止状态执行默认启动或执行 `restart`
- **THEN** 当前 Gateway 的运行方式保持不变，产品不把尚未应用的配置显示为已生效

#### Scenario: 配置环境在两种后台模式中保持一致
- **GIVEN** 配置提供一个或多个 `gateway.environment` 字符串键值
- **WHEN** Gateway 经普通后台模式或 macOS 登录服务启动
- **THEN** Gateway 运行时及其子进程都使用这些配置值，且配置值优先于同名的启动进程环境
- **AND** 登录服务定义和启动反馈不复制或显示这些配置值
- **AND** 本次显式 CLI 控制优先于同名配置环境，不能被配置静默取消
- **AND** 未显式配置 `PATH` 时，macOS 登录服务仍可发现系统目录及 Homebrew 常用目录中的命令

#### Scenario: 持久代理配置作用于真实网络客户端
- **GIVEN** `gateway.environment` 显式启用 `NODE_USE_ENV_PROXY=1` 并提供 HTTP/HTTPS 代理及 NO_PROXY
- **WHEN** Gateway 应用配置后发出 HTTP、原生 fetch 或通道 WebSocket 请求
- **THEN** 公网请求使用配置的代理，包括配置应用前已经初始化的原生客户端
- **AND** NO_PROXY 匹配的本机/内网请求直连，工具子进程继承同一环境
- **AND** 配置代理不可用时请求明确失败，不静默降级公网直连

### Requirement: 启用登录自启的 macOS Gateway 由系统保持运行

#### Scenario: 用户登录后自动运行
- **GIVEN** Gateway 已成功应用登录自启
- **WHEN** 对应 macOS 用户进入新的登录会话
- **THEN** 无需手工执行 Gateway 命令，Gateway 自动运行并恢复节点与消息入口

#### Scenario: Gateway 意外退出后自动恢复
- **GIVEN** 启用登录自启的 Gateway 正在运行
- **WHEN** Gateway 进程意外退出
- **THEN** macOS 自动启动新的 Gateway 进程，Gateway 随后恢复节点与消息入口

#### Scenario: 人工停止只暂停当前登录会话
- **GIVEN** Gateway 已成功应用登录自启
- **WHEN** 运维者执行 `stop`
- **THEN** Gateway 在当前登录会话中保持停止，不被立即自动拉起
- **AND** 若 `gateway.autostart` 仍为 `true`，下一次登录仍会自动运行

### Requirement: 登录自启应用失败时 Gateway 降级运行并如实失败

#### Scenario: 登录服务应用失败后降级为普通后台进程
- **GIVEN** macOS Gateway 配置要求启用登录自启
- **WHEN** 运维者执行有效的默认启动或 `restart`，但登录服务定义、加载或启动确认失败
- **THEN** 产品先确保没有残留的受管 Gateway，再以普通后台方式运行一个 Gateway
- **AND** 启动结果同时显示 Gateway 当前已运行、登录自启和意外退出恢复未生效，以及可供排查的原始错误
- **AND** 命令返回非零退出码，使自动化不会把降级运行误判为完整成功

### Requirement: Gateway 的默认本机 home 与默认 Agent workspace 有唯一归属

Gateway 的默认本机 config、持久状态和全局 extensions 归入 `~/.nanoassistant/`；未显式指定 workspace 的 Agent 创建在 `~/.nanoassistant/workspaces/<agent-id>/`。本地 config 中显式的 `agents[].workspace_root` 或 `node.workspace_base` 仍优先，外部代码仓不被移动。

#### Scenario: 未指定 workspace 的 Agent 落到默认产品 home
- **WHEN** Gateway 创建一个未显式提供 workspace_root 的 Agent
- **THEN** 回报并使用 `~/.nanoassistant/workspaces/<agent-id>/` 作为其本机 workspace

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 在后台运行并尽快返回；macOS 根据 `gateway.autostart` 选择当前用户
登录服务或普通后台进程，其他平台保持普通后台进程。`stop` / `restart` 按配置定位并
管理该进程；显式 `--foreground` 仅作 debug/高级模式。单实例状态防止对同一 config
重复启动。`stop`/`restart` 必须先停止新入站、heartbeat、cron 和 dispatch 生产者，
再收拢内核运行，最后关闭 IM/channel 资源；进行中的操作进入明确终态，终态事件有机会
完成投递；关闭阶段的次要错误不得覆盖导致进程退出的最早真实错误。启动命令等待 Node 与 DSH 初始化和持久恢复完成，并写入 PID、process birth、ready 和 runtime_pid；通道连接仍由日志与 IM 节点状态呈现。

#### Scenario: 默认启动后台运行并尽快返回
- **WHEN** 运维者执行 `pnpm pa`（无子命令）
- **THEN** Gateway 根据当前平台和已应用配置在登录服务或普通后台进程中启动，命令确认 Node 与 DSH 完成初始化和持久恢复后打印 pid、IM service 状态和日志路径并返回
- **AND** macOS 额外明确显示登录自启的应用状态，其他平台保持既有普通后台启动反馈
- **AND** 运行时 readiness 由 `status` 和状态文件呈现，通道连接由 `gateway.log` 或 IM 节点状态呈现

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的 Gateway
- **WHEN** 运维者对同一 config 再次发起默认启动
- **THEN** 启动被拒，提示 Gateway 已运行；需替换时先 `stop` 或使用 `restart`
- **AND** 本次命令不替换运行实例，也不宣称配置变更已经应用

#### Scenario: stop 终止 Gateway 并清理当前运行状态
- **WHEN** 运维者执行 `pnpm pa stop`
- **THEN** 对应 Gateway 被优雅终止（超时则升级 SIGKILL），运行状态文件被清理并报告 `STOPPED`；没有所属活动实例时也完成停止，`status` 返回 `NOT RUNNING`
- **AND** 对登录服务管理的 Gateway，当前登录会话中的自动重拉同时停止

#### Scenario: stop 无法停止登录服务时不越过失败
- **GIVEN** 当前 Gateway 由 macOS 登录服务管理
- **WHEN** 运维者执行 `stop`，但产品无法从当前登录会话停止该服务
- **THEN** 命令返回非零且不报告 Gateway 已停止
- **AND** 产品不再单独终止进程或启动替代实例，保留当前运行状态供继续排查

#### Scenario: start stop restart 对同一 config 串行
- **WHEN** 同一 config 的多个 lifecycle 命令并发执行
- **THEN** 命令经同一个 config-scoped lock 串行化，且 `restart` 在一次持锁期间完成 stop、应用目标运行方式和 start

#### Scenario: stop 只向已证明的进程实例发信号
- **GIVEN** `.gateway-state.json` 记录 PID、resolved config 和 process birth
- **WHEN** 运维者执行 `stop`
- **THEN** 每次发信号前重新核对 PID 的 live birth，不向已复用该 PID 的无关进程发信号
- **AND** 状态缺少 birth、config 不匹配或 live birth 改变时 fail closed，不发信号并保留证据；首次跨运行时迁移先正常停止旧版本，不借旧 PID 自动采纳新身份

#### Scenario: stop 收拢活动运行后终止 Gateway
- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作，活动操作进入明确终态，内核 Task 被收拢后进程退出，日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误
- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因；任何资源关闭失败只作为次要诊断，不替换首因

### Requirement: 高成本低 prompt cache 命中模型调用留下可定位告警

Gateway 每次模型调用独立观察已归一的总输入 token 与缓存读取 token；当 provider 明确报告缓存命中数据、总输入超过 30,000 且缓存命中率低于 80% 时，在既有 `gateway.log` 写一条 warning。warning 固定包含 model、agent_id、session_id、input_tokens、cache_read_tokens 与 cache_hit_rate_percent，不包含 prompt 或用户文本；阈值不提供额外配置。没有 `agent_id` 的非 Gateway 运行、缓存字段未返回、总输入不超过 30,000 或命中率不低于 80% 时不写此 warning。

#### Scenario: 运维者从 warning 定位高成本缓存未命中会话
- **GIVEN** Gateway 的某次模型调用返回总输入 30,001 token 和 `cache_read_tokens=0`
- **WHEN** 该次调用结束
- **THEN** `gateway.log` 出现低 prompt cache 命中 warning，包含该调用的 model、agent_id、session_id、input_tokens、cache_read_tokens 与 cache_hit_rate_percent
- **AND** 运维者可用 `agent_id + session_id` 定位该 Agent workspace 下对应 `.nanoassistant/sessions/<session_id>.jsonl`
- **AND** warning 不包含该次调用的 prompt 或用户文本

#### Scenario: 缓存数据未知或无需告警时保持静默
- **WHEN** provider 未返回缓存读取字段，或某次调用的总输入不超过 30,000，或缓存命中率不低于 80%
- **THEN** Gateway 不为该次调用写低 prompt cache 命中 warning

### Requirement: Gateway lifecycle timing 由 Gateway 配置拥有

后台启动、停止和轮询只读取 `gateway:` 下的 lifecycle timing。

#### Scenario: 加载 Gateway lifecycle timing
- **GIVEN** config 提供 `gateway.startup_timeout_seconds`、`gateway.shutdown_grace_seconds` 或 `gateway.poll_interval_seconds`
- **WHEN** Gateway 加载配置
- **THEN** 对应 timing 用于后台启动、停止或轮询
- **AND** 未提供的字段使用 Gateway 默认值

### Requirement: IM 服务在线时 Gateway 主动连出并保持双向通信

Gateway 始终**主动**向 IM 服务发起 WebSocket 持久连接(因其在 NAT 后,不能被反向连接)。连接上后注册节点、周期发心跳;经该连接接收下行的 Web IM 消息中继、配置同步、Agent 创建/能力解析、手动 heartbeat 触发。

#### Scenario: 连接后注册节点并周期心跳
- **GIVEN** 配置了 IM 服务地址
- **WHEN** Gateway 启动并连上 IM 服务 WebSocket
- **THEN** 首帧发 `node.register`(携带 node_id、agent 列表与四组 per-agent 种子映射——`agent_workspaces` / `agent_workspace_is_default` / `agent_skills` / `agent_tool_allowlist`；均为 agent_id → 本地 config 解析值的映射，供 IM 在首次落库时建立 profile；其中 workspace root/provenance 是 Gateway 对本机状态的声明，IM 不自行推导；对由 IM `agent.create` 创建且仍持久化 create operation 的 Agent，另带 `agent_create_operations` 映射；重连重发同帧内容一致), 随后在线期间周期发 `node.heartbeat`(含 `node_id` / `status=online` / `agent_count`), IM 服务据此刷新节点状态

#### Scenario: register ACK 是业务发送门禁且握手有界
- **GIVEN** Gateway transport 已连上 IM，但 `node.register` 尚未被确认
- **WHEN** register send 阻塞、IM 不返回 ACK 或明确拒绝该 control frame
- **THEN** Gateway 在默认 10 秒 handshake deadline 内断开该 socket并进入有界 reconnect backoff，期间不发送业务 FIFO
- **AND** ACK 一旦收到即开放业务发送并结束 handshake deadline；随后的配置收敛 callback 不被该 deadline 取消

#### Scenario: runtime workspace_root 以本地 config 为准,IM 镜像值不进入 runtime
- **GIVEN** IM 中某 agent profile 的 workspace_root 为路径 A,Gateway 本地 config 为路径 B
- **WHEN** Gateway 同步 agent 配置并处理该 agent 的会话(含 heartbeat)
- **THEN** session / heartbeat 实际读写路径 B,路径 A 不被读写;其余公开配置字段(Custom Instructions / skills / tool_allowlist / features 等)仍以 IM 镜像为准同步

#### Scenario: IM 推送 agent.create 时在节点落地工作区并回非空 workspace_root
- **WHEN** IM 服务经下行请求在本节点创建一个 Agent
- **THEN** Gateway 在本地建该 Agent 工作区、注册进 live 路由,并在回包中返回非空 `workspace_root`(绝对路径);该 Agent 配置写回本地持久化 config

#### Scenario: 节点能力提供默认 workspace 路径模板
- **WHEN** IM 请求 `node.capabilities`
- **THEN** Gateway 复用默认 workspace resolver 返回 canonical `default_workspace_template`，Agent ID
  位置保留为 `{agent_id}` 占位符
- **AND** 该模板只供创建页展示；默认 `agent.create` 仍在 Gateway 本机重新解析最终路径

#### Scenario: IM 创建 operation 由 Gateway 原样持久化并回显
- **GIVEN** 下行 `agent.create` 携带 `create_operation_id` X
- **WHEN** Gateway 成功持久化新 Agent
- **THEN** 本地 Agent config 保存 X，`agent.created` 回包携带同一 X，之后的 `node.register` 在
  `agent_create_operations` 为该 Agent 广告 X
- **AND** Gateway 对同一 Agent 的恢复式 `agent.create` 仅接受同一 X；不同或缺失 X 不得把既有
  Agent 变为新的创建结果

#### Scenario: IM 请求当前 Agent 配置时返回 live 快照
- **WHEN** IM 服务请求某 Agent 的当前配置
- **THEN** Gateway 返回该 Agent 的 live 配置快照(display_name / skills / tool_allowlist / group_reply_policy / default_model / workspace_root / features / custom_prompt)，其中 `custom_prompt` 是唯一公开的 Agent 专属说明字段

#### Scenario: IM 经 RPC 请求读取 HEARTBEAT.md 预览内容（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.heartbeat.md.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/.nanoassistant/HEARTBEAT.md`，回帧 `node.heartbeat.md`（含 content；文件不存在则 content 为空串）；IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）

#### Scenario: IM 经 RPC 请求列出 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.jobs.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/.nanoassistant/cron/jobs.json`，回帧 `node.cron.jobs`（含 jobs 列表；文件不存在则 jobs 为空列表）

#### Scenario: IM 经 RPC 请求删除某条 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.delete.request`（含 agent_id / workspace_root / job_id）
- **THEN** Gateway 从 `jobs.json` 中移除匹配 job_id 的条目并回写，回帧 `node.cron.delete`（含 deleted: true/false）；job_id 不存在时 deleted 为 false，不报错

### Requirement: 断线后自动重连且保持投递与权限边界

临时连接失败、心跳超时或服务关闭后，Gateway 自动重连（指数退避、有上限），使用仍有效的凭据重新注册并恢复新消息收发；明确撤权或账户停用终止自动重连。连接层将未确认的在途帧结算为投递结果未知，将未发送帧结算为未发送，不自行重放或建立离线业务队列。已有 PA 业务持久恢复按其自身契约处理，不由传输层推断业务成功或自动重复副作用。注册 ACK 后的节点绑定和 Agent 配置收敛在后台运行,不得占住业务收发路径;控制面工作失败仅保留诊断,不使已连接 Gateway 失去中继能力。业务帧等待远端 IM ACK 使用 10 秒默认上限,不得因正常的跨机往返延迟而主动断线。断线期间外部 IM 主路径(通道 → Gateway → 内核)仍可用。

#### Scenario: 重连不盲目重放未确认业务帧
- **GIVEN** 一帧 `conversation.query` 已发出但 socket 在收到 ack 前断开
- **WHEN** Gateway 重连成功
- **THEN** 新连接先注册；连接层不自动重放那帧 conversation.query，调用方收到投递结果未知并按自身持久化契约处理。

#### Scenario: 慢控制面收敛不阻塞已恢复的业务中继
- **GIVEN** Gateway 已收到 `node.register` ACK，但节点绑定或 IM 上的 Agent 配置读取缓慢或暂时失败
- **WHEN** 用户随后经 Web IM 发送消息，或 Gateway 上行一条业务帧
- **THEN** 该消息与业务帧仍在既有连接上继续中继
- **AND** 控制面收敛在后台继续；失败只留下可诊断日志，不关闭该连接

#### Scenario: 正常远端 ACK 延迟不触发重连
- **GIVEN** Gateway 已向远端 IM 发送一条业务帧
- **WHEN** IM 在超过 1 秒、但未超过默认 10 秒业务 ACK 上限时确认该帧
- **THEN** Gateway 接受该 ACK 并维持当前连接，不把这次延迟当作断线重连

#### Scenario: 重连采用指数退避并封顶
- **WHEN** IM 服务持续不可达,Gateway 反复重连
- **THEN** 重连间隔按指数退避增长直到上限(不无限激增、不放弃)

#### Scenario: control rejection 与普通断线使用同一退避
- **WHEN** IM 以 protocol error 拒绝 `node.register` 或 `node.heartbeat`
- **THEN** Gateway 断开当前 socket，结算在途及排队帧，并在下一次连接前执行既有指数退避
- **AND** backoff 只在新连接的 register ACK 后重置，不能因 transport connect 成功但注册失败而形成热循环

#### Scenario: send yield 内到达的匹配响应不会丢失
- **GIVEN** 一帧已经取得唯一 wire owner 并对 transport 可见，但本地 `send()` coroutine 尚未返回
- **WHEN** IM 在该窗口返回匹配 ACK、channel result 或 generic error
- **THEN** Gateway 把响应结算给同一 owner且只结算一次；wrong type/request 不释放 owner，后继 FIFO 不会永久阻塞

#### Scenario: IM 离线时外部 IM 主路径仍可用
- **GIVEN** IM 服务不可达
- **WHEN** 外部通道来一条入站消息
- **THEN** 该消息照常走通道 → Gateway → 内核 → 回发,Agent 执行不受 IM 离线影响(本地自治)

#### Scenario: 临时中断后无需人工干预
- **WHEN** 休眠或网络中断后连接条件恢复且授权有效
- **THEN** 节点无需重启、重新绑定或登录即可重新上线；用户新发送的消息可获得 Agent 回复。

#### Scenario: 权限终止
- **WHEN** 节点被撤权或账户停用
- **THEN** 节点停止自动重连，不继续接收业务消息。

### Requirement: 首次连新 IM 实例时支持自动确认节点绑定

Gateway 首次连一个尚无 owner 的 IM 节点时需确认绑定。默认打开浏览器让运维者点确认;设 `NANO_MULTIAGENT_AUTO_BIND=1`(或 `--auto-bind`)时 Gateway 自动发确认请求完成绑定,不开浏览器(供自动化 / CI / e2e)。节点已有 owner 时跳过绑定。

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

### Requirement: 节点产品与执行运行时状态分别可观察且由节点统一管理

#### Scenario: 启动后区分在线和可执行
- **WHEN** 个人助手节点启动并连接IM，但执行运行时尚未就绪
- **THEN** 状态如实区分渠道在线与Agent可执行，不把接收连接成功当作模型已可工作；就绪后既有个人助手入口可用。

#### Scenario: 执行运行时退出后恢复
- **WHEN** 执行运行时退出而节点产品仍可运行
- **THEN** 保留已接收业务输入、发送回执和真实中断状态；受管恢复后新会话按正确数字人配置恢复，不能把未知结果伪装成成功或盲目重放副作用。

#### Scenario: 停止所属进程
- **WHEN** 运维者停止该节点
- **THEN** 停止新的工作接收/派发并收拢节点管理的运行时和子任务，保留需要恢复的业务事实，不停止其他节点或无关进程。

#### Scenario: 旧Coding CLI退役
- **WHEN** 用户安装最终迁移版本并查看启动入口
- **THEN** 个人助手启停、IM管理和客户端入口继续可用，旧自研Coding CLI不再作为产品入口或运行依赖。

#### Scenario: 部署更新后持久运行状态加载当前版本
- **GIVEN** 运维者保留节点的持久运行状态并更新代码或锁定依赖
- **WHEN** 从目标部署版本启动 Gateway
- **THEN** DSH 加载该部署的插件与依赖，不沿用旧 checkout 的依赖链接
- **AND** 既有会话、工作区与身份不因路径修复被删除
- **AND** 受管依赖入口被同名普通文件或目录占用时，明确失败并保留其内容

### Requirement: 电脑端可在模型与助手为空时上线设置

安装器连接已有 IM，自动准备当前用户目录中的运行依赖与私有配置，不要求部署 IM 或手写 YAML。节点绑定后可在未配模型、未建 Agent 时保持出站连接并接收设置操作；重复安装保留配置与数据。

#### Scenario: 空节点
- WHEN 用户首次安装并确认绑定
- THEN 无需预先配置模型即可在页面看见电脑并开始配置；不会伪造已可执行的助手。

#### Scenario: 重复与失败
- WHEN 安装重跑或下载/依赖步骤失败
- THEN 保留现有节点和数据，显示继续/恢复方法，不切换到未准备好的版本。

### Requirement: 受管电脑按一次明确授权安全切换固定版本

#### Scenario: 准备和切换
- **WHEN** 用户发起该电脑更新
- **THEN** 电脑下载并校验服务指定版本，完整准备成功且现有任务安全结束后才切换；关闭网页不取消已授权更新。

#### Scenario: 失败与数据保留
- **WHEN** 更新失败或用户在切换前取消
- **THEN** 保留身份、模型、助手、聊天和文件；下载失败不停止旧程序，新程序启动失败尝试恢复原版本，恢复结果如实可见。

#### Scenario: 新旧安装与重复运行
- **WHEN** 首次安装，或旧用户按一次性指引升级，或用户重复执行安装入口
- **THEN** 受管安装具备后续按钮更新能力，不重建现有身份和配置；相同版本复用，版本切换不因旧进程在线被误报成功。

### Requirement: Agent 停用终止全部受管执行并持续禁止唤醒

#### Scenario: 停止整个 Agent
- **WHEN** 主人停用 Agent
- **THEN** 立即禁止新执行，并停止跨聊天主会话、所有层级子 Agent、前后台 Bash、持久终端及其他受管后台工作
- **AND** 不等待模型决定是否停止，其他独立 Agent 继续工作
- **AND** 按 DSH 的平台受管范围确认清理，未确认全部停止时不能报告已停用

#### Scenario: 自动输入与恢复
- **GIVEN** Agent 被停用
- **WHEN** 收到消息、提及、Task、Heartbeat、Schedule、子任务回报或自动恢复信号
- **THEN** 均不能启动模型或工具，不能补发旧输出；停用跨节点重启和重连保持

#### Scenario: 节点离线时请求停用
- **WHEN** 节点尚未收到停用请求
- **THEN** 中心保留意图并阻断新的中心路由，明确等待节点确认；重连时先应用停用后处理普通恢复

#### Scenario: 保留记录和管理能力
- **WHEN** Agent 已停用或全部 Agent 均停用
- **THEN** 已有工作记录和历史仍按原权限可读，生命周期、模型设置及已保存普通配置等不需执行的管理仍可用，读取历史不唤醒 Agent
- **AND** 依赖执行的插件操作与能力探测保留最近已知信息并明确不可执行，不为读取临时启动停用 Agent

#### Scenario: 旧共享运行数据升级
- **GIVEN** 节点仍使用旧共享运行目录
- **WHEN** 启动采用独立 Agent 进程的新版本
- **THEN** 明确要求先停止旧服务并完成离线迁移的规划、执行和校验；普通启动不扫描复制全部历史，不自动拆分数据
- **AND** 迁移保留原始源数据，校验成功后才发布新目录布局；进程拓扑以仓库 `SPEC.md` 为权威

#### Scenario: 已提交的外部动作
- **WHEN** 停用前外部系统已经接受动作，或进程已超出 DSH 可管理范围
- **THEN** 保留真实结果或未知状态，不把停止描述成副作用回滚；不扩展到其他独立 Agent 或远端服务
