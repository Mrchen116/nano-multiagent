# im/ios-client Specification (delta for feat-780)

## ADDED Requirements

### Requirement: iPhone 能阅读和回复话题

#### Scenario: 从消息进入话题
- **WHEN** 用户在原生聊天里对一条合格消息选择在话题中回复，或打开已有话题
- **THEN** 话题以单独一层展示根消息和按时间排列的回复，返回回到主时间线
- **AND** 话题回复不出现在主时间线
- **AND** 本需求不新增主时间线上的「回复」动作

#### Scenario: 关注与未读和 Web 一致
- **WHEN** 用户在 iPhone 上关注、取消、接收或阅读一条群话题
- **THEN** 谁增加未读、何时清除，与 Web 的同一话题一致
