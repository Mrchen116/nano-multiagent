# im/gateway-relay Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。原有 Scenario 完整保留，作用域由各 Requirement 开头的模式限定确定。

## MODIFIED Requirements

### Requirement: Gateway 上报实际配置边界并在 durable ACK 后完成投递

本条按 conversation/首条用户消息定位的配置边界及 Scenario 适用于 `single_thread`。global 的实际配置应用事实随主工作轮次经工作记录同步，作用域和持久回看见 [agent-work](agent-work.md)；不为全局主上下文构造聊天锚点。

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

### Requirement: IM 是可选中心服务,离线与中继关闭都不连累外部 IM 主路径

以下外部 IM 自动回复及离线完整主路径 Scenario 适用于 `single_thread`。global 在 IM 离线时仍可本地接受和读取已收到消息；显式投递依赖既有目标解析/投递链的实际可用性，不可用明确失败，不能报告发送成功。global 的工作记录本地持久并在重连同步，见 [agent-work](agent-work.md)。两种模式均不在 IM 内执行 agent。

IM 整体离线时,经 Node Gateway Channel 的外部 IM 主路径仍可用(Gateway 本地自治);中继单独关闭时,IM 仍作为配置中心独立可用。IM 不直接调用 agent 内核,所有 Agent 执行经 Node Gateway 中继。

#### Scenario: IM 离线不影响外部 IM 主路径
- **GIVEN** IM 服务不可达
- **WHEN** 终端用户经外部 IM 与 Agent 交互
- **THEN** Node Gateway 本地自治继续处理,主路径不受 IM 可用性影响

#### Scenario: 关闭中继后配置中心仍可用
- **GIVEN** 中继能力被关闭
- **WHEN** 前端访问 Agent 配置 / 节点管理等配置中心接口
- **THEN** 这些接口照常可用(仅 Web IM 聊天链路停用)

### Requirement: 后台 agent 通知实时到达在线用户,无需刷新

以下后台普通回复、气泡及 message-scoped sidecar Scenario 适用于 `single_thread`。global 的后台返回及综合过程进入 [agent-work](agent-work.md) 的工作轨迹，不因任务完成自动创建聊天消息；显式发送的消息仍沿原实时投递链。

Agent 的任意后台任务完成后回发给人类用户的通知，与前台回复一样实时到达：在线浏览器无需刷新即可看到一次性完整终态消息，不经历可见空泡或“生成中”。既有 background Bash 继续保留这条文本气泡契约。对后台 subagent / Workflow，同一消息还持久保存结构化后台返回，作为“过程”中的可归因原始结果。消息只进入存储、要刷新才显示，或实时可见但刷新后丢失 sidecar，都不满足本契约。

#### Scenario: 后台通知在在线用户流中实时长出气泡
- **GIVEN** 用户浏览器已建立用户流连接(`/im/ws/user`)
- **WHEN** 该用户某个 Agent 的后台任务完成并回发通知，包括 background Bash
- **THEN** 浏览器收到一帧 `op:"event"`、`event_type:"message.created"`，消息内容即最终全文、投递状态 `completed`；用户无需刷新即可看到该气泡

#### Scenario: subagent 与 Workflow 气泡同时携带结构化后台返回
- **GIVEN** 用户浏览器已建立用户流连接(`/im/ws/user`)
- **WHEN** 后台 subagent 或 Workflow 结束并由 parent Agent 回发普通回复
- **THEN** 浏览器收到的终态消息正文是主 Agent 的最终回复
- **AND** `background_returns` 含对应 task id/type、status、原始 result/error，以及存在的 agent/run identity、usage、duration 和 artifact locator

#### Scenario: 历史读取恢复相同后台返回
- **GIVEN** 含后台返回的消息已经送达
- **WHEN** 用户刷新、重连或重新打开会话历史
- **THEN** 同一消息恢复内容相同、顺序相同的后台返回过程项

#### Scenario: 同一后台通知重发不产生重复气泡
- **GIVEN** 某条后台通知已送达并在会话中显示
- **WHEN** Gateway 重启后按同一 task id 重发
- **THEN** 会话不新增第二条气泡，原消息中的后台返回也只保留一条

#### Scenario: 一条回复消费多条后台通知
- **WHEN** parent 在同一 round boundary 消费多条后台 notification 并形成一条回复
- **THEN** IM 按消费顺序持久化多条后台返回，每条按自己的 task id 幂等

#### Scenario: idle 后台回复只有结构化返回时仍实时可见
- **WHEN** Gateway 投递的 `agent.message` 正文为空，但 `background_returns` 非空
- **THEN** IM 接受并持久化该消息，在同一 `message.created` 中完整发布 sidecar，浏览器显示可展开过程项
- **AND** 不制造占位文本；只有正文与 sidecar 都为空时才拒绝消息
