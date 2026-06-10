# IM Specification

> 对齐: feat-394
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
