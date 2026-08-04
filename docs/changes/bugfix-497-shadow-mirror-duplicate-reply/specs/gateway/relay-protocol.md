# Gateway Relay Protocol Specification (delta for bugfix-497)

> Target canonical: `docs/specs/gateway/relay-protocol.md`

## MODIFIED Requirements

### Requirement: 外部 channel 影子镜像以稳定事件身份可恢复补写

外部入站 adapter 必须在规范化消息上提供 typed provider-stable event identity，才能进入 shadow conversation 同步；该 identity 包含 connector/account identity 与 provider message/event/delivery id，Gateway 不从松散 metadata、`external_chat_id` 或文本 hash 推导它。Gateway 在运行前持久记录该 identity 与 canonical payload，并为 run 中每个逻辑 Agent 气泡分配稳定消息身份、持续保存正文与富时间线终态。IM 可用时，live 与恢复投递必须指向同一消息；IM 离线时外部回复不等待，Gateway 重启或 IM 恢复后按固定顺序补齐 user anchor、每条唯一完整 Agent 气泡与锚定配置边界。token usage 原样保持在线归属：中间气泡为空，最终气泡承载 `turn_end` 提供的整轮累计 usage，不在 Gateway 内推算分摊。

#### Scenario: IM 离线时外部回复继续
- **GIVEN** 外部消息已持久进入影子同步流程，IM 当前不可达
- **WHEN** Agent 完成回复
- **THEN** 回复照常投递到外部 channel，待补写的用户消息与完整 Agent 时间线保持可恢复

#### Scenario: 恢复后补齐原影子时间线
- **WHEN** IM 恢复或 Gateway 重启并重放同一外部事件
- **THEN** Gateway 复用稳定事件与消息身份补齐唯一用户消息及每个逻辑 Agent 气泡
- **AND** 每条 Agent 气泡包含与全程在线一致的正文、思考/工具顺序与终态、逐气泡耗时、可选 token usage 和可用的 Kernel 消息身份
- **AND** 配置边界只在用户消息锚点确认后投递，并位于该消息之前

#### Scenario: live 与恢复命中同一 Agent 消息
- **GIVEN** IM 已通过 live 投递创建某 Agent 气泡并接收部分或全部富时间线
- **WHEN** Gateway 随后调和或重放该气泡的终态快照
- **THEN** IM 补全原消息，不新增、替换或重置为 plain 气泡
- **AND** 重复调和仍只存在同一条消息

#### Scenario: 恢复只呈现终态历史
- **GIVEN** 某 Agent 气泡在 IM 离线期间已经完成
- **WHEN** IM 恢复并补齐该气泡
- **THEN** 用户直接得到 terminal 富时间线
- **AND** 不重演打字、工具运行中动画或原始等待时长

#### Scenario: IM 写入成功后本地标记前崩溃
- **GIVEN** IM 已创建或调和某影子消息，但 Gateway 在记录返回 id 前崩溃
- **WHEN** Gateway 重启并重放同一步骤
- **THEN** IM 按稳定 caller identity 返回原消息，时间线不产生重复或孤儿消息

#### Scenario: Feishu 入站映射稳定事件身份
- **WHEN** Feishu adapter 规范化一条 provider message event
- **THEN** Gateway 收到的 typed identity 以该 app identity 区分 connector account，并以 provider message id 区分事件
- **AND** 重放同一 provider event 复用同一影子同步记录

#### Scenario: 外部 adapter 缺少稳定事件身份
- **GIVEN** 一个 external adapter 无法为某入站提供 provider-stable message/event/delivery id
- **WHEN** Gateway 接收该入站
- **THEN** 外部 Agent run 与回复仍可继续，但该事件不进入 shadow conversation 同步，不创建 shadow conversation、用户消息、Agent 消息或配置边界，并暴露可诊断 contract failure
- **AND** Gateway 不以聊天 id、回复文本或文本 hash 伪造事件身份

#### Scenario: Agent 镜像使用稳定输出身份
- **GIVEN** 同一外部事件的同一 run 产生一个或多个逻辑 Agent 气泡
- **WHEN** Gateway live 投递、终态调和，或因重启/响应后崩溃重放其中任一气泡
- **THEN** 每条气泡始终按事件、run 与持久化 bubble ordinal 派生的同一稳定消息身份去重，final 与中间气泡的身份规则一致
- **AND** 回复正文变化、Kernel message id 晚到或 provider response id 是否已返回均不改变该 source identity
