# kernel 契约层增量 (delta-spec) — bugfix-420

> 本文件是本 unit 对长青契约层 `docs/specs/kernel/spec.md` 的增量草案。
> 收尾由 orchestrator 软对账后并入 canonical。规范见 `docs/SPEC_GUIDE.md`「契约层增量」。
> 视角：`agent.sdk` 消费者（驱动会话、观察父会话 turn 流中被注入的 `<task-notification>` user-role 消息者）。

## ADDED Requirements

### Requirement: 经 task_stop 停止后台任务，model-facing 通知不与 tool_result 重复

消费者经 `task_stop` 停止一个后台任务后，父会话**不应**收到一条与 `task_stop` tool_result 内容重复、且不带任何新增 payload 的 `<task-notification>`。按任务类型分两支：停后台 bash 抑制 model-facing 通知；停后台 subagent 保留通知但携带子 agent 被停前的部分产出。无论哪支，被停任务最终都进入 killed 终态，且仍可经 `agent` 工具从 transcript 续跑。

#### Scenario: 停后台 bash 不再发重复通知
- **GIVEN** 消费者派了一个后台 bash 任务且它仍在运行
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 父会话只收到 `task_stop` 的 tool_result 一条停止信号
- **AND** 后续 turn 流中不再注入与该 tool_result 重复的 `<task-notification>`

#### Scenario: 停后台 subagent 通知携带部分结果
- **GIVEN** 消费者派了一个后台 subagent，它在被停前已产出至少一段 assistant 文字
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 父会话收到一条 `<task-notification>`，其 `<status>` 为 `killed`
- **AND** 该通知带 `<result>`，内容为子 agent 被停前最后一段 assistant 文字

#### Scenario: 子 agent 无产出时通知省略 result
- **GIVEN** 消费者派了一个后台 subagent，它在产出任何 assistant 文字前就被停
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 父会话收到的 `killed` 通知省略 `<result>`（不出现空 `<result>`）

#### Scenario: 停止后任务进 killed 终态且可续跑
- **WHEN** 消费者对任意后台任务（bash / subagent）调 `task_stop`
- **THEN** 该任务最终进入 killed 终态
- **AND** 对该 subagent 再发 follow-up 时，它从 transcript 续跑（与停止前的 resume 行为一致）
