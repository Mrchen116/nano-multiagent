# im Specification (delta for bugfix-404)

## MODIFIED Requirements

### Requirement: node.register 首见 agent 时以上报 workspace_root 落库

IM 处理 `node.register` 时，对帧中**首次出现**（无既有 profile）的 agent，workspace_root 取帧内 `agent_workspaces` 上报值落库；帧未携带该 agent 的值时才回落 managed default。已存在 profile 的 agent，其 workspace_root 保持既有值不被注册改写（重连重发幂等）。

#### Scenario: 首见 agent 用上报值落库
- **GIVEN** IM 中无 agent X 的 profile
- **WHEN** 收到 `node.register`，`agent_workspaces["X"]` 为非默认绝对路径 P
- **THEN** agent X 的 profile workspace_root 落库为 P，`GET /im/v1/agents` 广播 P 且 `workspace_is_default=false`

#### Scenario: 已存在 profile 不被重注册改写
- **GIVEN** agent X 的 profile workspace_root 已为 P
- **WHEN** 再次收到 `node.register`（无论帧内上报何值）
- **THEN** profile workspace_root 仍为 P

#### Scenario: 帧未带 agent_workspaces 退回默认（旧帧兼容）
- **GIVEN** IM 中无 agent Y 的 profile
- **WHEN** 收到不含 `agent_workspaces` 字段的 `node.register`
- **THEN** agent Y 按 managed default 落库（修复前行为）

### Requirement: agent workspace_root 创建后不可经配置接口修改

agent 的 workspace_root 在创建时确定（agent.create 由节点分配 / node.register 种子），此后 update config 接口忽略 payload 中的 workspace_root 字段，存量值保持。

#### Scenario: update config 携带 workspace_root 被忽略
- **GIVEN** agent X 的 profile workspace_root 为 P
- **WHEN** 调用 update config 接口，payload 含 `workspace_root: Q`（Q ≠ P），其余字段合法
- **THEN** 返回成功，其余字段按 payload 更新，workspace_root 仍为 P
