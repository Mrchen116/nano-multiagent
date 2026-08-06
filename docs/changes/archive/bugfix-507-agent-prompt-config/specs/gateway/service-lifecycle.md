# gateway Service Lifecycle Specification (delta for bugfix-507)

> 对齐 canonical: `docs/specs/gateway/service-lifecycle.md`。

## MODIFIED Requirements

### Requirement: IM 服务在线时 Gateway 主动连出并保持双向通信

Gateway 始终**主动**向 IM 服务发起 WebSocket 持久连接(因其在 NAT 后,不能被反向连接)。连接上后注册节点、周期发心跳;经该连接接收下行的 Web IM 消息中继、配置同步、Agent 创建/能力解析、手动 heartbeat 触发。

#### Scenario: 连接后注册节点并周期心跳
- **GIVEN** 配置了 IM 服务地址
- **WHEN** Gateway 启动并连上 IM 服务 WebSocket
- **THEN** 首帧发 `node.register`(携带 node_id、agent 列表与四组 per-agent 种子映射——`agent_workspaces` / `agent_skills` / `agent_tool_allowlist` / `agent_custom_prompts`；最后一组只携带规范化后的非空 Custom Instructions；均为 agent_id → 本地 config 解析值的映射，供 IM 在首次落库时建立 profile；重连重发同帧内容一致), 随后在线期间周期发 `node.heartbeat`(含 `node_id` / `status=online` / `agent_count`), IM 服务据此刷新节点状态

#### Scenario: register ACK 是业务发送门禁且握手有界
- **GIVEN** Gateway transport 已连上 IM，但 `node.register` 尚未被确认
- **WHEN** register send 阻塞、IM 不返回 ACK 或明确拒绝该 control frame
- **THEN** Gateway 在默认 10 秒 handshake deadline 内断开该 socket并进入有界 reconnect backoff，期间不发送业务 FIFO
- **AND** ACK 一旦收到即开放业务发送并结束 handshake deadline；随后的配置收敛 callback 不被该 deadline 取消

#### Scenario: runtime workspace_root 以本地 config 为准,IM 镜像值不进入 runtime
- **GIVEN** IM 中某 agent profile 的 workspace_root 为路径 A,Gateway 本地 config 为路径 B
- **WHEN** Gateway 同步 agent 配置并处理该 agent 的会话(含 heartbeat)
- **THEN** session / heartbeat 实际读写路径 B,路径 A 不被读写;其余公开配置字段(Custom Instructions / skills / tool_allowlist / features 等)仍以 IM 镜像为准同步

#### Scenario: IM 推送 agent.create 时在节点落地工作区并回非空 workspace_root
- **WHEN** IM 服务经下行请求在本节点创建一个 Agent
- **THEN** Gateway 在本地建该 Agent 工作区、注册进 live 路由,并在回包中返回非空 `workspace_root`(绝对路径);该 Agent 配置写回本地持久化 config

#### Scenario: IM 请求当前 Agent 配置时返回 live 快照
- **WHEN** IM 服务请求某 Agent 的当前配置
- **THEN** Gateway 返回该 Agent 的 live 配置快照(display_name / skills / tool_allowlist / group_reply_policy / default_model / workspace_root / features / custom_prompt)，其中 `custom_prompt` 是唯一公开的 Agent 专属说明字段

#### Scenario: IM 经 RPC 请求读取 HEARTBEAT.md 预览内容（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.heartbeat.md.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/HEARTBEAT.md`，回帧 `node.heartbeat.md`（含 content；文件不存在则 content 为空串）；IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）

#### Scenario: IM 经 RPC 请求列出 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.jobs.request`（含 agent_id / workspace_root）
- **THEN** Gateway 读取 `<workspace_root>/.nanoassistant/cron/jobs.json`，回帧 `node.cron.jobs`（含 jobs 列表；文件不存在则 jobs 为空列表）

#### Scenario: IM 经 RPC 请求删除某条 cron 任务（feat-394-M13 决策 G）
- **WHEN** IM 服务下发 `node.cron.delete.request`（含 agent_id / workspace_root / job_id）
- **THEN** Gateway 从 `jobs.json` 中移除匹配 job_id 的条目并回写，回帧 `node.cron.delete`（含 deleted: true/false）；job_id 不存在时 deleted 为 false，不报错
