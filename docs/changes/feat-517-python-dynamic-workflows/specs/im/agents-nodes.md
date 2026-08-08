# IM - Agents and Nodes Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Agent 配置页以单一 Workflow 工具选择管理完整能力

#### Scenario: Workflow 默认未选择
- **WHEN** 用户新建 Agent 或查看没有显式启用 Workflow 的 Agent
- **THEN** 工具选择器显示 `Workflow` 可选项但不默认选中

#### Scenario: 选择 Workflow
- **WHEN** 用户勾选 `Workflow` 并成功保存 Agent
- **THEN** 页面显示已选择真值与 size guideline
- **AND** 该 Agent 下一轮在 Web/外部 IM 完整获得 Workflow 能力

#### Scenario: 取消 Workflow
- **WHEN** 用户取消 `Workflow` 并成功保存 Agent
- **THEN** 页面显示未选择真值
- **AND** 该 Agent 下一轮完整失去 Workflow tool、prompt、commands 与 ultracode 入口

#### Scenario: 调整 size guideline
- **GIVEN** `Workflow` 已选择
- **WHEN** 用户选择 unrestricted、small、medium 或 large 并保存
- **THEN** 再次打开配置页显示保存值，下一轮运行反馈采用该值

#### Scenario: 取消后保留 guideline 草稿值
- **GIVEN** 用户曾保存一个非默认 guideline
- **WHEN** 用户取消后再次启用 Workflow
- **THEN** 页面恢复此前保存值，不把取消工具误当成删除用户配置
