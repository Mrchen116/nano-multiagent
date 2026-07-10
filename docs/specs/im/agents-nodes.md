# IM - Agents and Nodes Specification

> 对齐: feat-446
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

Agent 配置中心、节点绑定、节点状态、runtime 能力解析、用户维事件流和配置 RPC 的 IM 契约。

## Requirements

### Requirement: Agent 配置中心可读可改,版本乐观锁,IM 自有字段不被 live 快照覆盖

前端经 `/im/v1/agents/*` 读写各 Agent 的展示名/描述/system_prompt/skills/tools 白名单/群聊策略/默认
模型/features/custom_prompt;配置版本化(`profile_version` 乐观锁);更新仅对新会话生效。当 IM 向在线网关
拉 live 快照合并时,IM 自有字段(`features`/`custom_prompt`)以持久化值为准,不被省略它们的 live 快照清空。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端 `GET /im/v1/agents/{id}/config`
- **THEN** 200 响应至少含 `{agent_id, owner_id, node_id, display_name, description, system_prompt,
  skills, tool_allowlist, group_reply_policy, default_model, workspace_root, workspace_is_default,
  profile_version, updated_at, features, custom_prompt}` 等字段(随产品演进可增,不应静默删/改名)

#### Scenario: PATCH 持久化 features 与 custom_prompt(乐观锁)
- **WHEN** 前端带 `profile_version` `PATCH /im/v1/agents/{id}/config { ..., features, custom_prompt }`
- **THEN** 200 回显写入的 `features`/`custom_prompt`,随后 `GET` 也反映该值(证明落库非仅回显);
  版本陈旧时按乐观锁拒绝(409 冲突)

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久化 profile 含 `features={memory_curation:false}` / `custom_prompt` 非空,网关在线
- **WHEN** 前端 `GET /im/v1/agents/{id}/config?source=live`(IM 向网关取 live 快照后合并)
- **THEN** 即便 live 快照不带这两字段,响应仍保留持久化的 `features` 与 `custom_prompt`(不回落默认)

#### Scenario: heartbeat cadence 返回真实配置值(feat-394 决策 E)
- **WHEN** 前端 `GET /im/v1/agents/{id}/config` 读某 Agent 的 heartbeat cadence
- **THEN** 返回该 Agent 的真实 `heartbeat.every` 配置值;未配置时体现为默认 `30m`(由后端/前端据此渲染,
  cadence 显示值不是前端写死的占位)

### Requirement: Agent 配置页可管理 skill_view 工具

前端在 Agent 配置页把 `skill_view` 作为普通可选工具呈现;未显式配置工具白名单的 Agent 默认启用它,
显式白名单仍精确表达用户选择。

#### Scenario: 新建 agent 时默认选中 skill_view
- **WHEN** 用户在 IM 新建 PA agent 并进入工具选择区域
- **THEN** `skill_view` 出现在可选工具列表中
- **AND** 默认处于选中状态

#### Scenario: 用户取消 skill_view 后保存配置
- **WHEN** 用户在 agent 配置页取消选择 `skill_view` 并保存
- **THEN** IM 持久化该 agent 的显式工具白名单
- **AND** 白名单不包含 `skill_view`

#### Scenario: 已显式配置工具白名单的 agent 不自动选回 skill_view
- **GIVEN** agent 已持久化显式工具白名单,且其中不包含 `skill_view`
- **WHEN** 用户再次打开该 agent 配置页
- **THEN** `skill_view` 显示为未选中

### Requirement: Skill 使用统计 API

浏览器前端可按 agent 查询 skill 使用统计;IM 通过在线 Gateway 读取对应 agent workspace 的运行态使用数据,
离线时以前端可处理的方式降级。

#### Scenario: 查询 agent 的 skill 使用统计
- **WHEN** 浏览器前端请求 `GET /im/v1/agents/:agentId/skills/usage`
- **THEN** 返回该 agent 的所有 skill 使用数据,包含 name、source、state、use_count、last_used_at、session_refs
- **AND** source 至少支持用户创建、历史会话蒸馏、自动创建、自动批量优化与 unknown

#### Scenario: agent 离线时查询 skill 统计
- **WHEN** agent 不在线或 Gateway 无法到达
- **THEN** API 返回离线/空数据语义,前端显示离线提示而非崩溃

### Requirement: HEARTBEAT.md 只读预览与 cron 任务管理经 WS RPC 代理到 gateway（feat-394-M13 决策 G）

IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）。相关 endpoint 均经 WS RPC
将请求委托给目标节点 gateway，由 gateway 读写其本地 workspace 后回包，IM 做路由转发与离线降级。

#### Scenario: 获取 HEARTBEAT.md 预览内容
- **WHEN** 前端 `GET /im/v1/agents/{id}/heartbeat-md`
- **THEN** 200 返回 `{content: string, node_online: bool}`；节点在线时 content 为 `HEARTBEAT.md` 内容
  （文件不存在则空串）；节点离线或 RPC 超时时 `{content:"", node_online:false}`

#### Scenario: 列 cron 任务经 RPC 代理
- **WHEN** 前端 `GET /im/v1/agents/{id}/cron-jobs`
- **THEN** 200 返回 jobs 数组；节点离线或超时时返回空列表（不报错），不直读 gateway 侧文件

#### Scenario: 删 cron 任务经 RPC 代理
- **WHEN** 前端 `DELETE /im/v1/agents/{id}/cron-jobs/{job_id}`
- **THEN** 204 表示删除成功；节点离线或 RPC 超时或 job_id 不存在均返回 404

### Requirement: Agent 创建必须挂在已绑定且在线的节点下,workspace_root 由节点分配

前端在节点下创建 Agent(`POST /im/v1/nodes/{node_id}/agents`):IM 校验该节点已绑定、归属当前 owner;
经网关 `agent.create` 由节点分配并回传 `workspace_root`,IM 持久化为 `AgentProfile`。未知节点在 owner
门禁处 404,重复 `agent_id` 409。

#### Scenario: 在已知节点创建返回带 node_id+workspace_root 的配置
- **GIVEN** 当前 owner 名下一个已知节点 `node-1`
- **WHEN** 前端 `POST /im/v1/nodes/node-1/agents {agent_id, display_name, skills, tool_allowlist, ...}`
- **THEN** 201 返回与 `GET .../config` 同形的配置体,`node_id == "node-1"`、`workspace_root` 为节点
  回传值、`workspace_is_default` 反映是否默认路径、`profile_version == 1`

#### Scenario: 重复 agent_id 与未知节点被拒
- **WHEN** 前端以已存在的 `agent_id` 再次创建
- **THEN** 409 `{detail:"agent_id already exists"}`
- **WHEN** 前端向不存在的 `node_id` 创建
- **THEN** 404 `{detail:"node_id not found"}`(owner-scope 门禁先于网关派发拦下)

### Requirement: node.register 首见 agent 时以上报 workspace_root 落库（bugfix-404-M2）

IM 处理 `node.register` 时,对帧中**首次出现**(无既有 profile)的 agent,workspace_root 取帧内
`agent_workspaces` 上报值落库;帧未携带该 agent 的值时才回落 managed default。已存在 profile 的
agent,其 workspace_root 保持既有值不被注册改写(重连重发幂等)。

#### Scenario: 首见 agent 用上报值落库
- **GIVEN** IM 中无 agent X 的 profile
- **WHEN** 收到 `node.register`,`agent_workspaces["X"]` 为非默认绝对路径 P
- **THEN** agent X 的 profile workspace_root 落库为 P,`GET /im/v1/agents` 广播 P 且
  `workspace_is_default=false`

#### Scenario: 已存在 profile 不被重注册改写
- **GIVEN** agent X 的 profile workspace_root 已为 P
- **WHEN** 再次收到 `node.register`(无论帧内上报何值)
- **THEN** profile workspace_root 仍为 P

#### Scenario: 帧未带 agent_workspaces 退回默认(旧帧兼容)
- **GIVEN** IM 中无 agent Y 的 profile
- **WHEN** 收到不含 `agent_workspaces` 字段的 `node.register`
- **THEN** agent Y 按 managed default 落库

### Requirement: agent workspace_root 创建后不可经配置更新修改（bugfix-404-M2）

agent 的 workspace_root 在创建时确定(`agent.create` 由节点分配 / `node.register` 种子),update
config 接口不含该字段(请求中出现也被忽略),且任何配置更新都不改变已存的 workspace_root。

#### Scenario: 配置更新不重置 workspace_root
- **GIVEN** agent X 的 profile workspace_root 为非默认路径 P
- **WHEN** 调用 update config 接口修改其他字段(如 system_prompt),payload 不含 workspace_root
- **THEN** 返回成功,workspace_root 仍为 P

#### Scenario: update config 携带 workspace_root 被忽略
- **GIVEN** agent X 的 profile workspace_root 为 P
- **WHEN** 调用 update config 接口,payload 含 `workspace_root: Q`(Q ≠ P),其余字段合法
- **THEN** 返回成功,其余字段按 payload 更新,workspace_root 仍为 P

### Requirement: 每个 AgentProfile 一一对应一个 IM users 行,响应恒带非空 user_id

每个 `AgentProfile` 有且只有一个 `users.username = "agent:" + agent_id` 的行(创建时同事务建,历史缺失
者读路径 lazy bootstrap)。因此前端只要看到一个 agent 行,就能拿到稳定非空的 `user_id`,据此把 Agent 作为
会话 participant 加入,不会被会话创建端点以"未知 user"400 拒绝。

#### Scenario: 列 agent 恒带可作 participant 的 user_id
- **WHEN** 前端 `GET /im/v1/agents`
- **THEN** 每个 agent 行带非空 `user_id`;以该 `user_id` 作 `participant_ids` 创建 direct 会话被接受

### Requirement: 浏览器经用户维 WebSocket 收事件流,鉴权后只回放本租事件

浏览器经 `/im/ws/user` 建用户维事件流;身份取自 JWT(`?token=<jwt>` 查询串或 `Sec-WebSocket-Protocol:
bearer.<jwt>` 子协议),无 token / 非法 token 立即关闭;身份只认 JWT,单凭 `?user_id=` 不构成信任锚。
握手后发 `{op:"resume", after_event_id:N}` 即回放该用户 owner 范围内、`event_id > N` 的事件帧
(`op:"event"`),跨租事件不投递。`GET /im/v1/sync` 给出会话列表快照 + 全局 `max_event_id`,供前端在
`resync_required` 后对齐游标。

#### Scenario: 无 token / 非法 token / 仅 user_id 的连接被拒
- **WHEN** 浏览器 `websocket_connect("/im/ws/user")`(无 token,或 `?token=not-a-jwt`,或仅 `?user_id=`)
- **THEN** 连接被服务端关闭(policy violation),收不到事件帧

#### Scenario: 合法 token 连接并 resume 回放本租事件
- **GIVEN** 已授权用户在自己会话里发过消息
- **WHEN** 浏览器以 `?token=<合法 jwt>` 连上后发 `{op:"resume", after_event_id:0}`
- **THEN** 收到 `op:"event"` 帧,含 `message.sent`、`message.delivered` 等 `event_type`;只含本 owner 事件

#### Scenario: sync 返回快照与全局游标
- **WHEN** 前端 `GET /im/v1/sync`
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(>0);前端据其对齐用户流游标

### Requirement: 设备绑定把节点归属到当前用户

终端用户在本机发起绑定:`POST /im/v1/bind {action:"start", node_id}` 取得绑定链接,浏览器登录后
`{action:"confirm", bind_id|bind_token}` 确认,确认后该节点及其上 Agent 自动归属当前用户。缺必填字段
大声失败(400),不静默。

#### Scenario: start 返回绑定结构
- **GIVEN** 已授权用户、一个已知节点
- **WHEN** 用户 `POST /im/v1/bind {action:"start", node_id}`
- **THEN** 201 返回 `{bind_id, node_id, user_id, status, bind_url, created_at, confirmed_at}`

#### Scenario: 缺动作必填字段返回稳定 400
- **WHEN** `start` 缺 `node_id`
- **THEN** 400 `{detail:"node_id is required for start"}`
- **WHEN** `confirm` 缺 `bind_id` 且缺 `bind_token`
- **THEN** 400 `{detail:"bind_id or bind_token is required for confirm"}`

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

新建/编辑 Agent 页需要的 runtime 候选项(skills / tools / models / features / 默认 system_prompt)由 IM
**当场**经 gateway WS 向在线节点解析后返回,IM 不在本地持久化该能力目录,也不据 IM 部署机文件系统推断。
节点级 `GET /im/v1/nodes/{id}/capabilities`(agent 尚不存在时用)与 agent 级 `GET /im/v1/agents/{id}/
capabilities` 都把网关返回的 `features` 列表透传给前端。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...],
  platform_default_model, default_system_prompt, features:[...]}`;网关 payload 无 features 时 IM 返回
  空 `features` 列表(优雅降级)

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}`
  (可含 `requires_tool`),由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider(例:`codex_oauth:gpt-5.5` → `openai_compat`,
  `kimiCoding:K2.6` → `anthropic`),供 agent 配置页模型下拉展示格式

#### Scenario: agent 能力的 skills 项携带 location
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `skills` 列表中每项携带 `location`(SKILL.md 路径,可空;网关 payload 无此字段时降级为空),前端据此对同名不同路径的 skill 分开展示

### Requirement: 节点上线/心跳/超时实时反映到 owner 的浏览器看板

Gateway 上行 `node.register` / `node.heartbeat` 驱动 IM 向**该节点 owner**的浏览器用户流广播
`node.status_changed` 事件(online);心跳超时由 IM 后台扫描翻为 offline 并广播
(`status:"offline", last_error:"heartbeat_timeout"`)。广播严格按 owner 隔离,不泄漏给他租浏览器。

#### Scenario: 节点注册广播 online 给本租浏览器
- **GIVEN** 节点已绑定某 owner,该 owner 一条浏览器用户流在线
- **WHEN** Gateway 上行 `node.register {node_id, agents, capabilities}`
- **THEN** 该 owner 浏览器收到 `op:"event"`、`event_type:"node.status_changed"`、`status:"online"` 帧;
  他租浏览器收不到

#### Scenario: 心跳超时翻 offline 并广播
- **GIVEN** 一个 online 节点最近心跳已过期
- **WHEN** IM 后台扫描运行
- **THEN** 节点态翻 `offline`,向本租浏览器广播一帧 `node.status_changed status:"offline"
  last_error:"heartbeat_timeout"`;对已 offline 节点重复扫描是无副作用的幂等(不重复广播)
