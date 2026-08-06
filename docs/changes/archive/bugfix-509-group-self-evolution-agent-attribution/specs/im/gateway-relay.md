# IM gateway-relay Specification (delta for bugfix-509)

## ADDED Requirements

### Requirement: IM 持久接收并实时发布结构化自进化 system notification

IM 接收 Gateway 的自进化 system notification 时，校验来源 AgentProfile 属于当前已认证 node，synthetic agent user 属于目标 conversation，并以当时的 `AgentProfile.display_name` 保存来源快照。IM 按 Gateway 的稳定 session-event 投递身份幂等持久化来源、更新对象与 system message；首次成功写入后经 canonical `message.created` 发布完整消息，重放只返回原消息。历史 REST 与实时事件暴露同一结构化 notice。普通或历史 system message 不带 notice 时继续按原正文工作。

#### Scenario: 合法来源通知持久化并实时发布
- **GIVEN** 来源 Agent 是目标 conversation 的参与者
- **WHEN** Gateway 上行包含来源 Agent id 与更新对象的 self-evolution system notification
- **THEN** IM 持久化 `sender_type=system` 的消息及来源显示名快照
- **AND** 在线浏览器无需刷新即可从 `message.created` 收到完整 notice

#### Scenario: 刷新后读取相同快照
- **GIVEN** 用户已实时看到一条 self-evolution system notification
- **WHEN** 用户刷新或重新进入 conversation 并读取历史
- **THEN** REST 返回与实时事件相同的来源 Agent、显示名快照和更新对象

#### Scenario: commit 后 ACK 丢失不产生重复通知
- **GIVEN** IM 已持久化并发布一条 self-evolution system notification，但 ACK 未到达 Gateway
- **WHEN** Gateway 以相同 session-event 投递身份重发
- **THEN** IM 返回首次创建的同一 message id，不再插入消息或发布第二个 `message.created`

#### Scenario: 来源 Agent 不属于 node 或会话时拒绝归因
- **WHEN** Gateway 上报的来源 AgentProfile 不属于当前已认证 node、profile/当前显示名不存在或其 synthetic agent user 不是目标 conversation 的参与者
- **THEN** IM 返回稳定 error ACK，不持久化也不向浏览器发布这条错误归因的通知

#### Scenario: 旧 system message 保持兼容
- **WHEN** IM 读取或接收一条没有结构化 notice 的普通或历史 system message
- **THEN** 消息仍以既有 content 和 system sender 语义返回，不因缺少 notice 失败

## MODIFIED Requirements

（无）

## REMOVED Requirements

（无）
