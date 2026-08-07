# IM Agents and Nodes Specification (delta for refactor-483)

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示
字段更新立即反映在 UI；model、system/custom prompt、skills、tools 与运行 features 等配置由 Gateway
在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live
快照合并时仍以持久值为准。局部更新对 `features`、`custom_prompt`、`heartbeat` 保留请求 presence：
字段未出现表示保持原值，字段出现且为空 object/null 表示显式清空。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段及 profile version

#### Scenario: PATCH 持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: PATCH 未携 optional block 时保持原值
- **GIVEN** Agent 已持久化 features、自定义说明和 heartbeat cadence
- **WHEN** 前端 PATCH 只修改其他配置且省略这些 optional block
- **THEN** 成功响应与随后读取仍返回原有 optional config

#### Scenario: PATCH 显式清空 optional block
- **WHEN** 前端 PATCH 携 `features:{}`、`custom_prompt:null` 或 `heartbeat:null`
- **THEN** 对应配置被清空，其他未携 optional block保持原值

#### Scenario: capability 缺项不删除已存 recognized config值
- **GIVEN** Agent 已保存的 feature key、skill/tool name或model name暂未出现在当前capability snapshot
- **WHEN** 前端修改其他配置并保存
- **THEN** 成功响应与随后读取仍保留这些recognized config值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新配置并延续原聊天历史

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久 profile 含 IM 自有运行字段
- **WHEN** IM 拉取并合并 Gateway live snapshot
- **THEN** live payload 省略这些字段时不把持久值清空

#### Scenario: heartbeat cadence 返回真实配置值
- **WHEN** 前端读取某 Agent 的 heartbeat cadence
- **THEN** 返回该 Agent 的真实 `heartbeat.every` 配置值；未配置时体现为默认 `30m`

### Requirement: Agent 创建必须挂在已绑定且在线的节点下,workspace_root 由节点分配

前端在节点下创建 Agent(`POST /im/v1/nodes/{node_id}/agents`)：IM校验该节点已绑定、归属当前
Bearer owner，并忽略请求体中任何legacy owner值；经网关 `agent.create` 由节点分配并回传
`workspace_root`，IM把请求中的recognized config（含features/custom prompt）与节点回包一起持久化为
`AgentProfile`。未知节点在owner门禁处404，重复`agent_id` 409。

#### Scenario: 在已知节点创建返回带 node_id+workspace_root 的配置
- **GIVEN** 当前 owner 名下一个已知节点 `node-1`
- **WHEN** 前端 `POST /im/v1/nodes/node-1/agents {agent_id, display_name, skills, tool_allowlist, ...}`
- **THEN** 201返回与 `GET .../config` 同形的配置体，`owner_id` 是当前Bearer owner、
  `node_id == "node-1"`、`workspace_root` 为节点回传值、`workspace_is_default` 反映是否默认路径、
  `profile_version == 1`

#### Scenario: 创建时的自定义运行配置完整持久化
- **WHEN** 前端创建 Agent并携feature overrides、自定义说明、skills、tools和model
- **THEN** 201响应与随后GET返回相同recognized config值

#### Scenario: 请求体 owner 不能改变 Agent 归属
- **GIVEN** 当前Bearer owner为A且目标节点归A
- **WHEN** 旧客户端在create body省略owner或携owner B
- **THEN** 新Agent仍归A，body owner不成为身份锚点

#### Scenario: 重复 agent_id 与未知节点被拒
- **WHEN** 前端以已存在的 `agent_id` 再次创建
- **THEN** 409 `{detail:"agent_id already exists"}`
- **WHEN** 前端向不存在的 `node_id` 创建
- **THEN** 404 `{detail:"node_id not found"}`（owner-scope门禁先于网关派发拦下）
