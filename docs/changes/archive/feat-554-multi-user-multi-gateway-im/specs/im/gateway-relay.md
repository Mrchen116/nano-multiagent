# feat-554 — im/gateway-relay

> 目标: docs/specs/im/gateway-relay.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## REMOVED Requirements

### Requirement: 配置边界使用 owner 用户流的持久事件与恢复语义


## MODIFIED Requirements

### Requirement: Gateway 上报实际配置边界并在 durable ACK 后完成投递

本条按 conversation/首条用户消息定位的配置边界及 Scenario 适用于 `single_thread`。global 的实际配置应用事实随主工作轮次经工作记录同步，作用域和持久回看见 [agent-work](agent-work.md)；不为全局主上下文构造聊天锚点。

Gateway 经 `/im/ws/gateway` 上行 `agent.config.boundary`，将某聊天真正采用新运行配置的事实关联到首条用户消息。IM 校验当前已注册 node 与 Agent profile 的管理归属一致、该 Agent 是聊天成员且锚点消息属于该聊天，幂等持久化成功后才返回 success ACK；持久化或关联校验失败返回稳定 error ACK。重复上报同一边界复用既有条目，不产生重复时间线项。

#### Scenario: 配置边界持久化后返回成功 ACK
- **GIVEN** Gateway 当前已注册，node 与 Agent profile 的管理归属一致、该 Agent 是聊天成员且锚点消息属于该聊天
- **WHEN** Gateway 上行一条新的 `agent.config.boundary`
- **THEN** IM 持久化唯一配置边界后返回 success ACK
- **AND** 当前聊天成员的历史读取与用户事件流最终可见该边界；未参与聊天的 Agent 管理者不因此取得读取资格

#### Scenario: 重复上报复用同一边界
- **GIVEN** 某配置边界已持久化但 Gateway 未收到 ACK
- **WHEN** Gateway 以相同幂等身份重发
- **THEN** IM 返回同一成功结果，时间线不新增第二条边界

#### Scenario: 归属或持久化失败不返回成功 ACK
- **WHEN** node／profile 管理归属、Agent 聊天成员关系或锚点关联不一致，或 IM 无法持久化边界
- **THEN** IM 返回稳定 error ACK，不把该边界发布给浏览器

#### Scenario: 跨管理归属群上报配置边界
- **GIVEN** C 管理的 Agent 与 A 同在 A 创建的群
- **WHEN** C 的已注册 Gateway 上报该 Agent 新采用配置的边界
- **THEN** 群成员看到正确边界，不因 conversation owner 与 node owner 不同被拒；未在群内的 Agent 或错误节点仍被拒。


### Requirement: 工具调用的授权决策随消息持久化与下发

IM 持久化并下发的工具调用数据，在原有字段（status / reason / detail / emoji / duration）之外，携带 「该工具调用是否经用户显式授权/拒绝」的标识。该标识在实时下发（WebSocket）与历史加载（REST）两条路径上一致，页面刷新后不丢失；无标识的历史工具调用保持兼容（不携带该字段）。

#### Scenario: 经用户授权的工具调用在历史加载中保留标识
- **GIVEN** 一条已落库的 agent 消息，其中某工具调用经用户授权允许
- **WHEN** 客户端重新加载该会话历史
- **THEN** 该工具调用数据携带「经用户授权允许」标识

#### Scenario: 旧工具调用无标识仍可加载
- **GIVEN** 一条历史消息的工具调用是在本能力上线前落库的、无授权标识
- **WHEN** 客户端加载该会话
- **THEN** 该工具调用正常加载，不携带授权标识、不报错

#### Scenario: 单 Thread 群成员操作任意现有批准选项
- **GIVEN** 不同 Gateway 的 Agent 同在群内，其中一个单 Thread Agent 等待批准
- **WHEN** 非管理者群成员操作其批准卡的现有任一选项
- **THEN** 决定送达产生该请求的 Agent 执行；聊天显示同一决定和提交者，其他 Agent 的执行不被误操作。

#### Scenario: 并发决定与离线确认
- **GIVEN** 多人操作同一张卡，或节点离线、确认迟到
- **WHEN** 决定提交、重试或服务重连
- **THEN** 同一请求只有一个生效决定，不重复执行工具；仅提交成功时显示等待确认，收到真实完成结果后才显示已生效。

#### Scenario: 全局模式保留自动审批
- **WHEN** 全局 Agent 在协作中执行需要授权判断的操作
- **THEN** 仍按既有自动审批和主动沟通处理，不新增工具批准卡，也不绕过授权判断。

### Requirement: 消息中继与流式回复幂等,投递回执推进状态

以下消息及显式投递的幂等、回执规则继续适用。global 入站 recipient 的 completed 仅表示已持久交给 Inbox，不代表主 Agent 已阅读或完成工作；无模型运行期间的预建回复气泡，后续发言是显式发送的独立消息。工作进展见 [agent-work](agent-work.md)。

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

#### Scenario: 多节点群独立投递
- **GIVEN** 群内 Agent 分属多个 Gateway，其中一台离线
- **WHEN** 不同真人成员按既有触发规则交办工作
- **THEN** 每个目标 Agent 收到真实发送者的输入，在线节点继续交付；离线目标显示真实未完成状态，不阻断其他目标。


## ADDED Requirements

### Requirement: 配置边界使用聊天成员用户流的持久事件与恢复语义

配置边界持久为 conversation event，并经 `/im/ws/user` 的 canonical `op:"event"` 信封发布，`event_type` 为 `agent.config.changed`。它与消息事件共享 成员范围内的 event id、resume replay、high-water 去重和 `resync_required` 语义；浏览器 payload 只含定位与展示所需字段，不暴露 runtime fingerprint、profile provenance、prompt、完整配置、secret、工具参数或变更字段明细。

#### Scenario: 在线浏览器实时收到配置边界
- **GIVEN** 当前聊天成员的浏览器已连接 `/im/ws/user`
- **WHEN** IM 持久化一条配置边界
- **THEN** 浏览器收到带唯一 event id 的 `agent.config.changed` event 信封
- **AND** payload 可定位 conversation、agent 与锚点消息

#### Scenario: 断线恢复重放配置边界
- **GIVEN** 浏览器断线期间 IM 持久化了配置边界
- **WHEN** 浏览器用 `after_event_id` 恢复用户流
- **THEN** 边界按既有 replay 规则补发，live/replay 不产生重复时间线项
- **AND** 超出恢复窗口时浏览器收到既有 `resync_required` 并从 REST 恢复权威时间线

### Requirement: Gateway HTTP 数据操作使用当前注册连接的运行凭据

已授权 Gateway 成功注册后取得仅绑定当前连接与 node 的不透明运行凭据，用于消息镜像和附件等机器数据操作。它与真人 access JWT 不互相替代，不授予人的聊天或配置管理权限。

#### Scenario: 机器为非管理者的聊天交付图片
- **GIVEN** B 与 A 管理的 Agent 私聊，A 本人不是成员
- **WHEN** A 的 Gateway 用当前运行凭据及所属 Agent 上传或读取该聊天附件
- **THEN** 操作按 node／Agent／聊天关系成功，B 能看到图文交付；A 的普通真人 JWT 仍无法读取 B 的原聊天和附件。

#### Scenario: 运行凭据过期或节点身份不匹配
- **GIVEN** Gateway 已断开、被新连接取代，或请求 Agent 不属于该 node
- **WHEN** 客户端使用旧运行凭据或伪造 node／Agent 关系执行机器操作
- **THEN** 请求被拒，不通过降级为 owner 读取或加入真人成员恢复；重新注册后只能使用新运行凭据。

#### Scenario: shadow 代记不冒充真人
- **GIVEN** Gateway 正在镜像其已有外部来源聊天
- **WHEN** 用运行凭据提交外部真人消息或 Agent 富消息
- **THEN** 沿用原来源身份、幂等及调和语义；普通真人 JWT 不能用同一机器入口冒充 Agent、system 或外部真人。

#### Scenario: 机器凭据仅限机器数据入口
- **WHEN** 用 Gateway 运行凭据请求账号、策略、设备绑定、完整配置管理或真人用户流
- **THEN** 请求被拒；正常 owner JWT 的管理能力保持不变。
