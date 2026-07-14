# gateway service-lifecycle Specification (delta for refactor-461)

## MODIFIED Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 以后台常驻进程运行,启动命令尽快返回;`stop` / `restart` 按配置定位并管理该进程;
显式 `--foreground` 仅作 debug/高级模式。单实例 PID 锁防止对同一 config 重复启动。`stop`/`restart`
必须先停止新入站、heartbeat、cron 和 dispatch 生产者,再收拢内核运行,最后关闭 IM/channel 资源;
进行中的操作进入明确终态,终态事件有机会完成投递;关闭阶段的次要错误不得覆盖导致进程退出的最早
真实错误。默认启动的 parent 只确认后台 child 已写入 PID 且仍存活,不把该启动确认表述为 Kernel health
或 Gateway runtime/channel readiness。

#### Scenario: 默认启动后台常驻并尽快返回
- **WHEN** 运维者执行 `python -m personal_assistant.main`(无子命令)
- **THEN** Gateway 在脱离的子进程中后台启动,主命令确认 child 已写入 PID 且仍存活后打印
  `Gateway started (pid=...)` / 日志路径,并在已配置时单独打印 IM service 状态后尽快返回
- **AND** 该确认不承诺 runtime/channel 已 ready,也不输出或探测 Kernel health/readiness endpoint

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

## ADDED Requirements

### Requirement: Gateway 生命周期 timing 由 Gateway 配置拥有并单向迁移旧值

Gateway 后台启动、停止和轮询使用的 timing 必须属于 `gateway:` 配置。系统必须继续读取旧 `kernel:` mapping 中三项仍有 Gateway 语义的 timing，以逐字段单向迁移保护既有自定义配置；旧 Kernel 连接、command 与 HTTP health 字段不得形成运行时输入。首次保存会裁掉旧 `kernel:` 的任意现存 config 前，系统必须先为该文件创建不可覆盖的迁移前备份。

#### Scenario: 旧自定义 timing 继续作用于 Gateway

- **GIVEN** 配置只在 `kernel:` mapping 中设置 `startup_timeout_seconds`、`shutdown_grace_seconds` 或 `health_poll_interval_seconds`
- **WHEN** Gateway 加载该配置并执行后台启动或停止
- **THEN** 三项值分别作用于 Gateway 的启动等待、关闭宽限和轮询间隔
- **AND** 系统不因此启动或连接独立 Kernel 进程

#### Scenario: 新 Gateway 配置逐字段优先

- **GIVEN** 同一配置同时含 `gateway:` timing 与旧 `kernel:` timing
- **WHEN** Gateway 加载配置
- **THEN** `gateway:` 中明确提供的字段优先
- **AND** `gateway:` 中未提供的字段才从对应旧字段迁移

#### Scenario: 保存配置后使用 canonical Gateway schema

- **GIVEN** Gateway 从含旧 `kernel:` mapping 的配置成功加载
- **WHEN** 现有配置同步流程保存该配置
- **THEN** 系统先在 config 同目录创建内容等于迁移前原文件的不可覆盖 backup
- **AND** 非默认生命周期 timing 写入 `gateway:` mapping
- **AND** 旧 `kernel:` mapping 不再写回
- **AND** backup 创建或校验失败时原 config 不被覆盖

#### Scenario: 旧连接和 HTTP 字段不再生效

- **GIVEN** 旧 `kernel:` mapping 含 `base_url`、认证信息、request id、HTTP timeout、`command` 或 `health_path`
- **WHEN** Gateway 加载并运行
- **THEN** 这些字段不被验证，也不影响 Gateway 构建进程内 Kernel
- **AND** Gateway 的 start、stop 与 restart 不依赖 Kernel HTTP endpoint
