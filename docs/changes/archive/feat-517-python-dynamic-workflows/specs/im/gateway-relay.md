# IM - Gateway Relay Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 后台 agent 通知实时到达在线用户,无需刷新

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
