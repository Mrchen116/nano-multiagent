# gateway/global-agent Specification (delta for feat-780)

## ADDED Requirements

### Requirement: Global 的话题发言写回话题，未关注的话题不进 Inbox

Inbox 的 target 仍是聊天。话题身份在消息上，不新建每个话题一条 Inbox target，也不新建主 session。

#### Scenario: 未关注的群话题没有 Inbox 行
- **GIVEN** Global Agent 没有关注该群话题，消息也没有 @ 或引用它
- **WHEN** 话题里出现新回复
- **THEN** Inbox 不增加这条消息，十分钟背景里也没有它

#### Scenario: 确认和结果使用 in_thread_of
- **WHEN** Global 接下一件需要确认和结果的请求，并向该请求消息发送 `in_thread_of`
- **THEN** 这些消息只出现在该话题
- **AND** 省略话题地址时，若这一轮正是由该话题叫醒，发言仍回到该话题；从主时间线一句答完则仍发到主时间线
