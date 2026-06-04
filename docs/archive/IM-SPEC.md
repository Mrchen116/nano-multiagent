# IM 服务 SPEC — src/IM/

> **版本** v1.1 | **日期** 2026-03-27
> 本文档是 `src/IM/` 的设计权威文件，从属于顶层 `SPEC.md`。

---

## 1. 定位

`IM` 是独立部署的可选中心服务，包含后端服务和内置 Web IM 前端。

**做什么**：
- 提供内置 Web IM（用户无需接入任何外部 IM 即可使用全部 Multi-Agent 能力）
- 管理用户账号、设备绑定、Agent 配置
- 将 Web IM 消息中继到 Node Gateway
- 聚合节点状态与执行统计

**不做什么**：不直接对接外部 IM（由 Node Gateway 的 Channel 负责），不执行 Agent 推理（由 agent 内核负责），不触发 heartbeat 周期任务（由 Node Gateway 本地调度），不直接调用 agent 内核。

**边界**：IM 服务只与用户浏览器和各机器上的 `personal_assistant`（Node Gateway）交互。IM 可离线，Node Gateway 仍可本地自治。

**消息主体**：对 IM 而言，人和 Agent 都是平等的消息参与者。产品与接口语义应优先围绕参与者/Actor 建模。

---

## 2. 核心能力

按业务优先级排列：

### P0 — 内置 Web IM

用户在未接入任何外部 IM 时也可完整使用 Multi-Agent 能力。

- 用户与任意 Agent 单聊
- 用户查看 Agent 之间的单聊会话（参与者为两个 Agent；用户是查看者而非该单聊参与者，并在自己的会话列表中可发现）
- 用户创建群聊（手动选择若干 Agent）
- 消息与状态实时推送（**用户维 WebSocket** `/im/ws/user` + `GET /im/v1/sync` 对齐游标；不再使用按会话 SSE）
- 多媒体/文件上传（落盘后路径透传给 Node Gateway）
- Token / Turn 统计展示（单聊全局、群聊按 Agent 分别查看）

### P0 — 设备绑定与用户归属

- 用户在本机执行绑定命令 → 系统提供浏览器跳转链接 → 登录 → 设备绑定确认
- 绑定后该设备上的 Agent 自动归属当前用户空间
- 同一用户支持多台机器部署多个 Agent，统一管理

### P1 — Agent 配置中心

- Web 端管理各 Agent 的显示名、描述、system prompt、skills 白名单、工具白名单、群聊策略、默认模型
- Agent 创建入口挂在节点下：只有已绑定且在线的节点才允许创建 Agent
- 每个 Agent 只属于一个节点（`agent -> node` 为多对一），不支持一个 Agent 绑定多个节点
- `workspace_root` 默认由节点按托管规则分配；创建请求可带可选自定义 **绝对路径**，经节点 `agent.create` 校验后回传，IM 持久化并以该值为准；编辑页以只读展示为主
- 配置变更仅对新会话生效，已开始的会话保持原行为
- 配置版本化（`profile_version` 乐观锁），支持冲突检测
- runtime 候选项（skills / tools / models）由**在线网关节点**当场解析并由节点校验；IM 只转发请求、**不在本地持久化**完整能力目录，也不依据 IM 部署机文件系统推断节点真实可用集合

### P1 — 节点管理与状态聚合

- 节点注册、心跳上报、在线/离线/降级状态
- 执行结果汇报与投递回执
- 节点看板：在线状态、最近心跳、错误摘要、承载 Agent 数量
- Web 端打开新建/编辑 Agent 相关页时，经 HTTP API 触发 IM 向**已连接节点**当场拉取 runtime capabilities（skills / tools / models 等），不在 IM 库内缓存该目录

---

## 3. 权限模型

V1 采用**个人 owner 模型**：

- 每个用户是自己所有 Agent 节点的 owner，用户之间数据隔离
- 不区分"管理员/普通用户"角色
- 不引入团队 / 组织 RBAC（避免过度设计）

---

## 4. 与 Node Gateway 的交互

IM 服务与 Node Gateway 之间存在两条独立路径（参见 `docs/NodeGateway-SPEC.md` §2）：

### 聊天消息路径（走 Channel）

Web IM 的聊天消息通过 Node Gateway 的 WebIM Channel 适配器进入，与外部 IM 通道地位平等，走相同的四步决策流水线。

```
Browser ──→ IM 服务 ──→ Node Gateway（WebIM Channel）──→ agent 内核
```

### WebSocket 连接（Gateway 主动发起）

Node Gateway 运行在用户个人机器上，通常在 NAT 后面，不可作为服务端。因此 **Gateway 主动向 IM 服务发起 WebSocket 持久连接**，所有双向通信复用该连接。

**上行（Gateway → IM 服务）**：

| 消息类型 | 用途 |
|---|---|
| `node.register` | 节点注册（携带 node_id、agent 列表；`capabilities` 仅含 relay/send_message/config_sync 等轻量开关，**不含** skills/tools/models 全表） |
| `node.heartbeat` | 周期心跳（在线状态、Agent 运行态摘要；**不携带** skills/tools/models 等重负载能力目录） |
| `node.report` | 执行结果汇报 |
| `node.delivery_receipt` | 投递回执 |

**下行（IM 服务 → Gateway）**：

| 消息类型 | 用途 |
|---|---|
| `relay.message` | Web IM 消息中继（进入 WebIM Channel 适配器） |
| `config.sync` | 配置版本通知 |
| `agent.create` | 节点侧创建 Agent 工作区并校验初始 runtime 配置 |
| `agent.capabilities.resolve` | 按某个 Agent 的真实 workspace 解析 runtime capabilities |
| `node.capabilities.resolve` | 节点级当场解析 runtime capabilities（供新建 Agent 页等；**不依赖**历史心跳入库） |
| `heartbeat.trigger` | 手动触发某个 Agent 的 heartbeat |

Gateway 断线后自动重连（指数退避），重连后重新注册。断线期间外部 IM 主路径不受影响。

---

## 5. HTTP API

### Web IM

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/conversations` | 会话列表（含未读数、最后消息摘要） |
| POST | `/im/v1/conversations` | 创建会话（单聊/群聊，指定参与者 Actor） |
| GET | `/im/v1/conversations/{id}` | 会话详情 |
| PATCH | `/im/v1/conversations/{id}` | 更新会话（置顶、免打扰、标题） |
| POST | `/im/v1/conversations/{id}/messages` | 以发送者 Actor 身份发送消息 |
| GET | `/im/v1/conversations/{id}/messages` | 分页读取消息历史 |
| GET | `/im/v1/sync` | 会话列表快照 + 全局 `max_event_id`（用户流 `resync_required` 后对齐） |
| WebSocket | `/im/ws/user?user_id=...` | 浏览器用户维事件流（JSON 帧：`op=event` 等；握手后发送 `{"op":"resume","after_event_id":N}`） |

> 说明：IM 对外接口以 Actor 语义建模。会话参与者、消息发送者、工具目标均使用稳定业务标识（如 `user_id`、`agent_id`、`conversation_id`），不暴露 IM 内部路由主键。

### Agent 配置

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/agents` | Agent 列表 |
| GET | `/im/v1/agents/{id}/config` | Agent 配置详情 |
| GET | `/im/v1/agents/{id}/capabilities` | 按该 Agent 真实 workspace 解析后的 runtime capabilities |
| PATCH | `/im/v1/agents/{id}/config` | 更新配置（需 `profile_version` 乐观锁） |

### 节点管理（面向前端）

节点注册、心跳、上报等通过 WebSocket 上行消息处理（见 §4），以下为前端查询与配置接口：

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/nodes` | 节点列表与状态（前端看板） |
| GET | `/im/v1/nodes/{id}/capabilities` | 向**已连接**的该节点当场请求并返回 runtime capabilities；节点未连接则失败（不把能力快照持久化在 IM 库） |
| POST | `/im/v1/nodes/{id}/agents` | 在指定在线节点上创建 Agent（节点分配 workspace_root） |
| PATCH | `/im/v1/nodes/{id}/config` | 节点中心配置（别名、中继开关、上报开关） |

### 用户与账号

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/me` | 当前用户信息与归属节点 |
| PATCH | `/im/v1/me` | 更新用户设置 |
| POST | `/im/v1/bind` | 设备绑定（生成绑定链接 / 确认绑定） |

### 统计

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/metrics/usage` | Token / Turn 聚合统计 |

---

## 6. 关键数据模型

| 模型 | 核心字段 | 说明 |
|---|---|---|
| `User` | `user_id`, `display_name`, `owned_node_ids`, `created_at` | 单用户 owner；在人机消息模型中对应一种参与者类型 |
| `AgentProfile` | `agent_id`, `owner_id`, `node_id`, `display_name`, `description`, `system_prompt`, `skills[]`, `tool_allowlist[]`, `group_reply_policy`, `default_model`, `workspace_root`, `profile_version` | 每个 Agent 只属于一个节点；`workspace_root` 由节点创建时自动分配并由 IM 持久化；配置变更仅对新会话生效；`owner_id` 关联所属用户；在 IM 消息模型中与人同为参与者 |
| `Conversation` | `conversation_id`, `owner_id`, `type`(direct/group), `participants[]`, `title`, `is_pinned`, `is_muted`, `unread_count`, `last_message_at` | 会话容器；participants 为 Actor 集合；`direct` 明确区分“用户-Agent 单聊”与“Agent-Agent 单聊”，二者不可混用；属于同一 owner 空间的 Agent-Agent 单聊对用户可发现、可查看；`owner_id` 用于用户间数据隔离 |
| `Message` | `message_id`, `conversation_id`, `sender`(actor), `content`, `attachments[]`, `created_at`, `delivery_status` | 消息；发送者是 Actor（人 / Agent / system），通过 conversation 间接关联 owner |
| `NodeStatus` | `node_id`, `owner_id`, `node_name`, `status`(online/offline/degraded), `last_heartbeat_at`, `agent_count`, `version`, `last_error` | 节点运行态；`owner_id` 关联所属用户 |
| `NodeCapabilities` | （逻辑视图，**不入库**）`node_id`, `models[]`, `skills[]`, `tools[]`, … | 由 `GET /im/v1/nodes/{id}/capabilities` 经 WebSocket `node.capabilities.resolve` 向在线网关索取后返回；作为新建 Agent 页候选项来源 |
| `RelayTask` | `message_id`, `target_node_id`, `payload`, `idempotency_key`, `status` | 消息中继任务 |

---

## 7. 关键流程

### 7.1 Web IM 消息往返

```
用户浏览器
  │ POST /im/v1/conversations/{id}/messages
  ▼
IM 服务
  │ 持久化消息 → 创建 RelayTask
  │ 通过 WebSocket 下推 relay.message 到 Node Gateway
  ▼
Node Gateway
  │ WebIM Channel 接收 → 四步决策 → POST /v1/sessions/{id}/messages:async
  ▼
agent 内核执行
  │ 结果/事件流回传
  ▼
Node Gateway → IM 服务（回执/结果）→ 用户维 WebSocket 推送到浏览器
```

### 7.2 设备绑定

```
用户在本机执行绑定命令
  → Node Gateway 请求 IM 服务 POST /im/v1/bind
  → IM 服务返回浏览器跳转链接
  → 用户浏览器打开链接 → 登录（如未登录）→ 确认绑定
  → IM 服务关联 node_id ↔ user_id
  → 该节点上的 Agent 自动归属当前用户
```

### 7.3 配置变更生效

```
用户在 Web 端修改 Agent 配置
  → PATCH /im/v1/agents/{id}/config（带 profile_version 乐观锁）
  → IM 服务要求所属节点校验 runtime 相关字段（skills / tools / models）
  → 校验通过后版本 +1，返回 ack
  → 可选：通过 WebSocket 下推 config.sync 通知 Gateway 拉取最新配置
  → 配置仅对新会话生效，已有会话不受影响
```

### 7.4 节点下创建 Agent

```
用户在 Web 端打开 /settings/nodes/{node_id}/agents/new
  → GET /im/v1/nodes/{node_id}/capabilities（IM 向在线网关当场请求）
  → 前端展示当场解析的 skills / tools / models 候选项
  → 用户提交 POST /im/v1/nodes/{node_id}/agents
  → IM 服务校验 node 已绑定、归属当前用户且当前 online
  → 通过 WebSocket 发送 agent.create 到 Node Gateway
  → Node Gateway 创建并分配 workspace_root，校验初始 runtime 配置
  → IM 服务持久化 AgentProfile（含 node_id、workspace_root）
  → IM 服务同步建对应 IM users 行（username = `agent:<agent_id>`，display_name = agent.display_name），见 §7.5
  → 可选：下推 config.sync
  → 返回新 Agent 配置（含 user_id 字段，供后续会话创建使用）
```

### 7.5 Agent ↔ IM users 行的同步契约（feat-340-M18 R9-1）

每一个 `AgentProfile` 必须有且只有一个对应的 IM `users` 行，关系如下：

- **绑定方式**：`users.username = "agent:" + agent_profile.agent_id`，一一对应，唯一。
- **生成时机**：在 `POST /im/v1/nodes/{node_id}/agents` 创建 AgentProfile 的同一事务内同步建。
- **兼容历史**：M18 之前已存在的 AgentProfile 没有这一行，因此读路径 `GET /im/v1/agents` 在发现缺失时执行 lazy bootstrap（同 username 规则建）。所以**调用方只要看到一个 agent 行，就能在响应里拿到稳定的 `user_id`**。
- **为什么需要**：会话创建端点 `POST /im/v1/conversations { participant_ids: [...] }` 把 agent 当作一种 participant，要求每个 id 都是合法 IM `users.id`。没有这条同步规则，前端只能拿到 `user_id: null`，进而被 400 `participant_ids contains unknown users` 拒绝，用户无法和新建 agent 私聊。
- **数据 invariant**：`AgentProfile.display_name` 变更后，对应 user 行的 `display_name` 不会跟随回写（保持现状即可，bubble 渲染走 agents map 拉新名）。如果未来需要回写，请在 patch agent 配置时统一更新。

`GET /im/v1/agents` 响应字段：

```json
{
  "agent_id": "agent-xxx",
  "owner_id": "user-uuid",
  "node_id": "node-1",
  "display_name": "Alpha",
  "user_id": "user-uuid-of-agent-row",
  ...其它字段
}
```

`user_id` 自 M18 起永远为非空字符串（之前可能为 `null`）。

---

## 8. 前端

### 设计目标

微信/Telegram 风格：信息密度高但不压迫，会话切换快，消息阅读连贯，输入反馈及时。桌面端与手机竖屏都自然，不是简单缩放。

### 信息架构

**桌面端**（两栏 + 设置工作区）：
- 左栏：会话列表、搜索、未读数
- 右栏：消息流、输入区、附件入口
- 顶部入口：Chat / Settings 工作区切换

**手机端**（单栏切换）：
- 首屏会话列表 → 进入会话后消息页 → 设置页独立入口

### 路由

| 路由 | 用途 |
|---|---|
| `/chat` | 会话列表 |
| `/chat/:conversationId` | 会话详情 |
| `/settings/agents` | Agent 配置列表（不承担创建入口） |
| `/settings/agents/:id` | Agent 配置编辑 |
| `/settings/nodes` | 节点状态与配置、Agent 创建入口 |
| `/settings/nodes/:nodeId/agents/new` | 在指定在线节点上创建 Agent |
| `/settings/account` | 账号与设备归属 |

### 技术栈

`React + TypeScript + Vite + React Router + TanStack Query + Zustand + Tailwind CSS v4 + Radix UI`

前端代码放 `src/IM/frontend/`，与 IM 服务同仓维护。

---

## 9. 模块结构

```text
src/IM/
├── app.py                      # 服务启动入口
├── api/
│   ├── deps.py                 # 依赖注入
│   └── routes/
│       ├── web_im.py           # 会话与消息（面向前端）
│       ├── agents.py           # Agent 配置管理（面向前端）
│       ├── nodes.py            # 节点状态查询与配置（面向前端）
│       ├── users.py            # 账号与设备绑定
│       └── metrics.py          # 统计查询
├── ws/
│   ├── gateway_handler.py      # 节点 Gateway WebSocket（/im/ws/gateway）
│   └── user_stream.py          # 浏览器用户维 WebSocket（/im/ws/user）、回放与广播
├── application/
│   ├── web_im_service.py       # 会话与消息业务
│   ├── config_service.py       # Agent 配置版本管理
│   ├── relay_service.py        # 消息中继（通过 WebSocket 下推到 Gateway）
│   ├── bind_service.py         # 设备绑定流程
│   └── report_service.py       # 节点上报聚合
├── domain/
│   ├── models.py               # User / AgentProfile / Conversation / Message / NodeStatus
│   └── policies.py             # owner 范围策略、配置版本生效策略
├── infra/
│   ├── db/                     # 数据库（SQLite / PostgreSQL）
│   └── storage/                # 附件存储
└── frontend/                   # Web IM 前端
    ├── package.json
    ├── src/
    │   ├── app/                # 路由与页面壳
    │   ├── components/         # 通用组件
    │   ├── features/
    │   │   ├── chat/           # 会话列表、消息流、输入
    │   │   └── settings/       # Agent 配置、节点管理、账号
    │   ├── services/           # API client；实时以用户维 WebSocket + TanStack Query 为主
    │   └── styles/             # design tokens
    └── public/
```

### 后端分层规则

- `api → application → domain + infra`
- `domain` 不依赖 `api` / `infra`
- 不拆过多层级，四层足够
- 中继能力放 `relay_service`，可单独关闭

---

## 10. 失效与降级

| 场景 | 影响 | 降级策略 |
|---|---|---|
| IM 服务整体离线 | Web IM 不可用，配置管理不可用 | 外部 IM 主路径正常（Node Gateway 本地自治） |
| 中继关闭 | Web IM 聊天不可用 | IM 服务仍可作为配置中心独立运行 |
| 单节点离线 | 该节点 Agent 不可达 | 消息入队等待，节点恢复后重试 |
| 数据库故障 | 全部写操作失败 | 只读降级（可查看历史，不可发送） |

---

## 11. 硬约束

1. 不直接调用 agent 内核，所有 Agent 执行通过 Node Gateway 中继
2. 不对接外部 IM，外部 IM 由 Node Gateway 的 Channel 适配器负责
3. 不触发 heartbeat 调度，heartbeat 完全由 Node Gateway 本地控制
4. 配置变更仅对新会话生效，不影响进行中会话
5. Web IM 必须同时支持桌面浏览器和手机竖屏
6. IM 离线不影响外部 IM 主路径（Node Gateway 本地自治）
7. 中继可单独关闭，关闭后配置中心功能不受影响
8. 消息中继必须幂等（`idempotency_key`）
9. Agent 创建必须挂在一个已绑定且在线的节点下；无节点不允许创建 Agent
10. runtime capabilities 的候选项与校验结果以**网关节点当场解析**为准；IM 不得通过自身部署机本地文件系统推断，且**不得**将完整目录快照写入 IM 持久化存储

---

## 12. 验收标准

1. 内置 Web IM 可完成一次完整消息往返（发送 → Agent 执行 → 回复展示）；当前前端通过 **用户维 WebSocket** 与/或 **`GET .../messages`** 刷新观察 relay 进度与终态
2. 用户可创建单聊和群聊，群聊中多 Agent 正确参与
3. 设备绑定流程完成后，节点 Agent 自动归属当前用户
4. Agent 配置变更可查询、版本化、冲突检测
5. 节点状态（在线/离线/降级）在节点看板正确展示
6. Token / Turn 统计在单聊和群聊中正确展示
7. 关闭中继后，IM 服务仍可作为配置中心独立运行
8. 前端在桌面与手机竖屏都可正常使用
9. IM 服务离线时，外部 IM 主路径仍可用（Node Gateway 自治验证）
10. 消息中继幂等，重复请求不产生重复消息
11. 用户只能在已绑定且在线的节点下创建 Agent；创建成功后 Agent 带单一 `node_id` 与节点分配的 `workspace_root`
12. 新建页与编辑页展示的 runtime 候选项来自节点能力接口，而不是 IM 服务本机扫描结果
