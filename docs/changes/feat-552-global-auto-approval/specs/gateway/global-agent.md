# Global Agent — feat-552 delta

目标：`docs/specs/gateway/global-agent.md`。依据 spec R1–R6、design D3–D8。原群聊复核、投递、Inbox 消费与访问权限不变。

## ADDED Requirements

### Requirement: 全局未获准动作由主 Agent 继续处理

#### Scenario: 自动拒绝或审核故障
- **WHEN** 全局消息驱动的主 Agent 或其普通 child 动作未获准
- **THEN** 不弹权限卡片、不挂权限 Future；原因交回主 Agent，由其选择合规替代、普通聊天询问或说明停止；故障不归咎于用户未授权。

#### Scenario: 正常发送询问
- **WHEN** Agent 在发起事项的合适聊天中澄清具体操作
- **THEN** send_message 根据目标和正文审核，正常询问适用协作/回复例外；工具整体不免审，不改变实际投递语义。

### Requirement: Inbox 保留工具形态与多来源授权语义

#### Scenario: 同页包含真人与 Agent
- **WHEN** Agent 读取实际 Inbox 消息
- **THEN** 审批获得工具调用、带 target/sender/id/text/partial 的宿主附加上下文；只有明确真人原话可表达人工意图，Agent 转述、自动事件与引用不升级。

#### Scenario: 多聊天提议与简短回复
- **WHEN** Agent 已通过 send_message 对不同聊天提出不同问题，某一用户回复
- **THEN** 历史发送目标/正文和该回复来源共同交给模型判断；同范围明确同意可继续，无关回复不凭全局时间邻近扩大授权；不要求新建专用确认实体。

#### Scenario: Inbox wake
- **WHEN** Gateway 因有未读消息唤醒全局主 session
- **THEN** wake 是系统通知；实际发送者身份与原话通过后续 Inbox read 提供，不能凭运行 origin=HUMAN 把通知当确认。

### Requirement: 等待确认可继续独立事项并按原来源恢复

#### Scenario: 其他聊天有工作
- **WHEN** 当前事项在等待用户回复
- **THEN** 待确认动作保持未执行，Agent 可完成独立工作，无事则 idle，回复到来后重新处理原事项。

#### Scenario: 普通跨轮或重启压缩后回复
- **WHEN** 用户回答旧问题
- **THEN** 根据当前可见问答与 CC 实时/恢复规则判断；必要时查背景后重述确认，不通过历史查询复认证旧授权，也不要求用户重提完整任务。

#### Scenario: 连续拒绝
- **WHEN** 普通 global wake 或 global child 的拒绝次数达到阈值
- **THEN** 不变成弹窗等待、不因计数放行，后续新动作仍能接受分类；Heartbeat（包括复用全局主 session）和独立 Cron 按各自自动入口继续原有 fallback；普通 global child 仍返回主 Agent，不因 BACKGROUND_TASK 调度值切到该 fallback。
