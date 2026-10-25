# gateway task-graphs Specification (delta for feat-657)

## ADDED Requirements

### Requirement: Agent 停用造成的旧任务冻结必须由真人明确恢复

#### Scenario: 停用后重新启用
- **GIVEN** Agent 停用时仍有未完成任务及相关等待计划
- **WHEN** 主人重新启用 Agent
- **THEN** 正在推进或等待的任务保留暂停，其他旧未完成任务不自动开始；相关等待计划不自动续跑
- **AND** Agent、自身工具或迟到的旧输入不能解除该冻结

#### Scenario: 指定任务恢复
- **WHEN** 有权限的真人在重新启用后明确恢复指定旧任务
- **THEN** 只恢复指定范围，并重新确认需要的执行和审批；其他冻结任务保持原状
- **AND** 普通 `/stop` 保留既有作用范围，不被解释为 Agent 永久停用
