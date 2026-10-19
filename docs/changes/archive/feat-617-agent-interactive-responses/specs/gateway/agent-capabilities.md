# Gateway agent-capabilities Specification (delta for feat-617)

## ADDED Requirements

### Requirement: Agent 按用户话语理解交互背景

#### Scenario: 指代、换题与授权
- **WHEN** 私聊自然消息有可用的发问时交互背景
- **THEN** Agent根据用户原话判断是否使用，换题可忽略，指代不明时可澄清；背景数据不替代正文、不构成业务授权。

#### Scenario: 群聊不读取私人操作
- **WHEN** 用户在群聊操作卡片后正常发言
- **THEN** 所有Agent均不取得未提交状态；明确提交后按公开消息读取已提交快照。
