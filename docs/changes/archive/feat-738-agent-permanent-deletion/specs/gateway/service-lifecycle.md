# Gateway Service Lifecycle Specification (delta for feat-738)

## ADDED Requirements

### Requirement: Agent 永久删除只清理目标独占数据，并以持久结果确认

#### Scenario: 完成已确认的清理
- **GIVEN** 产品确认目标普通或 Global Agent 已停止，所有者授权永久删除
- **WHEN** 节点确认完成删除
- **THEN** 该 Agent 的独占原生会话、子会话、轨迹、执行记录及自动触发已移除，旧会话无法继续或恢复
- **AND** 按原确认结果删除或保留专用工作区，其他 Agent 及共享资源继续可用

#### Scenario: 中断后的重试
- **WHEN** 已确认的清理因中断或失败重试
- **THEN** 节点保留禁止目标运行的状态，按已确认范围继续，未确认清理完成时返回等待或失败原因
- **AND** 重启不重新创建或注册已删除的身份

#### Scenario: 同节点的其他 Agent 持续运行
- **GIVEN** 目标 Agent 已确认停止，同节点其他 Agent 正在执行
- **WHEN** 节点清理目标 Agent 的数据
- **THEN** 清理可与其他 Agent 的执行并行完成，共享运行时持续服务，其他 Agent 的在途执行、接收新工作及读取历史继续按原路径进行
