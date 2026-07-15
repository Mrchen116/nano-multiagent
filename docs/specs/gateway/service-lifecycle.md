# gateway (personal_assistant) - Service Lifecycle Specification

> 对齐: refactor-461
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

后台服务管理、IM 长连接、断线恢复和节点绑定的 Gateway 契约。

## Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 以后台常驻进程运行,启动命令尽快返回;`stop` / `restart` 按配置定位并管理该进程;
显式 `--foreground` 仅作 debug/高级模式。单实例 PID 锁防止对同一 config 重复启动。`stop`/`restart`
必须先停止新入站、heartbeat、cron 和 dispatch 生产者,再收拢内核运行,最后关闭 IM/channel 资源;
进行中的操作进入明确终态,终态事件有机会完成投递;关闭阶段的次要错误不得覆盖导致进程退出的最早
真实错误。后台 parent 只确认 child 已写入 PID + process birth 且仍存活；runtime/channel readiness
由日志和 IM 节点状态呈现。

#### Scenario: 默认启动后台常驻并尽快返回
- **WHEN** 运维者执行 `python -m personal_assistant.main`(无子命令)
- **THEN** Gateway 在脱离的子进程中后台启动,主命令确认 child 已写入 PID + process birth 且仍
  存活后打印 pid / IM service 状态 / 日志路径并尽快返回
- **AND** runtime/channel readiness 由 `gateway.log` 或 IM 节点状态呈现

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的后台 Gateway
- **WHEN** 运维者对同一 config 再次发起后台启动
- **THEN** 启动被拒,提示「gateway is already running (pid=…)」并指引先 `stop` 或 `restart`

#### Scenario: stop 终止后台 Gateway 并清理状态
- **WHEN** 运维者执行 `... main stop`
- **THEN** 对应后台进程被优雅终止(超时则升级 SIGKILL),PID/状态文件被清理;若本无运行则报「NOT RUNNING」,
  状态陈旧则报「STALE」

#### Scenario: start stop restart 对同一 config 串行
- **WHEN** 同一 config 的多个 lifecycle 命令并发执行
- **THEN** 命令经同一个 config-scoped lock 串行化,且 `restart` 在一次持锁期间完成 stop + start

#### Scenario: stop 只向已证明的进程实例发信号
- **GIVEN** `.gateway-state.json` 记录 PID、resolved config 和 process birth
- **WHEN** 运维者执行 `stop`
- **THEN** 每次发信号前重新核对 PID 的 live birth,不向已复用该 PID 的无关进程发信号
- **AND** 旧状态缺少 birth 时,仅在 live command 精确属于
  `personal_assistant.main --config <同一 resolved config> ... --foreground` 后采纳当前 birth
- **AND** command 不匹配或观察期间 birth 改变时 fail closed,不发信号并保留旧证据

#### Scenario: stop 收拢活动运行后终止 Gateway
- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作,活动操作进入明确终态,内核 Task 被收拢后进程退出,
  日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误
- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因;任何资源关闭失败只作为次要诊断,不替换首因

### Requirement: Gateway lifecycle timing 由 Gateway 配置拥有

后台启动、停止和轮询只读取 `gateway:` 下的 lifecycle timing。

#### Scenario: 加载 Gateway lifecycle timing
- **GIVEN** config 提供 `gateway.startup_timeout_seconds`、
  `gateway.shutdown_grace_seconds` 或 `gateway.poll_interval_seconds`
- **WHEN** Gateway 加载配置
- **THEN** 对应 timing 用于后台启动、停止或轮询
- **AND** 未提供的字段使用 Gateway 默认值

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
