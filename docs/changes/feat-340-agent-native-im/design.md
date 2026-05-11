# feat-340: Agent-native IM 前端按新原型重写 — 技术方案

> 对齐: spec.md v1

> Unit branch: `unit/feat-340-agent-native-im` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式:YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

- 2026-05-11 (M12 立项,post-acceptance fix round 2): reviewer round 2 verdict pass-with-issues,2 个 in-unit fix-implementation(R2-1 major: zh.json shell.tabs.agents 漏抽;R2-2 minor: app.py 还有 ?user_id= legacy WS fallback,R1 注释承诺 unit lands 前删)。打包小 fix milestone。
- 2026-05-11 (M11 立项,post-acceptance fix round 1): reviewer round 1 输出 8 个 in-unit fix-implementation issues(4 blocking + 3 major + 1 minor),打包为单个 fix milestone M11。覆盖 chat CSS 缺失、im-chat-api 不带 Bearer、WS token query 名错配、SPA fallback 404、i18n 漏抽、tsc 失败、Settings 多余 Policies 链接。
- 2026-05-11 (M10 立项): 补 M10 backend-status-broadcast,闭合 §5 映射表"heartbeat scheduler"未归属的 producer 与 §接口 2a 中 `node.status_changed` / `agent.status_changed` 的 owner-scoped 推送路径;M6 依赖追加 M10、M5 退出标准追加 agent status WS 实时反映。原因:M2 完成后 M6 worker 启动时发现 producer 与无 conversation_id 的 owner-scoped 旁路 dispatcher 都没归任何既有 milestone,需补一个。

## 架构总览

### 现状(before)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  IM Frontend (React + Zustand + React Query + React Router v7)    │   │
│  │  - 当前为浅色 Workspace 布局, 5 页骨架已搭                          │   │
│  │  - hardcoded owner-1001 / username=you 作为单用户                  │   │
│  │  - 无 i18n, 无 auth, 无通知, 无富 tool_call/token chip 视图        │   │
│  │  - mock-*-api.ts + im-*-api.ts 双层(测试可解耦)                   │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
└───────────────────┼────────────────────────────────────────────────────────┘
                    │ HTTP /im/v1/*   +   WS /im/ws/user?user_id=…
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  IM Service (FastAPI, SQLite at data/im.db)                              │
│  - /im/v1/{messages,agents,nodes,conversations,users,me,uploads,...}      │
│  - WS /im/ws/user (浏览器实时事件) + /im/ws/gateway (Gateway 中继)        │
│  - ConversationEvent 表 + /im/v1/sync 断点续传                           │
│  - 数据模型 multi-tenant ready (User/Agent/Conv/Msg/Node 都有 owner_id)  │
│  - 没有 auth (bearer token = no-op)                                      │
│  - Message.attachments 字段已有, tool_calls 结构待定                     │
│  - UsageMetric 表已有, token_usage 中继路径不完整                        │
└───────────────────┬───────────────────────────────────────────────────────┘
                    │ WS /im/ws/gateway (relay + heartbeat)
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Personal Assistant Gateway (process)                                     │
│  - Channel registry + heartbeat scheduler                                 │
│  - Inbound pipeline: WS event → kernel dispatch → relay deliver           │
└───────────────────┬───────────────────────────────────────────────────────┘
                    │ HTTP /v1/{runs,events,sessions,tools,hook}
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Agent Kernel (FastAPI HTTP API)                                          │
│  - RuntimeEvent: INPUT / TURN_START / MESSAGE_UPDATE / TOOL_CALL /        │
│                  TOOL_RESULT / RUN_ERROR / RUN_TIMEOUT / RUN_ABORT        │
│  - TokenUsage 在 MESSAGE_UPDATE / TOOL_RESULT payload 里                  │
│  - tool_calls 实时事件已支持, 但 IM 中继 schema 未对齐                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 目标(after)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  IM Frontend (重写)                                                │   │
│  │  - 暗色顶栏 + 浅色主体, IBM Plex Sans/Mono, oklch 调色板          │   │
│  │  - 桌面: 顶栏 + Chat/Agents 两侧栏 + 内容; 移动: 底栏 + Me 聚合页 │   │
│  │  - Auth: 登录/注册/登出, JWT/Cookie session, currentUser 替换硬码 │   │
│  │  - i18n: react-i18next, EN/中, localStorage + me.locale 持久化     │   │
│  │  - 富 Chat: 4 类会话渲染 + Tool Calls 面板 + Token Chip + Mention  │   │
│  │  - 附件 chip / Notification API / 移动响应式                        │   │
│  │  - Service Worker (后台通知) + lazy bundle                          │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
└───────────────────┼────────────────────────────────────────────────────────┘
                    │ HTTP /im/v1/* (含 Authorization: Bearer)
                    │ WS /im/ws/user (token in protocol or query)
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  IM Service (扩展)                                                        │
│  - /im/v1/auth/{login,register,logout,refresh,me}  ← 新                  │
│  - /im/v1/{messages,...} 全部走 currentUser owner_id (从 token 提取)     │
│  - Message schema 扩展: tool_calls[] + token_usage 字段(可空)            │
│  - WS event_type 扩展: message.delta(text) / tool_call.update /          │
│    tool_call.result / token_usage.update / heartbeat.node_status         │
│  - bearer auth 真启用 (require_bearer_auth → JWT 校验)                    │
│  - Gateway/IM 中继路径桥接 Agent Kernel 的 RuntimeEvent → IM event       │
└───────────────────┬───────────────────────────────────────────────────────┘
                    │
                    ▼  (Gateway / Kernel 保持不变;仅事件桥接层补齐)
```

变更核心:**前端 5 页全部重写视觉 + 接通真实数据**;**IM 后端扩 auth + 事件 schema + Message 富字段**;**Gateway/Kernel 保持不变,事件桥接层补齐 token_usage / tool_call 实时中继**。

## 关键决策

### 决策 1: Auth 用 JWT + Refresh Token

- **选择**: JWT(access 15min + refresh 7d 轮换),Authorization: Bearer 头,WS 用 `Sec-WebSocket-Protocol: bearer.<token>` 或 query。密码 bcrypt 哈希,users 表加 `password_hash` 字段。前端 access_token 存 localStorage。
- **理由**: 无状态、WS 鉴权友好、前端可解析 user_id、本地/局域网工具不需外部 IdP。
- **拒绝**: Session cookie+CSRF(SPA/WS 翻车多)、OAuth(过度)、API key(无过期)。
- **风险**: localStorage XSS——项目无第三方脚本,access 短 TTL 缓解;紧急封号靠 `user.is_active` 每次 refresh 校验。
- **新端点**: `POST /im/v1/auth/{register,login,refresh,logout}`、`GET /im/v1/auth/me`。
- **现有改造**: `require_bearer_auth()` 启用真 JWT 校验;所有 `/im/v1/*` 路由从 token 提取 `owner_id`,移除 `?user_id=` query param 强绑。

### 决策 2: i18n 用 react-i18next + JSON 文案

- **选择**: `react-i18next` + `src/IM/frontend/src/i18n/{en,zh}.json` 平铺 key + localStorage `im_lang` + 后端 `users.locale` 字段。UserMenu/Me 页 LangToggle 切换并 PATCH `/im/v1/me`。
- **理由**: 社区最广 + React 19 兼容 + 按需加载、JSON 文案 grep 友好、低改造成本(无新构建插件)。
- **拒绝**: lingui(需 babel/swc 插件,本项目用 esbuild)、自研 t()(无插值/复数)、react-intl(重于需求)。
- **风险**: 翻译漏抽,ESLint 规则兜底;后端系统消息保持 EN,不强制 i18n。
- **决策原则**: 选项里**代码复杂度最低 + 易于演进 + 运行稳定** 优先(用户明示,后续所有决策沿用)。

### 决策 3: WS 实时事件 schema 扩展(增量 delta + sync 兜底)

- **选择**: 新增 WS 事件类型 `message.created` / `message.delta` / `message.completed` / `tool_call.upserted` / `tool_call.completed` / `node.status_changed` / `agent.status_changed`,带 `seq` 顺序号。增量 delta 传"新增 token",前端按 seq 拼接;断线/gap → 触发 `/im/v1/sync` 兜底。
- **理由**: 延迟低 + 带宽省 + 原型逐字效果天然实现;sync 兜底机制 IM 已有,复用零成本;事件类型扩展是 enum 加项,演进容易。
- **拒绝**: 全文重发(移动端带宽爆,1k token 推 1000 次全文);SSE 改造(WS 已通,无收益);kernel 直出 IM 格式(破坏 kernel 产品无关性)。
- **风险**: delta 丢/乱 → seq + sync 兜底;WS 重连 → 现有 `/im/v1/sync` 断点续传无改动。

### 决策 4: Tool Calls / Token Usage 内嵌 Message JSON 列

- **选择**: `messages` 表加两列 `tool_calls TEXT NULL`(JSON 数组 `[{id,name,status,duration_ms,input,output}]`) + `token_usage TEXT NULL`(JSON `{output,context_used,context_window}`)。不单独建表。
- **理由**: tool_call 与消息强从属、不跨消息查询、生命周期一致;最少改 + 最简查询 + SQLite JSON1 演进路径开放;UsageMetric 表已负责跨消息统计,不抢职责。
- **拒绝**: 独立 `tool_calls` 表(多表 join、N+1、本期无跨消息查询需求);独立 TokenUsage 表(同上)。
- **风险**: 本期只读不查 JSON 列,无性能问题;真要按 tool_call 维度统计,JSON1 函数足够或将来 backfill 拆表。

### 决策 5: 中继桥接层放 IM 服务内

- **选择**: Gateway 把 kernel `RuntimeEvent` 原样投递到 IM,IM 内新增 `event_bridge` 模块翻译为 ConversationEvent + 写 `messages.tool_calls` / `messages.token_usage` + 广播 WS 事件。kernel 不动,Gateway 仅扩展投递的事件种类(已转 message,补转 tool_call/token_usage)。
- **理由**: IM 是"对浏览器的服务",事件 schema 归它定义;kernel 保持产品无关(coding_cli 也用);改动局部、单一责任。
- **拒绝**: kernel 直出 IM 格式(破坏复用);Gateway 内翻译(Gateway 已含多种职责,继续加重越界)。
- **风险**: 桥接层是新模块,需单元测试覆盖映射(MESSAGE_UPDATE→delta、TOOL_CALL→tool_call.upserted、TokenUsage→token_usage 字段)。

### 决策 6: 设计 token 重写 + 沿用 Tailwind v4 utility

- **选择**: 不引入新样式库。改 `styles/global.css` 的 CSS 变量(IBM Plex Sans/Mono + oklch 调色板)+ Tailwind v4 `@theme` 暴露 token + 删除旧 `im-card` / `im-title` 等编码暖米色视觉的辅助类。组件 class 串随视觉重写一并更新。Radix primitives 保留。
- **理由**: 当前代码已经 100% Tailwind utility(527 className vs 1 inline style),无切换成本;token 集中改一处便于演进;Radix 是 unstyled 壳,样式语义切换无影响。
- **拒绝**: 沿用原型 inline style(主题切换难、snapshot 噪音大);CSS Modules / CSS-in-JS(双轨,违反复杂度低)。
- **风险**: 旧 class 的 snapshot test 会大批失效——重写为行为 test;`im-card` 引用面要 grep 评估删除影响。

### 决策 7: 桌面通知仅前台 Notification API

- **选择**: `Notification.requestPermission()` + 仅在 `document.hidden` / `visibilityState !== "visible"` 时触发。点击 → `window.focus()` + 路由跳会话。Account/Me 页 toggle 开关 + localStorage 持久化。
- **理由**: 无需 Service Worker / VAPID / 后端 push 服务,覆盖 spec 场景 D 够用。
- **拒绝**: Service Worker + Web Push(后端 VAPID + 订阅持久化复杂,本期不值)。
- **演进路径**: 将来要"浏览器关闭也通知" → 加 SW + push,可独立增量,不破坏本期。

### 决策 8: 附件复用 `/im/v1/uploads` + 白名单 + 大小限制

- **选择**: 沿用 `POST /im/v1/uploads`(multipart),返回 `{attachment_id, url, mime, size}`。MIME 白名单(`image/*` / `application/pdf` / `text/plain` / `text/markdown` / `application/json`);单文件 ≤ 10 MB;单消息 ≤ 5 个附件。前端 chip:图片缩略图 / 文档 icon + 文件名 + 叉号删除。
- **理由**: 复用已有端点;白名单 + 大小限制是默认安全姿势。
- **风险**: 存储增长——超范围,运维定期清理。

### 决策 9: Mention picker 候选 = 当前会话内的 agents + 模糊匹配

- **选择**: 数据源 = 当前会话的 agent 参与者列表 `[{agent_id, display_name, avatar_initials, status}]`。`@` 触发,前缀/子串模糊匹配排序;↑↓/Enter/Esc 按 spec。
- **理由**: spec Q8 已锁:用户严格隔离,群聊参与者只能是"当前用户 + 自有 agents",所以候选不含其他 user,只列 agent;数据形态比"User|Agent 混合"更简单。
- **拒绝**: 全局拉所有 agents(破坏会话语义);含 User 候选(隔离原则下当前用户 @ 自己无意义)。
- **风险**: 大量 agent 虚拟列表——本期推后。

### 决策 10: 开发态无后向兼容,DB 直接重建

- **选择**: 开发期不写迁移脚本;模型变更直接 drop & recreate(`data/im.db` 重新建)。Bootstrap 脚本 `python -m IM.cli init_admin --username … --password …` 创建首个用户。前端 hardcoded `owner-1001` 整段删除,`resolveCurrentUserId()` 删除。测试 fixture 用 mock JWT。
- **理由**: 用户明示当前处于开发态、不背兼容包袱——简化最大化。生产化前再补迁移脚本(不在本 unit)。
- **拒绝**: 渐进迁移脚本(本期负担无价值);auth dev bypass(留隐患)。
- **风险**: 现有本地 db 重启会丢——开发态可接受;用户 README 提示。

### 决策 11: 状态事件(node/agent)的 owner-scoped 广播路径

- **选择**: 在 `src/IM/ws/user_stream.py` 的 `UserStreamRegistry` 上新增便利函数 `broadcast_to_user(user_id, frame)`(直接复用既有 `user_id → set[WebSocket]` 索引,不引入新索引);在 `src/IM/ws/gateway_handler.py` 的 `_handle_register` / `_handle_heartbeat` / 节点断连路径上,接 PA 上行帧之后做 node 状态 diff(`record_heartbeat` 返回的 before/after status 或显式比较),变化时 build `node.status_changed` 帧并 `broadcast_to_user(owner_id, frame)`(owner_id 从 `nodes` 行查出);agent.status_changed 同路径——agent_profiles 的 status 字段在 `_handle_register` 写入 agent_count 之后做 agent 维度 diff(若实施期发现 agent.status 没有显式字段,M10 worker 在 progress.md 记决策:把 `agent_profiles.status` 用 `last_heartbeat_at_node_status` 派生,或与 node.status 一致折叠)。offline 判定阈值:连续 `heartbeat_interval × 4 ≈ 60s` 未收到 → offline 边界事件(M10 worker 在 progress.md 钉死实际数值)。
- **理由**: `UserStreamRegistry` 已经是 user-keyed(M1 装好),不需要新机制;diff 放 receive 端最自然,不需要单独 scheduler;复用已有 `broadcast_to_users` 路径(同一个出口 → 一致的死连接清理与 fan-out 语义)。
- **拒绝**: (a) 单独 scheduler 周期轮询所有 nodes 推 status——多一个常驻协程、状态权威源容易撕裂(scheduler vs receive 两个写点)。(b) 引入内部 event bus / pub-sub 抽象——本 unit 唯二订阅方(node.status / agent.status)+ 一处生产端,抽象无价值。(c) 把 producer 塞进 M2 event_bridge——bridge 是 kernel → IM 翻译,PA heartbeat 不是 kernel 事件,语义不一致。
- **风险**: (1) heartbeat 失踪 → offline 判定依赖 timeout 任务,M10 必须实现 timeout 触发器(asyncio task 每 10s 扫一次 `nodes` 表,过期则 emit offline + broadcast);(2) 同一 owner 多连接(多 tab)→ 现有 `broadcast_to_users` 已 fan-out 处理;(3) seq 号给 node/agent 事件 — design §4 说"per conversation 或全局",node/agent 无 conversation,M10 用 owner-scoped 单调递增(从 `nodes.last_heartbeat_at` 派生或简单 monotonic 计数,worker 决定)。

## 接口与数据流

### 1. 新增 HTTP 端点(IM 服务)

| 方法 | 路径 | 请求体 | 响应 | 说明 |
|---|---|---|---|---|
| POST | `/im/v1/auth/register` | `{username, password, display_name?, locale?}` | `{access_token, refresh_token, user}` | 注册并自动登录 |
| POST | `/im/v1/auth/login` | `{username, password}` | `{access_token, refresh_token, user}` | 登录 |
| POST | `/im/v1/auth/refresh` | `{refresh_token}` | `{access_token, refresh_token}` | refresh 轮换 |
| POST | `/im/v1/auth/logout` | `{refresh_token}` | `{ok: true}` | 加 jti 黑名单 |
| GET  | `/im/v1/auth/me` | — | `{user_id, username, display_name, locale, ...}` | 从 Bearer 解析 |

### 2. 现有端点改造

- 全部 `/im/v1/*` 路由从 `?user_id=` query 切到 `Authorization: Bearer <token>` 头提取 `owner_id`
- `require_bearer_auth()` 实装 JWT 校验(HS256,密钥从 env `IM_JWT_SECRET`)
- `PATCH /im/v1/me`:locale 字段可改
- **删除 `GET /im/v1/users`**:严格用户隔离下,列出全部 user 与隔离原则冲突;前端无"用户列表"页,删除即可。如未来需 admin 视图,新立 unit 加 `/im/v1/admin/users`。

### 2a. 租户隔离硬约束

- **所有 repository 查询必须按 owner_id 过滤**——封装到 `OwnerScopedRepository` 基类(在 `src/IM/infra/repository.py`):构造时绑定 `owner_id`,后续 list/get/update/delete 自动加 `WHERE owner_id = ?`。
- API 路由从 token 解出 owner_id → 注入 repository → 路由层无需也无法跳过过滤。
- **WS 广播按 token 解出的 owner_id 过滤,非己之事件不投递**(`message.*` / `tool_call.*` / `node.status_changed` / `agent.status_changed` 全部):IM 内事件分发器维护 `owner_id → ws_connections[]` 索引,事件投递时按事件资源的 owner_id 选择目标连接,绝不广播给全体。
- 单元测试加跨租户隔离断言:用户 A 不能用 token A 读到任何 owner_id=B 的资源(返回 404,非 403,避免泄漏存在性)。

### 3. 现有数据模型扩展

```python
# src/IM/domain/models.py
class User:
    ...
    password_hash: str | None   # 新增,bcrypt
    locale: str = "en"          # 新增

class Message:
    ...
    tool_calls: list[ToolCall] | None  # 新增,持久化为 JSON 列
    token_usage: TokenUsage | None     # 新增,持久化为 JSON 列

class ToolCall:                # 新类型(嵌入,非独立表)
    id: str
    name: str
    status: Literal["running", "completed", "failed"]
    duration_ms: int | None
    input: dict
    output: str | None

class TokenUsage:              # 新类型(嵌入)
    output: int
    context_used: int
    context_window: int
```

### 4. WS 事件 schema(新增 IM → Browser)

```ts
type WsEvent =
  | { type: "message.created"; seq: number; conversation_id: string; message: Message }
  | { type: "message.delta"; seq: number; message_id: string; delta_text: string }
  | { type: "message.completed"; seq: number; message_id: string; content: string; token_usage?: TokenUsage }
  | { type: "tool_call.upserted"; seq: number; message_id: string; tool_call: ToolCall }
  | { type: "tool_call.completed"; seq: number; message_id: string; tool_call_id: string; output: string; duration_ms: number; status: "completed" | "failed" }
  | { type: "node.status_changed"; seq: number; node_id: string; status: "online" | "offline"; last_heartbeat_at: string; last_error?: string }
  | { type: "agent.status_changed"; seq: number; agent_id: string; status: "online" | "offline" };
```

所有事件带 `seq` 递增序号(per conversation 或全局,具体由 worker 实现时定);前端检测 gap → 调 `GET /im/v1/sync?after_seq=…` 兜底。

### 5. Kernel → IM 桥接层

- 位置:`src/IM/application/event_bridge.py`(新模块)
- 输入:Gateway 投递的 `RuntimeEvent`(MESSAGE_UPDATE / TOOL_CALL / TOOL_RESULT / TURN_START / TURN_END / TokenUsage payload)
- 输出:
  - 写 `messages.content`(增量累积)、`messages.tool_calls` JSON、`messages.token_usage` JSON
  - 投递 ConversationEvent → 触发 WS 广播

映射表:

| Kernel 事件 | IM 持久化 | WS 广播 |
|---|---|---|
| `TURN_START` (agent message) | 新 message row(content="", status=running) | `message.created` |
| `MESSAGE_UPDATE`(增量 token,无 token_usage) | append `messages.content` | `message.delta` |
| `MESSAGE_UPDATE`(完成,含 TokenUsage) | 写 `messages.token_usage` + status=completed | `message.completed` |
| `TOOL_CALL`(running) | 插入到 `messages.tool_calls` JSON 数组 | `tool_call.upserted` |
| `TOOL_RESULT` | 更新 `messages.tool_calls` 对应项 status/output/duration_ms | `tool_call.completed` |

PA gateway 上行帧 → IM 状态广播(M10 落地,见决策 11):

| PA 上行 / IM 内部触发 | IM 持久化 | WS 广播(owner-scoped,经 `broadcast_to_user(owner_id, frame)`)|
|---|---|---|
| `node.register`(首次或重连) | `nodes` 行 upsert + status=online | `node.status_changed: online` |
| `node.heartbeat`(状态变化:status 字段或 last_error 翻转) | `node_status` 表更新 | `node.status_changed`(仅状态翻转时,稳态不广播) |
| `node.heartbeat`(`agent_count` 变化或 agent 维度 diff) | `agent_profiles.status` 更新 | `agent.status_changed`(diff) |
| offline 守护任务(asyncio,扫 `nodes.last_heartbeat_at` 过期 60s) | `nodes.status=offline` | `node.status_changed: offline` |
| WS 连接断开(`gateway_handler` finally 块) | `nodes.status=offline`(立即,不等 timeout) | `node.status_changed: offline` |

### 6. 前端数据流(浏览器内)

```
┌──────────────────────────────────────────────────────────────┐
│  AppProviders (React Query Client + Zustand store + i18n)     │
└──────────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   REST 查询      WS 订阅       UI 触发(发送/上传)
        │              │              │
        ▼              ▼              ▼
  React Query      WS reducer    Mutation
  cache(事实源)   ───patch───▶  /im/v1/messages POST
                                /im/v1/uploads POST
                                /im/v1/agents PATCH
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
              组件订阅 cache 渲染
```

- **事实源**:React Query cache。WS 事件不直接渲染,先 patch cache,组件订阅 cache 自然更新。
- **状态分层**:Zustand store 只放纯 UI state(选中会话 ID、附件草稿、mention picker open、search 输入串等);**所有服务器数据走 React Query**。
- **i18n**:`react-i18next` 顶层 Provider;`useTranslation()` 在叶子组件用。
- **Auth context**:Zustand store 一片 `authSlice = { accessToken, refreshToken, user }`,fetch wrapper 自动注入 header,401 → 触发 refresh → 失败跳 /login。

### 7. 模块归属

| 模块 | 路径 | 职责 |
|---|---|---|
| Auth | `src/IM/application/auth_service.py` + `api/routes/auth.py` | JWT 签发/校验/refresh |
| Tenant isolation | `src/IM/infra/repository.py` (OwnerScopedRepository) + `src/IM/api/ws/dispatcher.py` (owner-scoped 广播) | 强制 owner_id 过滤,杜绝跨租户泄漏 |
| Event Bridge | `src/IM/application/event_bridge.py` | Kernel → IM 翻译 |
| Message extensions | `src/IM/domain/models.py` + `infra/db.py` | ToolCall / TokenUsage 嵌入 |
| WS event schema | `src/IM/api/ws/event_types.py`(新)+ 现有 ws/gateway | 类型 + 序列化 |
| Frontend auth | `src/IM/frontend/src/features/auth/` | 登录/注册/refresh hook |
| Frontend i18n | `src/IM/frontend/src/i18n/` | en.json / zh.json + i18next 配置 |
| Frontend shell | `src/IM/frontend/src/app/shell/` | 顶栏 / 底栏 / UserMenu / Me 页 |
| Frontend chat 重写 | `src/IM/frontend/src/features/chat/` | 4 类会话 + 富交互 |
| Frontend agents/nodes/account 重写 | 各自 features 子目录 | 字段表单 + dirty + 真存盘 |
| Notifications | `src/IM/frontend/src/features/notifications/` | Notification API 封装 + toggle |
| Attachments | `src/IM/frontend/src/features/chat/attachments/` | 上传 hook + chip 组件 |
| Design tokens | `src/IM/frontend/src/styles/global.css` | IBM Plex + oklch + Tailwind @theme |

依赖方向:`api → application → domain ← infra`(沿用 CLAUDE.md 既有规则,不引入反向)。

## Milestones

桌面 + 移动响应式 + 5 页全栈 + 多用户 auth + i18n + 附件 + 通知 + 后端事件 schema 扩展——估算超 2000 行改动、跨 30+ 文件、单 worker 远超 4 小时。**必须拆分**(触发条件 #2:工作量),且模块间多组真不交集(触发条件 #1:可真并行)。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-340-M1 | backend-auth-multiuser | — | A | `src/IM/api/routes/auth.py`(新)、`src/IM/application/auth_service.py`(新)、`src/IM/domain/models.py`(User+password_hash/locale)、`src/IM/infra/db.py`(users 表)、`src/IM/cli/init_admin.py`(新)、`require_bearer_auth` 实装、全部 `/im/v1/*` 路由切换到 token 提 owner_id、删除 `GET /im/v1/users`、`src/IM/infra/repository.py`(OwnerScopedRepository 基类)、WS 广播 owner_id 过滤(`src/IM/api/ws/dispatcher.py`)、跨租户隔离单元测试 | `curl -X POST /im/v1/auth/register` → 拿 token → `curl -H "Authorization: Bearer <t>" /im/v1/me` 返回正确身份;`?user_id=` query 彻底移除;用户 A 无法用 token A 读到 owner_id=B 的资源(返回 404);WS 用户 A 连接收不到 owner_id=B 的事件 |
| feat-340-M2 | backend-event-schema | — | A | `src/IM/domain/models.py`(Message.tool_calls/token_usage)、`src/IM/infra/db.py`(messages 表 2 列)、`src/IM/application/event_bridge.py`(新)、`src/IM/api/ws/event_types.py`(新)、`src/personal_assistant/gateway/inbound_pipeline.py`(转发 TOOL_CALL/TOOL_RESULT/TokenUsage) | 跑端到端测试:用户发消息 → kernel mock 出 MESSAGE_UPDATE 增量 + TOOL_CALL + TokenUsage → 浏览器 WS 收到 `message.delta` / `tool_call.upserted` / `message.completed`,DB messages 行写入 tool_calls/token_usage JSON |
| feat-340-M3 | frontend-shell-i18n-auth | M1, M2 | B | `src/IM/frontend/src/styles/global.css`(token 重写)、`src/IM/frontend/src/i18n/{en,zh}.json` + i18next 配置、`src/IM/frontend/src/features/auth/`(登录/注册/refresh)、`src/IM/frontend/src/app/{shell, router, providers}.tsx`(暗顶栏 + 移动底栏 + UserMenu + 路由)、`src/IM/frontend/src/features/me/me-page.tsx`(新)、移除 hardcoded `owner-1001` / `resolveCurrentUserId` | 启动应用,看到登录页(EN/中 可切);登录后看到暗顶栏 + Chat/Agents/UserMenu;移动断点切到底栏 + Me 聚合;路由 `/login` `/register` `/me` 工作;无 hardcoded user;旧测试更新或重写 |
| feat-340-M4 | frontend-chat-rewrite | M3 | C | `src/IM/frontend/src/features/chat/`(全部子文件:chat-overview / chat-detail / message-pane / conversation-list / 各组件)+ 4 类会话渲染 + Tool Calls 面板 + Token Chip + @mention picker + 新建群聊模态 + 分类标签 + 搜索 + 会话头部 chip/badge/⚙ + 流式 WS reducer | 端到端:可看到原型 4 种会话样式;发消息触发流式渲染(消息逐字 + tool_call running 动画 + 完成 token chip);群聊 @ 触发 picker 200ms 内出现;新建群聊真创建;桌面 + 移动两端像素级对齐原型 |
| feat-340-M5 | frontend-agents-rewrite | M3 | C | `src/IM/frontend/src/features/settings/agents/`(全部:list / detail / create + Identity/Behavior/Access&Model/Workspace&Runtime 四卡 + dirty/Save/Discard + Open chat) | Agents 列表/详情/新建桌面+移动像素级对齐;字段全部真存盘;dirty 检测正确;Open chat 跳直聊;status pill 由 `agent.status_changed` WS 实时反映(M10 完成后端,M5 消费即可) |
| feat-340-M6 | frontend-nodes-rewrite | M3, M10 | C | `src/IM/frontend/src/features/settings/nodes/` + 列表 + relay/reporting toggle + 节点视角列 agents/新建 agent + heartbeat 实时驱动 status | Nodes 页像素级对齐;toggle 真存盘;status 由 `node.status_changed` WS 实时反映 |
| feat-340-M7 | frontend-account-rewrite | M3 | C | `src/IM/frontend/src/features/settings/account/` + Account 页字段表单 + locale 切换 + 通知开关 | Account 页像素级对齐;display_name/default_entry_node/locale/通知开关全部真存盘 |
| feat-340-M8 | feature-attachments | M4 | D | `src/IM/frontend/src/features/chat/attachments/`(上传 hook + chip 组件 + drag&drop)、`src/IM/api/routes/uploads.py`(白名单 + size 校验加固)、Message.attachments 渲染 | 桌面拖入图片/PDF → chip 出现 → 发送 → agent 气泡显示附件 + tool 能读到附件路径;白名单/大小限制起效 |
| feat-340-M9 | feature-notifications | M3, M4 | D | `src/IM/frontend/src/features/notifications/`(Notification API 封装 + Account/Me toggle + permission flow + visibility 判断 + 点击聚焦) | 标签未激活时 agent 完成回复 → 系统通知弹出;点击 → 窗口聚焦 + 跳到对应会话;toggle 关闭后不再弹 |
| feat-340-M10 | backend-status-broadcast | M1, M2 | A | `src/IM/ws/user_stream.py` 新增 `broadcast_to_user(user_id, frame)` + node/agent 事件 builder(在 `src/IM/api/ws/event_types.py` 补 `build_node_status_changed` / `build_agent_status_changed`)、`src/IM/ws/gateway_handler.py` `_handle_register` / `_handle_heartbeat` / WS disconnect finally 块插入状态 diff + emit、新增 asyncio offline 守护任务(每 10s 扫 `nodes.last_heartbeat_at` 过期 60s)、跨租户隔离单测(owner A 不收 owner B 节点事件)+ 端到端集成测试(PA gateway 起 → IM 收 register → 浏览器 owner WS 收 online;PA 断 → 收 offline) | PA gateway 起一个 node 发 register/heartbeat → 浏览器 owner WS 收到 `node.status_changed: online`;PA 断开或心跳超时 → 收到 `node.status_changed: offline`;agent 维度 status 翻转 → 收到 `agent.status_changed`;owner A WS 收不到 owner B 的事件;单测覆盖 diff 不变不广播、跨租户隔离 |
| feat-340-M12 | fix-r2 (post-acceptance fix, round 2) | M11 | F | `src/IM/frontend/src/i18n/zh.json` 补 `shell.tabs.agents` = "智能体"(R2-1 major);`src/IM/app.py` 删除 `?user_id=` legacy WS fallback(R2-2 minor) | `npx tsc -b` 干净;中文模式顶栏 tab 全中文;WS 仅接受 `?token=`,`?user_id=` 返 403 |
| feat-340-M11 | fix-r1 (post-acceptance fix, round 1) | M3, M4, M5, M7 | E | reviewer round 1 的 8 个 in-unit issues:`src/IM/frontend/src/styles/global.css`(补 chat-* 类规则或改用 utility)、`src/IM/frontend/src/features/chat/im-chat-api.ts`(切 authFetch)、`src/IM/frontend/src/features/chat/v2/chat-stream.ts`(WS query `access_token` → `token`)、`src/IM/app.py`(加 `/login` `/register` `/me` SPA fallback)、shell + Settings 侧栏 + agents 操作的 hardcoded 字符串切 `t()`、`src/IM/frontend/src/features/settings/account/account-page.test.tsx`(fixture 类型修)、Settings 侧栏移除/注释 Policies 链接 | 重跑 reviewer R2,J2/J5/J6/J9 旅程全通(Chat workspace 有样式、API 有 Bearer、WS 真连、SPA 直链 OK)、`npx tsc -b` 无错、i18n 中文模式无 EN 漏字、Settings 侧栏与 spec 一致 |

依赖图:

```mermaid
graph LR
  M1[M1: backend-auth-multiuser] --> M3[M3: frontend-shell-i18n-auth]
  M2[M2: backend-event-schema] --> M3
  M1 --> M10[M10: backend-status-broadcast]
  M2 --> M10
  M3 --> M4[M4: chat-rewrite]
  M3 --> M5[M5: agents-rewrite]
  M3 --> M6[M6: nodes-rewrite]
  M10 --> M6
  M3 --> M7[M7: account-rewrite]
  M4 --> M8[M8: attachments]
  M3 --> M9[M9: notifications]
  M4 --> M9
```

并行编排:
- **并行组 A**:M1 + M2 + M10(纯后端,改动文件完全不交集;M10 需 M1+M2 合并后才启动,故实际是 A 内的第二波)
- **并行组 B**:M3(只有一个,因为它是壳)
- **并行组 C**:M4 + M5 + M6 + M7(四页前端重写,文件完全不交集 — chat/ vs settings/agents/ vs settings/nodes/ vs settings/account/;M6 额外依赖 M10 后端 producer,需等 M10 完才能验"WS 实时反映";M5 消费 agent.status_changed 也需 M10,但 M5 主体 UI/字段保存不依赖,可与 M10 并行,只在收尾消费事件)
- **并行组 D**:M8 + M9(M8 改 chat 输入框扩展、M9 加新 features/ 目录,M9 还需读 M4 的消息事件 hook 名做 reducer 订阅,实际多半串行但勉强可并行)

## 风险与回退

### 风险 1:M3 阻塞所有下游(壳是单点)

- **描述**:M3 包含 token 重写 + i18n + auth + 路由壳。如果 M3 拖长,M4-M7 全部空等。
- **缓解**:M3 worker 优先把"shell + 路由 + auth"先打通到能 runtime 跑(EN 文案先全英写死,zh 后补),不必死等所有 token 终极完美。M4-M7 启动时 M3 已经提供"可登录 + 顶栏在 + 路由能切"即可。
- **回退**:若 M3 验证发现 i18n 框架选型不合适,在 M3 内修不外溢;影响范围限于 M3。

### 风险 2:WS 事件 schema 在 M2 定型后,M4-M7 发现不够用

- **描述**:实施期常见——事件类型设计时漏一个 case,M4 写到一半发现要加。
- **缓解**:M2 完成时,M4 worker 启动前先和事件 schema 走一遍 spec 5 场景"思想实验",确认覆盖。如发现缺,在 design.md Changelog 追加 + 同步 M2/progress.md。
- **回退**:加事件是 enum 加项,不破坏既有;extend 是安全操作。

### 风险 3:像素级对齐 vs 行为测试稳定性

- **描述**:原型 magic number 多(`262px`、`16/16/4/16`、`oklch(...)` 具体值)。视觉重写后旧 snapshot test 大量失效。
- **缓解**:snapshot test 删,重写为"行为 + 可访问性 + 关键 layout"测试(`screen.getByRole`、`expect(...).toHaveAccessibleName`)。视觉对齐靠 design-review 流程兜底(/design-review skill 可调用)。
- **回退**:CSS 变量出问题,只回退 global.css,不动组件 class——token 切换是原子操作。

### 风险 4:Kernel 事件桥接对 Gateway/Kernel 双侧行为有暗依赖

- **描述**:`event_bridge` 翻译时假设了 kernel 事件 payload 的字段名/形态。kernel 升级可能破坏。
- **缓解**:event_bridge 单元测试用 kernel 真实事件 fixture(从 logs/<session>/ 取一份),不用手写假数据。kernel 改 schema 时 fixture 一起更新。
- **回退**:fixture 测试一旦 fail,锁版本回退 kernel 改动。

### 风险 5:开发态 DB 重建 → 用户本地对话丢失

- **描述**:M1 + M2 上线后,旧 `data/im.db` schema 不兼容,启动时需重建。
- **缓解**:Bootstrap 检测 schema version 不匹配 → 提示"开发态需重建 DB,数据将丢失,Y/N",非交互模式默认拒绝并退出。运行 `python -m IM.cli reset_db` 显式确认。
- **回退**:迁移路径留作生产化 unit(超范围)。

### 风险 6:租户隔离查询泄漏(新)

- **描述**:JWT 启用后,每个 DB 查询都必须 `WHERE owner_id = current_user_id`;任何一处漏写过滤 = 跨用户数据泄漏(返回别人的对话/agent/node/消息)。SQL 拼接式查询尤其危险。
- **缓解**:`OwnerScopedRepository` 基类强制把过滤封装在底层,业务代码拿到的 repo 实例本身就绑定 owner_id,**无法**写出跨 owner 查询(API 层不提供绕过);WS 分发器按 owner_id 路由,绝不全员广播;跨租户隔离单元测试覆盖每一种资源(用户 A 用 token A 访问 owner_id=B 的资源应返回 404)。
- **回退**:若发现实现期某条路径绕过 OwnerScopedRepository(例如直接拼 SQL),CI 用 grep 规则禁止 `SELECT ... FROM (messages|agent_profiles|conversations|nodes|conversation_participants)` 出现在 repository 基类以外的位置。

### 风险 7:M10 状态广播 producer 复杂度被低估(新)

- **描述**:owner-scoped 旁路看似只补一个广播函数,但实际牵涉(a) heartbeat receive 端状态 diff、(b) offline timeout 守护任务、(c) WS 连接断开 finally 块、(d) agent 维度 status 派生(agent_profiles.status 字段语义在现有代码里不明确)。任一点漏了,reviewer 验"online↔offline 实时反映"会 fail。
- **缓解**:M10 worker 启动时先 explore `record_heartbeat` 返回值 + `gateway_handler._handle_register/_handle_heartbeat` + finally 路径,写一份 5 行 diagram 钉死 4 个触发点和数据流后再动手;agent.status 派生策略若 explore 发现不可行,在 progress.md 钉死"folding into node.status"做最小决策。
- **回退**:若 owner-scoped 旁路实施期发现现有 `UserStreamRegistry.broadcast_to_users` 行为有意外副作用,新增 producer 暂用 `broadcast_to_users({owner_id}, frame)` 直接调既有路径(不引新函数),不破坏既有 conversation-scoped 流量。
