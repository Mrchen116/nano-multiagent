# IM Specification

> 对齐: feat-430-im-slash-skill-picker
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本契约层只收 **IM 的消费者真正依赖的对外行为**：
> 浏览器前端（内置 Web IM）、Node Gateway（`personal_assistant`）、终端用户，以及 `tests/im_service/`
> 里的契约测试。每条 Scenario 的主语 = 这些消费者之一;IM 内部如何分层/装配不在此层（那在代码 +
> 归档 design）。跨包架构（IM 在系统里的位置、依赖方向）在顶点 [`SPEC.md`](../../../SPEC.md)。

## Purpose

`IM` 是**独立部署的可选中心服务**:内置 Web IM + 配置中心 + 消息中继。它让用户无需接入任何外部 IM 即可
完整使用 Multi-Agent 能力,并统一管理跨机器的 Agent 节点。它对外呈现两个面:

- **HTTP `/im/v1/*`**:账号/会话/消息/Agent 配置/节点/绑定/统计/策略,供浏览器前端调用。
- **WebSocket 两条**:`/im/ws/user`(浏览器用户维事件流)、`/im/ws/gateway`(Node Gateway 持久双向连接)。

对 IM 而言**人和 Agent 都是平等的消息参与者(Actor)**;对外接口以稳定业务标识(`user_id` / `agent_id` /
`conversation_id`)建模,不暴露内部路由主键。权限是**个人 owner 模型**:每个用户是自己所有节点/Agent 的
owner,用户之间数据隔离,无团队/组织 RBAC。

**显式不负责**:不执行 Agent 推理(交 agent 内核);不直接调用 agent 内核(经 Node Gateway 中继);不对接
外部 IM(由 Node Gateway 的 Channel 负责);不触发 heartbeat 调度(由 Node Gateway 本地控制);不持久化节点
的 runtime 能力目录(skills/tools/models 当场向在线网关解析,不入库)。IM 离线时外部 IM 主路径不受影响
(Node Gateway 本地自治)。

## Requirements

### Requirement: 账号注册/登录走 JWT,刷新令牌轮换且可吊销

终端用户经 `/im/v1/auth/*` 注册/登录获得一对令牌(短期 access + 长期 refresh);refresh 一次性轮换,旧
refresh 轮换或登出后立即失效。错误凭证大声失败(401/拒绝),不静默成功,也不泄漏用户是否存在。

#### Scenario: 注册返回令牌对且密码经哈希,弱口令/重名被拒
- **WHEN** 终端用户 `POST /im/v1/auth/register {username,password,display_name,locale?}`
- **THEN** 201 返回 `{access_token, refresh_token, user}`,`user` 含 `id/username/display_name/owner_id`
  且不泄漏密码哈希;口令短于下限或用户名重复时注册失败(不创建用户)

#### Scenario: 登录凭证错误返回 401 且不区分"用户不存在"与"密码错"
- **WHEN** 终端用户以错误密码或未知用户名 `POST /im/v1/auth/login`
- **THEN** 401(同一种失败语义,避免存在性预言机);凭证正确时返回新令牌对

#### Scenario: refresh 轮换令牌,旧 refresh 失效;登出吊销 refresh
- **WHEN** 用户 `POST /im/v1/auth/refresh` 用合法 refresh
- **THEN** 返回新 access+refresh,且原 refresh 再次使用被拒;`POST /im/v1/auth/logout` 后该 refresh 也被拒

### Requirement: 数据面 HTTP 路由强制 Bearer 鉴权且按 owner 隔离

除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes / metrics 等)
要求合法 Bearer access token;缺失或非法 token 返回 401。一个租户**读不到也写不进**另一个租户的资源,
跨租访问返回 **404 而非 403**(不暴露资源是否存在)。请求主体身份取自 token,不接受 `?user_id=` 之类的
查询参数作为信任锚。

#### Scenario: 无 token 的数据面请求返回 401
- **WHEN** 浏览器前端未带 Bearer 调 `GET /im/v1/me` / `/im/v1/conversations` / `/im/v1/agents` /
  `/im/v1/nodes` / `/im/v1/metrics/usage`
- **THEN** 全部 401(无 `?user_id=` 捷径)

#### Scenario: 身份取自 token 而非查询参数
- **GIVEN** 已授权用户 alice
- **WHEN** alice `GET /im/v1/me`(或 `PATCH /im/v1/me`,即使带 `?user_id=` 也忽略)
- **THEN** 返回/更新的恒是 token 主体 alice 自己

#### Scenario: 列表按 owner 隔离,跨租读单条 404
- **GIVEN** alice 与 bob 各自注册、各建一个会话
- **WHEN** alice `GET /im/v1/conversations`
- **THEN** 只见 alice 自己的会话;bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404,
  向其发消息也 404

#### Scenario: metrics 仅返回调用方 owner 的行
- **WHEN** 已授权用户 `GET /im/v1/metrics/usage`
- **THEN** 返回行的 `owner_id` 全归属该调用方(空列表亦可),不含他租数据

### Requirement: 会话与消息以 Actor 语义建模,响应字段稳定且分页

前端经 `/im/v1/conversations*` 创建/读取会话与消息;消息发送者是 Actor(人/Agent/system),响应暴露
稳定的 `delivery_status` / `sender_type` / `attachments` 等字段并以 `{items, next_before_message_id}`
信封分页。未知会话的消息/详情/更新接口保持稳定的 404 语义。

#### Scenario: 创建会话指定参与者 Actor
- **WHEN** 前端 `POST /im/v1/conversations {title, participant_ids:[...]}`
- **THEN** 201 返回含会话 `id`;后续以该 `conversation_id` 读写消息

#### Scenario: 创建消息回显投递状态与发送者类型
- **WHEN** 前端 `POST /im/v1/conversations/{id}/messages {sender_user_id, content, sender_type?, attachments?}`
- **THEN** 201 返回 `{id, conversation_id, delivery_status, sender_type, attachments, ...}`;
  `sender_type` 缺省为 `user`,可显式为 `agent`;`attachments` 为空时是 `[]`

#### Scenario: 列消息走 items+游标信封并暴露同样字段
- **WHEN** 前端 `GET /im/v1/conversations/{id}/messages?limit=N`
- **THEN** 200 返回恰含键 `["items","next_before_message_id"]`;每条携 `delivery_status`/`sender_type`/
  `attachments`;最后一页 `next_before_message_id` 为 `null`,有更多时为下一游标 message id

#### Scenario: 未知会话相关读写返回稳定 404
- **WHEN** 前端对不存在的 `conversation_id` 调 messages / 详情(GET) / 更新(PATCH)
- **THEN** 全部 404,`detail == "conversation_id not found"`

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

### Requirement: 系统级策略(policies)可读可改,字段集稳定

前端设置页经 `/im/v1/policies` 读写系统级策略(默认模型 / 每 run 最大轮数 / 附件大小上限 / 留存天数 /
审计级别 / 限流);PATCH 整体回写并回显。

#### Scenario: 读写 policies 字段集稳定
- **WHEN** 前端 `GET /im/v1/policies`
- **THEN** 200 响应键恰为 `{default_model, max_turn_per_run, max_attachment_size_mb, retention_days,
  audit_level, rate_limit_per_min}`;`PATCH` 同结构写入并原样回显

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

### Requirement: Gateway 经 /im/ws/gateway 持久双向连接,协议帧契约稳定

Node Gateway(常在 NAT 后)主动向 IM 建 `/im/ws/gateway` 持久连接,所有双向通信复用之。上行
`node.register` / `node.heartbeat` / `node.report` / `node.delivery_receipt`;下行 `relay.message` /
`config.sync` / `agent.create` / 各 `*.capabilities.resolve` / `prompt-preview` 等。非法/不支持的帧返回
稳定错误信封而非静默丢弃或崩连接。

#### Scenario: 非 JSON 帧返回 invalid_message 错误信封
- **WHEN** Gateway 经 `/im/ws/gateway` 发非 JSON 文本
- **THEN** 收到 `{type:"error", payload:{code:"invalid_message", message:"message must be valid JSON"}}`

#### Scenario: 不支持的消息类型返回 unsupported_message_type
- **WHEN** Gateway 发 `{type:"unknown.type", payload:{}}`
- **THEN** 收到 `{type:"error", payload:{code:"unsupported_message_type", message:"unknown.type"}}`

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

### Requirement: 消息中继幂等,投递回执推进状态

同一消息以相同 `idempotency_key` 重复中继时,IM 复用同一 relay 任务,**不产生重复消息/重复投递**;
Gateway 上行 `node.delivery_receipt` 把对应消息的 `delivery_status` 沿 `sent` → `completed` 推进,
并回流到前端可见的消息投递状态。

#### Scenario: 重复 idempotency_key 不产生第二条中继
- **GIVEN** 一条消息已用某 `idempotency_key` 中继过
- **WHEN** 同一消息以同一 `idempotency_key` 再次中继
- **THEN** 复用同一中继任务(不新建),终端用户侧不出现重复消息

#### Scenario: 投递回执推进消息投递状态
- **WHEN** Gateway 上行该消息的 `node.delivery_receipt`(先 `sent` 后 `completed`)
- **THEN** 该消息投递状态相应推进至 `completed`,前端读取/事件流可见终态

### Requirement: IM 是可选中心服务,离线与中继关闭都不连累外部 IM 主路径

IM 整体离线时,经 Node Gateway Channel 的外部 IM 主路径仍可用(Gateway 本地自治);中继单独关闭时,IM 仍
作为配置中心独立可用。IM 不直接调用 agent 内核,所有 Agent 执行经 Node Gateway 中继。

#### Scenario: IM 离线不影响外部 IM 主路径
- **GIVEN** IM 服务不可达
- **WHEN** 终端用户经外部 IM 与 Agent 交互
- **THEN** Node Gateway 本地自治继续处理,主路径不受 IM 可用性影响

#### Scenario: 关闭中继后配置中心仍可用
- **GIVEN** 中继能力被关闭
- **WHEN** 前端访问 Agent 配置 / 节点管理等配置中心接口
- **THEN** 这些接口照常可用(仅 Web IM 聊天链路停用)

### Requirement: 后台 agent 通知实时到达在线用户,无需刷新

Agent 后台任务(`run_in_background`)完成后回发给人类用户的通知,与前台回复一样实时到达:
在线用户的浏览器在不刷新的前提下,立即看到该通知作为一条新消息气泡出现。通知一次性携带
完整内容送达,不经历可见的空泡或"生成中"中间态。消息只进入存储、要刷新才显示,不满足本契约。

#### Scenario: 后台通知在在线用户流中实时长出气泡
- **GIVEN** 用户浏览器已建立用户流连接(`/im/ws/user`)
- **WHEN** 该用户某个 agent 的后台任务完成并回发通知
- **THEN** 浏览器收到一帧 `op:"event"`、`event_type:"message.created"`,消息内容即最终全文、
  投递状态 `completed`;用户无需刷新即可看到该气泡

#### Scenario: 同一后台通知重发不产生重复气泡
- **GIVEN** 某条后台通知已送达并在会话中显示
- **WHEN** Gateway 重启后重发同一条通知
- **THEN** IM 识别其为同一通知,用户流不再新增第二条气泡,会话中该通知仍只有一条

### Requirement: 中继看门狗按 liveness 判存活,不误杀活着但安静的消息

中继看门狗判定某 `running` 消息是否失去进展时,依据其存活信号是否仍在刷新:agent run 在"活着但安静"
窗口内产生的 liveness 心跳(执行静默长工具 / 等待 LLM / 等待用户权限决策,三类同源)必须推进该消息的
存活判定(推进最近事件时间戳或刷新通用存活标记),使活跃 run 不被误判为卡死。看门狗对上述窗口不再按
类型分别豁免(不再有 permission 专用特例)。只有在判定窗口内既无新事件也无 liveness 心跳的消息才被回收为
`failed`;维持存活信号的 Gateway/内核崩溃后心跳停止,存活信号 stale 超过回收阈值,该消息仍被正常回收,
不永久停留 running。

#### Scenario: 活跃长工具的消息不被误收
- **GIVEN** 某 running 消息对应的 run 正在执行静默长工具并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息因存活信号持续刷新而不被判超时收尾

#### Scenario: 等待 LLM 的消息不被误收
- **GIVEN** 某 running 消息对应的 run 长时间等待 LLM 返回但连接活着并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾

#### Scenario: 等待权限的消息不被误收
- **GIVEN** 某 running 消息对应的 run parked 等待用户权限决策、Gateway 存活并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾,无需 permission 专用豁免;用户决定后仍能继续

#### Scenario: 真静默消息仍被兜底收尾
- **GIVEN** 某 running 消息在判定窗口内无任何新事件(含心跳)、存活信号 stale 超过回收阈值
- **WHEN** 看门狗扫描
- **THEN** 该消息被翻为 `failed` 并推 `relay.failed`,徽标随之收口,不永久停留 running

### Requirement: 工具徽标按中断原因显示终态

run 异常终止、工具自身超时或工具被拒绝时,IM 工具徽标必须从「运行中」收口为一个**按原因区分**的非成功
终态,不再停留在转圈状态。失败原因区分:工具因自身 deadline 到点被掐 → 「执行超时」(耗时过长);run 因
看门狗 liveness 收尸或进程异常/中断 → 「已中断」(卡死/中断)。

#### Scenario: 在飞工具按原因收口
- **GIVEN** 一条消息里某工具已开始执行(徽标运行中)
- **WHEN** 终态下发到前端
- **THEN** 该工具徽标收口为对应文案:工具自身超时显示「执行超时」、看门狗 liveness 收尸或其他异常终止显示「已中断」

#### Scenario: 被拒绝的工具显示已拒绝
- **GIVEN** 一个工具被 auto_mode 分类器自动 block 或被用户在权限卡片上拒绝
- **WHEN** 该工具的终态渲染
- **THEN** 徽标显示「已拒绝」(区别于「执行超时」「已中断」)

#### Scenario: 权限未决期间显示等待批准
- **GIVEN** 一个工具正等待用户权限决策(未批未拒)
- **WHEN** 徽标渲染
- **THEN** 显示「等待批准」,既不收口为失败也不显示「已拒绝」

#### Scenario: 已完成工具徽标不被改写
- **GIVEN** 同一条消息里其他工具已正常完成
- **WHEN** 在飞工具收口
- **THEN** 已完成工具的徽标保持原终态不变

#### Scenario: 超时收口的工具仍显示其命令与描述
- **GIVEN** 一个 bash 工具调用运行中,已显示其命令与 description
- **WHEN** 该工具因看门狗超时(或其他异常终止)被收口为失败态
- **THEN** 该工具行仍显示原命令与 description(连同失败标识),用户能看出是哪条命令被中断,
  而非只剩工具名 + 失败标识

### Requirement: 工具调用的授权决策随消息持久化与下发

IM 持久化并下发的工具调用数据，在原有字段（status / reason / detail / emoji / duration）之外，携带
「该工具调用是否经用户显式授权/拒绝」的标识。该标识在实时下发（WebSocket）与历史加载（REST）两条路径
上一致，页面刷新后不丢失；无标识的历史工具调用保持兼容（不携带该字段）。

#### Scenario: 经用户授权的工具调用在历史加载中保留标识
- **GIVEN** 一条已落库的 agent 消息，其中某工具调用经用户授权允许
- **WHEN** 客户端重新加载该会话历史
- **THEN** 该工具调用数据携带「经用户授权允许」标识

#### Scenario: 旧工具调用无标识仍可加载
- **GIVEN** 一条历史消息的工具调用是在本能力上线前落库的、无授权标识
- **WHEN** 客户端加载该会话
- **THEN** 该工具调用正常加载，不携带授权标识、不报错

### Requirement: 工具调用折叠态摘要有信息量且用真实工具名

每条 agent 消息下方的工具调用面板,折叠态每行显示"工具在干什么"的一句人话而非仅工具名+耗时,失败行有
可见失败标识,工具名一律为真实注册名。

#### Scenario: bash 带 description 显示人话
- **WHEN** agent 调用 bash 且填了 description
- **THEN** 该工具行折叠态显示 description 文案,不显示命令本身

#### Scenario: bash 未填 description 降级
- **GIVEN** 某次 bash 调用的 description 为空
- **WHEN** 用户看该工具行折叠态
- **THEN** 降级显示命令首段(截断),而不是空白

#### Scenario: 工具调用失败时折叠态标红
- **GIVEN** 某个工具调用失败(bash 退出码非 0、edit 未命中、web 返回错误,或 memory/skill_manage
  返回 success=false 这类不抛错的失败)
- **WHEN** 用户扫工具调用面板而不展开任何一行
- **THEN** 失败的那一行有可见的失败标识(标红 + 失败提示)

#### Scenario: 工具名显示真实注册名
- **WHEN** 用户看任意工具调用行
- **THEN** 工具名显示其真实注册名(`bash` / `read` / `write` / `edit` / `agent` / `task_stop` /
  `web_fetch` / `memory` / `skill_manage` / `web_search`),不出现别名或改写名

#### Scenario: web_search 折叠显查询词
- **WHEN** agent 调用 `web_search` 搜索某查询词且搜索成功
- **THEN** 该工具行折叠态显示 `🔍` 图标 + 查询词文本(如 `🔍 nano multiagent 架构`),不出现裸 JSON args
- **AND** 搜索失败(provider 不可用/报错)时折叠仍显 `🔍` + 查询词,该行标红,展开能看到出错原因

#### Scenario: web_fetch 折叠显抓取的网址
- **WHEN** agent 调用 `web_fetch` 抓取某 URL
- **THEN** 该工具行折叠态显示 `🌐` 图标 + 该 URL(如 `🌐 https://example.com/doc`),不显示
  `status=200 (title)` 这类机器视角文案
- **AND** 抓取失败(网络错误/非法 URL/4xx-5xx)时折叠仍显 `🌐` + 该 URL

### Requirement: 工具折叠行图标随工具自带,自定义工具可拥有专属图标

折叠行图标优先取工具/presenter 自带的 emoji(经内核事件透传 + 落库);工具未声明 emoji 时回退到前端
按工具名的图标表(内置工具不退化,未知/DIY/MCP 工具回退通用 🔧)。

#### Scenario: 自定义 / MCP 工具声明了 emoji
- **GIVEN** 一个自定义(`.nano/tools/`)/ MCP / 新产品工具的 presenter 声明了专属 emoji
- **WHEN** agent 调用该工具,记录出现在聊天面板
- **THEN** 折叠行显示该工具自带的 emoji,而非通用 🔧

#### Scenario: 工具未声明 emoji 回退(不退化)
- **WHEN** agent 调用一个未声明 emoji 的工具
- **THEN** 折叠行回退按工具名取图标:内置工具显其既有图标,未知/DIY/MCP 工具显通用 🔧

### Requirement: 工具调用展开态按工具类型呈现详情

展开一行工具调用时,按工具类型给出对应的结构化呈现,而非裸 JSON。

#### Scenario: bash 展开看到命令与输出
- **WHEN** 用户展开一个 bash 工具行
- **THEN** 看到 description、执行的命令、以及该命令真实的 stdout/stderr
- **AND** 退出码非 0 时,exit code 与报错以标红呈现

#### Scenario: edit 展开看到 diff
- **WHEN** 用户展开一个 edit 工具行
- **THEN** 看到增删着色的 diff,而不是裸 JSON

#### Scenario: write 展开看到写入内容
- **WHEN** 用户展开一个 write 工具行
- **THEN** 看到写入的文件内容预览与字节数

#### Scenario: web_fetch 展开看到网页信息
- **WHEN** 用户展开一个抓取成功的 web_fetch 工具行
- **THEN** 看到 URL、状态码,以及抓取到的正文文本(正文非空)
- **AND** 抓取失败时,展开看到可读的错误说明或状态码,绝不出现空正文或 `status=None` 这类机器串

#### Scenario: web_search 展开按结果条目渲染
- **WHEN** 用户展开一个成功的 web_search 工具行
- **THEN** 展开区按条目列出每条结果的标题、网址(完整可读的纯文本,可手动复制)、摘要,而非一坨原始字符串
- **AND** 查询无任何命中时,展开区显示明确的"无结果"空态文案,而不是空白或原始字符串

#### Scenario: agent 展开看到完整派发 prompt
- **WHEN** 用户展开一个 agent 工具行
- **THEN** 完整(不截断)显示派发给子 agent 的 prompt
- **AND** prompt 呈现在子 agent 执行结果之前
- **AND** 子 agent 失败时仍显示派发 prompt 与错误文本(不退化为空错误卡)

#### Scenario: memory / skill_manage / task_stop 有专属呈现
- **WHEN** 用户展开 memory、skill_manage 或 task_stop 工具行
- **THEN** 看到该工具的结果卡片(写入的记忆 / 创建的 skill / 停止的任务),而不是截断的 JSON
- **AND** memory / skill_manage 返回失败(success=false)时,卡片呈现失败态而非成功态

### Requirement: 长输出可控展开,不撑爆聊天流

工具输出很长时,展开态默认截断 + 可控展开全部,展开后限高内部滚动,不打乱聊天流滚动位置。

#### Scenario: 长输出默认截断
- **GIVEN** 某工具输出超过单屏展示阈值
- **WHEN** 用户展开该工具行
- **THEN** 先显示截断版输出,并提供"点击展开全部"入口

#### Scenario: 展开全部后限高滚动
- **WHEN** 用户点"点击展开全部"
- **THEN** 补出完整输出,且详情区限高、内部滚动,聊天流整体高度与滚动位置不被撑乱
- **AND** 提供"收起"回到截断态

#### Scenario: 源头已截断的输出
- **GIVEN** 工具输出大到在产生端已被截断
- **WHEN** 用户展开全部
- **THEN** 在输出末尾明确标注"输出过长,已在源头截断"

### Requirement: 工具执行中状态不退化

工具尚在执行时折叠态保持运行中提示,完成后自动更新为完成态。

#### Scenario: 工具执行中
- **GIVEN** 某工具调用尚未完成
- **WHEN** 用户查看工具调用面板
- **THEN** 该行折叠态显示"运行中"提示(脉冲),完成后自动更新为完成态

### Requirement: agent 回复轮次的本轮墙钟耗时随终态对外可见

一轮 agent 回复从占位消息创建(`message.created`,`delivery_status=running`)到收尾(`message.completed`)
之间的本轮处理墙钟,在收尾时作为该消息的 `elapsed_ms`(整数毫秒)对消费者可见——既随
`message.completed` 事件帧下发,也在历史消息读取的响应里回填。起点为占位消息的 `created_at`
(agent 开始处理这一轮),终点为收尾时刻;仅 agent 消息有该值,进行中(未收尾)的消息无 `elapsed_ms`。

#### Scenario: message.completed 携带本轮墙钟
- **GIVEN** 一条 agent 占位消息已于 `created_at` 创建、处于 `running`
- **WHEN** 该轮收尾、IM 发出 `message.completed`
- **THEN** 该事件帧含 `elapsed_ms`,约等于收尾时刻与 `created_at` 之差(毫秒)

#### Scenario: 历史消息读取回填本轮墙钟
- **GIVEN** 一条已收尾的 agent 消息
- **WHEN** 消费者读取该会话历史消息
- **THEN** 该消息含 `elapsed_ms`,刷新后仍可见,与事件下发值一致

#### Scenario: 进行中消息无墙钟值
- **WHEN** 消费者读取一条尚未收尾(`running`)的 agent 消息
- **THEN** 该消息无 `elapsed_ms`,不呈现伪造耗时

### Requirement: agent 气泡呈现本轮墙钟,工具聚合徽标不再呈现累加耗时

agent 回复气泡显示本轮墙钟:进行中实时增长,收尾后定格为最终值;零工具的纯文本回复同样显示;
用户自己的消息气泡不显示耗时。工具调用聚合徽标折叠态只呈现调用次数,不再呈现各工具执行耗时的累加;
展开后每个工具仍各自显示其执行耗时。

#### Scenario: agent 气泡显示本轮墙钟(进行中与定格)
- **WHEN** 一轮 agent 回复正在进行
- **THEN** 气泡上显示一个随时间实时增长的计时
- **AND** 该轮收尾后,计时定格为本轮最终墙钟

#### Scenario: 零工具纯文本回复也显示耗时
- **WHEN** agent 这一轮只回文本、未调用任何工具
- **THEN** 气泡同样显示本轮墙钟

#### Scenario: 用户自己的消息气泡不显示耗时
- **WHEN** 用户查看自己发出的消息气泡
- **THEN** 该气泡不显示任何耗时

#### Scenario: 折叠态工具徽标不含累加时长
- **GIVEN** 一条有 N 次工具调用的 agent 气泡
- **WHEN** 查看折叠态工具徽标
- **THEN** 徽标只显示调用次数,不含各工具执行耗时的累加

#### Scenario: 展开后单工具耗时仍在
- **WHEN** 展开工具列表
- **THEN** 每个工具行仍各自显示其执行耗时

### Requirement: 聊天流消息按时间顺序渲染，实时与刷新一致

聊天流中的消息按各自创建时刻先后渲染。该顺序在实时事件流到达时即生效，无需刷新，
且与刷新页面（走历史拉取）后的顺序一致。

#### Scenario: 实时到达的 agent 回复按时间排在用户消息之后
- **GIVEN** 用户在会话里发了一条消息，其后 agent 产生一条更晚的回复
- **WHEN** agent 回复经实时事件流到达前端（无需刷新）
- **THEN** 用户消息在上、agent 回复在下，与刷新页面后的顺序一致；
  不会出现「回复气泡短暂排在用户消息之前」的错位

#### Scenario: 实时事件到达顺序与时间顺序不一致时仍按时间渲染
- **GIVEN** 两条消息的时间先后已定（由各自创建时刻决定）
- **WHEN** 它们的实时事件以与时间相反的顺序先后到达前端
- **THEN** 聊天流仍按创建时刻先后渲染，到达先后不影响最终顺序；
  时刻相同的消息有稳定确定的相对次序，不抖动

### Requirement: 群会话支持成员增减、改名与解散（owner 隔离、解散限创建者）

前端经 `/im/v1/conversations/{id}*` 对一个已存在的群会话管理其成员与元数据：向群添加参与者（Actor）、
移除某个参与者、修改群名、解散整个群。所有操作按 owner 租户隔离（跨租户 404）；解散仅会话创建者可执行，
非创建者被拒。这些能力让用户在内置 Web IM 里完成基本群治理，无需重建群。

#### Scenario: 向已存在的群会话添加参与者
- **GIVEN** 终端用户在自己租户下有一个群会话，且账号下存在尚未加入该群的 agent
- **WHEN** 前端 `POST /im/v1/conversations/{id}/participants` 带一组 Actor（`{type:"agent", id:"<agent_id>"}`）
- **THEN** 200 返回该会话快照，其 `participants` 含新加入的 agent；此后该 agent 能收发该会话后续消息

#### Scenario: 重复添加已在群的参与者保持幂等
- **GIVEN** 某 agent 已是该群成员
- **WHEN** 前端再次 `POST /participants` 提交同一 agent
- **THEN** 成员不重复出现，会话快照参与者集合不变（不报 500）

#### Scenario: 添加请求为空或 agent 无法解析被拒
- **WHEN** 前端 `POST /participants` 提交空列表或无法解析为已知 agent 的 id
- **THEN** 400 拒绝，会话成员不变

#### Scenario: 跨租户添加参与者返回 404
- **WHEN** 用户对不属于自己租户的会话 `POST /participants`
- **THEN** 404，不泄漏该会话存在

#### Scenario: 修改群名生效，空名被拒
- **WHEN** 前端 `PATCH /im/v1/conversations/{id}` 提交非空 `title`
- **THEN** 200 返回更新后的会话，会话列表与详情显示新群名
- **AND** 提交空 `title` 时不接受为新名（会话名保持原值）

#### Scenario: 会话参与者带 user_id 供成员管理
- **WHEN** 前端读取会话（`GET /conversations` 或写操作返回的快照）
- **THEN** 每个 participant 带 `user_id`（agent participant 的 `id` 是 agent_id，`user_id` 是其稳定 IM 用户标识），前端据 `user_id` 调移除端点

#### Scenario: 移除参与者后该成员从群消失
- **GIVEN** 群里有多个 agent 成员
- **WHEN** 前端 `DELETE /im/v1/conversations/{id}/participants/{user_id}` 指定某 agent 的 `user_id`
- **THEN** 204；该会话快照参与者集合不再含该成员；可一直移除到群里只剩用户本人，群仍存在

#### Scenario: 仅创建者可解散群，非创建者被拒
- **WHEN** 会话创建者 `DELETE /im/v1/conversations/{id}`
- **THEN** 204，该会话及其消息被删除，列表不再返回它
- **AND** 非创建者发起同一请求时 403，会话不被删除

### Requirement: token 气泡展示整轮缓存命中率

#### Scenario: 有命中
- **WHEN** 用户点开一条助手回复的 token 气泡详情
- **THEN** 在「已用上下文」行下方看到「缓存命中」一行，含命中量与百分比（整轮累计口径）

#### Scenario: 无命中
- **WHEN** 本轮无任何缓存命中且用户点开详情
- **THEN** 「缓存命中」行仍显示，值为 `0 (0%)`，不隐藏该行

### Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示

#### Scenario: 内部 Web IM 一轮含多段思考与工具调用
- **WHEN** 一轮带多段思考、多次工具调用的助手回复在内部 Web IM 展示
- **THEN** 气泡内有一个可折叠「过程」区域，把多段思考与工具调用按真实先后次序混排；每段思考可展开读完整内容、可收起；历史回看仍可展开

#### Scenario: 内部 Web IM 无思考
- **WHEN** 助手回复本轮无任何思考
- **THEN** 过程区域里不出现思考行（无思考不留空壳）

#### Scenario: 外部 channel
- **WHEN** 同一条回复送达外部接入的 IM
- **THEN** 只显示正文、不含任何思考
### Requirement: 待决权限卡提供常驻选填的拒绝理由输入框

IM 的待决工具授权卡在决策按钮区上方常驻一个选填的拒绝理由输入框。用户拒绝时填写的理由随拒绝决定一并提交、最终透传给处理该运行的节点；选择允许类决策时该输入框内容不产生任何效果。

#### Scenario: 待决权限卡展示理由输入框
- **GIVEN** 一张处于待决态、显示「允许 / 本会话内允许 / 拒绝 / 总是允许」的工具授权卡
- **WHEN** 用户查看该卡片
- **THEN** 决策按钮区上方常驻一个选填理由输入框，留空亦可正常做任意决策

#### Scenario: 拒绝时提交所填理由
- **GIVEN** 待决权限卡的理由输入框已填入文本
- **WHEN** 用户点「拒绝」
- **THEN** 该拒绝决定连同所填理由一并被提交转发给承载该运行的节点

#### Scenario: 允许类决策忽略理由框
- **GIVEN** 待决权限卡的理由输入框已填入文本
- **WHEN** 用户点「允许 / 本会话内允许 / 总是允许」中任一
- **THEN** 该工具被照常放行，理由框内容不产生任何可观察影响
