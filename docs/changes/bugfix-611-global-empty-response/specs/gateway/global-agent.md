# gateway global-agent Specification (delta for bugfix-611)

## ADDED Requirements

### Requirement: 全局轮次区分内部收尾与公开交付

#### Scenario: 模型空返回
- **WHEN** 全局 Agent 的模型请求返回空响应错误
- **THEN** 使用运行时既有重试策略恢复，耗尽后报告失败，不因全局模式把错误当作成功结束。

#### Scenario: 已交付或无需公开更新
- **WHEN** 全局 Agent 已交付结果、已告知阻塞或没有需要公开的更新
- **THEN** 系统要求它以简短、非空的内部说明收尾，说明留在工作轨迹，不自动成为聊天消息。
- **AND** 公开回复仍须显式发送，内部说明不代表用户已收到结果，也不要求重复发送已交付的内容。
