# gateway relay-protocol Specification (delta for bugfix-509)

## ADDED Requirements

### Requirement: Gateway 向 IM 中继可本地化且可归因的自进化通知

Gateway 消费某 Agent 的 `self_evolution_review` session event 时，继续把它作为非第一人称 system notification 送往原 IM conversation，同时携带稳定的 session-event 投递身份、来源 Agent id 与更新对象语义；不得只发送需要消费者解析的固定英文正文。Gateway 等待 IM 业务 ACK；拒绝、超时或断线可被通知 callback 诊断，但不改变后台 review 或前台聊天结果。Gateway 不改变 Coding CLI 的事件或提示行为。

#### Scenario: 群聊自进化事件保留来源 Agent
- **GIVEN** 一个 Gateway session 归属于群聊中的某个 Agent
- **WHEN** 该 session 发布 `self_evolution_review`
- **THEN** Gateway 发往 IM 的 system notification 携带该 session 的来源 Agent id
- **AND** 携带 skills、memory 或两者的结构化更新对象，不要求 IM 从英文正文反推语义

#### Scenario: 单聊沿同一结构化通知路径
- **GIVEN** 一个 Gateway session 归属于 IM 单聊中的 Agent
- **WHEN** 该 session 发布 `self_evolution_review`
- **THEN** Gateway 同样发送结构化来源与更新对象，供 IM 按单聊展示策略渲染

#### Scenario: ACK 丢失后重放保持同一投递身份
- **GIVEN** IM 已持久化一条 self-evolution notification，但 Gateway 未收到 ACK
- **WHEN** Gateway 连接恢复并重发该业务帧
- **THEN** 重发携带与首次相同的 session-event 投递身份，IM 可复用原消息而不是创建第二条

#### Scenario: 通知失败不改变后台任务结果
- **WHEN** IM 断线、ACK 超时、拒绝来源归属或无法持久化该 system notification
- **THEN** Gateway 记录可诊断失败，但不把通知投递失败变成 self-evolution review 或前台聊天失败

## MODIFIED Requirements

（无）

## REMOVED Requirements

（无）
