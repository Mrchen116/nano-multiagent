# gateway global-agent Specification (delta for feat-623)

## MODIFIED Requirements

### Requirement: 依据配置接收信号，并自主安排读取

#### Scenario: 忙碌期间有其他聊天的新请求
- **GIVEN** 全局主 Agent 正在处理工作
- **WHEN** 其他聊天发来符合接收条件的新请求
- **THEN** 新请求保留供其读取，不因收到请求就强制中断当前工作
- **AND** 符合触发配置的新输入在主 Agent 下一次模型请求前提供 Inbox 系统提醒，不必等当前任务结束；已开始的模型请求和工具执行不被硬中断
- **AND** 提醒不包含新消息正文或代表真人授权，正文与来源仍通过 Inbox 主动读取；原发送前复核继续生效
- **AND** 用户能在工作视图中查看其后续读取和处理过程

#### Scenario: 空闲时收到符合触发条件的输入
- **GIVEN** 全局主 Agent 空闲
- **WHEN** 收到符合该 Agent 触发配置的输入
- **THEN** 它能开始处理，不要求用户额外操作才能唤醒

#### Scenario: 普通群聊更新遵循各 Agent 配置
- **WHEN** 群内有未提及某个全局 Agent 的普通更新
- **THEN** 其处理和唤醒行为符合该 Agent 的配置，而不是由全局模式统一改成固定规则
- **AND** PA 自己参与的群聊同样遵守该规则。

#### Scenario: PA 通过主人观察未参与聊天
- **WHEN** PA 通过主人权限接收自己未参与聊天的更新
- **THEN** 它们按 [personal-agent](personal-agent.md) 的背景批次规则保存和通知，不被当作需要及时打断式提醒的直接请求；主人直接请求仍及时通知且可读取相关背景。
