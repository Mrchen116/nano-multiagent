# IM Conversations and Messages Specification (delta for bugfix-497)

> Target canonical: `docs/specs/im/conversations-messages.md`

## ADDED Requirements

### Requirement: 外部 channel Agent 富消息按稳定来源身份原位调和

IM 接受 Gateway 为 external shadow conversation 提供的稳定 Agent 消息身份与 terminal 富时间线快照。相同会话和来源身份始终映射到同一消息：live 已建泡时原位补全，live 缺失时直接创建 terminal 消息。调和后的消息与普通 Agent 历史共享正文、思考/工具过程、可选 token usage、耗时、状态、分页与读取语义；中间气泡的 token usage 为空，最终气泡保留整轮累计 usage，与全程在线一致。

#### Scenario: live 已存在时调和原消息
- **GIVEN** external shadow conversation 中已有一条带相同来源身份的 live Agent 气泡
- **WHEN** IM 收到该气泡的 terminal 富快照
- **THEN** IM 保留原 message id 和时间线位置并补全其终态字段
- **AND** 不新增 plain 或第二条 Agent 气泡

#### Scenario: live 从未建立时创建完整 terminal 消息
- **GIVEN** IM 在整个 Agent run 期间不可达，没有建立 live 气泡
- **WHEN** Gateway 恢复后提交该逻辑气泡的 terminal 富快照
- **THEN** IM 创建一条已完成 Agent 消息，完整保留正文、思考/工具顺序与终态、逐气泡耗时、在线同口径的可选 token usage 和可用的 Kernel 消息身份
- **AND** 历史读取直接返回该终态，不伪造 running 过程

#### Scenario: 相同快照重复提交幂等
- **WHEN** Gateway 因 ACK 丢失或重启重复提交同一来源身份的 terminal 快照
- **THEN** IM 返回原 message id，持久历史仍只有一条消息

#### Scenario: 打开的会话实时收敛
- **GIVEN** 用户正打开目标 external shadow conversation
- **WHEN** 某条缺失或不完整的 Agent 消息完成调和
- **THEN** 浏览器 user-stream 收到以 `message_id` 为唯一主键、携带其余完整消息字段的 canonical 事件
- **AND** 当前气泡无需手工刷新即可在原位置收敛；刷新后内容、顺序与数量一致
- **AND** 浏览器不重演打字、工具运行中动画或原始等待时长
