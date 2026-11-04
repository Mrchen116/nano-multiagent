# gateway personal-agent Specification (delta for feat-705)

> 目标：`docs/specs/gateway/personal-agent.md`。

## MODIFIED Requirements

### Requirement: PA 复用完整 Global 执行能力

#### Scenario: 主人请求与普通工具
- **WHEN** 主人交办工作或查询历史
- **THEN** 直接进入 Global 主上下文，复用普通工具、Skills、插件、任务、子 Agent 与调度；不增加主人输入审核或 PA 目标引擎。
- **AND** 日常直接处理、完整独立事项的单一内部执行责任、原执行者接续及主 Agent 唯一沟通交付均遵循 [Global 契约](global-agent.md)，不另设 PA 执行模型。
