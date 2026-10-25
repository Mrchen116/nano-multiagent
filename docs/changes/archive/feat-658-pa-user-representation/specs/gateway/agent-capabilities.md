# Gateway agent-capabilities Specification (delta for feat-658)

## ADDED Requirements

### Requirement: 通用交互说明区分本地采用与发送请求

#### Scenario: 普通 Agent、Global 与 PA 生成草稿
- **WHEN** Agent 使用可用交互能力提供可编辑回复
- **THEN** 可以使用通用 ComposeMessage 将当前编辑内容采用到指定聊天输入框，不需要 PA 专属字段或草稿工具；ToAssistant 继续表示向本会话提交请求，不能混淆。
- **AND** 工具 schema、固定提示、加载的 Skill 与示例表达同一语义；系统负责补齐固定 format/catalog_version，Agent 只填写内容及适用的更新参数。

#### Scenario: 实际注册与恢复一致
- **WHEN** 上下文经历唤醒、历史恢复、执行子 Agent 交接或独立审核
- **THEN** 工具身份、来源、已有委托范围和真实发送回执仍一致；本地采用不成为公开发送或新增业务许可；没有暴露的工具不被提示为可调用。
