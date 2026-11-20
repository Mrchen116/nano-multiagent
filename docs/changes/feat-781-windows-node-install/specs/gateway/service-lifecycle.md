# Gateway Service Lifecycle Specification (delta for feat-781)

## ADDED Requirements

### Requirement: Windows 受管电脑按当前用户的登录自启设置运行

#### Scenario: 默认登录和异常退出恢复
- **GIVEN** 用户已绑定 Windows 10 或 11 x64 电脑，使用默认自启设置。
- **WHEN** 用户重新登录原 Windows 账号，或登录期间后台程序意外退出且故障消失。
- **THEN** 原电脑在网络可用时恢复在线，原助手可以继续回复；关闭安装窗口不影响后台运行。

#### Scenario: 停止和关闭登录自启
- **WHEN** 用户主动停止后台程序。
- **THEN** 程序保持停止至用户再次启动，或在仍启用自启时重新登录。
- **WHEN** 用户关闭并应用登录自启设置，重启并登录。
- **THEN** 原电脑保持离线，用户可以手动启动，继续使用原绑定和工作区。设置应用失败时能看到实际状态及恢复操作。

### Requirement: Windows 受管电脑复用已经下载的运行环境

#### Scenario: 仅应用变更的更新
- **GIVEN** 已安装的运行环境完整可用，IM 选择的新 Windows 版本继续使用相同内容。
- **WHEN** 用户更新电脑端。
- **THEN** 新应用使用既有运行环境，用户只需下载有变化的应用内容及版本说明、校验所需的小型文件。

## MODIFIED Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

默认启动让 Gateway 在后台运行并尽快返回；macOS 与受管 Windows x64 电脑根据 `gateway.autostart` 选择当前用户
登录服务或普通后台进程，其余平台保持普通后台进程。`stop` / `restart` 按配置定位并
管理该进程；显式 `--foreground` 仅作 debug/高级模式。单实例状态防止对同一 config
重复启动。`stop`/`restart` 必须先停止新入站、heartbeat、cron 和 dispatch 生产者，
再收拢内核运行，最后关闭 IM/channel 资源；进行中的操作进入明确终态，终态事件有机会
完成投递；关闭阶段的次要错误不得覆盖导致进程退出的最早真实错误。启动命令等待 Node 与 DSH 初始化和持久恢复完成，并写入 PID、process birth、ready 和 runtime_pid；通道连接仍由日志与 IM 节点状态呈现。

#### Scenario: 默认启动后台运行并尽快返回
- **WHEN** 运维者执行 `pnpm pa`（无子命令）
- **THEN** Gateway 根据当前平台和已应用配置在登录服务或普通后台进程中启动，命令确认 Node 与 DSH 完成初始化和持久恢复后打印 pid、IM service 状态和日志路径并返回
- **AND** macOS 与受管 Windows x64 电脑额外明确显示登录自启的应用状态，其他平台保持既有普通后台启动反馈
- **AND** 运行时 readiness 由 `status` 和状态文件呈现，通道连接由 `gateway.log` 或 IM 节点状态呈现

#### Scenario: 重复启动被单实例锁拦下
- **GIVEN** 某 config 已有一个存活的 Gateway
- **WHEN** 运维者对同一 config 再次发起默认启动
- **THEN** 启动被拒，提示 Gateway 已运行；需替换时先 `stop` 或使用 `restart`
- **AND** 本次命令不替换运行实例，也不宣称配置变更已经应用

#### Scenario: stop 终止 Gateway 并清理当前运行状态
- **WHEN** 运维者执行 `pnpm pa stop`
- **THEN** 对应 Gateway 先优雅停止。超时后 Unix 升级 SIGKILL，Windows 强制收拢已核实归属的进程树并确认其全部退出，随后清理运行状态文件并报告 `STOPPED`；没有所属活动实例时也完成停止，`status` 返回 `NOT RUNNING`
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
