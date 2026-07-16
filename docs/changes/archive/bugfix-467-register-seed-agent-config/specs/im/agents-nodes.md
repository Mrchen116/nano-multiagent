# Delta: IM - Agents and Nodes (bugfix-467)

> 对齐: bugfix-467
> 上级: [IM Specification](../../../../../specs/im/spec.md)

## MODIFIED

### Requirement: node.register 首见 agent 时以上报种子值落库（bugfix-404-M2 / bugfix-467）

IM 处理 `node.register` 时,对帧中**首次出现**(无既有 profile)的 agent,以帧内种子值落库:
workspace_root 取 `agent_workspaces` 上报值(缺失时回落 managed default),skills / tool_allowlist
取 `agent_skills` / `agent_tool_allowlist` 上报值(帧未携带或单 agent 值非法时按空落库,兼容旧帧;
单 agent 值内混入非法项时仅丢弃非法项)。已存在 profile 的 agent,其各字段保持既有值不被注册
改写(重连重发幂等),以保护用户经配置更新(含特意清空)后的收敛。

#### Scenario: 首见 agent 用上报值落库
- **GIVEN** IM 中无 agent X 的 profile
- **WHEN** 收到 `node.register`,`agent_workspaces["X"]` 为非默认绝对路径 P,
  `agent_skills["X"]` 为技能列表 S,`agent_tool_allowlist["X"]` 为工具列表 T
- **THEN** agent X 的 profile 落库 workspace_root=P、skills=S、tool_allowlist=T,
  `GET /im/v1/agents` 广播 P 且 `workspace_is_default=false`

#### Scenario: 已存在 profile 不被重注册改写
- **GIVEN** agent X 的 profile 已存在(含用户特意清空的 skills / tool_allowlist)
- **WHEN** 再次收到 `node.register`(无论帧内上报何值)
- **THEN** profile 的 workspace_root / skills / tool_allowlist 均保持既有值

#### Scenario: 帧未带种子字段退回默认与空(旧帧兼容)
- **GIVEN** IM 中无 agent Y 的 profile
- **WHEN** 收到不含 `agent_workspaces` / `agent_skills` / `agent_tool_allowlist` 字段的 `node.register`
- **THEN** agent Y 的 workspace_root 按 managed default 落库,skills / tool_allowlist 落库为空
