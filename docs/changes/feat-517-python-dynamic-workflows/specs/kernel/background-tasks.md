# kernel (agent) - Background Tasks Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠

后台 bash / subagent / Workflow 任务自然终态后，发起它的 session 在下一轮输入中收到一条 `<task-notification>`，内含任务结果；消费者无需轮询即可感知。该通知在任意 workspace_root 下均可靠送达，不因 session 绑定非默认工作区而丢失。同步前台工具的结果只经 tool result 返回，不额外发 notification；只有真正转为后台后的任务才走一次通知通路。

对后台 subagent 与 Workflow，消费者经 `Kernel.stream()` 还能在“哪一轮消费了该 notification”的事件上取得与 XML 同源的结构化后台返回，包含 task 类型/身份、terminal status、原始 result 或 error、usage、duration 与 artifact locator。parent 有 active run 时它跟随实际消费该 pending message 的 round boundary；parent idle 时它跟随为该 notification 新建的 BACKGROUND_TASK-origin run。两条路径都不得只保留文本或把返回归到会话中最新的其他回复。后台 bash 的结构化 Web 展示不在本 requirement 增量范围内。

#### Scenario: 非默认 workspace 下后台任务完成通知送达
- **GIVEN** 一个绑定非默认 workspace_root 的 session 启动了后台任务
- **WHEN** 任务完成
- **THEN** 该 session 下一轮输入含一条带任务结果的 `<task-notification>` 消息

#### Scenario: 前台命令完成只走 tool result，不发通知
- **GIVEN** 某 session 执行一条前台 bash 命令（未声明 `run_in_background`），且在前台预算内完成、失败或自身超时
- **WHEN** 消费者消费该 run 的结果
- **THEN** 该命令的结果只经其 tool result 同步返回
- **AND** 该 session 后续输入中不含针对该命令的 `<task-notification>`

#### Scenario: 前台命令超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 执行一条前台 bash 命令，运行时长超出前台预算被 auto-background
- **WHEN** 该命令稍后在后台完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`，不重复、不遗漏

#### Scenario: 前台 subagent 在预算内完成只走 tool result，不发通知
- **GIVEN** 某 session 经 `agent` 工具派发一个前台子 agent，且在前台预算内完成
- **WHEN** 子 agent 跑完一轮返回
- **THEN** 父 session 只经该 `agent` 工具的 tool result 同步取得结果文本
- **AND** 后续输入和 stream event 都不含针对该执行的后台 notification / return sidecar

#### Scenario: 前台 subagent 超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 派发的前台子 agent 运行时长超出系统默认前台预算被 auto-background（其 tool result 返回 `async_launched` + agent_id）
- **WHEN** 该子 agent 稍后完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）
- **AND** 消费者无法通过 `agent` 工具参数自定义该前台预算

#### Scenario: 后台 subagent 的 XML 与结构化返回同源
- **GIVEN** 某 session 派发 `Agent(run_in_background=true)`，或前台 subagent 超预算后真正转入后台
- **WHEN** 子 agent 进入 terminal 且其 notification 被 parent 消费
- **THEN** parent model context 取得一次 `<task-notification>`
- **AND** `Kernel.stream()` 在对应消费边界提供同一 task id、agent id、status、原始 result/error、usage、duration 与 output file，不从 assistant 文案反推这些字段

#### Scenario: active 与 idle parent 都保留正确归因
- **WHEN** 两条后台 subagent notification 分别注入 active parent 与启动 idle parent run
- **THEN** 每条结构化返回都跟随实际消费它的 reply，按 task id 唯一且不串到另一条 reply

#### Scenario: active parent 在消费前终止仍保留结构化归因
- **GIVEN** 一条或多条后台 notification 已被 active parent 接受，但尚未到达 round boundary
- **WHEN** parent 因非用户终态转入 continuation，或因用户 `/stop` 暂存到下一次 submit
- **THEN** notification XML 与对应结构化返回按原 FIFO 一起进入真正消费它们的 continuation / held-flush reply
- **AND** 每条 task id 仍只出现一次，不只保留 XML 或归到更晚的无关回复

## ADDED Requirements

### Requirement: Workflow 后台任务支持 cooperative stop 且完成结果不重复通知

#### Scenario: Workflow 启动成为后台 task
- **WHEN** `Workflow` tool 成功启动一个运行
- **THEN** 消费者立即取得可由通用 task id 识别和停止的后台任务记录
- **AND** 详细阶段与 Agent 状态仍可通过 Workflow 查询取得

#### Scenario: task_stop 停止 Workflow
- **WHEN** 消费者用通用 task stop 停止运行中的 Workflow task
- **THEN** tool 只请求 cooperative stop 并返回非终态 `stopping`，不把该 task 同步写成 `killed`
- **AND** Workflow manager 收口 partial result/diagnostics 后，把 Workflow snapshot 与通用 task 记录都写成 `stopped`

#### Scenario: 重复停止 Workflow 是幂等的
- **GIVEN** Workflow task 正在收口或已进入 `stopped`
- **WHEN** 消费者再次调用 task stop
- **THEN** 收口中返回 `stopping`，终态后返回 `stopped`
- **AND** 不重复取消 child、覆盖 partial result 或生成额外通知

#### Scenario: 同一 Workflow 终态只通知一次
- **WHEN** Workflow runtime 与后台 task registry 都观察到同一终态
- **THEN** notifier 只在原子 claim `notified` 成功时向 parent session 发一条 model-facing task notification
- **AND** tool launch result 不被误当第二条完成通知
- **AND** 停止的 Workflow 通知状态是 `stopped`，并携带已收口的 partial result/diagnostics
