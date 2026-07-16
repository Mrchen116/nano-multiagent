# Delta: gateway - Service Lifecycle (bugfix-467)

> 对齐: bugfix-467
> 上级: [gateway (personal_assistant) Specification](../../../../../specs/gateway/spec.md)

## MODIFIED

#### Scenario: 连接后注册节点并周期心跳
- **GIVEN** 配置了 IM 服务地址
- **WHEN** Gateway 启动并连上 IM 服务 WebSocket
- **THEN** 首帧发 `node.register`(携带 node_id、agent 列表与三组 per-agent 种子映射——
  `agent_workspaces` / `agent_skills` / `agent_tool_allowlist`,均为 agent_id → 本地 config
  解析值的映射,供 IM 首次落库种子使用;重连重发同帧内容一致),
  随后在线期间周期发 `node.heartbeat`(含 `node_id` / `status=online` / `agent_count`),
  IM 服务据此刷新节点状态
