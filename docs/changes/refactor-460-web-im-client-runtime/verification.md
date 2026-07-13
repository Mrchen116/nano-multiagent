# Verification Report: refactor-460

## Summary

Mode: `full`

Delta range: N/A

Focus issues: N/A

requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 13/13；Requirement groups 7/9 fully covered |
| Correctness | Scenarios 19/22 covered |
| Coherence | 6/9 design decisions fully followed；3 项存在偏离 |

1 critical issue found. Fix before PR.

## Completeness

- Tasks: 13/13 complete。M1、M2 两份 `tasks.md` 没有未勾选项，6 个 Roadpoint 均在 `progress.md` 标为 DONE。
- Spec 覆盖：单一 user-stream、鉴权 freshness、subscriber 隔离、账号 cache 隔离、canonical Chat、legacy 删除、绑定与 Agent 详情单聊均有实现；连接恢复后的 Chat 权威快照收敛不完整，详见 C1。
- Prototype / Reference 覆盖：N/A。design 明确不改变 UI/交互/视觉；两个 milestone 均把当前真实 Web IM 作为基线，并在各自 `evidence/` 中持久化桌面、移动、绑定、实时消息与状态截图/报告。
- 独立复核：相关 7 个 Vitest 文件共 48 tests passed；`tests/contract/test_im_frontend_user_stream_ownership.py` 3 passed。另以当前 TanStack Query 实现复现：默认 `invalidateQueries(..., { refetchType: "all" })` 在 query fetch error 时仍 resolve，只有传 `{ throwOnError: true }` 才 reject。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 当前会话实时呈现回复、thinking、tool、permission 与完成态 | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:628`；`src/IM/frontend/src/features/chat/chat-stream-reducer.ts:28` | `chat-workspace.integration.test.tsx`、reducer tests、真栈报告 | covered |
| 静默回复撤销临时气泡 | `src/IM/frontend/src/features/chat/chat-stream-reducer.ts:365` | reducer / workspace regression | covered |
| 外部 channel live message 进入已打开会话且显示名一致 | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:635`；`src/IM/frontend/src/features/chat/chat-stream-reducer.ts:28` | workspace/reducer regression | covered |
| 未打开会话的 preview、未读与应用内 toast 一致 | `src/IM/frontend/src/features/chat/hooks/use-global-message-toast.ts:197`；`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:682` | toast 8 tests + 真栈 toast | covered |
| 当前会话和自己的消息不产生多余 toast | `src/IM/frontend/src/features/chat/hooks/use-global-message-toast.ts:227` | toast tests | covered |
| 后台标签页 Agent 完成通知一次且点击可导航 | `src/IM/frontend/src/features/notifications/agent-completion-notifier.tsx:144` | notifier 16 tests | covered |
| 前台/开关关闭/未授权时不发桌面通知 | `src/IM/frontend/src/features/notifications/agent-completion-notifier.tsx:152` | notifier gating tests | covered |
| 恢复不重放已处理提醒 | `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:152`；`src/IM/frontend/src/features/notifications/agent-completion-notifier.tsx:97` | runtime cursor + notifier tests | covered |
| 断线窗口错过的新消息在 Chat 恢复后可见 | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:631` | 仅断言注册 callback，未断言恢复后的 message refetch | 缺实现（C1） |
| Node/Agent 状态事件实时更新 Chat、Nodes、Agents | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:642`；`src/IM/frontend/src/features/settings/nodes/nodes-page.tsx:68`；`src/IM/frontend/src/features/settings/agents/agent-status-ws-consumer.ts:62` | 三类 consumer regression | covered |
| 连接恢复后 Chat 的 Node/Agent 状态回到权威值 | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:631` | 无 Chat recovery cache 测试 | 缺实现（C1） |
| 长登录、expired access + valid refresh 后恢复 | `src/IM/frontend/src/features/auth/auth-session.ts:75`；`src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:176` | auth/runtime tests + 真栈 expired JWT | covered；HTTP 401 的 fresh-token 分支有 W2 |
| A→B 切换后 socket、cursor、server cache 隔离 | `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:237`；`src/IM/frontend/src/app/providers.tsx:18` | runtime/App tests + 真栈 | covered |
| JWT-only user stream、resume 回放、sync cursor | `src/IM/frontend/src/realtime/user-stream/index.ts:15`；`src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:210` | runtime + Python ownership/backend contract evidence | covered |
| 绑定只 confirm 一次、更新同用户 auth snapshot、六组 owner cache settled 后导航 | `src/IM/frontend/src/features/chat/bind-confirm-page.tsx:40` | bind integration + 真栈 | 部分偏离（W1） |
| Agent 详情使用 canonical Chat 创建单聊并显示失败 | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1456` | agent detail tests + 真栈 | covered |
| legacy cluster 删除且只保留 canonical Chat | `src/IM/frontend/src/features/chat/canonical-chat-architecture.test.ts:37`；`tests/contract/test_im_frontend_user_stream_ownership.py:49` | architecture contracts | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. user-stream seam 位于 Chat/Settings 外 | 是 | `src/IM/frontend/src/realtime/user-stream/index.ts:1` |
| 2. auth 拥有 token freshness，HTTP/WS 共享 single-flight | 部分 | `src/IM/frontend/src/features/auth/auth-session.ts:16`；fresh-but-rejected HTTP 401 未强制 refresh（W2） |
| 3. 每标签页单连接、多 subscriber，领域语义留在调用方 | 是 | `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:48` |
| 4. cursor 在 transport 接收时推进，subscriber 故障隔离 | 是 | `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:152` |
| 5. reconnect/resync 统一 recovery，各领域刷新权威状态 | 部分 | runtime 会 signal；Chat 只刷新 conversations（C1） |
| 6. QueryClient 生命周期跟随 user id，不跟随 token rotation | 是 | `src/IM/frontend/src/app/providers.tsx:18` |
| 7. 绑定是一次 session + server-state 收敛 | 部分 | 编排顺序正确，但默认 QueryClient 吞掉 refetch error（W1） |
| 8. 只保留无版本后缀 canonical Chat | 是 | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:1`；`features/chat/v2/` 已不存在 |
| 9. replace, don't layer | 是 | legacy stream/client/mock/types/组件已删除，生产消费者全部 import shared runtime |

### Prototype / Reference Contract

N/A。design 没有 prototype/reference must-match 行。

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — Chat 的 recovery callback 只刷新会话列表，丢失的当前消息和非持久状态无法收敛。** `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:631-633` 只 invalidate `['chat','conversations']`；但 `resync_required` 会在 `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:106-120` 把 cursor 前移到 sync 的 `max_event_id`，窗口内漏掉的 message/status 帧随后不会 replay。结果是当前会话可能一直缺消息，Chat 的 `['chat','agents']` / `['chat','nodes']` 也会停留在断线前状态，违背 motivation 的恢复场景、delta-spec 的“断线期间新消息恢复后可见 / 状态回到当前值”，也违背 design Domain ownership 明定的 Chat recovery 行为。修复：在 Chat `onRecovery` 中 settled 地刷新 active `['chat','messages', conversationId]`、`['chat','conversations']`、`['chat','agents']`、`['chat','nodes']`；补 integration test 实际调用 captured recovery callback，分别让 REST 返回新消息和新状态并断言页面收敛，而不是只断言 callback 非空（现有 `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx:776-783`）。

### WARNING（应该修）

- **W1 — 绑定页无法识别真实 cache refetch 失败，会错误导航到可能仍是旧 owner 数据的 Chat。** `src/IM/frontend/src/features/chat/bind-confirm-page.tsx:53-63` 依赖 `Promise.allSettled` 出现 rejected；TanStack Query 默认 `throwOnError=false`，query fetch error 会被 `refetchQueries` catch 后让 `invalidateQueries` resolve。因此当前 failure 分支在真实 QueryClient 下不可达；`src/IM/frontend/src/features/chat/bind-confirm-page.test.tsx:99-101` 直接 mock promise rejection，掩盖了真实语义。修复：调用 `queryClient.invalidateQueries({ queryKey, refetchType: 'all' }, { throwOnError: true })`（或等价使用会传播 fetch error 的 API），并把集成测试改为给六组真实 query cache 注册会失败/后成功的 queryFn，证明首次不导航、retry 不二次 confirm、全部成功后才导航。
- **W2 — `authFetch` 收到 401 时若 access JWT 仍在 freshness 窗口内，会拿同一个已被服务端拒绝的 token再请求一次，而不会 refresh。** `src/IM/frontend/src/features/auth/auth-fetch.ts:31-35` 调用的 `ensureFreshSession()` 会在 `src/IM/frontend/src/features/auth/auth-session.ts:75-80` 对 fresh JWT 直接返回 ready。它不满足 design 中“HTTP 401 与 WS freshness 共用同一个 refresh coordinator”的完整语义，也让被撤销/服务端失配但 `exp` 尚新的 token 无法自愈。修复：在 auth session module 增加复用同一个 module-level promise 的 force-refresh 内部入口供 HTTP 401 使用，保留 WS connect 的 freshness 判断；补一个结构合法、`exp` 在未来但首个 API 请求返回 401 的回归，断言 refresh 一次并用新 token replay。

### SUGGESTION（可以修）

- **S1 — ownership contract 把“唯一 `/im/ws/user` owner”扩大成禁止 runtime 外任何 `new WebSocket`。** `tests/contract/test_im_frontend_user_stream_ownership.py:23-34` 会阻止未来与 user-stream 无关的合法 WebSocket seam，超出本 unit 契约。建议把断言收窄为禁止 runtime 外构造 `/im/ws/user`（或匹配 URL builder/import owner），同时继续断言 runtime 内该 endpoint 只有一个生产 owner。

# Round 2

## Verification Report: refactor-460

### Summary

Mode: `full`

Delta range: `e241071366b5f7d4a8dd4f0527dc7ef7443a7658..29ae09c90a468a55a50a12e341c3d79570c93efc`（派发包中的 base SHA `e241071352...` 不存在，按实际同名短 SHA `e2410713` 还原）

Focus issues: Round 1 C1/W1/W2/S1；Round 1 acceptance 的 direct Web `NO_REPLY` 与在线非当前 Agent toast/unread；code review 的 storage、bind token、重复 query、dead API、shared JSON seam

requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 22/22；Requirement groups 8/8 |
| Correctness | Scenarios 22/22 covered |
| Coherence | 9/9 design decisions followed |

上一轮全部阻断项和警告均已关闭。本轮没有 CRITICAL 或 WARNING；1 项不阻断的简化建议见末尾。

### Focus issue closure

| Issue | 结论 | 代码与回归证据 |
|---|---|---|
| C1 Chat recovery 只刷新 conversations | closed | `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:629-642` 同次 settled 刷新 conversations、agents、nodes 和 active messages；`chat-workspace.integration.test.tsx:776-843` 实际触发 recovery 后断言四类 UI/缓存收敛 |
| W1 bind refetch 失败仍导航 | closed | `src/IM/frontend/src/features/chat/bind-confirm-page.tsx:53-67` 对六组真实 refetch 使用 `throwOnError:true`，失败保持原页；`bind-confirm-page.test.tsx:158-186` 使用真实 QueryClient 证明失败、重试和一次 confirm |
| W2 fresh-but-rejected 401 重放旧 token | closed | `src/IM/frontend/src/features/auth/auth-fetch.ts:24-35` 的 401 路径强制 refresh；`auth-session.ts:45-68,85-97` 仍复用同一 single-flight；`auth-fetch.test.ts:86-113` 覆盖本地 fresh、服务端拒绝后的 refresh + replay |
| S1 ownership guard 过宽 | closed | `tests/contract/test_im_frontend_user_stream_ownership.py:23-33` 只禁止 runtime 外拥有 `/im/ws/user`，不再禁止无关 WebSocket |
| storage 不可用击穿 runtime | closed | `src/IM/frontend/src/realtime/user-stream/user-stream-runtime.ts:48-50,92-115` 提供 per-user 内存 cursor fallback，读写异常只上报；`user-stream.test.ts:207-238` 覆盖 resume、事件、ping、重连和 in-tab continuity |
| bind token 跨参数错误复用 | closed | `bind-confirm-page.tsx:39-44` 按 token 缓存已消费结果；`bind-confirm-page.test.tsx:188-218` 证明 token A reconciliation 失败后 token B 会重新 confirm |
| duplicate Agent query / dead mention API | closed | `agent-detail-page.tsx:1328-1451` 详情页只消费 detail-state 与 canonical rail query；`chat-api.ts:13-172` 已无未调用 mention client；architecture regression 在 `canonical-chat-architecture.test.ts:37-64` |
| shared JSON transport/error seam | closed | `src/IM/frontend/src/features/auth/auth-fetch.ts:38-53` 统一 JSON 解析与错误格式；`chat-api.ts:13-131` 复用该 seam；`chat-api.test.ts:224-232` 保留用户可见 operation label/body |
| direct Web `NO_REPLY` 与在线非当前 Agent 提醒 | closed | `src/personal_assistant/gateway/runtime_delivery/context.py:411-424` 在 Web relay 源头使用既有静默 policy；`src/IM/infra/repositories.py:1471-1558` 持久化并 exactly-once 发布 tombstone；`src/IM/ws/user_stream.py:23-45` 保留 nullable-FK tombstone 的 provisional id。`use-global-message-toast.ts:229-274` 关联 canonical created/completed、弹 toast 并刷新权威 conversations；M3 真栈证据同时证明 live 撤泡、reload 无残留、toast、preview、排序和 unread |

### Completeness

- M1 6/6、M2 7/7、M3 9/9，共 22/22 个退出标准均已勾选；三份 `progress.md` 对应 Roadpoint 均为 DONE。
- `motivation.md` 的 6 个用户 requirement group 与两份 IM delta-spec 的 2 个 requirement group 均有生产实现和长期回归，不依赖一次性验收脚本冒充覆盖。
- design 没有前端 prototype / reference must-match contract；本 unit 明确保持既有 UI。桌面、移动、绑定、实时消息以及 M3 两条失败旅程的可复查 evidence 均保存在 unit 目录。
- M3 扩到 Gateway/IM 的代码是补齐既有 `message_discarded` / tombstone 语义，不引入新协议或平行机制；与 canonical `docs/specs/im/gateway-relay.md:76-87` 的普通聊天 provisional rollback 契约一致。

### Correctness

| Requirement | Scenario 覆盖 | 实现与测试证据 | 状态 |
|---|---:|---|---|
| 当前会话实时呈现完整消息过程 | 3/3 | shared stream + `chat-stream-reducer.ts` + Chat integration；direct Web silence 的 Gateway→IM→browser/reload 回归与 M3 真栈证据 | covered |
| 会话列表、未读和应用内提醒一致 | 2/2 | `use-global-message-toast.ts:178-282`、Chat conversations refresh；toast tests 与在线双会话真栈 | covered |
| 桌面系统通知一次且可导航 | 3/3 | `agent-completion-notifier.tsx:88-180` 的 visibility/preference/permission/dedupe/navigation；notifier 回归与恢复 cursor 回归 | covered |
| Node/Agent 状态实时变化 | 1/1 | Chat、Nodes、Agents 三类 subscriber + recovery refetch；各 consumer regression 和 Gateway lifecycle 真栈证据 | covered |
| 长登录与账号切换 | 2/2 | auth single-flight、token/user generation、per-user cursor、QueryClient user boundary；auth/runtime/App regression 与真栈 expired-token/account-switch | covered |
| 绑定与 Agent 详情非实时入口 | 2/2 | bind 一次性编排 + canonical `createConversation`；真实 QueryClient regression、Agent detail tests 与真栈 | covered |
| JWT 用户流、resume/sync 与租户隔离 delta | 5/5 | `realtime/user-stream/`、IM user-stream backend；runtime tests、backend/contract tests及既有 HTTP/WS integration | covered |
| recovery 一致且不重复提醒 delta | 4/4 | transport cursor + per-domain recovery + user-keyed caches；Chat recovery integration、notifier/toast/runtime/App regressions | covered |

### Coherence

| design 决策 | 结论 | 代码证据 |
|---|---|---|
| 1. user-stream seam 位于领域页面外 | followed | `src/IM/frontend/src/realtime/user-stream/index.ts:1-52` |
| 2. auth 拥有 freshness，HTTP/WS 共享 single-flight | followed | `auth-session.ts:16,45-68,75-97`；`auth-fetch.ts:24-35` |
| 3. 每标签页单连接、多 subscriber | followed | `user-stream-runtime.ts:48-60,275-293` |
| 4. cursor 在 transport 推进，subscriber 故障隔离 | followed | `user-stream-runtime.ts:92-115,161-189` |
| 5. reconnect/resync 统一 recovery，各领域读权威状态 | followed | `user-stream-runtime.ts:118-148,239-253`；Chat/Nodes/Agents/toast recovery callbacks |
| 6. QueryClient 跟随 user id，不跟 token rotation | followed | `src/IM/frontend/src/app/providers.tsx:18-25` |
| 7. bind 是一次 session + server-state 收敛 | followed | `bind-confirm-page.tsx:39-68` |
| 8. 只保留无版本后缀 canonical Chat | followed | `tests/contract/test_im_frontend_user_stream_ownership.py:48-67`；`canonical-chat-architecture.test.ts:37-64` |
| 9. replace, don't layer | followed | legacy Chat/stream/API 表面已删除；production `/im/ws/user` lifecycle owner 仅 `realtime/user-stream` |

跨包依赖方向未变化：IM 不 import agent；Gateway 仍只通过既有 IM/Gateway 与 `agent.sdk` 边界工作；本轮没有跨机文件假设或第二套 realtime/delivery 机制。

### Independent validation

- Focused frontend: 8 files, 108 tests passed。
- Focused backend/Gateway/contracts: 64 tests passed。
- Full frontend: 62 files, 581 tests passed；production build passed。
- `ruff check src tests`: passed。
- `pytest -q -m "not e2e"`: 3505 passed, 1 skipped, 23 deselected。
- M3 persisted real-stack evidence reviewed: direct Web `NO_REPLY` live tombstone + reload；非当前 Agent toast/preview/order/unread；Agent detail Open chat。

### SUGGESTION（不阻断）

- **S2 — 简化 Chat recovery 中实际上不会命中的 rejection 扫描。** `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:637-641` 使用默认 `throwOnError:false` 的 `invalidateQueries`，query fetch error 会落进 Query 状态而不会令 Promise reject，因此后续 `results.find(rejected)` 在常规 fetch failure 下没有作用。当前实现已满足“四类 query 同次 settled 尝试”的 requirement，不影响本轮 verdict；后续可删除该 failure scan，或若确实需要把 refetch failure 上报给 runtime，则像 bind 一样显式传 `{ throwOnError: true }` 并补相应回归。

All checks passed. Ready for PR.
