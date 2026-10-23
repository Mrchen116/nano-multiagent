# Global Task closing delta

## MODIFIED Requirements

### Requirement: 全局轮次区分内部收尾与公开交付

#### Scenario: 模型空返回
- **WHEN** 全局 Agent 的模型请求返回空响应错误
- **THEN** 使用运行时既有重试策略恢复，耗尽后报告失败，不因全局模式把错误当作成功结束。

#### Scenario: 已交付或无需公开更新
- **WHEN** Global 已通过 send_message 实际交付文字或卡片，或本轮没有值得公开的新信息
- **THEN** 使用简短非空的私有结语说明已交付、已沟通的阻塞或无需公开回复的原因，不要求 NO_REPLY，也不重复公开发送收尾。
- **AND** Task 自动续跑与 shared 交互卡片引导遵循同一规则；SingleThread 保留其静默交付协议。
