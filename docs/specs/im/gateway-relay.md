# IM - Gateway Relay Specification

> 对齐: bugfix-471
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

IM 与 Gateway 之间 WebSocket、中继任务、离线边界、后台通知、liveness 看门狗和授权决策持久化的契约。

## Requirements

### Requirement: Gateway 经 /im/ws/gateway 持久双向连接，协议帧契约稳定

Node Gateway 主动向 IM 建 `/im/ws/gateway` 持久连接，所有双向通信复用之。既有上下行帧保持；Gateway 额外上行 `agent.config.boundary`，IM 仅在配置边界 durable insert 成功后返回 success ACK。非法、不支持或持久化失败的帧返回稳定错误信封，不静默丢弃或崩连接。

#### Scenario: 非 JSON 帧返回 invalid_message 错误信封
- **WHEN** Gateway 经 `/im/ws/gateway` 发非 JSON 文本
- **THEN** 收到稳定 `invalid_message` 错误信封

#### Scenario: 不支持的消息类型返回 unsupported_message_type
- **WHEN** Gateway 发 `{type:"unknown.type", payload:{}}`
- **THEN** 收到稳定 `unsupported_message_type` 错误信封

#### Scenario: 配置边界复用串行 ACK 通道
- **WHEN** Gateway 上行 `agent.config.boundary`
- **THEN** 该业务帧与其他需确认业务帧按连接顺序等待 ACK，ACK 表示 IM 已完成 durable insert 或幂等命中

### Requirement: Gateway 上报实际配置边界并在 durable ACK 后完成投递

Gateway 经 `/im/ws/gateway` 上行 `agent.config.boundary`，将某聊天真正采用新运行配置的事实关联到首条用户消息。IM 校验已注册 node、owner、conversation、agent 与锚点归属，幂等持久化成功后才返回 success ACK；持久化或归属校验失败返回稳定 error ACK。重复上报同一边界复用既有条目，不产生重复时间线项。

#### Scenario: 配置边界持久化后返回成功 ACK
- **GIVEN** Gateway 已注册且 owner、conversation、agent 与锚点归属一致
- **WHEN** Gateway 上行一条新的 `agent.config.boundary`
- **THEN** IM 持久化唯一配置边界后返回 success ACK
- **AND** owner 的历史读取与用户事件流最终可见该边界

#### Scenario: 重复上报复用同一边界
- **GIVEN** 某配置边界已持久化但 Gateway 未收到 ACK
- **WHEN** Gateway 以相同幂等身份重发
- **THEN** IM 返回同一成功结果，时间线不新增第二条边界

#### Scenario: 归属或持久化失败不返回成功 ACK
- **WHEN** node、owner、conversation、agent 或锚点归属不一致，或 IM 无法持久化边界
- **THEN** IM 返回稳定 error ACK，不把该边界发布给浏览器

### Requirement: 配置边界使用 owner 用户流的持久事件与恢复语义

配置边界持久为 conversation event，并经 `/im/ws/user` 的 canonical `op:"event"` 信封发布，`event_type` 为 `agent.config.changed`。它与消息事件共享 owner-scoped event id、resume replay、high-water 去重和 `resync_required` 语义；浏览器 payload 只含定位与展示所需字段，不暴露 runtime fingerprint、profile provenance、prompt、完整配置、secret、工具参数或变更字段明细。

#### Scenario: 在线浏览器实时收到配置边界
- **GIVEN** owner 浏览器已连接 `/im/ws/user`
- **WHEN** IM 持久化一条配置边界
- **THEN** 浏览器收到带唯一 event id 的 `agent.config.changed` event 信封
- **AND** payload 可定位 conversation、agent 与锚点消息

#### Scenario: 断线恢复重放配置边界
- **GIVEN** 浏览器断线期间 IM 持久化了配置边界
- **WHEN** 浏览器用 `after_event_id` 恢复用户流
- **THEN** 边界按既有 replay 规则补发，live/replay 不产生重复时间线项
- **AND** 超出恢复窗口时浏览器收到既有 `resync_required` 并从 REST 恢复权威时间线

### Requirement: 消息中继幂等,投递回执推进状态

同一消息以相同 `idempotency_key` 重复中继时,IM 复用同一 relay 任务,**不产生重复消息/重复投递**;
Gateway 上行 `node.delivery_receipt` 把对应消息的 `delivery_status` 沿 `sent` → `completed` 推进,
并回流到前端可见的消息投递状态。

#### Scenario: 重复 idempotency_key 不产生第二条中继
- **GIVEN** 一条消息已用某 `idempotency_key` 中继过
- **WHEN** 同一消息以同一 `idempotency_key` 再次中继
- **THEN** 复用同一中继任务(不新建),终端用户侧不出现重复消息

#### Scenario: 投递回执推进消息投递状态
- **WHEN** Gateway 上行该消息的 `node.delivery_receipt`(先 `sent` 后 `completed`)
- **THEN** 该消息投递状态相应推进至 `completed`,前端读取/事件流可见终态

### Requirement: IM 是可选中心服务,离线与中继关闭都不连累外部 IM 主路径

IM 整体离线时,经 Node Gateway Channel 的外部 IM 主路径仍可用(Gateway 本地自治);中继单独关闭时,IM 仍
作为配置中心独立可用。IM 不直接调用 agent 内核,所有 Agent 执行经 Node Gateway 中继。

#### Scenario: IM 离线不影响外部 IM 主路径
- **GIVEN** IM 服务不可达
- **WHEN** 终端用户经外部 IM 与 Agent 交互
- **THEN** Node Gateway 本地自治继续处理,主路径不受 IM 可用性影响

#### Scenario: 关闭中继后配置中心仍可用
- **GIVEN** 中继能力被关闭
- **WHEN** 前端访问 Agent 配置 / 节点管理等配置中心接口
- **THEN** 这些接口照常可用(仅 Web IM 聊天链路停用)

### Requirement: 后台 agent 通知实时到达在线用户,无需刷新

Agent 后台任务(`run_in_background`)完成后回发给人类用户的通知,与前台回复一样实时到达:
在线用户的浏览器在不刷新的前提下,立即看到该通知作为一条新消息气泡出现。通知一次性携带
完整内容送达,不经历可见的空泡或"生成中"中间态。消息只进入存储、要刷新才显示,不满足本契约。

#### Scenario: 后台通知在在线用户流中实时长出气泡
- **GIVEN** 用户浏览器已建立用户流连接(`/im/ws/user`)
- **WHEN** 该用户某个 agent 的后台任务完成并回发通知
- **THEN** 浏览器收到一帧 `op:"event"`、`event_type:"message.created"`,消息内容即最终全文、
  投递状态 `completed`;用户无需刷新即可看到该气泡

#### Scenario: 同一后台通知重发不产生重复气泡
- **GIVEN** 某条后台通知已送达并在会话中显示
- **WHEN** Gateway 重启后重发同一条通知
- **THEN** IM 识别其为同一通知,用户流不再新增第二条气泡,会话中该通知仍只有一条

### Requirement: Gateway 可原子回滚未形成用户回复的 provisional 消息

Gateway 为普通聊天预先创建的 `running` agent 消息是 provisional 状态。若 Agent 最终选择协议静默,
Gateway 发送 `message_discarded`;IM 在同一事务内留下可重放 tombstone、删除 provisional 消息及其
message-scoped 过程事件,并恢复会话 preview / last_message_at / unread_count。浏览器收到 tombstone 后按
message_id 移除占位气泡;重复 discard 幂等,刷新历史也不得重新出现该消息。

#### Scenario: NO_REPLY 回滚 running 占位且断线后不复活
- **GIVEN** 某群聊 Agent run 已创建 running 占位消息
- **WHEN** Gateway 判定完整 assistant message 为静默 token 并发送 `message_discarded`
- **THEN** IM 删除该消息并广播 `message.discarded`,会话投影恢复到该消息出现前
- **AND** 在线浏览器移除占位;断线客户端重放 tombstone 或刷新历史后同样看不到该消息

### Requirement: 中继看门狗按 liveness 判存活,不误杀活着但安静的消息

中继看门狗判定某 `running` 消息是否失去进展时,依据其存活信号是否仍在刷新:agent run 在"活着但安静"
窗口内产生的 liveness 心跳(执行静默长工具 / 等待 LLM / 等待用户权限决策,三类同源)必须推进该消息的
存活判定(推进最近事件时间戳或刷新通用存活标记),使活跃 run 不被误判为卡死。看门狗对上述窗口不再按
类型分别豁免(不再有 permission 专用特例)。只有在判定窗口内既无新事件也无 liveness 心跳的消息才被回收为
`failed`;维持存活信号的 Gateway/内核崩溃后心跳停止,存活信号 stale 超过回收阈值,该消息仍被正常回收,
不永久停留 running。

#### Scenario: 活跃长工具的消息不被误收
- **GIVEN** 某 running 消息对应的 run 正在执行静默长工具并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息因存活信号持续刷新而不被判超时收尾

#### Scenario: 等待 LLM 的消息不被误收
- **GIVEN** 某 running 消息对应的 run 长时间等待 LLM 返回但连接活着并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾

#### Scenario: 等待权限的消息不被误收
- **GIVEN** 某 running 消息对应的 run parked 等待用户权限决策、Gateway 存活并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾,无需 permission 专用豁免;用户决定后仍能继续

#### Scenario: 真静默消息仍被兜底收尾
- **GIVEN** 某 running 消息在判定窗口内无任何新事件(含心跳)、存活信号 stale 超过回收阈值
- **WHEN** 看门狗扫描
- **THEN** 该消息被翻为 `failed` 并推 `relay.failed`,徽标随之收口,不永久停留 running

### Requirement: 工具调用的授权决策随消息持久化与下发

IM 持久化并下发的工具调用数据，在原有字段（status / reason / detail / emoji / duration）之外，携带
「该工具调用是否经用户显式授权/拒绝」的标识。该标识在实时下发（WebSocket）与历史加载（REST）两条路径
上一致，页面刷新后不丢失；无标识的历史工具调用保持兼容（不携带该字段）。

#### Scenario: 经用户授权的工具调用在历史加载中保留标识
- **GIVEN** 一条已落库的 agent 消息，其中某工具调用经用户授权允许
- **WHEN** 客户端重新加载该会话历史
- **THEN** 该工具调用数据携带「经用户授权允许」标识

#### Scenario: 旧工具调用无标识仍可加载
- **GIVEN** 一条历史消息的工具调用是在本能力上线前落库的、无授权标识
- **WHEN** 客户端加载该会话
- **THEN** 该工具调用正常加载，不携带授权标识、不报错
