# gateway/routing-delivery Specification (delta for feat-780)

## ADDED Requirements

### Requirement: 话题回复只把关注者及时叫醒

团队协作的群里，未关注、未被 @、也未被引用的话题回复不中继。它不进入该 Agent 的群背景，也不在十分钟后并入下一次运行。私聊话题仍按私聊新消息及时到达。仅限本人的 Agent 不接收群话题，包括群里 @ 它；创建者与它的私聊话题仍及时到达。

#### Scenario: 未关注的群话题
- **GIVEN** 团队协作的 Agent 没有关注这条群话题
- **WHEN** 话题里出现没有 @ 它、也没有引用它的回复，无论发送者是人还是 Agent
- **THEN** 不创建运行，群背景和十分钟积压里也没有这条消息

#### Scenario: 已关注或被点名
- **WHEN** 话题回复来自它已关注的话题，或 @ 了它，或引用了它
- **THEN** 按现在的高优路径及时叫醒，并把话题根和这条回复交给该聊天现有的 session
- **AND** 它随后要人看见的话写回这个话题，不另写一条主时间线消息

#### Scenario: 仅限本人
- **WHEN** 群话题里 @ 了一个仅限本人的 Agent，同时创建者在和它的私聊话题里说话
- **THEN** 群话题不叫醒它
- **AND** 私聊话题会到达

### Requirement: 自动正文和 send_message 能写进话题

`send_message` 的 `target` 支持 `<chat_id>:<8位短消息id>`（single_thread 亦支持 `current:<8位短消息id>`）直接写入对应话题；传主时间线 `target` 则写入主时间线，不做静默改写。外部通道和内部子执行不能使用话题 target。SingleThread 由话题唤醒时自动正文写回该话题；由主时间线唤醒且本轮已显式向请求话题发过言时，随后的自动正文也写回该话题而不双写主时间线。

#### Scenario: 一句回答留在主时间线
- **GIVEN** single_thread 由一条主时间线消息叫醒，这一轮没有向它的话题发送过
- **WHEN** 运行只产生一条最终正文
- **THEN** 这条正文出现在主时间线，不创建话题

#### Scenario: 多步发言只出现在请求的话题
- **GIVEN** 同一轮已经用 `send_message` 向用户那条请求的话题 `target` 写入确认
- **WHEN** 运行结束时还有自动正文
- **THEN** 自动正文也进入该话题
- **AND** 主时间线不再增加这一轮的气泡

#### Scenario: 从话题叫醒就回到话题
- **WHEN** single_thread Agent 由一条话题回复叫醒并输出自动正文
- **THEN** 自动正文进入该话题；显式 `send_message` 传该话题 `target` 亦进入该话题，传主时间线 `target` 则发往主时间线
