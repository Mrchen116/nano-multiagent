# refactor-460: Web IM client runtime 收口 — 技术方案

> 对齐: motivation.md v1
>
> Unit branch: `unit/refactor-460` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/IM/frontend/src/features/chat/im-chat-api.ts`（2107 行）同时承担旧 Chat 映射、REST helper、
  bootstrap/cache 以及当前较完整的 user-stream lifecycle；`chat-api.ts` / `mock-chat-api.ts` 再包一层运行时切换。
- `src/IM/frontend/src/features/chat/v2/` 是生产路由真正挂载的 Chat：REST、wire type、timeline reducer 和页面均在此；
  但 `chat-workspace-page.tsx` 为实时消息和状态反向 import legacy user stream。
- `src/IM/frontend/src/features/chat/v2/chat-stream.ts` 是第二套 user-stream，仅被桌面通知使用；它不发送
  `resume`、不 ping、不重连、不处理 `resync_required`。
- `use-global-message-toast.ts`、`agent-completion-notifier.tsx`、Nodes 页面和 Agent status consumer 分别解释
  同一用户流的消息、通知和状态事件，却使用两套连接与两套 Chat query cache。
- 绑定确认、Agent 详情打开单聊、Agent 配置列表 envelope normalization 是 legacy client 最后的非实时生产调用方。
- 生产路由不再挂载旧 `ConversationList` / `MessagePane`，后者已在源码标明仅为旧测试保留。当前 legacy cluster
  的实现代码超过 4200 行，另有相应旧测试。

### 既有约束

- 本 unit 只改 `src/IM/frontend` 与其测试/文档；不改变 IM 后端 `/im/ws/user`、`/im/v1/sync`、REST schema、
  Gateway 协议或持久化数据。
- 后端 user stream 的 current 契约是：JWT 握手、客户端立即 `resume(after_event_id)`、持久事件按 cursor 回放、
  gap/window miss 返回 `resync_required`、客户端以 `/im/v1/sync.max_event_id` 对齐。
- `node.status_changed` / `agent.status_changed` 是同一 envelope 的非持久状态帧，payload 有 owner-scoped `seq`，
  但没有持久事件 `event_id`；断线后不能只依赖 replay，消费方必须刷新权威 REST 快照。
- `authFetch` 已是共享的 authenticated HTTP transport，负责 base URL、Bearer token 和 401 refresh；本 unit 不再
  新造通用 REST client。
- current Chat 使用 React Query；user-stream transport 不得反向持有 QueryClient，否则 transport 会知道 Chat、
  Settings 和通知的领域语义。
- 测试遵循 `docs/TESTING_GUIDE.md`：新接口通过其 observable interface 测，废弃路径的旧测试随路径删除；
  浏览器真栈证据走 e2e/reviewer，不把一次性验收脚本塞进常规 Vitest。

### 契约层 grounding 结论

- `docs/specs/im/agents-nodes.md` 的 JWT、resume、replay 与 sync 契约和 Python 后端一致。
- 生产 Chat 使用 legacy shared stream 时能满足 resume/reconnect 主路径；独立 `chat-stream.ts` 不满足该契约，
  桌面通知因此存在断线失活和历史回放风险。这是代码相对 current 契约的 drift，本 unit 负责修复。
- `docs/specs/im/conversations-messages.md` 中实时消息、顺序、NO_REPLY tombstone 与外部 channel live insert 行为
  已由 v2 reducer/页面消费，本 unit保持这些行为，不改变 wire schema。
- canonical 尚未写明浏览器长时间登录、账号切换和提醒去重的恢复行为；本 unit 以两个 IM delta-spec 补齐。

### 可复用能力

- **改造使用** legacy shared stream 的 cursor、resume、ping、backoff 和 sync 语义；这些行为正确但归属错误，且
  token rotation、stale callback、subscriber isolation 未收口，不能原样复制后继续保留旧实现。
- **直接使用** `useAuthStore` 的当前 session 与 subscribe 能力；runtime 从 session 获取 user/token，调用方不再
  传易过期凭证。
- **直接使用** `authFetchJson` 访问 `/im/v1/sync`，让 sync 与普通 HTTP 共享 refresh 语义。
- **保留使用** v2 `chat-types.ts`、`chat-stream-reducer.ts` 与各领域现有纯事件处理函数；transport 只提供 raw event，
  不吞并 Chat/Settings/Notification 的展示规则。
- **不用** `v2/chat-stream.ts`：补齐它会形成第二个 lifecycle owner；迁移桌面通知后删除。
- **不用** runtime mock facade：current v2 Chat 从未走 `VITE_CHAT_API_MODE`，测试已使用 fetch/WebSocket adapter。

### 本变更沿用的既有模式

- 沿用 `authFetch` 的“共享 transport 隐藏鉴权、领域 client 解释响应”模式：user-stream runtime 隐藏连接生命周期，
  各领域 subscriber 解释事件并更新自己的 state/cache。
- 沿用 React `useEffect -> subscribe -> dispose` 的消费方式，但所有 effect 跨同一个 seam；不新增全局 React context。
- 沿用 v2 reducer 作为 active conversation 的 timeline 权威，不把 timeline 状态搬入 React Query。

### 相关历史

- `feat-340-agent-native-im/M4` 建立 v2 Chat 和 legacy isolation 门禁，原意是 v2 不再反向依赖 legacy；M9 桌面通知
  又独立打开了 `chat-stream.ts`。
- `feat-451-chat-history-pagination/M2` 已因真实浏览器恢复问题把 Chat 从独立 `openChatStream` 切回 shared stream，
  证明单一可靠用户流是已验证方向，而非新假设。
- `bugfix-405-chat-status-realtime` 与 `bugfix-442-sidebar-realtime-sync` 继续把状态和列表刷新接到 legacy shared
  stream，扩大了其实际职责，也让抽取共享 seam 成为删除 legacy 的前置条件。

## 架构总览

本 unit 的核心是把“浏览器如何可靠收到 owner-scoped 事件”做成 deep module；调用方只学会订阅，不再学习
token、cursor、socket、timer、resume、sync 和重连顺序。

```mermaid
graph TD
    Auth["auth store"] --> Runtime["realtime/user-stream<br/>deep module"]
    Runtime -->|"authenticated WebSocket"| IM["IM /im/ws/user"]
    Runtime -->|"sync snapshot cursor"| Sync["IM /im/v1/sync"]
    Auth --> CacheReset["session-scoped query cache reset"]

    Chat["canonical Chat<br/>event mapper + reducer"] -->|subscribe| Runtime
    Toast["global toast<br/>conversation cache sync"] -->|subscribe| Runtime
    Notify["desktop notification"] -->|subscribe| Runtime
    Node["Nodes status consumer"] -->|subscribe| Runtime
    Agent["Agents status consumer"] -->|subscribe| Runtime

    Chat --> ChatCache["one Chat query cache"]
    Toast --> ChatCache
    Notify --> ChatCache
    CacheReset --> ChatCache
```

Before 是“两条 socket + legacy/v2 两套 Chat 数据面”；After 是“一个 transport lifecycle + 多个领域 subscriber +
一个 canonical Chat”。runtime 不认识 QueryClient、消息气泡或状态卡片，避免把共享 module 做成万能事件中心。

## 关键决策

### 决策 1: user-stream seam 放在 Chat/Settings 之外

**新增 `src/IM/frontend/src/realtime/user-stream` deep module，外部 interface 只有订阅与取消订阅。**

- **理由**: Chat、通知和设置都是真实消费者；放在任一 feature 内都会制造反向依赖。小 interface 隐藏全部生命周期，
  同时为五类调用方产生 leverage 和 locality。
- **拒绝**: 继续放在 `im-chat-api.ts`；补强 `v2/chat-stream.ts`；让 App 组件直接持有 socket。
- **风险**: 新顶层目录必须靠 architecture contract 守住，防止未来第二处直接 `new WebSocket('/im/ws/user')`。

### 决策 2: runtime 自己跟随 auth session

**subscriber 不传 `selfUserId` 或 token；runtime 监听 auth store，并在 user/token 变化时切换 connection generation。**

- **理由**: access token 会被 `authFetch` 自动轮换，调用方捕获 token 会在后续重连使用过期凭证。session 是连接身份
  的唯一权威。
- **拒绝**: 保留每个 effect 传 token；等 socket 自然断开后再读取 token；让调用方手工通知 refresh。
- **风险**: 主动换 socket 产生短窗口，必须先保留 per-user cursor，再由新 generation resume；旧 socket callback
  必须因 generation 不匹配而失效。

### 决策 3: 每标签页单连接、多 subscriber，领域语义留在调用方

**runtime 分发开放的 `UserStreamEvent`，不维护全局事件白名单，也不直接更新任何 React Query cache。**

- **理由**: IM 会持续增加消息、状态、relay 等事件；transport 若维护 Chat union 或 cache switch，每次领域变化都要
  修改共享 module。raw envelope 让 transport interface 稳定，领域 mapper 继续拥有 validation 和展示语义。
- **拒绝**: 一个全局 reducer 处理全部事件；每个 feature 独立 socket；runtime 只允许 Chat `WsEvent`。
- **风险**: caller 可能各写一份映射；Chat wire -> `WsEvent` 的公共转换应集中在 canonical Chat 内复用。

### 决策 4: cursor 表示 transport 已接收，subscriber 故障彼此隔离

**合法持久事件一经 runtime 接收即单调推进 per-user cursor；每个 subscriber 独立调用，单个异常不阻塞其他人。**

- **理由**: cursor 是连接恢复位置，不是所有 UI 副作用完成的事务。把它绑到最慢/失败 subscriber 会导致无限 replay
  和重复通知；领域恢复应依赖 REST snapshot。
- **拒绝**: 所有 subscriber 成功后才写 cursor；任一 subscriber 失败就关闭 socket；为每个 subscriber 建独立 cursor。
- **风险**: 崩溃 subscriber 会错过该帧；runtime 在 recovery 时通知所有 subscriber 刷新各自权威查询，且错误必须
  可被测试观察而不破坏分发。

### 决策 5: reconnect 与 resync 统一为 recovery signal

**`onRecovery` 在非首次重连或 `resync_required` 对齐后触发，各领域据此刷新自己的 REST 权威状态。**

- **理由**: 持久消息可以 replay，node/agent status 没有持久 `event_id`，普通 reconnect 也可能漏状态；调用方只需理解
  “连续性曾中断，需要重读”，不必区分 transport 原因。
- **拒绝**: 只在 `resync_required` 刷新；runtime 直接知道并刷新所有 query key；为 status 另建 socket。
- **风险**: reconnect + resync 可能重复触发刷新；同一 generation 内 recovery callback 要合并，subscriber callback
  用 settled isolation 执行。

### 决策 6: server-state cache 生命周期跟随登录用户

**AppProviders 在 user id 变化或 logout 时清空 QueryClient；同一用户 token rotation 不清 cache。**

- **理由**: query key 当前不含 owner，快速切换账号可能短暂复用前一用户的 Chat/Settings cache；只修 socket 不能满足
  账号隔离。cache reset 属于登录 session 生命周期，不属于 user-stream transport 或任一领域 subscriber。
- **拒绝**: 给所有 query key 追加 user id；让每个页面分别监听 logout；依赖 stale/refetch 最终覆盖旧数据。
- **风险**: logout 时所有 server cache 清空是预期副作用；UI-only preference/Zustand state 不在 QueryClient 内，不受影响。

### 决策 7: 完成迁移后只保留 canonical Chat

**删除 legacy client/mock/types/旧组件，把当前 `v2/` 提升为无版本后缀的 `features/chat/` current surface。**

- **理由**: 生产路由早已只使用 v2；保留 `v2` 与根目录 legacy 会继续迫使维护者判断版本，mock env 也与真实入口不符。
  删除和提升命名共同完成迁移闭环。
- **拒绝**: 永久保留 compatibility shim；只删 `im-chat-api.ts` 但留下 v2 目录；重写 current Chat workspace。
- **风险**: 42 个 current v2 文件的机械移动会产生大 diff；必须使用 `git mv`、先删同名 legacy 文件、再靠 build 和
  route/integration tests 证明只改路径，不趁机拆 workspace。

### 决策 8: replace, don't layer

**先把全部实时消费者切到新 interface 并删除旧 stream，再迁移最后的非实时调用方并删除整个 legacy cluster。**

- **理由**: 兼容 wrapper 会让两套 interface 长期共存，失去 deletion test；分两步则每一步都有独立用户价值和回退点。
- **拒绝**: 新 runtime 包一层旧 `attachUserConversationStream`；一次提交同时抽取、搬 42 个文件和删全部测试。
- **风险**: 中间态仍有 legacy REST 代码，但 M1 完成后它不再拥有 socket；M2 必须以“零生产 import”作为删除门禁。

## 接口与数据流

### External interface

调用方唯一需要学习的 interface：

| 名称 | 形状 | 契约 |
|---|---|---|
| `subscribeUserStream` | `(subscriber: UserStreamSubscriber) => () => void` | 首个 subscriber + 有效 session 时连接；最后一个取消或 logout 时关闭；取消幂等 |
| `UserStreamSubscriber.onEvent` | `(event: UserStreamEvent) => void` | 每个合法 event frame 调一次；subscriber 间故障隔离；同一 socket 内保持收到顺序 |
| `UserStreamSubscriber.onRecovery` | `() => void \| Promise<void>`（可选） | 非首次重连或 resync 对齐后通知重读权威状态；同 generation 合并；callbacks settled 隔离 |
| `UserStreamEvent` | `{eventType, payload, eventId?}` | `payload` 为开放 record；持久帧有单调 `eventId`，status 等即时帧允许缺失 |

`subscribeUserStream` 不接受 URL、token、user id、cursor、WebSocket factory、timer 或 QueryClient；这些都不是 caller
正确使用该 module 所需的知识。

### Internal seams

IM 是 remote-but-owned 依赖。runtime 内部定义 socket/environment port，production 使用 Browser WebSocket +
sessionStorage + auth store + `authFetchJson` adapter，Vitest 使用 fake socket/storage/scheduler adapter。内部 seam 不从
external interface 暴露。

| 内部依赖 | Production adapter | 测试用途 |
|---|---|---|
| session source | `useAuthStore.getState/subscribe` | 驱动 login、token rotate、account switch、logout |
| socket factory | browser `WebSocket` | 精确驱动 open/message/close/stale callback |
| cursor store | `sessionStorage`, key 按 user id | 验证 resume、单调推进、账号隔离 |
| scheduler | `window.setTimeout/setInterval` | fake timers 验证 backoff/ping/取消 |
| sync client | `authFetchJson('/im/v1/sync')` | 验证 max cursor 对齐和失败降级 |

### 主路径

```mermaid
sequenceDiagram
    participant C as Domain subscriber
    participant R as UserStream runtime
    participant A as Auth store
    participant IM as IM user stream
    participant Q as Domain REST/cache

    C->>R: subscribe(onEvent, onRecovery)
    R->>A: read current user + token
    R->>IM: connect ?token=current
    IM-->>R: open
    R->>IM: resume(after_event_id=cursor[user])
    IM-->>R: op=event
    R->>R: parse + advance cursor when event_id exists
    R-->>C: onEvent(raw event)
    C->>Q: reducer / cache patch / notification decision

    IM--xR: unexpected close
    R->>R: bounded exponential backoff
    R->>A: re-read latest session
    R->>IM: reconnect with latest token + resume
    R-->>C: onRecovery()
    C->>Q: invalidate/refetch owned state
```

### Connection state machine

```mermaid
stateDiagram-v2
    [*] --> Dormant
    Dormant --> Connecting: first subscriber + authenticated session
    Connecting --> Live: socket open / resume sent
    Connecting --> Backoff: unexpected close
    Live --> Backoff: unexpected close
    Backoff --> Connecting: retry timer + subscribers + session
    Live --> Reconciling: resync_required
    Reconciling --> Live: sync attempted / recovery signaled
    Live --> Connecting: user or token changed / new generation
    Backoff --> Dormant: logout or last unsubscribe
    Connecting --> Dormant: logout or last unsubscribe
    Live --> Dormant: logout or last unsubscribe
```

- 每次 connect 递增 generation；旧 generation 的 `open/message/close/timer` callback 以及 sync async completion 不得
  改变当前状态、cursor 或安排重连。
- backoff 从 1 秒指数增长并封顶 30 秒，成功 open 后归零；Live 每 25 秒 ping，离开 generation 时清 timer。
- `resync_required` 调 `/im/v1/sync`；cursor 更新为 `max(current, max_event_id)`，sync 失败不回退 cursor，仍发
  `onRecovery` 让领域自行重读。后续 reconnect 继续按现有 cursor 恢复。

### Domain ownership

| Subscriber | 保留的领域职责 | recovery 行为 |
|---|---|---|
| Chat workspace | raw message/tool/thinking/permission -> canonical `WsEvent`；active timeline reducer；node/agent chip patch | 刷 current messages、conversations、agents、nodes |
| Global toast | self/current-conversation 过滤、toast dedupe/文案；预热并刷新 canonical conversations query | 刷 conversations，保留已通知 key 防重复 |
| Desktop notifier | agent created/completed/discarded 配对、visibility/preference/permission gate、点击导航 | 不清已处理状态；靠 cursor 避免旧 completion 再入 |
| Nodes page | node status payload validation + settings nodes cache patch | 刷 settings nodes |
| Agent status consumer | agent status validation + agents list/detail cache patch | 刷 settings agents |

### Legacy retirement mappings

| 现有 legacy 调用 | canonical 归属 |
|---|---|
| `confirmBindToken` | `features/settings/im-settings-api.ts` 的窄 bind 请求；身份直接来自 Bearer session |
| Agent detail `createDirectChatByAgentUserId` | canonical Chat `createConversation({title, agentIds})`，只失效 canonical conversation key |
| `normalizeItemsEnvelope` | Agent config client 内部 normalization，不为一个调用方暴露跨 feature helper |
| legacy preview snapshot/cache | 删除；canonical React Query conversations 是唯一列表状态 |
| `VITE_CHAT_API_MODE` / `mock-chat-api` | 删除；component/integration tests 继续注入 fetch/socket adapter |

### Auth session 与 server cache

`AppProviders` 持有 QueryClient，因此由它订阅 auth store 的 user id：从 A 变为 `null`、从 A 变为 B 时执行
`queryClient.clear()`；`null -> B` 时保持空 cache 让各页面按 B 重新取数；A 的 token refresh（user id 不变）不清理。
user-stream runtime 独立监听完整 `{userId, accessToken}`，负责 socket generation，不接触 QueryClient。

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im: `specs/im/agents-nodes.md`, `specs/im/web-chat-ux.md`
- gateway: no spec delta
- cli: no spec delta

## 风险与回退

- **token rotate 与 close 竞态**：旧 socket 的延迟 close 可能误关/重连新 session。以 generation guard + fake socket
  顺序测试兜底；失败时回退 M1，不保留双 runtime 降级。
- **cursor 与通知重复/丢失**：cursor 提前或回退都影响 replay。测试覆盖非法帧不推进、持久帧单调推进、status 无
  event id 不推进、subscriber 抛错仍推进且其他人继续、resync 使用 max 对齐。
- **非持久状态断线漏帧**：每次 continuity recovery 通知 Nodes/Agents/Chat 刷 REST；不能只依赖 replay。
- **React StrictMode mount/unmount**：多 subscriber 和重复 dispose 必须只产生一条活动 socket；最后 subscriber 离开
  后不再重连。
- **大规模路径移动**：M2 仅做 canonicalization、调用方迁移和删除，不重写 workspace；`git mv` 后以 route test、
  Chat integration、完整 Vitest 和 production build 对账。若 M2 失败，可整体回退 M2，M1 runtime 仍可独立工作。
- **快速账号切换复用旧 server cache**：M1 在 AppProviders 统一按 user id 清 QueryClient，并用 provider/auth 集成测试
  证明 token refresh 不误清、logout/account switch 必清；不把安全性寄托在 query stale time。
- **旧测试虚假安全感**：新 interface 测试覆盖 lifecycle 后删除 `im-chat-api`/`chat-stream` 的重叠测试；保留或迁移
  current UI/reducer tests，不以测试数下降作为完成证据。

本 unit 不改变 UI 结构、交互或视觉状态，因此按 design-author 规则不产 `prototype.html`；reviewer 直接以当前真实
Web IM 为视觉与交互基线。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| Worktree Web IM + Gateway 真栈 | `./scripts/e2e-down.sh` | `cd src/IM/frontend && npm run build && cd ../../.. && ./scripts/e2e-up.sh` | `source .e2e-ports.env && curl -fsS "$IM_URL/openapi.json" >/dev/null && curl -fsS "$IM_URL/" >/dev/null && grep -Eq "auto-bound to IM\|Gateway started\|INFO im_connection" .gateway.log` |

**Review 驱动方式**: 端到端真栈并真驱动浏览器客户端。登录 `$IM_URL` 后依次走 Chat 实时回复/NO_REPLY、切到
Me 页验证应用内与系统通知、Gateway 断连/重连时观察 Chat/Nodes/Agents 状态、浏览器短暂离线后恢复、绑定确认、
Agent 详情打开单聊；桌面与移动 viewport 各抽检一次。不得用直接调用内部 reducer 或伪造 subscriber 代替客户端旅程。

## Milestones

拆成两个串行 Milestone，命中“>10 文件 / >4 小时”与“必须分阶段验证”两条硬触发：M1 约涉及 12-16 个
实现/测试文件并新增完整连接生命周期；M2 要迁移/移动 40+ current v2 文件并删除 4200+ 行 legacy。先证明 M1
恢复语义，再删除旧表面，能把 correctness 风险与机械迁移风险分开。

```mermaid
graph LR
    M1["M1 realtime-runtime"] --> M2["M2 legacy-retirement"]
```

### Scenario coverage

| motivation Scenario | 实现路径 | Milestone |
|---|---|---|
| Agent 回复实时更新 | runtime -> Chat event mapper -> timeline reducer | M1 |
| 静默回复撤销临时气泡 | `message.discarded` 经同一 mapper/reducer | M1 |
| 外部 channel 消息实时进入已打开会话 | raw `message.created` -> canonical Chat | M1 |
| 未打开会话收到新消息 | global toast + canonical conversations query | M1 |
| 当前会话和自己的消息不产生多余提醒 | toast 领域过滤/去重 | M1 |
| 后台标签页收到 Agent 完成通知 | desktop notifier subscriber | M1 |
| 不满足通知条件时不弹通知 | notifier visibility/preference/permission gate | M1 |
| 恢复连接不重放历史通知 | per-user cursor + notifier state + recovery | M1 |
| Gateway 断连与重连 | status subscriber + recovery refetch | M1 |
| 长时间保持登录后发生网络重连 | auth-following connection generation | M1 |
| 退出后切换为另一用户 | socket generation + session-scoped QueryClient reset | M1 |
| 确认 Gateway 绑定 | narrow settings bind client | M2 |
| 从 Agent 详情打开单聊 | canonical Chat create-conversation client | M2 |

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-460-M1 | realtime-runtime | — | A | `src/IM/frontend/src/realtime/`; `src/IM/frontend/src/app/{providers*,App.test.tsx}`; `features/chat/{im-chat-api.ts,im-chat-api.test.ts,chat-api.ts,mock-chat-api.ts,hooks/use-global-message-toast*}`; `features/chat/v2/{chat-api.ts,chat-stream*,chat-types.ts,chat-workspace-page*,chat-workspace.integration.test.tsx}`; `features/notifications/agent-completion-notifier*`; `features/settings/nodes/nodes-page*`; `features/settings/agents/agent-status-ws-consumer*`; `tests/contract/test_im_frontend_user_stream_ownership.py` | **[reviewer]** 覆盖 motivation 中“当前会话实时过程”“会话列表/未读/toast”“桌面通知”“Node/Agent 状态”“长时间登录与账号切换”的全部 Scenario，特别验证断线恢复后不重放已处理通知。<br>**[worker]** runtime interface 测试覆盖单 socket/多 subscriber、resume/ping/backoff、token/user generation、cursor 单调性、resync/recovery、subscriber isolation、last-unsubscribe；provider/auth 集成测试覆盖 token refresh 不清 cache、logout/account switch 清 cache；architecture contract 证明 `/im/ws/user` 只有 runtime 一个 lifecycle owner。<br>**[worker]** 相关 Vitest + `npm run build` 通过；M1 后生产实时调用方对 legacy stream 和 `v2/chat-stream.ts` 为零，旧 stream 实现/测试删除而非 wrapper 保留。 |
| refactor-460-M2 | legacy-retirement | refactor-460-M1 | B | `src/IM/frontend/src/features/chat/` 全目录 canonicalization/deletion；`app/{router*,shell/app-shell*}`；`features/chat/bind-confirm-page*`; `features/settings/im-settings-api*`; `features/settings/agents/{agent-detail-page*,im-agent-config-api*}`；所有受路径移动影响的 frontend imports/tests；`src/IM/frontend/README.md`; 本 unit delta-spec | **[reviewer]** 覆盖 motivation 中“确认 Gateway 绑定”“从 Agent 详情打开单聊”，并回归 M1 全部实时旅程、Chat 桌面/移动核心交互。<br>**[worker]** `im-chat-api.ts`、legacy `chat-api.ts`/`mock-chat-api.ts`/`types.ts`、旧 ConversationList/MessagePane 及只服务旧路径的测试删除；原 `v2/` current 文件通过 `git mv` 成为无版本后缀 canonical Chat；生产源码无 `VITE_CHAT_API_MODE`、`chat-v2` query key、legacy import 或第二处 user-stream socket。<br>**[worker]** `npm run test`、`npm run build`、相关 Python contract、`pytest -m "not e2e"` 与 `scripts/e2e-critical.sh` 通过；README 与真实入口一致。 |
