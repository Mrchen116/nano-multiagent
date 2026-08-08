# IM - Agents and Nodes Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Agent 配置页以单一 Workflow 工具选择管理完整能力

#### Scenario: Workflow 默认未选择
- **WHEN** 用户新建 Agent 或查看没有显式启用 Workflow 的 Agent
- **THEN** 工具选择器显示 `Workflow` 可选项但不默认选中

#### Scenario: 选择 Workflow
- **WHEN** 用户勾选 `Workflow` 并成功保存 Agent
- **THEN** 页面只以现有工具 pill 的选中态显示已选择真值，不增加工具说明、独立开关或嵌套设置
- **AND** 该 Agent 下一轮在 Web/外部 IM 完整获得 Workflow 能力

#### Scenario: 取消 Workflow
- **WHEN** 用户取消 `Workflow` 并成功保存 Agent
- **THEN** 页面显示未选择真值
- **AND** 该 Agent 下一轮完整失去 Workflow tool、prompt、commands 与 ultracode 入口
