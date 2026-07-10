# kernel Specification (delta for bugfix-404)

## MODIFIED Requirements

### Requirement: 后台任务完成后主动通知 parent session（任意 workspace_root 下成立）

后台任务（bash `run_in_background` / 后台 subagent）完成后，内核向 parent session 投递 `<task-notification>`：parent 有活跃 run 时注入 pending message；parent 空闲时以 `origin=BACKGROUND_TASK` 起新 run。该行为对**任意 workspace_root** 的 session 成立，不限于默认 workspace。

#### Scenario: 非默认 workspace 的 session 后台任务完成，空闲 parent 收到新 run
- **GIVEN** 消费者经 `agent.sdk` 在非默认 `workspace_root` 下创建 session，并在其中启动了一个后台 bash 任务，随后该 session 的 run 已结束（parent 空闲）
- **WHEN** 后台任务进程退出
- **THEN** 内核对该 session 发起一个 `origin=BACKGROUND_TASK` 的新 run，其输入含 `<task-notification>`（任务结果），session JSONL 可见该 turn

#### Scenario: 子 session 的后台任务完成不触发顶层 run
- **GIVEN** 某后台任务的 parent 是子 session（subagent）
- **WHEN** 该任务完成
- **THEN** 不发起新 run（既有跳过语义保留），且以 debug 级日志记录跳过

#### Scenario: 通知投递失败可观察
- **WHEN** 完成通知向 parent session 投递失败（如 session 已不可定位）
- **THEN** 内核以 error 级日志记录（含 task_id、parent_session_id、workspace_root），不静默丢弃

#### Scenario: 前台完成不发通知（不回归）
- **WHEN** 前台 bash 在 budget 内同步完成
- **THEN** 不投递 `<task-notification>`（结果已随 tool_result 返回）
