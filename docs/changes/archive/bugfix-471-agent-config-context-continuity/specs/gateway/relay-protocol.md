# gateway (personal_assistant) - Relay Protocol Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: Gateway 可靠上报聊天实际采用的配置边界

当某聊天首次采用不同的有效运行配置时，Gateway 先持久记录稳定的配置边界 intent；已有 IM user anchor 的 intent 直接进入 durable outbox，外部 channel 尚无 anchor 时以 shadow saga identity 保持 pending，取得 anchor 后才进入 outbox。Gateway 经既有 WebSocket 串行 ACK 通道发送 `agent.config.boundary`，只有 IM durable success ACK 才删除 outbox item；断线、error ACK 或进程重启后保留并继续处理。该事实不复用 run report 或 message delivery receipt，也不携带 prompt、完整配置、secret、工具参数或变更字段明细。

#### Scenario: IM 断线后重放配置边界
- **GIVEN** Gateway 已持久记录聊天配置边界，但 IM 暂时断线
- **WHEN** 连接恢复或 Gateway 重启后重新注册
- **THEN** Gateway 重放同一 `agent.config.boundary`，直到收到 durable success ACK
- **AND** 重放使用相同幂等身份

#### Scenario: error ACK 保留待投递事实
- **WHEN** IM 因归属、anchor 或持久化错误返回 error ACK
- **THEN** Gateway 不删除本地 outbox item，也不把 error ACK 当作已交付
- **AND** 可重试错误退避重放，确定性校验错误保留为可诊断状态，均不阻塞其他待投递事实

### Requirement: 外部 channel shadow mirror 以稳定事件身份可恢复补写

外部入站 adapter 在 normalized message 上提供 typed provider-stable event identity，包含 connector/account identity 与 provider message/event/delivery id；Gateway 不从松散 metadata、`external_chat_id` 或文本 hash 推导它。Gateway 在运行前持久记录该 identity 与 canonical payload。IM 可用时，Gateway 按固定顺序幂等找建 shadow conversation、创建 shadow user message、按 stable run/output identity 补写 Agent reply，再投递锚定配置边界；IM 离线时外部回复不等待，Gateway 重启或 IM 恢复后重放未完成步骤。

#### Scenario: IM 离线时外部回复继续
- **GIVEN** 外部消息已持久进入 shadow 同步流程，IM 当前不可达
- **WHEN** Agent 完成回复
- **THEN** 回复照常投递到外部 channel，待补写步骤保持可恢复

#### Scenario: 恢复后补齐原 shadow 时间线
- **WHEN** IM 恢复或 Gateway 重启并重放同一外部事件
- **THEN** Gateway 复用稳定事件身份补齐唯一用户消息与 Agent 回复
- **AND** 配置边界只在 user message anchor 确认后投递，并位于该消息之前

#### Scenario: HTTP 成功后本地标记前崩溃
- **GIVEN** IM 已创建某 shadow message，但 Gateway 在记录返回 id 前崩溃
- **WHEN** Gateway 重启并重放同一步骤
- **THEN** IM 按 caller idempotency key 返回原 message，时间线不产生重复或孤儿消息

#### Scenario: Feishu 入站映射稳定事件身份
- **WHEN** Feishu adapter 规范化一条 provider message event
- **THEN** Gateway 收到的 typed identity 以该 app identity 区分 connector account，并以 provider message id 区分事件
- **AND** 重放同一 provider event 复用同一 shadow saga

#### Scenario: 外部 adapter 缺少稳定事件身份
- **GIVEN** 一个 external adapter 无法为某入站提供 provider-stable message/event/delivery id
- **WHEN** Gateway 接收该入站
- **THEN** 外部 Agent 回复仍可继续，但该事件不创建 durable shadow saga 或配置边界，并暴露可诊断降级状态
- **AND** Gateway 不以聊天 id、回复文本或文本 hash 伪造事件身份

#### Scenario: Agent mirror 使用稳定输出身份
- **GIVEN** 同一外部事件的 Agent run 已产生最终回复或带 Kernel message id 的可见输出
- **WHEN** Gateway 因重启或响应后崩溃而重放 shadow mirror
- **THEN** 最终回复按 saga 与 run 的 final identity 去重，其他输出按 saga、run、output kind 与 logical output id 去重
- **AND** 回复文本变化或 provider response id 是否已返回不改变 source identity

## MODIFIED Requirements

N/A.

## REMOVED Requirements

N/A.
