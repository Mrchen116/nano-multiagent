# IM personal-agent Specification (delta for feat-658)

## MODIFIED Requirements

### Requirement: PA 回复草稿复用 IntelligentUI
#### Scenario: 编辑并采用
- **WHEN** 主人编辑 PA 提供的回复草稿并采用
- **THEN** 编辑内容进入正确的原聊天输入框，主人确认发送后才向对方发布；采用使用与普通 Agent 相同的通用交互动作，不绑定原消息；采用不自动发送。
#### Scenario: PA 代发
- **WHEN** PA 按真实委托在原聊天代表用户发送
- **THEN** 以用户为发言主体，保留实际 PA 的可辨认来源，发送成功以真实回执为准；受众、完整内容和原始委托范围仍经正常外发检查。

## ADDED Requirements

### Requirement: 代表用户的消息在各端保持同一身份
#### Scenario: 双方与后续查看
- **WHEN** 用户本人或其他成员在 Web 桌面、移动端及原生 iOS 查看群聊/私聊中的代发消息
- **THEN** 展示该用户的主头像与姓名、相邻的“PA 代发”标记，用户本人侧沿用本人消息归属；正文不依赖代发前缀说明身份。
- **AND** 刷新、历史、现有引用、搜索及会话预览中出现的发送者身份一致，完整消息保留实际代发来源；不向成员暴露私人 PA 工作上下文。
#### Scenario: 自身发言与旧记录
- **WHEN** PA 以自身身份发言、报告或提供草稿，或客户端显示升级前的旧 PA 消息
- **THEN** 保留 PA 的身份与原文；旧代发标记不会自动提升为用户发言或授权，草稿不自动对外发送。
