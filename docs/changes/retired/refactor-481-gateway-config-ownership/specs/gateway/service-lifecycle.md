# Gateway service lifecycle delta — refactor-481

> 本 delta 对 `docs/specs/gateway/service-lifecycle.md` 增量描述 single-writer lifecycle、
> runtime endpoint overlay 与 remote-committed token rotation。
> unit 收尾时按实现证据并入 canonical。

## ADDED Requirements

### Requirement: 运行时 IM endpoint override 不改变持久配置

运维者用 `--im-service-url` 指定的 IM endpoint 只作用于本次 Gateway 进程。Gateway 在该
进程内发生 token refresh、Agent 创建/编辑或其他本地配置写回时，必须以 durable snapshot
为基线，不能把 runtime endpoint 写进 YAML。停止后不带 override 再启动，应恢复使用 YAML
原有 endpoint。

#### Scenario: override 期间的 durable update 不污染 YAML
- **GIVEN** `config.yaml` 的 `im_service.url` 为 A
- **WHEN** 运维者以 `--im-service-url B` 启动 Gateway，并在运行期间触发 token refresh
  或 Agent 配置写回
- **THEN** 当前进程连接 B
- **AND** 写回后的 `config.yaml` 仍保存 A

#### Scenario: 无 override 重启恢复 durable endpoint
- **GIVEN** 上一次进程以 runtime endpoint B 运行，durable YAML endpoint 始终为 A
- **WHEN** 运维者停止 Gateway 并在不传 `--im-service-url` 时重新启动
- **THEN** 新进程连接 A，不继承上一次的 B

### Requirement: IM rotating credential 以远端提交为准并安全镜像到本地

IM 服务成功返回新 access/refresh pair 时，旧 refresh token 已被撤销；Gateway 必须把新 pair
视为当前进程不可回退的连接事实。本地 YAML 是该事实的 durable mirror：写失败可以重试，但
不得让当前进程重新使用已撤销的旧 pair。

#### Scenario: 远端 rotation 成功但本地写入 pre-commit 失败
- **GIVEN** Gateway 已从 IM refresh 获得新 pair，IM 已拒绝旧 refresh token
- **WHEN** 新 pair 写入本地配置时发生 pre-commit failure
- **THEN** 当前 Gateway 保留新 pair，并用它完成当前或下一次 IM reconnect
- **AND** Gateway 日志明确显示本地 credential mirror 待重试，不把旧 durable pair 恢复为
  当前凭据

#### Scenario: 存活进程补齐最新 credential mirror
- **GIVEN** 新 pair 已在当前进程生效，但本地 mirror 仍 pending
- **WHEN** 本地配置恢复可写，或后续 reconnect/config reconcile 触发重试
- **THEN** YAML 最终保存当前最新 pair；更早 generation 的迟到重试不能覆盖它

#### Scenario: mirror 完成前进程退出
- **GIVEN** 远端 rotation 已成功，但进程退出前本地 mirror 始终失败
- **WHEN** Gateway 再次启动
- **THEN** 配有 username/password 时可重新 login 并恢复连接
- **AND** token-only 配置在旧 refresh token 被拒后给出可操作的重新认证错误，不把远端
  rotation 误报为已回滚，也不以同一失效 token 无限热重试

## MODIFIED Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 以后台常驻进程运行，启动命令尽快返回；`stop` / `restart` 按配置定位并
管理该进程；显式 `--foreground` 仅作 debug/高级模式。每个 resolved config 的 foreground
runtime（无论 spawned child 还是 direct `--foreground`）必须先取得同一 config-scoped lifetime
writer lease；未取得者在打开可写配置 owner或执行 workspace/channel bootstrap 前退出。
`stop`/`restart` 必须先停止新入站、heartbeat、cron 和 dispatch 生产者，再收拢内核运行，最后
关闭 IM/channel 资源；进行中的操作进入明确终态，终态事件有机会完成投递；关闭阶段的次要错误
不得覆盖导致进程退出的最早真实错误。后台 parent 只确认 child 已写入 PID + process birth 且
仍存活；runtime/channel readiness 由日志和 IM 节点状态呈现。

#### Scenario: 默认启动后台常驻并尽快返回
- **WHEN** 运维者执行 `python -m personal_assistant.main`（无子命令）
- **THEN** Gateway 在脱离的子进程中后台启动，主命令确认 child 已写入 PID + process birth
  且仍存活后打印 pid / 本次 effective IM service / 日志路径并尽快返回
- **AND** runtime/channel readiness 由 `gateway.log` 或 IM 节点状态呈现

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的后台 Gateway
- **WHEN** 运维者对同一 config 再次发起后台启动
- **THEN** 启动被拒，提示「gateway is already running (pid=…)」并指引先 `stop` 或 `restart`
- **AND** 被拒进程不改 YAML bytes/mtime 或 workspace 文件树，不发起 Feishu identity probe、
  owner bind 或 skill provisioning

#### Scenario: foreground 与 background 共用同一 writer lease
- **GIVEN** 某 resolved config 已有一个存活的 background child 或 direct foreground Gateway
- **WHEN** 另一个 direct foreground 或 background child 竞争同一 config
- **THEN** 只有 lease holder 进入 runtime；loser 报告 holder PID，且 config/workspace 文件
  不变、不发起 Feishu probe/provision

#### Scenario: stop 终止后台 Gateway 并清理状态
- **WHEN** 运维者执行 `... main stop`
- **THEN** 对应后台进程被优雅终止（超时则升级 SIGKILL），PID/状态文件被清理；若本无运行则报
  「NOT RUNNING」，状态陈旧则报「STALE」

#### Scenario: start stop restart 对同一 config 串行
- **WHEN** 同一 config 的多个 lifecycle 命令并发执行
- **THEN** 命令经同一个 config-scoped lock 串行化，且 `restart` 在一次持锁期间完成 stop + start

#### Scenario: stop 只向已证明的进程实例发信号
- **GIVEN** `.gateway-state.json` 记录 PID、resolved config 和 process birth
- **WHEN** 运维者执行 `stop`
- **THEN** 每次发信号前重新核对 PID 的 live birth，不向已复用该 PID 的无关进程发信号
- **AND** 旧状态缺少 birth 时，仅在 live command 精确属于
  `personal_assistant.main --config <同一 resolved config> ... --foreground` 后采纳当前 birth
- **AND** command 不匹配或观察期间 birth 改变时 fail closed，不发信号并保留旧证据

#### Scenario: stop 收拢活动运行后终止 Gateway
- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作，活动操作进入明确终态，内核 Task 被收拢后进程退出，
  日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误
- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因；任何资源关闭失败只作为次要诊断，不替换首因
