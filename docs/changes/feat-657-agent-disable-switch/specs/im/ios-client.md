# im ios-client Specification (delta for feat-657)

## ADDED Requirements

### Requirement: 原生客户端提供 Agent 停用与重新启用控制

#### Scenario: 管理者操作
- **WHEN** 有权管理的真人在 Agent 详情、工作或配置入口操作停用
- **THEN** 与 Web 使用相同的持久停用语义，无需先保存其他设置；原生按钮或开关清楚表明目标 Agent

#### Scenario: 等待确认与恢复
- **WHEN** 停用正在处理、节点离线或清理未确认
- **THEN** 原生界面显示相同真实状态与可用重试，不把设备在线显示成 Agent 已启用
- **AND** 仅在确认停用后可重新启用，明确旧任务不会自动恢复
