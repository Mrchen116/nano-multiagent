# Gateway External Channels Specification (delta for bugfix-535)

> Target canonical: `docs/specs/gateway/external-channels.md`

## MODIFIED Requirements

### Requirement: 外部 channel 可见回复镜像

飞书消息触发 agent run 时，Gateway 把该 run 中每个用户可见 assistant 文本气泡镜像回原飞书 chat。镜像边界是完整 assistant 气泡完成，不是 token delta；同一个最终气泡即使遇到重叠的投递机会也只能成功发送一次。较早的投递失败时，仍存活的兜底机会必须能够接管；已取消的旧 run 不得在取消后晚发该气泡。thinking、tool telemetry、token usage、debug/status 等运行态事件不作为普通飞书聊天消息外发。

#### Scenario: 飞书收到中间可见回复和最终回复
- **GIVEN** 用户在飞书向 plato-bot 发送一个会让 agent 先回复“我查一下”再继续处理的问题
- **WHEN** 内部 IM 影子会话中出现“我查一下”这一用户可见 assistant 气泡
- **THEN** 飞书原对话也收到对应文本消息
- **AND** 后续最终答案也发送到同一飞书对话

#### Scenario: 重叠投递机会只产生一条最终气泡
- **GIVEN** 外部 channel 触发的 run 产生了一个最终 assistant 文本气泡
- **WHEN** Gateway 的多个投递机会在首次发送完成前重叠
- **THEN** 飞书原对话最终只收到一条该文本消息
- **AND** 较早发送失败时，仍存活的兜底机会可以接管并发送一次
- **AND** 已取消的旧 run 不会在取消后晚发该文本

#### Scenario: IM 触发 run 不走外部镜像
- **GIVEN** 用户在内部 IM 的 `plato · feishu` 影子会话中发送消息
- **WHEN** agent 产生中间回复和最终回复
- **THEN** 这些回复只出现在内部 IM
- **AND** 飞书原对话不收到对应消息
