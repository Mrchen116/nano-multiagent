# im personal-agent Specification (delta for feat-623)

## MODIFIED Requirements

### Requirement: 双向主人消息可用于协助

#### Scenario: 主人先回复
- **WHEN** 主人亲自在原聊天回复
- **THEN** PA 能接收该消息并避免重复回复，读取不改变主人的已读状态。

#### Scenario: 观察主人与他人沟通
- **WHEN** 主人和他人在 PA 未参与的授权聊天里沟通
- **THEN** 双方原话可供 PA 理解背景，主人向对方交办或承诺、对方向主人请求均不自动变成 PA 的新任务；PA 可以按既有目标与授权继续协助。
- **AND** 普通观察消息不触发 PA 向该聊天自动发送拒绝警告。
