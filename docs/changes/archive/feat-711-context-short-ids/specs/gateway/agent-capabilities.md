# gateway/agent-capabilities 增量

## ADDED Requirements

### Requirement: 上下文恢复引用简短且稳定

#### Scenario: 首次阅读任务与工具结果
- **WHEN** Agent 首次阅读普通用户材料或最终工具结果
- **THEN** 正文末尾提供会话内有序短编号，无需另查引用表
- **AND** assistant 与窗口控制消息不加正文标记

#### Scenario: 裁剪、换窗与重启后恢复原文
- **GIVEN** Agent 已记录当前窗口与材料的短编号
- **WHEN** 经历裁剪、换窗或同一会话进程重启后恢复材料
- **THEN** 原编号保持有效，可恢复原始内容并分段继续读取，原文中形似引用标记的内容仍保留
- **AND** 物理替换副本不形成重复 History 项，单独补标记不使活动原文成为归档项

#### Scenario: 标记不改变既有业务证据与授权
- **WHEN** 宿主读取带短引用材料的结构化审批证据、Task 消费回执或 source_history
- **THEN** 审批证据与消费回执仍对应原始业务正文，source_history 仍使用原宿主证据序号
- **AND** 既有来源、身份与访问权限范围保留，短引用不构成新的操作授权

### Requirement: 剩余上下文预算简洁表达

#### Scenario: 查询剩余预算
- **WHEN** Agent 调用 get_context_remaining 查询当前窗口预算
- **THEN** 仅获得工作预算剩余量或未知状态，并知道该数值是估算
- **AND** 默认结果不携带内部预算中间参数或引用分页
