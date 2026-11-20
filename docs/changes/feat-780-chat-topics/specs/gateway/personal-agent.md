# gateway/personal-agent Specification (delta for feat-780)

## ADDED Requirements

### Requirement: 未关注的话题不进入 PA 的十分钟观察批

#### Scenario: 观察中的群话题
- **GIVEN** PA 获准观察一个群，但没有关注其中某条话题
- **WHEN** 该话题出现没有 @ 它、也没有引用它的回复
- **THEN** 这条回复不进入观察 Inbox，也不触发十分钟合并通知
- **AND** PA 此后有权读取该聊天时，仍可按话题根读到这些消息

#### Scenario: 被点名的话题及时可读
- **WHEN** 观察或参与的话题里 @ 了 PA，或引用了它，或它已经关注
- **THEN** 按高优及时可读，不并进普通背景的十分钟批
