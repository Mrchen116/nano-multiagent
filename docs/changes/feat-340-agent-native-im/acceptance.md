# feat-340 — 验收报告

> 对齐: docs/changes/feat-340-agent-native-im/spec.md / design.md

# Round 1 — 2026-05-11

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 4
- major: 3
- minor: 2

## Top Concern

Chat 页核心数据通路全部 401 + 视觉骨架完全没渲染:`im-chat-api.requestJson` 没接入 `authFetch`,所有 `/im/v1/agents` `/im/v1/nodes` `/im/v1/conversations` `/im/v1/messages` `/im/v1/uploads` 调用裸 `fetch()` 不带 Bearer;同时 chat-* 类名(82 处)在 global.css 里没有任何样式定义,Chat workspace 整页渲染为无样式纯文本流。WS `/im/ws/user` 用的 query param 也对不上(前端 `access_token=`,后端 `token=`),所有实时事件被 1008 拒。

## 用户旅程体验

平台:Chrome 控制 / curl / 真实启动 IM service (`uvicorn IM.app:app --port 8011`) + 新建 alex / bob 两个用户 + 真实登录拿 token + 走前端 SPA + 真后端。

### 旅程清单

| # | 旅程 | 目标 | 结果 |
|---|---|---|---|
| J1 | 注册/登录 (Login page) | spec 多用户 + i18n 入口 | ✅ pass (登录页样式 OK,login API 返回 token 含 user) |
| J2 | 登录后落 Chat workspace | spec 场景 A:看到 262px 侧栏 + 4 类会话渲染 | ❌ blocking — Chat 内容区无样式,所有 chat-* class 无 CSS,内容如同 raw <div> 流 |
| J3 | 浏览 Agents 列表 + 详情 + 新建 | spec 场景 A:四组卡片 + dirty Save + Open chat ↗ | ⚠️ partial — Settings 壳和 Agents 空态正常,但因 J5 阻塞无法创建任何 agent 真测详情/dirty |
| J4 | Nodes 列表 + status pill + relay toggle | spec 场景 C | ⚠️ partial — 列表空态正常;无创建节点入口(本来就只能从 PA Gateway 注册),无法验真实 status pill |
| J5 | 跨页/Chat 调 `/im/v1/agents` `/im/v1/nodes` 等 | 鉴权后看到自己数据 | ❌ blocking — Chat 页的 GET 全部 401:`im-chat-api.ts:612 requestJson` 没穿 Authorization,而 Agents/Account 走 `authFetch` 才正常 |
| J6 | WS 实时事件订阅 (`/im/ws/user`) | spec 场景 A/B:流式渲染、状态实时反映 | ❌ blocking — `/im/ws/user?access_token=…` 被后端拒(后端 read `?token=…`),console error `WebSocket handshake: Unexpected response code: 403`(实际 close 1008) |
| J7 | i18n EN↔中切换 | spec i18n 验收 | ⚠️ partial — Account 页可切并存盘,刷新后保持;但顶栏 Agents、Settings 侧栏 (Agents/Nodes/Policies/Account) 全部未抽 i18n,中文模式下还是英文 |
| J8 | 多用户租户隔离 (alex vs bob via API) | spec 多用户 + 决策 §2a | ✅ pass — `Bearer` 解析正确,bob token 看不到 alex 数据;`GET /im/v1/users` 返 404(已删) |
| J9 | 桌面 `/login` `/register` `/me` 直链/刷新 | SPA shell | ❌ blocking — IM `app.py` 只挂了 `/`,`/chat`,`/settings`,`/bind/confirm`;直链 `/login` `/register` `/me` 返 FastAPI 404 raw JSON,刷新即失败 |
| J10 | 移动 (375x812) `/me` 聚合页 | spec 场景 D | ❌ 同 J9 — `/me` 直链 404;通过 `/` 进也会被路由跳走,移动壳从未真出现过 |
| J11 | 拖文件附件 → 发送 → bubble 渲染 | spec 场景 E + 附件验收 | ⚠️ 无法验证 — 因 J5 阻塞无法创建会话/agent,也没法发消息;静态代码 attachments/ 目录存在 |
| J12 | 桌面通知(后台时触发) | spec 场景 D + 通知验收 | ⚠️ 无法验证 — 同上,需要 agent 完成回复才能触发 |

### 关键截图

- `/tmp/feat340-01-login.png` — 登录页样式 OK
- `/tmp/feat340-02-after-login.png`(也 `/tmp/feat340-03-chat-1440.png`) — Chat 页 1440 宽,内容区完全无样式
- `/tmp/feat340-04-agents.png` — Agents 空态(壳样式 OK,主体被 J5 阻断)
- `/tmp/feat340-05-nodes.png` — Nodes 空态
- `/tmp/feat340-06-account.png` — Account 三组卡片(M7 视觉完成度最高)
- `/tmp/feat340-07-zh-account.png` / `feat340-08-zh-saved.png` — i18n 切到中文(部分覆盖)
- `/tmp/feat340-09-mobile-me.png` — `/me` raw 404 JSON

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| 1 | blocking | Chat workspace 整页无样式:`conversation-sidebar` / `chat-sidebar-*` / `chat-message-*` 等共 82 处 className 在 `src/IM/frontend/src/styles/global.css`(867 行)里 **0** 条匹配规则,Chat 页变成纯 block 流。spec 验收"桌面 Chat 页左 262px 会话栏 + 右消息面板"100% 不满足。 | fix-implementation | M4 实施时只写了组件 className 没写对应 CSS。design 决策 6 说"用 Tailwind v4 utility + global.css token",但 M4 引入的是自定义类名而非 utility,需要补齐 CSS 规则(或改成纯 utility) |
| 2 | blocking | 前端 `im-chat-api.ts:612 requestJson` 不带 `Authorization: Bearer`,导致 Chat workspace 所有 GET (`/im/v1/agents` `/im/v1/nodes` `/im/v1/conversations` `/im/v1/messages` `/im/v1/uploads` `/im/v1/users` `/im/v1/bind` `/im/v1/metrics/usage`) 全部 401;场景 A/B/E 全部走不通 | fix-implementation | 把 `requestJson` 改成调 `authFetch` 即可。M3/M4 漏:`features/chat/im-chat-api.ts` 是 legacy 路径,只有 `features/chat/v2/` 走了重写,但 Chat workspace 顶层 sidebar/list 仍引 legacy api |
| 3 | blocking | WS `/im/ws/user` 鉴权 query 名对不上:前端 `chat-stream.ts:21,25` 用 `access_token=`,后端 `app.py:342` 读 `token=`,握手 1008。所有 message.delta / tool_call.* / node.status_changed / agent.status_changed 实时事件用户都收不到 | fix-implementation | 单边改前端 query 名即可(后端命名"token"也合理且与 design 决策 1 描述吻合)。M1 R5 加 WS auth 时与 M2/M4/M10 的 stream 客户端没对齐 |
| 4 | blocking | 直链 `/login` `/register` `/me` 返 FastAPI 404 (raw JSON);刷新/书签/分享链接全部失败。`app.py:165-187` 只挂了 `/`、`/chat/*`、`/settings/*`、`/bind/confirm` | fix-implementation | M3 加新前端路由(/login /register /me)时忘了在 IM `app.py` 添加同名 SPA fallback。补 3 条 `@app.get` 即可,或改成通配 `/{path:path}` 兜底(注意排除 `/im/*` `/assets/*`) |
| 5 | major | i18n 覆盖不全:顶栏 "Agents"、Settings 侧栏 "Agents/Nodes/Policies/Account"、Account 页 "Open chat ↗" 等多处中文模式仍 EN。spec 验收条 "全 UI 文本支持 EN/中 两套" 不满足 | fix-implementation | M3 注入 i18next 时遗漏了 shell + settings 导航 + agent action 几处 key;扫一遍 hardcoded 字符串补 t() |
| 6 | major | `account-page.test.tsx:126:9` tsc 报错仍在:`stored: { default_entry_node_id: string }` 与 PATCH payload `string \| null` 不兼容。`npx tsc -b` 失败 — 生产构建只能跳 tsc 走 vite 单步。M4b 已记录此问题但未修。 | fix-implementation | M7 重写 account 时把 `default_entry_node_id` 改成可空,但 test fixture 的 `stored` 类型没对齐。改 fixture initial 类型为 `string \| null` |
| 7 | major | Settings 侧栏多出 "Policies" 链接,spec/design 都未提及。spec 仅列 Identity/Behavior/Access&Model/Workspace&Runtime 四组卡片(都在 Agent 详情里),Nodes/Account 是同级页,没有 Policies 这一项 | fix-implementation | 若是 stub 路由,删除链接;若属规划中的功能,先注释,等独立 unit 立项再放。当前态会误导用户 |
| 8 | minor | Chat workspace 标签:`+ Group` 按钮存在但点开 New Group 模态因 J5 401 无候选 agent,无法测;同上,@mention picker 因无 agent 也无法测 200ms picker。 | fix-implementation | 修 J5(#2)后自动解锁,验证再说,可能没有真问题 |
| 9 | minor | 远端 Google Fonts 加载 (`fonts.googleapis.com/css2?family=IBM+Plex+Sans...`):局域网 / 隔离环境下字体回退;首次 Network panel 看到 ~1023ms。spec/design 没强制本地化 | minor — Side Findings | 不立 issue;若将来要离线优先可独立 unit 处理 |

## 验收标准覆盖(对照 spec.md §验收标准)

### 视觉对齐(像素级)
- ❌ 桌面 Chat 页左 262px 侧栏 + 右消息面板 — Issue #1
- ❌ 移动 < 768px 退顶栏为底栏 + Me 聚合 — Issue #4 阻断进入
- ✅ 主色 oklch accent + 暗色顶栏 + IBM Plex Sans/Mono(顶栏 + Account/Auth 页可见)
- ⚠️ 用户/Agent 气泡圆角 — Issue #1 阻断:无法看到任何气泡

### Chat 页交互
- ❌ 分类标签 All/Agent/Group/Network 实时过滤 — Issue #1 视觉 + Issue #2 数据
- ❌ 搜索框实时过滤 — 同上
- ❌ 4 种会话类型渲染 — Issue #1+#2 双重阻断
- ❌ Tool Calls 面板 — 无法验证
- ❌ Token Usage Chip 含 70/90% 预警 — 无法验证
- ❌ @mention picker 200ms 弹 — 无法验证(无 agent)
- ❌ 新建群聊模态 + 真存盘 — Issue #2 阻断
- ❌ 会话头部 Node chip + Kind badge + ⚙ 跳 agent — 无法验证

### Agents 页
- ⚠️ 列表 / 详情 / 新建 — 壳样式 OK,但 Agents 空态强制用户先有 node 才能建 agent;无 Web 入口创建 node,空跑;无法真测 dirty/Save/Discard/Open chat ↗

### Nodes 页
- ⚠️ status pill / relay toggle / 节点视角列 agents — 同上,空态;Issue #3 还会阻塞 status 实时反映

### Account 页
- ✅ 三组卡片 + dirty/Save/Discard 视觉 + 字段表单 — 验证 display_name / locale toggle 真存盘
- ⚠️ default_entry_node_id 因无 node 选项空

### 实时与状态
- ❌ Agent 消息文本 + tool_call 实时增量 — Issue #3 WS 失败
- ❌ running 状态 pulse/spin — 无法验证
- ❌ 节点/agent online/offline heartbeat 驱动 — Issue #3
- ✅ 空态文案(Chat / Agents / Nodes / Account)有
- ⚠️ 错误反馈(toast/inline)— Chat 区因 401 反复刷新 fail 没看到 user-facing toast

### i18n
- ❌ 全 UI EN/中 — Issue #5(部分覆盖)

### 附件
- ⚠️ 桌面拖入 + chip + 真发送 — Issue #2 阻断验证

### 通知
- ⚠️ 后台 Notification API — Issue #2 阻断验证

### 多用户
- ✅ 注册/登录/登出走通(alex + bob),`/im/v1/auth/me` 返正确身份
- ✅ 跨租户隔离(API 层):bob token 看不到 alex 的 agents/conversations
- ⚠️ `?user_id=` query 残留?后端 WS `/im/ws/user` 的 fallback 还保留 `?user_id=`(`app.py:350`),design 决策 1 说"移除 `?user_id=` query 强绑",但 M1 R5 注释里写"kept temporarily so M2 worker tests don't break; it will be removed in a follow-up before the unit lands"。**该 follow-up 还没做**,记录为 in-unit fix
- ✅ `GET /im/v1/users` 已删(返 404)
- ✅ 群聊参与者 / @ 候选仅本 user 自有 agents — 代码层 mention picker 数据源是当前会话 participants,符合 design 决策 9(但因 #2 没真测)

### 全栈接通
- ❌ 因 #1 #2 #3 三连击,"前端不通过 mock"目标在 Chat 域基本失守

## 上层文档同步

- [x] `SPEC.md`(架构总览):**无需更新** — 本 unit 不改顶层包边界,仅扩 IM 内部
- [x] `docs/内核设计SPEC.md`(agent 内核):**无需更新** — kernel/coding_cli 未改
- [x] `AGENTS.md` / `CLAUDE.md`:**需要更新** — `data/im.db` 文件名已改为 `data/im_service.sqlite3`(默认值;`IM_DB_PATH` 环境变量也未在 runbook 提);新增 `IM_JWT_SECRET`、`init_admin` 流程未在 README/AGENTS 里写。bootstrap 步骤需补
- [x] 相关产品 SPEC(`docs/CodingCLI-SPEC.md` / `docs/NodeGateway-SPEC.md` / `docs/IM-SPEC.md`):**需要更新** `docs/IM-SPEC.md` — 加 auth 端点表、新 WS 事件 schema、`?token=` query 鉴权、租户隔离 OwnerScopedRepository 概念;其他无需更新

文档同步项不在本验收范围内立 issue,在 unit→main PR body 里列 TODO 即可。

## 上一轮处置 (M4b → 本轮)

M4b 报告过 "M7 留下 pre-existing tsc 错误 `account-page.test.tsx:126:9`" — **本轮验证仍在**,在本 unit 引入,归类为 in-unit fix-implementation (Issue #6)。

## Side Findings

(minor out-of-unit / 不立 issue)

- Side-F1 (out-of-unit, minor):仓库 `tests/im_service/integration/test_m103_im_gateway_e2e.py` + `test_m136_group_chat_flow.py` 共 8 个用例失败,根因 `_FakeKernelClient` 缺 `submit_message` 属性。在 main 分支也 fail (baseline),与 feat-340 无关。不立 issue,记录于此供 orchestrator 在 PR body 提示。
- Side-F2 (Side note,minor):前端代码 `imageUrls` 推断有 dynamic-import 警告(`vite build` 输出):`auth-store.ts` 在 `chat/im-chat-api.ts` 是 dynamic import 同时在 ~12 处 static import,Vite 提示"dynamic import will not move module into another chunk"。功能无影响,优化项,可后续。

## Recommended Action 路由建议

| Issue | Action | 给谁 |
|---|---|---|
| #1 chat-* CSS 缺失 | fix-implementation | M4 worker(主)+ 可能 M5/M6 spot-check |
| #2 im-chat-api 不带 Authorization | fix-implementation | M4 worker |
| #3 WS token query 名错配 | fix-implementation | M4 或 M3 worker(改 chat-stream.ts) |
| #4 SPA `/login` `/register` `/me` 404 | fix-implementation | M3 worker(IM `app.py` 加路由) |
| #5 i18n 顶栏 + Settings 侧栏未抽 | fix-implementation | M3 worker |
| #6 account-page.test.tsx tsc 错 | fix-implementation | M7 worker |
| #7 Settings 多出 Policies 链接 | fix-implementation | M5 worker(或 M3,看 nav 在哪里写) |

建议 orchestrator 派一个 **fix milestone**(可叫 `feat-340-fix1`),把 #1~#7 一起做完。这些都是发现性的连锁阻断,worker 修通后**必须**重新跑完整轮 J2~J12 验证。

## 第一轮验收禁用 revise-design 闸的说明

本轮所有 issue 都明显是**实现遗漏**(missing CSS、漏接 authFetch、WS query 名笔误、SPA 路由没补、i18n 漏抽),没有任何"design 写错了"的证据。design.md 决策 1/3/6 与现状完全一致,只是 worker 实现时漏抽/对错。
