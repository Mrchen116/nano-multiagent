# Gateway Task Graphs — bugfix-678 Delta

Target: `docs/specs/gateway/task-graphs.md`

## ADDED Requirements

### Requirement: 单次动作拒绝不建立隐藏任务续跑限制

#### Scenario: 可替代步骤与其他任务
- **WHEN** 工具权限拒绝、人工审批未获准或审核技术故障返回 Agent
- **THEN** 不从该结果推断当前任务或整批任务停止续跑；Agent 可继续获准替代与独立工作，原动作权限限制保持。

#### Scenario: 需要暂停或等待
- **WHEN** Agent 判断任务当前无法继续
- **THEN** 经正常 task_graph 状态和原因显式表达，调度遵循既有状态/安排与用户停止规则，不从单次拒绝猜测任务去留。

## MODIFIED Requirements

### Requirement: 自动失败屏障 SHALL 与 Task 业务状态分离

#### Scenario: 故障与修复
- **WHEN** 读取、持久化或主执行模型故障发生
- **THEN** 停止受影响的无效自动重复，不伪造业务状态；相关运行恢复后可重新评估。普通参数与版本错误允许模型修正。
- **AND** 审核子调用的技术故障交回执行 Agent，不据此建立任务或整批任务的隐藏续跑限制。

#### Scenario: 拒绝与新输入
- **WHEN** 审批拒绝后出现新输入、心跳或其他工具成功
- **THEN** 不存在由该次拒绝推导的任务续跑屏障；新输入与合法独立工作仍可处理，Agent 自主决定下一步或显式任务状态。
- **AND** 该动作及等价影响仍通过原审批链，通知和其他工具成功不授予被拒影响的权限。
