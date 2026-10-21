# IM gateway-relay Specification (delta for feat-630)

## MODIFIED Requirements

### Requirement: Gateway 经 /im/ws/gateway 持久双向连接，协议帧契约稳定

Node Gateway 主动向 IM 建立 `/im/ws/gateway` 持久连接，用于实时消息、回执、必要控制与小体积权威元数据。工作记录批量补传使用独立、按节点授权的同步入口；补传失败不阻断实时沟通。既有上行 `agent.config.boundary` 仍仅在配置边界 durable insert 成功后返回 success ACK。非法、不支持或持久化失败的帧返回稳定错误信封，不静默丢弃或崩连接。

#### Scenario: 非 JSON 帧返回 invalid_message 错误信封
- **WHEN** Gateway 经 `/im/ws/gateway` 发非 JSON 文本
- **THEN** 收到稳定 `invalid_message` 错误信封。

#### Scenario: 不支持的消息类型返回 unsupported_message_type
- **WHEN** Gateway 发 `{type:"unknown.type", payload:{}}`
- **THEN** 收到稳定 `unsupported_message_type` 错误信封。

#### Scenario: 配置边界保留 durable ACK 与必要顺序
- **WHEN** Gateway 上行 `agent.config.boundary`
- **THEN** ACK 表示 IM 已完成 durable insert 或幂等命中；同一配置边界及相关操作的因果顺序保持，不因历史工作记录补传而等待。

#### Scenario: 工作记录同步失败不拆实时连接
- **GIVEN** 实时通路仍可用
- **WHEN** 节点工作记录同步请求失败或超时
- **THEN** 消息、回执、停止与权限响应仍可通过实时连接，历史记录可以稍后恢复。

## ADDED Requirements

### Requirement: 已持久保存的消息在节点暂不可达时保留并自动投递

#### Scenario: 中心已保存而节点离线
- **WHEN** 用户发送消息，IM 已持久保存消息和目标投递任务，但目标节点暂不可达
- **THEN** 返回已保存的同一消息，保留待投递状态，不把暂时离线误报为消息未保存
- **AND** 节点恢复后自动投递，重试不产生第二条消息。

#### Scenario: 一个目标暂不可达
- **WHEN** 群聊消息的部分 Agent 不可达，其他目标仍可用
- **THEN** 各目标独立接收和恢复，晚到或重复确认不使已有终态回退，不阻断其他目标。

### Requirement: 实时请求确认与工作同步具有独立恢复边界

#### Scenario: 业务请求确认迟到
- **WHEN** 某请求超时后收到迟到确认，或同类其他请求正在进行
- **THEN** 确认只归属原请求，不误完成其他请求；结果未知的有副作用操作按原身份核对，不盲目重新执行。

#### Scenario: 历史积压与多节点恢复
- **WHEN** 大量历史记录积压或节点同时重连
- **THEN** 节点的正常消息与必要控制仍有处理机会，单节点补传不使其他用户的通信等待其清空历史。
