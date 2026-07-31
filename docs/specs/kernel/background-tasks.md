# kernel (agent) - Background Tasks Specification

> 对齐: feat-474
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

后台任务完成通知、停止通知和派生子 agent 前台执行隔离的对外契约。

## Requirements

### Requirement: 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠

后台 bash / subagent 任务自然终态（成功或失败）后，发起它的 session 在下一轮输入中收到一条 `<task-notification>` 消息，内含任务结果——消费者无需轮询即可感知。该通知在任意 workspace_root 下均可靠送达，不因 session 绑定非默认工作区而丢失。（经 `task_stop` 主动终止后的通知去重 / 携带部分结果行为，见下方「经 task_stop 停止后台任务」要求。）反之，同步前台工具（前台 bash 或前台 subagent 在预算内完成 / 失败 / 超时 / 被中断）的结果只经该工具的 tool result 同步返回，绝不再额外发 `<task-notification>`—— 一次执行只走一条结果通路。仅当前台调用超出前台预算、真正转为后台任务（auto-background）后，其后续完成才发一次 `<task-notification>`（此后它就是后台任务）。前台子 agent 的前台预算由系统默认决定，消费者无法经 `agent` 工具参数自定义该超时。

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

### Requirement: 运行中的后台 subagent follow-up 必须先被 live session 接收再确认 queued

消费者经 `agent` 工具向一个仍在运行的后台 subagent 发送 follow-up prompt 时，内核只有在确认该 prompt 已被同一个 live subagent session 接收、可在安全轮次边界消费后，才向消费者报告 follow-up 已 queued。内核不得静默丢弃 prompt，也不得为该 prompt 偷偷启动另一个无关的并发 subagent。

#### Scenario: running follow-up 被同一个 subagent 消费
- **GIVEN** 消费者已启动一个后台 subagent，并拿到其 `agent_id`
- **WHEN** 消费者在该 subagent 仍运行时，经 `agent` 工具带该 `agent_id` 发送 follow-up prompt
- **THEN** 成功的 queued 结果表示该 prompt 已被同一个运行中的 subagent session 接收
- **AND** 该 follow-up 在安全轮次边界被消费，且后续可观察输出或 transcript 体现它进入的是同一个 subagent session

#### Scenario: live delivery 不可确认时不得确认 queued
- **GIVEN** 消费者持有一个看似仍在运行的 subagent `agent_id`
- **WHEN** 消费者发送 follow-up prompt，但内核无法确认 live subagent 能接收它（包括该运行已被停止或取消）
- **THEN** 该工具调用不报告 follow-up 已成功 queued
- **AND** 内核不得为该 prompt 静默创建第二个并发 subagent run

### Requirement: 经 task_stop 停止后台任务，model-facing 通知不与 tool_result 重复

消费者经 `task_stop` 停止一个后台任务后，发起 session **不应**收到一条与 `task_stop` tool result 内容重复、且不带任何新增 payload 的 `<task-notification>`。按任务类型分两支：停后台 bash 抑制 model-facing 通知；停后台 subagent 保留通知但携带子 agent 被停前的部分产出。无论哪支，被停任务最终都进入 killed 终态，且仍可经 `agent` 工具从 transcript 续跑。

#### Scenario: 停后台 bash 不再发重复通知
- **GIVEN** 消费者派了一个后台 bash 任务且它仍在运行
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 只收到 `task_stop` 的 tool result 一条停止信号
- **AND** 后续输入中不再注入与该 tool result 重复的 `<task-notification>`

#### Scenario: 停后台 subagent 通知携带部分结果
- **GIVEN** 消费者派了一个后台 subagent，它在被停前已产出至少一段 assistant 文字
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 收到一条 `<task-notification>`，其 `<status>` 为 `killed`
- **AND** 该通知带 `<result>`，内容为子 agent 被停前最后一段 assistant 文字

#### Scenario: 子 agent 无产出时通知省略 result
- **GIVEN** 消费者派了一个后台 subagent，它在产出任何 assistant 文字前就被停
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 收到的 `killed` 通知省略 `<result>`（不出现空 `<result>`）

#### Scenario: 停止后任务进 killed 终态且可续跑
- **WHEN** 消费者对任意后台任务（bash / subagent，含前台超预算自动转后台的 subagent）调 `task_stop`
- **THEN** 该任务最终进入 killed 终态
- **AND** 对该 subagent 再发 follow-up 时，它从 transcript 续跑（与停止前的 resume 行为一致）

### Requirement: 派生子 agent 的前台执行与内核 run 隔离

经 `agent` 工具派发的前台子 agent，复用内核同一事件循环执行，不在独立的瞬时事件循环上运行共享内核组件；因此前台子 agent 能正常完成并返回结果。任意工具调用（含子 agent）的失败被收敛在该工具的 tool result 边界内，不破坏内核的 run、不影响同一内核上的其它 run，也不中断该消费者进程的其它常驻活动。

#### Scenario: 前台子 agent 正常返回结果
- **WHEN** 消费者经 `agent` 工具派发一个前台子 agent（提供 description 与 prompt；可选 `subagent_type`）
- **THEN** 该工具调用返回子 agent 的执行结果（status=completed 含结果文本），而非因跨事件循环绑定而失败

#### Scenario: 单次工具 / 子 agent 失败被隔离，不拖垮内核与常驻进程
- **GIVEN** 某消费者进程常驻运行内核（持续有心跳 / 中继等常驻活动）
- **WHEN** 一次 `agent` 工具派发的子 agent 调用失败
- **THEN** 该失败仅作为该工具调用的失败结果（status=failed + error）返回
- **AND** 内核的其它 run 与该消费者进程的常驻活动不受影响、继续正常运行（进程不失联、不需重启）
