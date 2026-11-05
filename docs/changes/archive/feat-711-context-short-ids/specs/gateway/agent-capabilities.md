# gateway/agent-capabilities 增量

## ADDED Requirements

### Requirement: 上下文恢复引用简短且稳定

#### Scenario: 首次阅读任务与工具结果
- **WHEN** Agent 首次阅读普通用户材料或最终工具结果
- **THEN** 正文末尾提供窗口内有序短编号，无需另查引用表
- **AND** assistant 与窗口控制消息不加正文标记

#### Scenario: 新窗口独立编号
- **WHEN** 成功切换到一个新窗口
- **THEN** 该窗新内容从短编号 1 开始，不同窗口可以重号，并通过 window_id 与 item_id 成对定位
- **AND** 同一规则下已发出的窗口编号及恢复引用保持不变；同窗内裁剪、进程重启或失败换窗不重排编号；不迁移旧版本会话级编号

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
