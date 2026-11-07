# Gateway agent-capabilities Specification (delta for feat-716)

## MODIFIED Requirements

### Requirement: Agent 按用户话语理解交互背景

#### Scenario: 指代、换题与授权
- **WHEN** 私聊自然消息携带了发问时的卡片改动
- **THEN** Agent 只把这条消息所携带的那一张卡片改动当作可参考的私人背景，根据用户原话判断是否使用，换题可忽略，指代不明时可澄清
- **AND** 背景数据不替代正文、不构成业务授权；由 IM 判定这次是否携带以及范围，Agent 不据此推断其他卡片状态，也不索要更多未提交内容

#### Scenario: 未携带背景的追问
- **WHEN** 用户上一条消息曾携带卡片改动，本条普通消息没有携带
- **THEN** Agent 不把上次的卡片状态当作本条消息的背景，需要时按用户原话澄清或请用户再说明

#### Scenario: 群聊不读取私人操作
- **WHEN** 用户在群聊操作卡片后正常发言
- **THEN** 所有 Agent 均不取得未提交状态；明确提交后按公开消息读取已提交快照。
