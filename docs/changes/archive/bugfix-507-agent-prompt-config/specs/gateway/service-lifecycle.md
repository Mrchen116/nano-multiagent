# gateway Service Lifecycle Specification (delta for bugfix-507)

> 对齐 canonical: `docs/specs/gateway/service-lifecycle.md`。

## MODIFIED Requirements

### Requirement: IM 服务在线时 Gateway 主动连出并保持双向通信

#### Scenario: 连接后注册节点并周期心跳

- **GIVEN** 配置了 IM 服务地址
- **WHEN** Gateway 启动并连上 IM 服务 WebSocket
- **THEN** 首帧 `node.register` 仅携带 `agent_workspaces`、`agent_skills`、
  `agent_tool_allowlist` 三组 per-agent seed
- **AND** register、live snapshot 和后续 config sync 均不携带或恢复 Agent prompt seed

#### Scenario: IM 请求当前 Agent 配置时返回 live 快照

- **WHEN** IM 服务请求某 Agent 的当前配置
- **THEN** Gateway 返回 display、skills、tools、policy、model、workspace、features 与
  `custom_prompt`
- **AND** `custom_prompt` 是唯一公开的 Agent 专属说明字段
