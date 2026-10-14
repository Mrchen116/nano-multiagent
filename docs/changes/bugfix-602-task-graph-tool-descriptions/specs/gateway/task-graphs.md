# gateway - Task Graphs Delta

目标：[current task graphs](../../../../specs/gateway/task-graphs.md)。未归并。

## ADDED Requirements

### Requirement: 任务工具公布动作与参数契约

#### Scenario: Agent 获取任务工具定义
- **WHEN** 已启用任务工具的 Agent 获取模型可见的 task_graph 定义
- **THEN** 工具及参数描述明确五动作字段归属：create 只建根，图内节点与关系使用后续 apply，不混用动作参数。
- **AND** apply 的变更说明字段必填，普通修改允许空说明，重新开启已完成工作仍要求原因。
- **AND** 批内节点定义与引用、仅引用此前定义的节点，以及依赖 from 为前置、to 为后续的方向有就近说明与可用示例。
- **AND** 描述不改变资源归属、权限、原子修改、幂等或记录不调度执行的既有契约。
