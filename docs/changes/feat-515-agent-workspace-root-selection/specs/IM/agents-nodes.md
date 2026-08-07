## MODIFIED Requirements

### Requirement: Agent 创建必须挂在已绑定且在线的节点下，workspace root 仅可在创建时由节点确定

前端在节点下创建 Agent (`POST /im/v1/nodes/{node_id}/agents`): IM 校验该节点已绑定、归属当前
owner；经网关 `agent.create` 由节点分配或校验 workspace root，成功回传 canonical absolute
`workspace_root` 及 `workspace_is_default` 后 IM 才持久化 `AgentProfile`。创建表单可选择
“使用默认目录”（不指定路径，由节点分配）或“自定义路径”（目标节点上的绝对路径）。未知节点在
owner 门禁处 404，重复 `agent_id` 为 409；节点离线保持 503。

#### Scenario: 默认目录由节点分配并回传
- **GIVEN** 当前 owner 名下一个已知在线节点 `node-1`
- **WHEN** 用户选择“使用默认目录”并在 `node-1` 创建 Agent
- **THEN** 201 返回与 `GET .../config` 同形的配置体，`node_id == "node-1"`，
  `workspace_root` 为节点回传的非空绝对路径，`workspace_is_default == true`，
  `profile_version == 1`

#### Scenario: 以可用父目录下的新自定义路径创建
- **GIVEN** 用户选择节点 `node-1` 上的路径 P，P 不存在而 P 的父目录存在且可用
- **WHEN** 用户以“自定义路径”创建 Agent
- **THEN** 201 返回 `workspace_root == P` 的节点 canonical path，
  `workspace_is_default == false`

#### Scenario: 节点 canonical root 在 IM 镜像和后续节点请求中保持不变
- **GIVEN** 节点 `node-1` 回传 canonical workspace root P 与 `workspace_is_default` 值 D
- **WHEN** 用户读取 Agent 配置或 IM 因 capabilities、prompt preview、cron、skill usage、
  heartbeat 请求该节点处理此 Agent
- **THEN** 配置响应的 root 仍为 P、`workspace_is_default == D`，下行给 `node-1` 的 root 也为 P
- **AND** IM 不按自身主机的目录规则重写 P

#### Scenario: 自定义路径的问题在创建页明确呈现
- **WHEN** 用户提交的自定义路径的父目录不存在或不可用，或目标不是目录
- **THEN** 不创建 AgentProfile，响应为 422 并带稳定 `code` 与可呈现 `detail`，页面在路径字段
  处说明原因

#### Scenario: 已有目录须经确认才创建
- **GIVEN** 自定义路径 P 在选中节点上已存在且是目录
- **WHEN** 用户第一次提交创建
- **THEN** 不创建 AgentProfile，响应为 409 `code=workspace_confirmation_required`，页面明确提示
  这是已有目录并要求用户确认
- **WHEN** 用户确认后以同一创建草稿再次提交
- **THEN** 才创建 Agent，且既有目录内容不被覆盖

#### Scenario: 同节点自定义 root 已归属另一 Agent
- **GIVEN** `node-1` 的 Agent A 已使用 canonical workspace root P
- **WHEN** 用户尝试在 `node-1` 为 Agent B 选择 P
- **THEN** 不创建 Agent B，响应为 409 `code=workspace_already_assigned`，页面明确说明 P 已归属
  Agent A

#### Scenario: 不同节点不共享 workspace root 唯一性
- **GIVEN** `node-1` 的 Agent A 使用路径 P
- **WHEN** 用户在另一在线节点 `node-2` 创建 Agent B 并选择同字符串路径 P
- **THEN** IM 不因 Agent A 拒绝该请求；由 `node-2` 的本地校验决定是否可创建

#### Scenario: workspace root 在创建后不可经配置更新修改
- **GIVEN** Agent X 在创建时获得 workspace root P
- **WHEN** 用户打开其设置或调用 update config 修改其他字段，即使 payload 含 workspace_root Q
- **THEN** 页面没有 root 编辑或迁移操作，已存 `workspace_root` 仍为 P
