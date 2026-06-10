# Gateway Specification (delta for bugfix-402)

## MODIFIED Requirements

### Requirement: 运维者用启停命令把 Gateway 当后台服务管理

Gateway 默认可作为后台常驻服务启动，使用持久化 config 和单实例 PID 锁。`stop`/`restart`
必须先停止新入站、heartbeat、cron 和 dispatch 生产者，再收拢内核运行，最后关闭 IM/channel
资源。Gateway 必须异步等待 Kernel 和自己拥有的 run-stream/delivery consumer，不得在主 event
loop 直接执行阻塞式 Kernel close。进行中的操作进入明确终态；关闭阶段的次要错误不得覆盖导致
进程退出的最早真实错误。项目提供的 e2e 停止脚本也必须先等待 Gateway grace shutdown，再停止
其依赖的 IM 服务，只有 Gateway 超时不退出时才强制终止。

#### Scenario: 默认启动后台常驻并尽快返回

- **WHEN** 运维者运行 `python -m personal_assistant.main`
- **THEN** 启动器创建后台 Gateway、写入 PID 状态并尽快返回，Gateway 使用持久化 config 运行

#### Scenario: 重复启动被单实例锁拦下

- **GIVEN** 同一 config 的 Gateway 已在运行
- **WHEN** 运维者再次启动
- **THEN** 新进程明确报告已运行，不创建第二套 worker

#### Scenario: stop 收拢活动运行后终止 Gateway

- **GIVEN** Gateway 有活动 Agent run 或权限等待
- **WHEN** 运维者执行 `stop` 或 `restart`
- **THEN** Gateway 停止生产新工作，活动操作进入明确终态，内核 Task 被收拢后进程退出，
  日志不出现 ContextVar cross-Context 二次异常

#### Scenario: 真实故障在关闭后仍是主要错误

- **WHEN** Gateway 因运行故障进入关闭流程
- **THEN** 日志保留原始首因；任何资源关闭失败只作为次要诊断，不替换首因

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

Heartbeat 是带 canonical 对话上下文的周期巡检；Cron 是可挂多条、在隔离 session 执行的无上下文
任务。两者由各自 per-agent feature 控制。Cron 的定时触发和 Agent 手动触发必须进入同一个
Gateway execution service，复用 Kernel 提交、IM 投递、运行历史和 canonical-session awareness；
手动触发只改变触发时机并立即返回入队确认。运行历史必须区分 trigger，记录
accepted/running/terminal 状态、Kernel run、目标会话、结果或错误；scheduler 的 last-due 状态不
得冒充运行历史。

#### Scenario: 手动运行已有 cron 任务立即入队

- **GIVEN** 某 Agent 已启用 cron，且 workspace 中存在目标 job
- **WHEN** Agent 的 cron 工具请求立即运行该 job
- **THEN** Gateway 校验后接管请求，工具立即返回 accepted 与请求标识，不等待模型任务执行完成

#### Scenario: 手动 cron 与定时 cron 使用同一执行语义

- **WHEN** 手动入队的 cron job 执行完成
- **THEN** 结果按该 job 原规则投递到目标会话、记录运行历史，并写入 canonical session awareness，
  后续用户追问可引用该结果

#### Scenario: 查询 cron 运行历史

- **WHEN** Agent 查询某 job 的运行历史
- **THEN** Gateway 返回手动和定时触发的最新结构化记录，包含触发来源、状态、时间、结果或错误，
  不只返回 scheduler 的 `last_due_at`

#### Scenario: 手动运行未知或不可运行任务

- **WHEN** cron 工具请求不存在或未启用的 job
- **THEN** Gateway 在创建 isolated session 前拒绝请求并返回明确错误，不执行其他任务

#### Scenario: 未启用的 Agent 两套机制都不跑

- **GIVEN** 某 Agent 的 heartbeat 与 cron 开关均关闭
- **WHEN** polling tick 或工具运行发生
- **THEN** 不为该 Agent 创建 heartbeat/cron run，cron 工具不获得可用手动运行能力

#### Scenario: Cron 汇报后用户追问,Agent 记得汇报内容

- **GIVEN** 某 Agent 的定时或手动 cron 任务已执行并把结果发回 canonical 直聊
- **WHEN** 用户在该直聊追问任务结果
- **THEN** Agent 的回复能引用刚发出的 cron 汇报内容
