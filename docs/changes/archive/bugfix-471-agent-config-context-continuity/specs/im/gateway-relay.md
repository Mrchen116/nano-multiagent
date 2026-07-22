# IM - Gateway Relay Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: Gateway 上报实际配置边界并在 durable ACK 后完成投递

Gateway 经 `/im/ws/gateway` 上行 `agent.config.boundary`，将某聊天真正采用新运行配置的事实关联到首条用户消息。IM 校验已注册 node、owner、conversation、agent 与 anchor 归属，幂等持久化成功后才返回 success ACK；持久化或归属校验失败返回稳定 error ACK。重复上报同一边界复用既有 entry，不产生重复时间线项。

#### Scenario: 配置边界持久化后返回成功 ACK
- **GIVEN** Gateway 已注册且 owner、conversation、agent 与 anchor 归属一致
- **WHEN** Gateway 上行一条新的 `agent.config.boundary`
- **THEN** IM 持久化唯一配置边界后返回 success ACK
- **AND** owner 的历史读取与用户事件流最终可见该边界

#### Scenario: 重复上报复用同一边界
- **GIVEN** 某配置边界已持久化但 Gateway 未收到 ACK
- **WHEN** Gateway 以相同幂等身份重发
- **THEN** IM 返回同一成功结果，时间线不新增第二条边界

#### Scenario: 归属或持久化失败不返回成功 ACK
- **WHEN** node/owner/conversation/agent/anchor 归属不一致，或 IM 无法持久化边界
- **THEN** IM 返回稳定 error ACK，不把该边界发布给浏览器

### Requirement: 配置边界使用 owner 用户流的持久事件与恢复语义

配置边界持久为 conversation event，并经 `/im/ws/user` 的 canonical `op:"event"` 信封发布，`event_type` 为 `agent.config.changed`。它与消息事件共享 owner-scoped event id、resume replay、high-water 去重和 `resync_required` 语义；浏览器 payload 只含定位与展示所需字段，不暴露 runtime fingerprint、profile provenance、prompt、完整配置、secret、工具参数或变更字段明细。

#### Scenario: 在线浏览器实时收到配置边界
- **GIVEN** owner 浏览器已连接 `/im/ws/user`
- **WHEN** IM 持久化一条配置边界
- **THEN** 浏览器收到带唯一 event id 的 `agent.config.changed` event 信封
- **AND** payload 可定位 conversation、agent 与 anchor message

#### Scenario: 断线恢复重放配置边界
- **GIVEN** 浏览器断线期间 IM 持久化了配置边界
- **WHEN** 浏览器用 `after_event_id` 恢复用户流
- **THEN** 边界按既有 replay 规则补发，live/replay 不产生重复时间线项
- **AND** 超出恢复窗口时浏览器收到既有 `resync_required` 并从 REST 恢复权威时间线

## MODIFIED Requirements

### Requirement: Gateway 经 /im/ws/gateway 持久双向连接,协议帧契约稳定

Node Gateway 主动向 IM 建 `/im/ws/gateway` 持久连接，所有双向通信复用之。既有上下行帧保持；Gateway 额外上行 `agent.config.boundary`，IM 仅在配置边界 durable insert 成功后返回 success ACK。非法、不支持或持久化失败的帧返回稳定错误信封，不静默丢弃或崩连接。

#### Scenario: 不支持的消息类型返回 unsupported_message_type
- **WHEN** Gateway 发 `{type:"unknown.type", payload:{}}`
- **THEN** 收到稳定 `unsupported_message_type` 错误信封

#### Scenario: 配置边界复用串行 ACK 通道
- **WHEN** Gateway 上行 `agent.config.boundary`
- **THEN** 该业务帧与其他需确认业务帧按连接顺序等待 ACK，ACK 表示 IM 已完成 durable insert 或幂等命中

## REMOVED Requirements

N/A.
