# IM前端蓝图

版本：v0.4  
日期：2026-03-27

## 1. 放置位置

前端代码统一放在：`src/IM/frontend/`。

目标：和 IM 服务端同域协作、同仓维护，降低联调成本。

## 2. 设计目标（微信/Telegram 风格）

1. 信息密度高但不压迫，优先聊天效率。
2. 会话切换快、消息阅读连贯、输入反馈及时。
3. 桌面端与手机竖屏都自然，不是简单缩放。

## 3. 权限模型（V1）

V1 采用个人 owner 模型：

1. 每个用户是自己所有 Agent 节点的 owner，用户之间数据隔离。
2. 不区分”管理员/普通用户”角色。
3. 不引入团队 / 组织 RBAC（避免过度设计）。

## 4. 配置功能放置（先明确归属）

### 4.1 放在 IM 前端（中心可管配置）

1. Agent Profile 配置：`display name`、`description`、`system prompt`、skills 白名单、工具白名单、群聊策略、默认模型。
2. 节点中心配置：节点别名、绑定关系、目标配置版本、是否启用中继/上报。
3. 内置 Web IM 会话配置：会话成员、会话级规则。
4. 节点运行态看板：在线状态、最近心跳、错误摘要；完整 runtime 候选项仅在打开对应设置页时经 API 向在线节点当场拉取（看板可不展示全量目录）。

### 4.2 不放在 IM 前端（节点本地配置）

1. 外部 IM 账号凭证（QQ token、机器人密钥等）。
2. `HEARTBEAT.md` 本地调度细节与本地 cron。
3. 本地工作区路径分配、文件权限、安全策略。
4. skills / tools / models 的真实可用集合推断；这些由节点上报能力并由节点校验，不由 IM 前端或 IM 服务本机猜测。

说明：手机端支持修改“中心可管配置”；本地敏感配置仍在 AgentNode 本地控制台/CLI 修改。

## 5. 信息架构

### 5.1 桌面端（两栏 + 设置工作区）

1. 左栏：会话列表、搜索、未读数。
2. 右栏：消息流、输入区、附件入口。
3. 顶部入口：`Chat / Settings` 工作区切换。

### 5.2 手机端（单栏切换）

1. 首屏会话列表。
2. 进入会话后显示消息页，顶部返回。
3. 设置页独立入口，可修改 Agent 配置和节点中心配置。

## 6. 配置页路由（IM前端内）

1. `/settings/agents`：Agent 列表与配置版本（只查看/进入编辑，不承担创建入口）
2. `/settings/agents/:id`：单 Agent 配置编辑（显示所属节点，并基于 `GET .../agents/{id}/capabilities` 当场解析结果编辑 runtime 配置）
3. `/settings/nodes`：节点状态查看、中心配置编辑、Agent 创建入口
4. `/settings/nodes/:nodeId/agents/new`：在指定在线节点上创建 Agent
5. `/settings/account`：账号与节点归属信息

## 7. 视觉与交互基线

1. 气泡式消息：自己/对方明确区分。
2. 时间分隔与已读状态轻量展示。
3. 输入区固定底部，支持多行输入。
4. 消息流默认贴底，上滚加载历史。
5. 动效克制：仅保留切页与消息出现过渡。

## 8. 技术栈建议（维护优先）

### 8.1 推荐栈（首选）

1. `React + TypeScript + Vite`
2. `React Router`
3. `TanStack Query`
4. `Zustand`
5. `Tailwind CSS v4 + Radix UI`
6. 测试：`Vitest + Playwright`

### 8.2 备选栈

1. `Next.js App Router` 也可行。
2. 但当前后端主干是 Python，首期更建议 `Vite + React`，减少跨栈耦合。

## 9. 组件最小集合

1. `ConversationList`
2. `ConversationItem`
3. `MessageList`
4. `MessageBubble`
5. `Composer`
6. `AttachmentPicker`
7. `TypingIndicator`
8. `SettingsShell`
9. `AgentConfigForm`
10. `NodeConfigTable`

## 10. 前端与后端接口

1. `POST /im/v1/conversations/{id}/messages`
2. `GET /im/v1/conversations/{id}/messages`（历史；含 relay 合成气泡，与列表展示一致）
3. `GET /im/v1/sync`（会话列表快照 + `max_event_id`；用户流 `resync_required` 或冷启动对齐）
4. **WebSocket** `/im/ws/user?user_id=...`（用户维事件流：`op=event` / `resume` / `ping` / `resync_required`；**不再使用**按会话 SSE）
5. `GET /im/v1/agents/{agent_id}/config`
6. `PATCH /im/v1/agents/{agent_id}/config`
7. `GET /im/v1/agents/{agent_id}/capabilities`
8. `GET /im/v1/nodes`
9. `GET /im/v1/nodes/{node_id}/capabilities`
10. `POST /im/v1/nodes/{node_id}/agents`
11. `PATCH /im/v1/nodes/{node_id}/config`（中心可管配置）
12. `GET /im/v1/metrics/usage`

## 11. 目录建议

```text
src/IM/frontend/
├─ src/
│  ├─ app/
│  ├─ components/
│  ├─ features/chat/
│  ├─ features/conversation/
│  ├─ features/settings/
│  │  ├─ agents/
│  │  ├─ nodes/
│  │  └─ account/
│  ├─ services/
│  └─ styles/
└─ public/
```

## 12. 具体页面清单

| 页面ID | 路由 | 设备 | 主要用途 | 操作主体 |
|---|---|---|---|---|
| `P1` | `/chat` | 桌面/手机 | 会话列表与快速进入 | 节点所有者（用户自己） |
| `P2` | `/chat/:conversationId` | 桌面/手机 | 消息阅读、发送、附件上传 | 节点所有者（用户自己） |
| `P3` | `/settings/agents` | 桌面/手机 | Agent 配置列表与版本查看 | 节点所有者（用户自己） |
| `P4` | `/settings/agents/:agentId` | 桌面/手机 | 单 Agent 配置编辑 | 节点所有者（用户自己） |
| `P5` | `/settings/nodes` | 桌面/手机 | 节点状态查看、中心配置编辑、Agent 创建入口 | 节点所有者（用户自己） |
| `P5a` | `/settings/nodes/:nodeId/agents/new` | 桌面/手机 | 在指定在线节点上创建 Agent | 节点所有者（用户自己） |
| `P6` | `/settings/account` | 桌面/手机 | 账号与节点归属信息 | 节点所有者（用户自己） |

## 13. 每页字段清单

### 13.1 `P1 /chat`（会话列表页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `conversation_id` | string | 是 | `GET /im/v1/conversations` | 会话唯一标识 |
| `title` | string | 是 | 同上 | 会话标题 |
| `last_message_preview` | string | 否 | 同上 | 最后一条摘要 |
| `last_message_at` | datetime | 否 | 同上 | 最后活跃时间 |
| `unread_count` | integer | 是 | 同上 | 未读数量 |
| `participants` | array | 否 | 同上 | 参与者头像/昵称 |
| `is_pinned` | boolean | 否 | `PATCH /im/v1/conversations/{id}` | 是否置顶 |
| `is_muted` | boolean | 否 | `PATCH /im/v1/conversations/{id}` | 是否免打扰 |
| `search_keyword` | string | 否 | 本地状态 | 列表筛选 |

### 13.2 `P2 /chat/:conversationId`（会话详情页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `conversation_id` | string | 是 | 路由参数 | 当前会话 |
| `message_id` | string | 是 | `GET /im/v1/conversations/{id}/messages` | 消息唯一标识 |
| `sender_type` | enum(user/agent/system) | 是 | 同上 | 发送者类型 |
| `sender_name` | string | 否 | 同上 | 展示昵称 |
| `content` | string | 否 | 同上 | 文本内容 |
| `attachments` | array | 否 | 同上 | 附件列表 |
| `created_at` | datetime | 是 | 同上 | 时间戳 |
| `delivery_status` | enum | 否 | `GET .../messages` 与用户流 relay 事件 | sent/running/completed/failed |
| `draft_text` | string | 否 | 本地状态 | 输入草稿 |
| `composer_attachments` | array | 否 | 本地状态 | 待发送附件 |

### 13.3 `P3 /settings/agents`（Agent 配置列表页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `agent_id` | string | 是 | `GET /im/v1/agents` | Agent 唯一标识 |
| `display_name` | string | 是 | 同上 | 展示名称 |
| `profile_version` | string | 是 | 同上 | 配置版本 |
| `enabled` | boolean | 是 | 同上 | 启用状态 |
| `node_id` | string | 是 | 同上 | 所属节点 ID |
| `node_name` | string | 否 | 同上 | 所属节点展示名 |
| `node_status` | enum | 否 | 同上 | 所属节点在线状态 |
| `updated_at` | datetime | 是 | 同上 | 最后更新时间 |

### 13.4 `P4 /settings/agents/:agentId`（Agent 配置编辑页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `agent_id` | string | 是 | 路由参数 | 目标 Agent |
| `node_id` | string | 是 | `GET /im/v1/agents/{id}/config` | 所属节点 ID |
| `node_name` | string | 否 | 同上 | 所属节点展示名 |
| `node_status` | enum | 否 | 同上/`GET /im/v1/agents/{id}/capabilities` | 所属节点在线状态 |
| `workspace_root` | string | 是 | 同上 | 由节点分配并管理的工作区路径（只读展示） |
| `display_name` | string | 是 | `GET/PATCH /im/v1/agents/{id}/config` | 显示名 |
| `description` | string | 否 | 同上 | 用途说明 |
| `system_prompt` | text | 是 | 同上 | 系统提示词 |
| `skills_allowlist` | array<string> | 否 | 同上 | 技能白名单；候选项来自 `GET .../agents/{id}/capabilities` 当场解析 |
| `group_reply_policy` | enum | 是 | 同上 | 群聊回复策略 |
| `no_reply_token` | string | 否 | 同上 | 默认为 `NO_REPLY` |
| `default_model` | string | 否 | 同上 | 默认模型；候选项来自所属节点能力 |
| `tool_allowlist` | array<string> | 否 | 同上 | 工具白名单；候选项来自 `GET .../agents/{id}/capabilities` 当场解析 |
| `profile_version` | string | 是 | 同上 | 乐观锁版本号 |
| `capabilities_updated_at` | datetime | 否 | `GET /im/v1/agents/{id}/capabilities` | 本次能力请求完成时间（非 IM 库内持久化快照） |

### 13.5 `P5 /settings/nodes`（节点状态与中心配置页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `node_id` | string | 是 | `GET /im/v1/nodes` | 节点ID |
| `node_name` | string | 否 | 同上/`PATCH` | 节点别名（可改） |
| `status` | enum(online/offline/degraded) | 是 | 同上 | 在线状态 |
| `last_heartbeat_at` | datetime | 否 | 同上 | 最近心跳 |
| `agent_count` | integer | 否 | 同上 | 承载Agent数量 |
| `node_version` | string | 否 | 同上 | 节点版本 |
| `desired_config_version` | string | 否 | `PATCH /im/v1/nodes/{id}/config` | 目标配置版本（可改） |
| `relay_enabled` | boolean | 否 | 同上 | 是否启用中心中继（可改） |
| `report_enabled` | boolean | 否 | 同上 | 是否启用上报（可改） |
| `last_error` | string | 否 | `GET /im/v1/nodes` | 最近错误摘要 |
| `capability_summary` | string | 否 | 前端派生/可选 | 节点列表可不展示全量目录；需摘要时可来自最近一次 `GET /im/v1/nodes/{id}/capabilities` 的拉取结果（须节点在线） |
| `can_create_agent` | boolean | 是 | 前端派生 | 仅在线节点允许进入创建 Agent 流程 |

### 13.6 `P5a /settings/nodes/:nodeId/agents/new`（在指定节点上创建 Agent）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `node_id` | string | 是 | 路由参数 | 创建目标节点 |
| `node_name` | string | 是 | `GET /im/v1/nodes/{node_id}/capabilities` | 目标节点展示名 |
| `node_status` | enum | 是 | 同上 | 创建时必须为 online |
| `capabilities_updated_at` | datetime | 否 | 可用 `GET /im/v1/nodes` 的 `last_heartbeat_at` 近似，或本次能力请求完成时间 | 能力目录非 IM 持久化字段；仅作展示辅助 |
| `display_name` | string | 是 | 本地表单/`POST /im/v1/nodes/{node_id}/agents` | Agent 显示名 |
| `description` | string | 否 | 同上 | 用途说明 |
| `system_prompt` | text | 是 | 同上 | 系统提示词 |
| `skills_allowlist` | array<string> | 否 | 同上 | 候选项来自该次 `GET .../capabilities` 当场解析结果 |
| `group_reply_policy` | enum | 是 | 同上 | 群聊回复策略 |
| `default_model` | string | 否 | 同上 | 候选项来自该次当场解析结果 |
| `tool_allowlist` | array<string> | 否 | 同上 | 候选项来自该次当场解析结果 |
| `workspace_root` | string | 否 | 表单可选、`POST` 响应 | 默认由节点分配；可选填自定义绝对路径，随创建请求下发，以节点回包与 IM 持久化为准 |

### 13.7 `P6 /settings/account`（账号与归属页）

| 字段 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `user_id` | string | 是 | `GET /im/v1/me` | 用户ID |
| `display_name` | string | 是 | 同上 | 用户显示名 |
| `owned_node_ids` | array<string> | 是 | 同上 | 归属节点列表 |
| `default_entry_node_id` | string | 否 | `GET/PATCH /im/v1/me` | 默认入口节点 |
| `created_at` | datetime | 否 | 同上 | 账号创建时间 |

## 14. 首期验收

1. 桌面端：两栏布局可用。
2. 手机端：列表/会话切换顺畅。
3. 手机端可完成 Agent 配置与节点中心配置修改。
4. 消息发送与实时回显稳定（用户流 WebSocket + 必要时 REST 刷新）。
5. 视觉风格达到现代聊天应用基线。

## 15. 协同清单（IM前端）

### 15.1 与 IM 服务协同

1. API 契约冻结：
   - `conversations` / `messages` / **`sync`** / **用户流 WebSocket**
   - `agents config`
   - `agents capabilities`
   - `nodes config/status/capabilities`
   - `node-scoped agent creation`
   - `account`
2. **用户流**与历史对齐（原按会话 SSE 已移除）：
   - 帧形态见 `docs/specs/im/spec.md`：Wire `data` 与持久化 `conversation_events` 的 `event_type` + payload 尽量一致
   - 客户端以 **全局 `event_id`** 去重；多 tab 可重复收到同一事件
   - `resync_required` 后调 `GET /im/v1/sync` 对齐游标并刷新会话列表
3. 配置保存并发控制：
   - `profile_version` 乐观锁
   - 冲突提示与覆盖策略
4. 附件协同：
   - 上传接口、大小限制、失败回执格式
   - 附件元信息字段（`name/size/mime/path`）

### 15.2 与 Agent 节点（node_app）协同

1. 节点状态语义统一：
   - `online/offline/degraded` 判定规则
   - `last_heartbeat_at` 时区与格式
2. 节点能力语义统一：
   - skills / tools / models 由节点上报并作为前端唯一候选来源
   - Agent 创建与 runtime 配置保存时由节点做最终校验
3. 中继与上报开关联动：
   - `relay_enabled/report_enabled` 修改后的生效时机
   - 生效失败时的回滚提示
4. 消息回执映射：
   - 节点回执状态与前端气泡状态一一映射
   - 失败重试按钮触发协议统一

### 15.3 与产品/设计协同

1. 聊天主流程稿：
   - 发消息、重试、撤回（若支持）、失败提示
2. 设置页规则稿：
   - 哪些字段手机可改，哪些只读
   - 高风险改动二次确认文案
3. 视觉规范：
   - Design Token（颜色、字号、间距、圆角、阴影）
   - 组件状态（hover/active/disabled/loading）

### 15.4 与测试/运维协同

1. 联调环境：
   - 本地 mock + dev IM 服务 + 可选节点沙箱
2. 回归用例：
   - 会话列表加载、**用户流**连续事件、relay 气泡与 `GET .../messages` 一致、配置保存冲突
   - 移动端适配与断网重连（含 WebSocket 重连与 `resume`）
3. 监控与排障：
   - 前端错误埋点字段（`trace_id/session_id/conversation_id`）
   - 网络请求与 **WebSocket** 断连/重试率看板

### 15.5 协同产物（必须落文档）

1. 《前端-IM服务 API 字段对照表》
2. 《**用户流（WebSocket）** 事件与 payload 契约表》（替代原按会话 SSE 表）
3. 《节点状态与回执映射表》
4. 《配置项权限与生效时机表》
