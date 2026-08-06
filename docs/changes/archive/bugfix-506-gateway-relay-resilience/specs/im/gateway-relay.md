# IM Gateway Relay Specification (delta for bugfix-506)

## MODIFIED Requirements

### Requirement: 消息中继与流式回复幂等,投递回执推进状态

同一消息以相同 `idempotency_key` 重复中继时,IM 复用同一 relay 任务,**不产生重复消息/重复投递**。同一 Agent 流式回复增量以稳定 `idempotency_key` 重传时,IM 只追加和发布一次,因此 Gateway 在 ACK 丢失后重连补发不会使用户看到重复正文。Gateway 上行 `node.delivery_receipt` 把对应消息的 `delivery_status` 沿 `sent` → `completed` 推进, 并回流到前端可见的消息投递状态。

#### Scenario: 重复 idempotency_key 不产生第二条中继
- **GIVEN** 一条消息已用某 `idempotency_key` 中继过
- **WHEN** 同一消息以同一 `idempotency_key` 再次中继
- **THEN** 复用同一中继任务(不新建),终端用户侧不出现重复消息

#### Scenario: 重传同一流式回复增量只显示一次
- **GIVEN** IM 已将某 Agent `message_delta` 以稳定 `idempotency_key` 追加到一条 running 回复
- **WHEN** Gateway 因 ACK 丢失或重连再次发送同一增量
- **THEN** IM 返回成功确认，但不再次追加正文，也不向用户流发布第二条相同 delta

#### Scenario: 投递回执推进消息投递状态
- **WHEN** Gateway 上行该消息的 `node.delivery_receipt`(先 `sent` 后 `completed`)
- **THEN** 该消息投递状态相应推进至 `completed`,前端读取/事件流可见终态
