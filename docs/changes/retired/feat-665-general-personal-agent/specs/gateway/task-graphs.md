# gateway/task-graphs 增量

## ADDED Requirements

### Requirement: Task 可关联真实内部执行并保持可控责任
#### Scenario: 持续执行与修订
- **WHEN** PA 为一个 Task 绑定已建立的内部执行者并收到修订
- **THEN** 保留原负责人和真实执行引用，修订送达原执行者；该执行者正常工作时不重复实施，其他任务仍能推进。
#### Scenario: 失败、未知、取消与恢复
- **WHEN** 绑定执行失败、状态未知、节点重启或用户停止 Task
- **THEN** 重新核实真实状态，失败不永久悬空，已停止任务不会被旧结果或调度复活；等待仍须满足现有真实 Schedule 契约。
