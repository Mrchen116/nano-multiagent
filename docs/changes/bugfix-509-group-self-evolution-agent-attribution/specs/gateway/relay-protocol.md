# gateway relay-protocol Specification (delta for bugfix-509)

## ADDED Requirements

### Requirement: Gateway 向 IM 中继可本地化且可归因的自进化通知

Gateway 消费某 Agent 的 `self_evolution_review` session event 时，继续把它作为非第一人称 system notification 送往原 IM conversation，同时携带由本次 Gateway delivery incarnation 与 session event 共同确定的稳定投递身份、来源 Agent id 与更新对象语义；不得只发送需要消费者解析的固定英文正文。Gateway 等待 IM 业务 ACK，并确认 ACK 含已持久化的非空 message id；拒绝、超时、断线或 malformed ACK 可被通知 callback 诊断，但不改变后台 review 或前台聊天结果。Gateway 不改变 Coding CLI 的事件或提示行为。

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

#### Scenario: Gateway 重启后的新事件不碰撞旧通知
- **GIVEN** 旧 Gateway 已投递某 session sequence 的通知，随后 Gateway 进程重启且 Kernel event sequence 从相同数字重新开始
- **WHEN** 新 Gateway 消费重启后的新 self-evolution event
- **THEN** 新 delivery incarnation 使其投递身份不同于历史通知，不被 IM 误判为旧消息重放

#### Scenario: 通知失败不改变后台任务结果
- **WHEN** IM 断线、ACK 超时、拒绝来源归属或无法持久化该 system notification
- **THEN** Gateway 记录可诊断失败，但不把通知投递失败变成 self-evolution review 或前台聊天失败

## MODIFIED Requirements

（无）

## REMOVED Requirements

（无）
