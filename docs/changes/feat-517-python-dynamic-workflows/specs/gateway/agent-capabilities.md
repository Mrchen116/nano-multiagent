# gateway (personal_assistant) - Agent Capabilities Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Workflow 是 Agent 可选且默认关闭的完整能力

#### Scenario: 能力列表提供 Workflow
- **WHEN** IM 查询节点或 Agent 可选工具
- **THEN** Gateway 报告 `Workflow` 为可选择、默认关闭的工具，并提供描述

#### Scenario: 保存启用 Workflow
- **WHEN** 用户把 `Workflow` 加入 Agent tool allowlist 并保存成功
- **THEN** Agent 的下一轮完整采用 Workflow tool、prompt、commands 与 ultracode 入口

#### Scenario: 保存禁用 Workflow
- **WHEN** 用户从 Agent tool allowlist 移除 `Workflow` 并保存成功
- **THEN** Agent 的下一轮完整移除相同能力，不保留 hidden Workflow prompt

#### Scenario: Workflow size guideline
- **WHEN** 用户为启用 Workflow 的 Agent 保存 unrestricted、small、medium 或 large
- **THEN** Gateway 持久化该值并用于后续新轮的 tool description 与运行反馈
- **AND** 未保存时使用 medium

#### Scenario: 运行中配置更新
- **WHEN** Agent 正在回复或已启动 Workflow 时保存新的 Workflow 选择/guideline
- **THEN** 当前整轮及其 Workflow 保持启动时配置，下一轮整体采用新配置
