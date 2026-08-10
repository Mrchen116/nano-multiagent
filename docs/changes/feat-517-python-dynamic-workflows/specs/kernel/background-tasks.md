# kernel (agent) - Background Tasks Specification (delta for feat-517)

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
