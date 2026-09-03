# gateway service-lifecycle Specification (delta for feat-542)

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 在后台运行并尽快返回；macOS 根据 `gateway.autostart` 选择当前用户
登录服务或普通后台进程，其他平台保持普通后台进程。`stop` / `restart` 按配置定位并
管理该进程；显式 `--foreground` 仅作 debug/高级模式。单实例状态防止对同一 config
重复启动。`stop`/`restart` 必须先停止新入站、heartbeat、cron 和 dispatch 生产者，
再收拢内核运行，最后关闭 IM/channel 资源；进行中的操作进入明确终态，终态事件有机会
完成投递；关闭阶段的次要错误不得覆盖导致进程退出的最早真实错误。启动命令只确认
Gateway 已写入 PID + process birth 且仍存活；runtime/channel readiness 由日志和 IM
节点状态呈现。

#### Scenario: 默认启动后台运行并尽快返回
- **WHEN** 运维者执行 `python -m personal_assistant.main`（无子命令）
- **THEN** Gateway 根据当前平台和已应用配置在登录服务或普通后台进程中启动，命令确认 Gateway 已写入 PID + process birth 且仍存活后打印 pid、IM service 状态和日志路径并尽快返回
- **AND** macOS 额外明确显示登录自启的应用状态，其他平台保持既有普通后台启动反馈
- **AND** runtime/channel readiness 由 `gateway.log` 或 IM 节点状态呈现

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的 Gateway
- **WHEN** 运维者对同一 config 再次发起默认启动
- **THEN** 启动被拒，提示「gateway is already running (pid=…)」并指引先 `stop` 或 `restart`
- **AND** 本次命令不替换运行实例，也不宣称配置变更已经应用

#### Scenario: stop 终止 Gateway 并清理当前运行状态
- **WHEN** 运维者执行 `... main stop`
- **THEN** 对应 Gateway 被优雅终止（超时则升级 SIGKILL），PID/状态文件被清理；若本无运行则报「NOT RUNNING」，状态陈旧则报「STALE」
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
- **AND** 旧状态缺少 birth 时，仅在 live command 精确属于 `personal_assistant.main --config <同一 resolved config> ... --foreground` 后采纳当前 birth
- **AND** command 不匹配或观察期间 birth 改变时 fail closed，不发信号并保留旧证据

#### Scenario: stop 收拢活动运行后终止 Gateway
- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作，活动操作进入明确终态，内核 Task 被收拢后进程退出，日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误
- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因；任何资源关闭失败只作为次要诊断，不替换首因

## REMOVED Requirements

无。
