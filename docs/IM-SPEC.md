# IM 服务 SPEC — src/IM/

> **版本** v1.0 | **日期** 2026-03-11
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

---

## 2. 核心能力

按业务优先级排列：

### P0 — 内置 Web IM

用户在未接入任何外部 IM 时也可完整使用 Multi-Agent 能力。

- 用户与任意 Agent 单聊
- 用户查看 Agent 之间的单聊会话
- 用户创建群聊（手动选择若干 Agent）
- 消息流式推送（SSE）
- 多媒体/文件上传（落盘后路径透传给 Node Gateway）
- Token / Turn 统计展示（单聊全局、群聊按 Agent 分别查看）

### P0 — 设备绑定与用户归属

- 用户在本机执行绑定命令 → 系统提供浏览器跳转链接 → 登录 → 设备绑定确认
- 绑定后该设备上的 Agent 自动归属当前用户空间
- 同一用户支持多台机器部署多个 Agent，统一管理

### P1 — Agent 配置中心

- Web 端管理各 Agent 的显示名、描述、system prompt、skills 白名单、工具白名单、群聊策略、默认模型
- 配置变更仅对新会话生效，已开始的会话保持原行为
- 配置版本化（`profile_version` 乐观锁），支持冲突检测

### P1 — 节点管理与状态聚合

- 节点注册、心跳上报、在线/离线/降级状态
- 执行结果汇报与投递回执
- 节点看板：在线状态、最近心跳、错误摘要、承载 Agent 数量

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
| `node.register` | 节点注册（携带 node_id、agent 列表、能力声明） |
| `node.heartbeat` | 周期心跳（在线状态、Agent 运行态摘要） |
| `node.report` | 执行结果汇报 |
| `node.delivery_receipt` | 投递回执 |

**下行（IM 服务 → Gateway）**：

| 消息类型 | 用途 |
|---|---|
| `relay.message` | Web IM 消息中继（进入 WebIM Channel 适配器） |
| `config.sync` | 配置版本通知 |
| `heartbeat.trigger` | 手动触发某个 Agent 的 heartbeat |

Gateway 断线后自动重连（指数退避），重连后重新注册。断线期间外部 IM 主路径不受影响。

---

## 5. HTTP API

### Web IM

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/conversations` | 会话列表（含未读数、最后消息摘要） |
| POST | `/im/v1/conversations` | 创建会话（单聊/群聊，指定参与者） |
| GET | `/im/v1/conversations/{id}` | 会话详情 |
| PATCH | `/im/v1/conversations/{id}` | 更新会话（置顶、免打扰、标题） |
| POST | `/im/v1/conversations/{id}/messages` | 发送消息 |
| GET | `/im/v1/conversations/{id}/messages` | 分页读取消息历史 |
| GET | `/im/v1/conversations/{id}/events` | SSE 事件流（流式回复、状态变更） |

### Agent 配置

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/agents` | Agent 列表 |
| GET | `/im/v1/agents/{id}/config` | Agent 配置详情 |
| PATCH | `/im/v1/agents/{id}/config` | 更新配置（需 `profile_version` 乐观锁） |

### 节点管理（面向前端）

节点注册、心跳、上报等通过 WebSocket 上行消息处理（见 §4），以下为前端查询与配置接口：

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/im/v1/nodes` | 节点列表与状态（前端看板） |
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
| `User` | `user_id`, `display_name`, `owned_node_ids`, `created_at` | 单用户 owner |
| `AgentProfile` | `agent_id`, `owner_id`, `display_name`, `system_prompt`, `skills[]`, `tool_allowlist[]`, `group_reply_policy`, `default_model`, `profile_version` | 配置变更仅对新会话生效；`owner_id` 关联所属用户 |
| `Conversation` | `conversation_id`, `owner_id`, `type`(direct/group), `participants[]`, `title`, `is_pinned`, `is_muted`, `unread_count`, `last_message_at` | 会话容器；`owner_id` 用于用户间数据隔离 |
| `Message` | `message_id`, `conversation_id`, `sender_type`(user/agent/system), `sender_id`, `content`, `attachments[]`, `created_at`, `delivery_status` | 消息（通过 conversation 间接关联 owner） |
| `NodeStatus` | `node_id`, `owner_id`, `node_name`, `status`(online/offline/degraded), `last_heartbeat_at`, `agent_count`, `version`, `last_error` | 节点运行态；`owner_id` 关联所属用户 |
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
Node Gateway → IM 服务（回执/结果）→ SSE 推送到浏览器
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
  → IM 服务版本 +1，返回 ack
  → 可选：通过 WebSocket 下推 config.sync 通知 Gateway 拉取最新配置
  → 配置仅对新会话生效，已有会话不受影响
```

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
| `/settings/agents` | Agent 配置列表 |
| `/settings/agents/:id` | Agent 配置编辑 |
| `/settings/nodes` | 节点状态与配置 |
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
│   └── gateway_handler.py      # Gateway WebSocket 连接管理（上行/下行消息处理）
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
│   ├── sse.py                  # SSE 推送
│   └── storage/                # 附件存储
└── frontend/                   # Web IM 前端
    ├── package.json
    ├── src/
    │   ├── app/                # 路由与页面壳
    │   ├── components/         # 通用组件
    │   ├── features/
    │   │   ├── chat/           # 会话列表、消息流、输入
    │   │   └── settings/       # Agent 配置、节点管理、账号
    │   ├── services/           # API client / SSE 消费
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

---

## 12. 验收标准

1. 内置 Web IM 可完成一次完整消息往返（发送 → Agent 执行 → 流式回复展示）
2. 用户可创建单聊和群聊，群聊中多 Agent 正确参与
3. 设备绑定流程完成后，节点 Agent 自动归属当前用户
4. Agent 配置变更可查询、版本化、冲突检测
5. 节点状态（在线/离线/降级）在节点看板正确展示
6. Token / Turn 统计在单聊和群聊中正确展示
7. 关闭中继后，IM 服务仍可作为配置中心独立运行
8. 前端在桌面与手机竖屏都可正常使用
9. IM 服务离线时，外部 IM 主路径仍可用（Node Gateway 自治验证）
10. 消息中继幂等，重复请求不产生重复消息
