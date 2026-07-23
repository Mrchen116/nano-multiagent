# kernel / background-tasks — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/background-tasks.md`

## ADDED Requirements

（无。）

## MODIFIED Requirements

### Requirement: 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠

后台 bash / subagent 任务自然终态（成功或失败）后，发起它的 session 在下一轮输入中收到一条
`<task-notification>` 消息，内含任务结果——消费者无需轮询即可感知。该通知在任意 workspace_root 下均
可靠送达，不因 session 绑定非默认工作区而丢失。（经 `task_stop` 主动终止后的通知去重 / 携带部分结果行为，
见下方「经 task_stop 停止后台任务」要求。）反之，同步前台工具（前台 bash 或前台 subagent 在预算内
完成 / 失败 / 超时 / 被中断）的结果只经该工具的 tool result 同步返回，绝不再额外发 `<task-notification>`——
一次执行只走一条结果通路。仅当前台调用超出前台预算、真正转为后台任务（auto-background）后，其后续完成才
发一次 `<task-notification>`（此后它就是后台任务）。前台子 agent 的前台预算由系统默认决定，消费者无法经
`agent` 工具参数自定义该超时。

#### Scenario: 非默认 workspace 下后台任务完成通知送达
- **GIVEN** 一个绑定非默认 workspace_root 的 session 启动了后台任务
- **WHEN** 任务完成
- **THEN** 该 session 下一轮输入含一条带任务结果的 `<task-notification>` 消息

#### Scenario: 前台命令完成只走 tool result，不发通知
- **GIVEN** 某 session 执行一条前台 bash 命令（未声明 `run_in_background`），且在前台预算内完成、失败或自身超时
- **WHEN** 消费者消费该 run 的结果
- **THEN** 该命令的结果只经其 tool result 同步返回（含成功输出 / 失败 / 超时归因）
- **AND** 该 session 后续输入中**不含**针对该命令的 `<task-notification>`（不出现"既返回结果又异步通知"的双通道）

#### Scenario: 前台命令超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 执行一条前台 bash 命令，运行时长超出前台预算被 auto-background（其 tool result 返回 `async_launched` + task_id）
- **WHEN** 该命令稍后在后台完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）

#### Scenario: 前台 subagent 在预算内完成只走 tool result，不发通知
- **GIVEN** 某 session 经 `agent` 工具派发一个前台子 agent（未声明 `run_in_background`），且在前台预算内完成
- **WHEN** 子 agent 跑完一轮返回
- **THEN** 父 session 经该 `agent` 工具的 tool result 同步拿到子 agent 的结果文本
- **AND** 该 session 后续输入中**不含**针对该子 agent 的 `<task-notification>`（不出现"既返回结果又异步通知"的双通道）

#### Scenario: 前台 subagent 超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 派发的前台子 agent 运行时长超出系统默认前台预算被 auto-background（其 tool result 返回 `async_launched` + agent_id）
- **WHEN** 该子 agent 稍后完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）
- **AND** 消费者无法通过 `agent` 工具参数自定义该前台预算

### Requirement: 派生子 agent 的前台执行与内核 run 隔离

经 `agent` 工具派发的前台子 agent，复用内核同一事件循环执行，不在独立的瞬时事件循环上运行共享内核
组件；因此前台子 agent 能正常完成并返回结果。任意工具调用（含子 agent）的失败被收敛在该工具的 tool
result 边界内，不破坏内核的 run、不影响同一内核上的其它 run，也不中断该消费者进程的其它常驻活动。

#### Scenario: 前台子 agent 正常返回结果
- **WHEN** 消费者经 `agent` 工具派发一个前台子 agent（提供 description 与 prompt；可选 `subagent_type`）
- **THEN** 该工具调用返回子 agent 的执行结果（status=completed 含结果文本），而非因跨事件循环绑定而失败

#### Scenario: 单次工具 / 子 agent 失败被隔离，不拖垮内核与常驻进程
- **GIVEN** 某消费者进程常驻运行内核（持续有心跳 / 中继等常驻活动）
- **WHEN** 一次 `agent` 工具派发的子 agent 调用失败
- **THEN** 该失败仅作为该工具调用的失败结果（status=failed + error）返回
- **AND** 内核的其它 run 与该消费者进程的常驻活动不受影响、继续正常运行（进程不失联、不需重启）

## REMOVED Requirements

（无整 Requirement 删除。）
