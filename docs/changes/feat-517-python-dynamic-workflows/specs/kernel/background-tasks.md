# kernel (agent) - Background Tasks Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Workflow 后台任务支持 cooperative stop 且完成结果不重复通知

#### Scenario: Workflow 启动成为后台 task
- **WHEN** `Workflow` tool 成功启动一个运行
- **THEN** 消费者立即取得可由通用 task id 识别和停止的后台任务记录
- **AND** 详细阶段与 Agent 状态仍可通过 Workflow 查询取得

#### Scenario: task_stop 停止 Workflow
- **WHEN** 消费者用通用 task stop 停止运行中的 Workflow task
- **THEN** Workflow runtime 收到停止请求并收口 partial result/diagnostics
- **AND** 通用 task 记录与 Workflow snapshot 最终一致，不提前丢失结果

#### Scenario: 同一 Workflow 终态只通知一次
- **WHEN** Workflow runtime 与后台 task registry 都观察到同一终态
- **THEN** parent session 只收到一条 model-facing task notification
- **AND** tool launch result 不被误当第二条完成通知
