# IM gateway-relay Specification (delta for bugfix-518)

## MODIFIED Requirements

### Requirement: 消息中继与流式回复幂等,投递回执推进状态

同一消息以相同 `idempotency_key` 重复中继时,IM 复用同一 relay 任务,**不产生重复消息/重复投递**。
对受支持的普通聊天动作，IM 可将经过 owner/route 校验的 opaque action metadata 随该唯一 relay task
送到目标 Gateway；metadata 不得成为浏览器消息历史或 Gateway local filesystem 路径的投影。同一
Agent 流式回复增量以稳定 `idempotency_key` 重传时,IM 只追加和发布一次,因此 Gateway 在 ACK 丢失后
重连补发不会使用户看到重复正文。Gateway 上行 `node.delivery_receipt` 把对应消息的
`delivery_status` 沿 `sent` → `completed` 推进, 并回流到前端可见的消息投递状态。

#### Scenario: 历史会话蒸馏身份随唯一 relay 可靠到达
- **GIVEN** 用户提交了已通过 owner 与同 Gateway 校验的历史会话蒸馏消息
- **WHEN** IM 创建或重放该消息的 relay task
- **THEN** 目标 Gateway 收到同一组 source conversation/Agent identities 与 scope
- **AND** IM 不读取或传递任何 Gateway workspace、JSONL 或 transcript 内容

#### Scenario: 重复 idempotency_key 不产生第二条中继
- **GIVEN** 一条消息已用某 `idempotency_key` 中继过
- **WHEN** 同一消息以同一 `idempotency_key` 再次中继
- **THEN** 复用同一中继任务(不新建),终端用户侧不出现重复消息

#### Scenario: 同一流式增量重传只追加一次
- **GIVEN** Gateway 已发送某 Agent reply 的一个带稳定 `idempotency_key` 的流式增量
- **WHEN** Gateway 因 ACK 丢失重传该增量
- **THEN** IM 只追加和发布一次该正文增量，用户不看到重复文本

#### Scenario: 投递回执推进消息投递状态
- **WHEN** Gateway 上行该消息的 `node.delivery_receipt`(先 `sent` 后 `completed`)
- **THEN** 该消息投递状态相应推进至 `completed`,前端读取/事件流可见终态

#### Scenario: 蒸馏来源失败的回执使消息可见失败
- **GIVEN** Gateway 在模型运行前不能验证蒸馏来源或 execution runtime capability
- **WHEN** Gateway 上行该消息的 failed `node.delivery_receipt`
- **THEN** IM 将该用户消息标记为 `failed`，并在既有读取/事件流中暴露 actionable failure state
