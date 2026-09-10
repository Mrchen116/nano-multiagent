# Global Agent — feat-552 delta

目标：`docs/specs/gateway/global-agent.md`。依据 spec R1–R6、design D3/D4/D8。

## ADDED Requirements

### Requirement: 全局自动拒绝由主 Agent 主动处理

#### Scenario: 动作自动被拒
- **WHEN** 全局主 Agent 或其 child 动作未获准
- **THEN** 不弹权限卡片、不占住权限等待；主 Agent 可选择合规替代、普通聊天询问或说明停止。

#### Scenario: 需要询问
- **WHEN** 缺少具体操作的确认
- **THEN** 主 Agent 自行选择合适聊天，向有权确认的用户说明操作和关键范围；正常询问本身可投递。

### Requirement: 系统提供的真实用户消息可成为授权依据

#### Scenario: 用户经 Inbox 要求内置定时任务
- **WHEN** 用户明确给出任务时间与内容
- **THEN** Auto 不因它通过 Inbox 送达就当作非用户指令；任务按原生 Cron 能力执行。

#### Scenario: 同一用户答复原提议
- **WHEN** 已投递的明确提议后原用户同意
- **THEN** 问题和回答一并用于再次审批；同范围操作不会重复因“未见授权”而拒绝。

#### Scenario: 不相干或伪造确认
- **WHEN** 用户未答、否决、另一聊天无关同意、引用/其他 Agent 转述、或多选问题未选定
- **THEN** 不执行仍未获准的操作，也不扩大确认范围。

### Requirement: 等待确认仍可推进独立事项

#### Scenario: 等待期间另一聊天有任务
- **WHEN** 待确认事项未得到答复
- **THEN** Agent 仍可处理独立任务；无事则空闲，待确认动作不执行。

#### Scenario: 空闲、重启或压缩后收到回答
- **WHEN** 用户回答原问题
- **THEN** 原事项重新处理；原文缺失时先查回可核验的记录，无法恢复则澄清，不凭摘要假定同意。

#### Scenario: 审核失败或连续拒绝
- **WHEN** 模型不可用、无有效结论或多次拒绝
- **THEN** 不自动放行、不弹窗阻塞全局运行，主 Agent 得到实际原因。

原有群聊发言复核、外部投递、Inbox 消费和跨聊天权限范围不变。
