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

---

# Round 2 — 2026-05-11

## Verdict

**pass-with-issues**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 0
- major: 1
- minor: 1

## Top Concern

顶栏 "Agents" tab 在中文模式下仍为英文:`zh.json` line 34 `shell.tabs.agents` 值仍是 "Agents" 而非 "智能体"。M11 R5 只修了 Settings 侧栏 nav 的 i18n,漏了顶栏同名 key。

## R1 Issues 验证状态

| R1 # | 原描述 | M11 修复状态 | R2 验证结果 |
|---|---|---|---|
| #1 | Chat workspace 整页无样式 | R1 补 CSS | ✅ 通过 — 桌面 1440px 侧栏 + 消息面板完整渲染 |
| #2 | im-chat-api.ts 不带 Authorization | R2 接入 authFetch | ✅ 通过 — /im/v1/agents /nodes /conversations 全部 200 |
| #3 | WS access_token= vs token= 错配 | R3 改前端 query 名 | ✅ 通过 — server logs 显示 ?token= [accepted],?access_token= 403 |
| #4 | /login /register /me 直链 404 | R4 补 SPA routes | ✅ 通过 — 三条路由全部 HTTP 200 返回 SPA shell HTML |
| #5 | i18n 顶栏 + Settings 侧栏未抽 | R5 修 Settings 侧栏 | ⚠️ 部分修复 — Settings 侧栏"智能体/节点/账户"✅;顶栏"Agents"仍 EN ❌ |
| #6 | account-page.test.tsx tsc 错误 | R6 修 fixture 类型 | ✅ 通过 — `npx tsc -b` 0 errors |
| #7 | Settings 侧栏多出 Policies 链接 | R7 删除 Policies | ✅ 通过 — 侧栏仅剩 Agents/Nodes/Account |
| #8 | Chat group/@ mention 无法测 | 依赖 #2 解锁 | ⚠️ 无法深测 — 无 agent 可用(需 Gateway 注册节点),但 + Group 按钮渲染正常 |

## 旅程体验

平台:Chrome headless + 真实 IM 服务 port 8012 (fresh DB) + `alex` 用户注册/登录 + 真实前端 dist。

### 旅程清单

| # | 旅程 | 结果 |
|---|---|---|
| J1 | /login /register /me 直链 | ✅ 全部 200 SPA shell;无 raw JSON |
| J2 | 登录后 Chat workspace @1440px | ✅ 262px 侧栏 + 右侧空态"Select a conversation";正确 CSS |
| J5 | API 鉴权:/im/v1/agents /nodes /conversations | ✅ 登录后全部 200,无 401 |
| J6 | WS /im/ws/user?token= 握手 | ✅ server log [accepted];?access_token= 被拒 403 |
| J9 | Settings 侧栏无 Policies | ✅ 仅 Agents/Nodes/Account |
| i18n | 中文模式全界面 | ⚠️ Settings 侧栏 ✅;顶栏 Agents tab 仍 EN |

### 关键截图

- `/tmp/feat340-r2-02-chat.png` — Chat 页登录后(首次加载,注意浏览器 session 残留导致旧 console error,后清除)
- `/tmp/feat340-r2-04-chat-fresh.png` — 1280px Chat 工作区样式正常
- `/tmp/feat340-r2-05-settings.png` — Settings 侧栏无 Policies
- `/tmp/feat340-r2-07-zh.png` — 中文模式 Account 页全部翻译正确;顶栏"Agents"仍 EN
- `/tmp/feat340-r2-08-chat-zh.png` — 中文模式 Chat 页,侧栏翻译正确;顶栏"Agents" EN 漏翻
- `/tmp/feat340-r2-09-me.png` — /me 直链正常渲染(SPA fallback 生效)
- `/tmp/feat340-r2-11-chat-1440.png` — 1440px Chat 完整布局

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| R2-1 | major | 中文模式顶栏 "Agents" tab 未翻译。`src/IM/frontend/src/i18n/zh.json` line 34:`"agents": "Agents"` — M11 R5 只改了 Settings 侧栏的 `settings.nav.agents`,但 `shell.tabs.agents` 的中文值仍为 "Agents"。截图 `/tmp/feat340-r2-07-zh.png` / `feat340-r2-08-chat-zh.png` 可见。 | fix-implementation | 单行修改:zh.json `shell.tabs.agents` 改为 "智能体"。已证明 R5 修了 settings.nav 路径,只是漏了 shell.tabs 同名 key |
| R2-2 | minor | `?user_id=` legacy WS fallback 仍在 `app.py:351-365`。R1 记录 "kept temporarily so M2 worker tests don't break; it will be removed in a follow-up before the unit lands"。unit 即将合 main,此遗留清理尚未完成。 | fix-implementation | M1 注释明确说"unit lands 前删除",当前临到 merge 还未执行。删除 app.py WS fallback 里的 user_id 分支即可 |

## 验收标准覆盖(对照 spec.md §验收标准,仅列变化项)

### 视觉对齐
- ✅ 桌面 Chat 页左 262px 侧栏 + 右消息面板 (R1 #1 已修)

### Chat 页交互
- ✅ 分类标签 All/Agent/Group/Network 渲染 (R1 #1+#2 已修,空态可见)
- ✅ 搜索框渲染 (样式正常)

### 实时与状态
- ✅ WS /im/ws/user 连接 [accepted] (R1 #3 已修)

### SPA 路由
- ✅ /login /register /me 直链 200 SPA shell (R1 #4 已修)

### i18n
- ⚠️ 全 UI EN/中 — Settings 侧栏 ✅;顶栏 Agents tab ❌ (R2-1)

### TypeScript
- ✅ npx tsc -b 0 errors (R1 #6 已修)

### Settings
- ✅ 侧栏无 Policies (R1 #7 已修)

## 上层文档同步

(延续 R1 结论,无新变化)

- [x] `SPEC.md`:无需更新
- [x] `docs/内核设计SPEC.md`:无需更新
- [x] `AGENTS.md` / `CLAUDE.md`:需更新(R1 已标记,待 PR 阶段处理)
- [x] `docs/IM-SPEC.md`:需更新(R1 已标记,待 PR 阶段处理)

## Side Findings

- Side-F3 (minor):浏览器 console 可见两条 `/im/v1/users` → 404 错误,该端点已在 M1 删除但前端仍周期性请求(见 `im-chat-api.ts`)。不影响主路径功能,属技术债,可后续清理。
- Side-F1 沿用:8 个 IM integration tests 仍 fail(baseline,与 feat-340 无关)。

## Recommended Action 路由建议

| Issue | Action | 给谁 |
|---|---|---|
| R2-1 顶栏 Agents 未翻 | fix-implementation | M3 或 M11 follow-up worker |
| R2-2 user_id fallback 清理 | fix-implementation | M1 或 M11 follow-up worker |

建议 orchestrator 派一个小 fix milestone,把 R2-1 + R2-2 一起做完,然后 R3 验收可快速通过。

---

# Round 3 — 2026-05-11

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 0
- major: 1
- minor: 0

## Top Concern

新建群聊会话创建成功（POST 201）但侧栏永远不显示该会话：`create_conversation` 路由（`web_im.py:136`）`del user` 丢弃了认证用户身份，会话 `owner_id` 从参与者 owner_id 集合计算——当用户（`owner_id=176effb9...`）和无主 agent（`owner_id=''`）参与同一会话时，`len(owner_ids) > 1` 触发随机 UUID，导致 `list_conversations_for_owner(owner_id=user.owner_id)` 永远查不到该会话。

## R2 Issues 验证状态

| R2 # | 原描述 | M12 修复状态 | R3 验证结果 |
|---|---|---|---|
| R2-1 | 中文模式顶栏 "Agents" tab 未翻译 | R1: zh.json shell.tabs.agents → "智能体" | ✅ 通过 — 顶栏显示"聊天"/"智能体"，截图 `/tmp/feat340-r3-05-zh-topbar.png` |
| R2-2 | `?user_id=` legacy WS fallback 仍在 app.py | R2: 删除 else 分支 + 更新 4 个测试 | ✅ 通过 — `?user_id=` 连接被 403 拒绝（python3 asyncio/websockets 直连验证）；`?token=<jwt>` 连接正常 accepted |

## 旅程体验

平台：Chrome headless (gstack-browse) + 真实 IM 服务 port 8013 (fresh user alexr3) + 真实前端 dist（tsc + vite build 干净）。

### 旅程清单

| # | 旅程 | 结果 |
|---|---|---|
| J1 | /login /register /me 直链 + 登录流 | ✅ 全部 200 SPA shell；登录 → 跳转 /chat；截图 `/tmp/feat340-r3-01-login.png` |
| J2 | 登录后 Chat workspace @1440px | ✅ 侧栏 + 消息面板完整渲染，中英文均可；截图 `/tmp/feat340-r3-11-chat-1440.png` |
| J5 (新建群聊) | "+ 群聊" 模态 → 选 agent → 创建 | ❌ major — 见 R3-1：POST 201 成功但会话不显示在侧栏 |
| J9 (Notifications) | 账户页启用桌面通知 checkbox | ✅ checkbox 可勾选，保存后生效；截图 `/tmp/feat340-r3-10-notifications.png` |
| J11 (跨租户) | Bob 用自己 token 访问 Alex 资源 | ✅ 404（正确拒绝）；ownerless 节点两者均可见（设计决策 2a：pre-bind 发现） |
| i18n R2-1 | 中文模式顶栏 Agents tab | ✅ 显示"智能体"；截图 `/tmp/feat340-r3-05-zh-topbar.png` |
| WS R2-2 | ?user_id= 被拒 / ?token= 被接受 | ✅ python asyncio 直连验证 |

### 关键截图

- `/tmp/feat340-r3-01-login.png` — 登录页
- `/tmp/feat340-r3-02-after-login.png` — 登录后 Chat 页
- `/tmp/feat340-r3-05-zh-topbar.png` — 中文模式顶栏"智能体"（R2-1 修复确认）
- `/tmp/feat340-r3-07-new-group-modal.png` — 新建群聊模态（UI 渲染正常）
- `/tmp/feat340-r3-08-group-created.png` — 创建后侧栏仍"暂无会话"（R3-1 现象）
- `/tmp/feat340-r3-10-notifications.png` — 通知 checkbox 启用态
- `/tmp/feat340-r3-11-chat-1440.png` — 1440px Chat 完整布局

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| R3-1 | major | 新建群聊 POST /im/v1/conversations 返回 201（会话已写库），但侧栏和 GET /im/v1/conversations 均不显示该会话。根因：`web_im.py:136` `del user`，`create_conversation` 路由不将认证用户的 `owner_id` 传给 repository；`repositories.py:377` 当参与者来自不同 owner_id（用户 `176effb9…` 与无主 agent `''`）时生成随机 UUID 作为 conversation `owner_id`，导致 `list_conversations_for_owner(owner_id=user.owner_id)` 永远查不到该会话。DB 直查确认 `owner_id='c68e4cb9…'` 既不属于 alex 也无对应用户。 | fix-implementation | M1 R4 commit（4c0ca50b）引入 `del user` 模式，设计 §决策 2a 要求"所有 /im/v1/* 路由从 token 提取 owner_id"。修复方向：在 `create_conversation` 路由中传入 `caller_owner_id=user.owner_id`，repository 层用调用者 owner_id 覆盖/指定 conversation 归属，保证同一 owner_id 下参与者无论是否有主都不触发随机 UUID。 |

## 验收标准覆盖（对照 spec.md §验收标准）

### R2 Issues（已修复项）
- ✅ i18n 全 UI EN/中 — R2-1 已修（顶栏"智能体"）
- ✅ WS ?user_id= legacy fallback 删除 — R2-2 已修
- ✅ vitest 52f/238t 全绿（含新增 2 个 i18n 断言）
- ✅ pytest 207 passed（8 pre-existing failures 不变）
- ✅ tsc -b 0 errors
- ✅ vite build 干净

### 本轮新发现
- ❌ 新建群聊会话不可见 — R3-1 (major)
- ✅ SPA 直链 /login /register /me 全部 200
- ✅ Chat workspace 1440px 完整渲染
- ✅ WS ?token= 握手正常
- ✅ 跨租户隔离 (404 正确拒绝)
- ✅ Notifications checkbox UI 正常

## 上层文档同步

（延续 R1/R2 结论，无新变化）

- [x] `SPEC.md`：无需更新
- [x] `docs/内核设计SPEC.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：需更新（R1 已标记）
- [x] `docs/IM-SPEC.md`：需更新（R1 已标记）

## Side Findings

- Side-F4 (minor, in-unit)：`/im/v1/conversations` GET 返回 `{"items": []}` 而不是 `[]`，包装层 `ListConversationsResponse` 格式与前端期望可能有细微差异（前端网络日志显示 200 + 614B 但侧栏空）——但这是 R3-1 的次级现象，修 R3-1 后需要复验。
- Side-F3 沿用：`/im/v1/users` 404 周期性请求仍在（pre-existing）。
- Side-F1 沿用：8 个 IM integration tests pre-existing failure。

## Recommended Action 路由建议

| Issue | Action | 给谁 |
|---|---|---|
| R3-1 新建群聊 owner_id 错误 | fix-implementation | M1 或 web_im/conversations worker |

建议 orchestrator 派一个小 fix milestone 修 R3-1（`create_conversation` 传入 caller owner_id），完成后 R4 验收只需重测 J5 New Group Chat 流程。

---

# Round 4 — 2026-05-11

## Verdict

**pass**

## Highest Required Action

**pass**

## Issues Count

- blocking: 0
- major: 0
- minor: 0

## Top Concern

无。R3-1（群聊 owner_id 错误）已由 M13 正确修复，3 个新增测试全部通过，真实产品走查确认会话立即可见于侧栏，跨租户隔离不退化。

## R3 Issues 验证状态

| R3 # | 原描述 | M13 修复状态 | R4 验证结果 |
|---|---|---|---|
| R3-1 | 新建群聊 POST 201 但侧栏不显示 | C2: `create_conversation` 路由传 `caller_owner_id=user.owner_id`；repository 层在 caller 提供时直接采用其 owner_id | ✅ 通过 — API 验证 + 浏览器截图双重确认：含无主 agent 的群聊会话创建后立即出现在侧栏 |

## 旅程体验

平台：Chrome headless (gstack-browse) + 真实 IM 服务 port 8014 (fresh DB，user alexr4) + 真实前端 dist + DB 注入 ownerless bot user + HTTP API 验证 + 浏览器 UI 验证。

### 旅程清单（R4 Focus）

| # | 旅程 | 结果 |
|---|---|---|
| J5-R4 | 含无主 agent 的群聊创建后侧栏立即可见 | ✅ POST 返回 `owner_id = alex.owner_id`；GET /im/v1/conversations 返回该会话；浏览器侧栏显示 "Alex + Bot R4 Group" |
| J5-CT | 跨租户隔离（Bob 不能看到 Alex 的会话） | ✅ Bob GET /im/v1/conversations 返回 `{"items":[]}`；Alex 的 conversation_id 不在 Bob 结果中 |
| J-i18n | 中文模式顶栏"智能体"仍正确 | ✅ 浏览器 snapshot 确认：顶栏 "聊天"/"智能体"，侧栏 "智能体"/"节点"/"账户" |
| J-chat | Chat workspace 1440px 完整渲染（regression check） | ✅ 侧栏 + 消息面板完整，样式正常 |

### 测试套件

- pytest 203 passed（ignore pre-existing m103/m136 2 files）✅ — M13 声明的 3 个新测试全部通过（`test_group_with_agent_appears_in_sidebar` / `test_cross_tenant_group_isolation` / `test_create_group_conversation_owner_id_uses_caller`）
- vitest 238 passed (52 files) ✅
- tsc -b 0 errors ✅

### 关键截图

- `/tmp/feat340-r4-01-login.png` — 登录页 SPA shell 正常（/login 直链 200）
- `/tmp/feat340-r4-02-after-login.png` — Chat 页登录后，侧栏已显示 "Alex + Bot R4 Group"（R3-1 修复确认）
- `/tmp/feat340-r4-03-zh-topbar.png` — 中文模式账户页："聊天"/"智能体" 顶栏（R2-1 修复 regression 确认）
- `/tmp/feat340-r4-04-chat-zh-sidebar.png` — 中文 Chat 页：侧栏 "全部/Agent/群聊/Agent 网络"，群聊可见（双重确认）

## 问题清单

无新问题。

## 验收标准覆盖（R4 新增确认项）

### R3 Issues（已修复）
- ✅ 新建群聊（含无主 agent 参与者）会话创建后立即出现在侧栏 — R3-1 已修（M13 caller_owner_id 穿透）
- ✅ 跨租户隔离不退化 — Bob 不能看到 Alex 的会话

### 延续 R1/R2/R3 已通过项（抽样确认无退化）
- ✅ Chat workspace 1440px 完整渲染（CSS 正常）
- ✅ i18n 中文模式顶栏"智能体"（R2-1 修复）
- ✅ SPA /login 直链 200
- ✅ vitest 238 / pytest 203 / tsc 0 errors

## 上层文档同步

（延续 R1/R2/R3 结论，无新变化）

- [x] `SPEC.md`：无需更新
- [x] `docs/内核设计SPEC.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：需更新（R1 已标记，待 PR 阶段处理）
- [x] `docs/IM-SPEC.md`：需更新（R1 已标记，待 PR 阶段处理）

## Side Findings

- Side-F1 沿用：8 个 IM integration tests（test_m103/test_m136）pre-existing failure（baseline，与 feat-340 无关）。
- Side-F3 沿用：`/im/v1/users` 404 周期性请求（pre-existing 技术债）。
- Side-note：`type: "direct"` 与 `direct_kind: "user-agent"` 出现在本次创建的"群聊"会话中（2 个参与者时系统判定为 direct-user-agent），但这是 design 决策的正常行为，不影响功能可用性。

---

# Round 5 — 2026-05-12

## Verdict

**partial**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 2
- major: 0
- minor: 1

## Top Concern

Streaming WS 链路已接通（M14 实现正确），但 `message.created` 事件永远不触发：kernel `run_status=running` 事件在 SSE 客户端连接之前就已发出，`kernel_event_observer` 从未捕获到 `turn_start` 信号，导致 agent 占位消息从未创建，后续的 `message.delta` 和 `message.completed` 将增量内容直接追加到用户原消息（错误 message_id）。从用户视角：消息发出后没有 agent 在打字的视觉占位，streaming 事件静默写入错误消息。

## R4 Issues 验证状态

R4 轮判定为 **pass**，无遗留 issue，R5 为新范围（streaming 端到端验证）。

## 本轮范围

R5 的专项要求是对 feat-340 中 M14（streaming chain 实现）进行端到端 WS 帧验收：
- 真实 LLM 调用（kernel SSE → Gateway observer → IM gateway WS → 用户 WS）
- 捕获：`message.created`、`message.delta`（×N≥2）、`message.completed`（含 token_usage.total>0）、`relay.report`（含 token_usage）

## 环境说明

验收发现旧 IM 进程（PID 98837，启动于 2026-05-11 22:26:24）早于 M14 代码提交（2026-05-12 02:39），运行的是 M14 之前的老代码。IM 返回 `unsupported_message_type: node.streaming_delta` 错误。重启 IM 服务后链路恢复正常——**这是测试环境问题，不是代码 bug**。

## 旅程体验

平台：`/tmp/ws_r5_v2.py` WS 帧捕获脚本 + 真实 IM 服务（重启后）+ Gateway（PID 62435）+ 真实 LLM 调用（kernel SSE）。

### 实测事件捕获结果

```
[WS] message.delta    | {"delta_text": "4", "event_id": 1687, ...}
[WS] message.delta    | {"delta_text": "4", ...}     (重复 ×3)
[WS] message.completed | {"token_usage": {"output": 1, "context_used": 2428, ...}}
[WS] relay.report     | {"token_usage": {"prompt": 2428, "completion": 1, "total": 2429}}
[WS] relay.completed  | {...}
```

### Streaming Chain 验收结果

| 事件 | 要求 | 实测 | 结论 |
|---|---|---|---|
| `message.created` | ≥1 | 0 | ❌ FAIL |
| `message.delta` | ≥2 | 3 | ✅ PASS |
| `message.completed` with token_usage.total>0 | ≥1 | 1（total=2429）| ✅ PASS |
| `relay.report` with token_usage | ≥1 | 1 | ✅ PASS |
| `relay.completed` | ≥1 | 1 | ✅ PASS |

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| R5-1 | blocking | `message.created` 从不触发。根因：kernel `run_status=running` 在 SSE 客户端连接前就已发出；`kernel_event_observer` 注册在 SSE 流打开之后，因此永远捕获不到 `turn_start` 信号。`on_turn_start` 从未被调用，EventBridge 从未创建 agent 占位消息，`message.created` 事件从未推送给用户 WS。 | fix-implementation | 在 kernel 返回 session_id 后、SSE 流打开前，Gateway 应当先创建 agent 占位消息（或通过 IM REST API 预创建），再启动 SSE 监听。或者改变 `run_status=running` 的发出时机（延迟到 SSE client 就绪后）。 |
| R5-2 | blocking | `message.delta` / `message.completed` 的 message_id 指向用户原消息，而非 agent 占位消息。`run_context_store` 存储的是用户消息的 message_id；R5-1 导致 agent 占位消息从未创建，因此 EventBridge 只能用错误 message_id 追加内容，streaming 增量写入用户发出的那条消息（"What is 2+2?" 被追加 "4"），用户侧看不到正确的 agent 回复气泡。 | fix-implementation | 修复 R5-1 后，`run_context_store` 应当改为存储 agent 占位消息的 message_id（由 `on_turn_start` 创建后返回），而非用户消息 id。整条 streaming 链的 message_id 语义需统一。 |
| R5-3 | minor | WS 发现：IM 服务在停机前未有序 graceful-close gateway WS 连接，Gateway 在 IM 重启后需手动重启才能重连。目前进程管理没有自动重连逻辑。 | minor — Side Findings | 不影响生产功能，但在开发调试中容易误判为代码 bug（本次验收就因此耗费排查时间）。可后续在 Gateway WS 客户端加指数退避重连。 |

## 验收标准覆盖（对照 spec.md §验收标准）

### Streaming Chain（M14 专项）
- ✅ WS 链路整体接通：kernel SSE → Gateway observer → IM gateway WS → 用户 WS 全路径有数据流
- ✅ `message.delta` ×3（≥2）：内容正确（"4"）
- ✅ `message.completed` with token_usage（total=2429）
- ✅ `relay.report` with token_usage（prompt=2428, completion=1, total=2429）
- ✅ `relay.completed` 触发
- ❌ `message.created`：未触发（R5-1 blocking）
- ❌ agent 回复消息正确落库：因 R5-1 + R5-2，streaming 内容写入了用户消息而非 agent 消息

### 延续 R1–R4 验收项（regression check，未重跑，上轮已 pass）
- ✅ Chat workspace 渲染（R1 已验）
- ✅ i18n 中英文（R2 已验）
- ✅ 群聊 owner_id（R3/R4 已验）
- ✅ WS 鉴权 ?token=（R2 已验）
- ✅ 跨租户隔离（R4 已验）

## 上层文档同步

（延续 R1–R4 结论，无新变化）

- [x] `AGENTS.md` / `CLAUDE.md`：需更新（R1 已标记，待 PR 阶段处理）
- [x] `docs/IM-SPEC.md`：需更新（R1 已标记，待 PR 阶段处理）

## Side Findings

- Side-F5 (in-unit, blocking)：kernel `run_status=running` 时序问题是 M14 设计的根本缺陷，不是测试环境 noise。即使在生产环境，SSE 订阅延迟也会导致 `turn_start` 丢失。这需要在 M14 follow-up 中从设计层面修复（预创建占位消息 or 延迟 running 信号）。
- Side-F1 沿用：8 个 IM integration tests（test_m103/test_m136）pre-existing failure（baseline）。

## Recommended Action 路由建议

| Issue | Action | 给谁 |
|---|---|---|
| R5-1 message.created 不触发（run_status 时序） | fix-implementation | M14 follow-up worker（需改 Gateway turn_start 逻辑或 kernel SSE 时序） |
| R5-2 message_id 指向用户消息而非 agent 占位 | fix-implementation | M14 follow-up worker（与 R5-1 一起修，修完后 run_context_store 语义重定义） |

建议 orchestrator 派一个 M15 fix milestone 专项修 R5-1 + R5-2，重点是 streaming 会话的 agent 占位消息创建时序。R6 验收只需重跑 streaming chain 帧捕获，确认 `message.created` 出现且 agent 消息 id 正确。

---

# Round 6 — 2026-05-12

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 3
- major: 0
- minor: 1

## Top Concern

前端 WS 仍在用 `?user_id=` 参数连接（被 403 拒绝），导致用户面**完全收不到任何实时事件**：消息发送后气泡不出现、没有逐字 streaming、没有 Token Chip。M15 声称修复的 R5-1（message.created 缺失）和 R5-2（message_id 指向用户消息）仍然重现——WS 证据显示 `message.created` 仍缺失，`message.completed` 的 content 字段仍将用户消息与 agent 回复拼接在一起（"What is 2+2? Please answer briefly.4"）。

## R5 Issues 验证状态

| R5 # | 原描述 | M15 修复声明 | R6 独立验证结果 |
|---|---|---|---|
| R5-1 | `message.created` 从不触发 | M15 声称已修复 | ❌ 仍 fail — WS 捕获脚本 60 秒内收到 message.delta / message.completed / relay.* 但零个 `message.created` |
| R5-2 | message_id 指向用户消息而非 agent 占位 | M15 声称已修复 | ❌ 仍 fail — `message.completed` data.content = "What is 2+2? Please answer briefly.**4**"，用户消息与 agent delta 被拼接在同一个 message_id（8f5bd07a）里；刷新后截图可见用户气泡显示 "What is 2+2? Please answer briefly.4"（用户发的消息里被追加了 agent 的回复内容） |

## 旅程体验

平台：Chrome headless (gstack-browse) + 真实 IM 服务 port 8011（新启动，commit 0aac561e）+ PA Gateway（feat340-r6-node，已绑定 alexr6 用户）+ 真实 LLM 调用（kernel:8000 → moonshot）+ WS 帧捕获脚本 `/tmp/feat340-r6-ws2.py`。

### 用户旅程清单

| # | 旅程 | 结果 |
|---|---|---|
| J1 | 打开 http://127.0.0.1:8011/ → 登录 (alexr6) | ✅ 登录页正常渲染，登录跳转 /chat 成功 |
| J2 | Chat workspace 侧栏显示对话 | ✅ 侧栏显示 "Direct with Alpha" 会话 |
| J3 | 向 Alpha agent 发送消息（UI 输入框） | ⚠️ 消息 HTTP POST 201 成功但 UI 不显示——前端 WS 用 `?user_id=` 被 403 拒绝，实时事件无法到达前端 |
| J4 | **Streaming bubble 逐字渐显** | ❌ fail — 发送后 10 秒内 UI 无任何新气泡，截图 t0.3s~t9.8s 全部显示旧消息状态 |
| J5 | **Token Chip 显示 input/output 数字** | ❌ fail — 页面内未看到任何 Token Chip |
| J6 | **刷新后消息仍在** | ⚠️ partial — 刷新后看到消息，但用户气泡内容错误（被追加了 agent delta），见 R6-2 |
| J7 | agent 回复是独立气泡 | ✅ 刷新后可看到 Alpha 的独立气泡显示 "4" |

### 关键截图

- `/tmp/feat340-r6-01-home.png` — 登录页 SPA 正常
- `/tmp/feat340-r6-02-after-login.png` — 登录后 Chat workspace 正常
- `/tmp/feat340-r6-03-agents.png` — Agents 列表，Alpha 显示绿色 online 状态
- `/tmp/feat340-r6-07-conv-open.png` — "Direct with Alpha" 对话界面，输入框可用
- `/tmp/feat340-r6-s01-t0.3.png` ~ `/tmp/feat340-r6-s09-t9.8.png` — 发送消息后 0.3s~9.8s 连续截图，全部显示旧消息，UI 无实时更新
- `/tmp/feat340-r6-15-after-reload.png` — 刷新后：用户气泡显示 "What is 2+2? Please answer briefly.4"（用户消息被 agent delta 污染），Alpha 气泡显示 "4"

### WS 帧捕获（reviewer 脚本 `?token=` 正确连接）

```
[13:09:18] message.sent       ✅ event_id=1701
[13:09:18] relay.accepted     ✅ event_id=1702
[13:09:20] message.delta      ✅ delta_text="4" event_id=1703 msg_id=8f5bd07a
[13:09:20] message.completed  ✅ content="What is 2+2? Please answer briefly.4" event_id=1704 msg_id=8f5bd07a
[13:09:20] relay.processing   ✅
[13:09:20] relay.report       ✅
[13:09:20] relay.completed    ✅
[13:09:20] message.delivered  ✅
message.created               ❌ 缺失（整个捕获期间 0 次）
```

**注意**：reviewer 的 WS 捕获脚本用 `?token=<jwt>` 正确连接，所以捕获到了后端推送的事件。但前端浏览器用 `?user_id=` 连接（403），所以前端完全收不到这些事件。

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| R6-1 | blocking | 前端 WS 仍在用 `?user_id=fff75c36...` 连接，被 403 拒绝，永远无法收到实时事件。浏览器 console 日志：`WebSocket connection to 'ws://127.0.0.1:8011/im/ws/user?user_id=fff75c36...' failed: 403`，连续出现，退避间隔从 1s 增大到 128s。前端既看不到消息气泡，也收不到任何 streaming 事件。 | fix-implementation | R2-2 修复了后端 WS 对 `?user_id=` 的接受（删除了 app.py 里的 fallback），但前端某处仍在构造 `?user_id=` 连接。前端 WS 连接代码需要改用 `?token=<jwt>`，而不是 `?user_id=`。 |
| R6-2 | blocking | `message.created` 事件仍然缺失（R5-1 重现）。WS 捕获脚本整个会话期间收到 message.delta/completed/relay.* 但零个 message.created。用户面表现：发消息后没有 agent 正在打字的占位气泡。 | fix-implementation | M15 声称修复了 R5-1，但独立验证 WS 帧序列中仍无 message.created 事件。需要重新检查 M15 的实现。 |
| R6-3 | blocking | `message.completed` 的 content 字段将用户消息与 agent delta 拼接在同一个 message_id（R5-2 重现）。刷新后用户气泡显示 "What is 2+2? Please answer briefly.**4**"——用户发的消息里被追加了 alpha 回复的 "4"。Agent 气泡单独显示 "4" 正确，但用户消息被污染了。 | fix-implementation | M15 声称修复了 R5-2，但刷新后截图 `/tmp/feat340-r6-15-after-reload.png` 清晰可见用户消息气泡内容异常。 |
| R6-4 | minor | "Open chat ↗" 按钮（Agent 详情页）点击无效，返回 404 并停在 `/settings/agents/Alpha`。截图 `/tmp/feat340-r6-05-chat-window.png` 底部可见 "404 Not Found"。 | fix-implementation | Agent 详情页的 Open chat 路由逻辑需要修复，应创建或跳转到与该 agent 的 direct 对话。 |

## 验收标准覆盖（对照 spec.md 核心用户故事）

| 用户故事 | 要求 | R6 结果 |
|---|---|---|
| 用户打开 IM Web 并登录 | 看到登录页，登录后进 Chat | ✅ pass |
| 向 agent 发消息 | 消息送达，agent 回复 | ⚠️ API 层通，但 UI 不更新 |
| **Streaming bubble 逐字渐显** | 发送后 bubble 字符级递增 | ❌ fail（R6-1 WS 断，前端无实时更新）|
| **Token Chip 显示 input/output 数字** | 回复完成后气泡下方显示 token 数 | ❌ fail（前端无实时事件，Token Chip 不点亮）|
| 刷新后消息仍在 | 刷新后对话历史保留 | ⚠️ partial（消息存在，但用户消息内容被 agent delta 污染）|
| **message.created 触发** | 用户面：agent 开始打字有占位 | ❌ fail（R5-1 重现，message.created 仍缺失）|
| **message_id 正确指向 agent 消息** | 用户面：刷新后用户消息和 agent 消息各自独立 | ❌ fail（R5-2 重现，用户消息被追加 agent delta）|
| 群聊 @ 提及 picker | @ 弹出选择框 | inconclusive（未重测，无阻塞已知 pass）|

## 上层文档同步

（延续 R1–R5 结论，无新变化）

- [x] `SPEC.md`：无需更新
- [x] `docs/内核设计SPEC.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：需更新（R1 已标记，待 PR 阶段处理）
- [x] `docs/IM-SPEC.md`：需更新（R1 已标记，待 PR 阶段处理）

## Side Findings

- Side-F6 (in-unit, minor)：创建对话时若只把 agent 加为 participants 而不把 caller user 自己加入，会导致 API 发消息时 "sender_user_id is not a participant" 400 错误。UI "Open chat ↗" 按钮 404 也可能与此相关。这是 create_conversation 路由的 UX 缺陷——caller 应该自动被加入。
- Side-F7 (in-unit, minor)：Alpha 在第一次 API 发消息后（"API test message"）自动回复了 "I received your API test message successfully. The system is working correctly and ready for your requests."——这是预置的欢迎回复逻辑，与 streaming/LLM 链路无关。不影响主路径验收。
- Side-F1 沿用：8 个 IM integration tests pre-existing failure（baseline）。

## §行动账本

| 桶 | 内容 |
|---|---|
| READ | SKILL.md, design.md §Runbook for Reviewer, acceptance.md R1-R5, spec.md（验收标准对照） |
| START_SERVICE | Agent Kernel PID=82553 :8000, IM Service PID=82571 :8011, PA Gateway PID=83204（feat340-r6-node，用 /tmp/feat340-gw-config.yaml 启动） |
| BROWSE | goto /login → fill login → click sign in → goto /settings/agents → click Alpha → click Open chat → goto /chat/2d6393... → fill message → press Enter → reload（共 ~20 次 browse 操作） |
| CAPTURE | 截图 15 张（/tmp/feat340-r6-*.png, /tmp/feat340-r6-s0*.png），WS 事件捕获脚本 /tmp/feat340-r6-ws2.py（收到 events: message.sent×3, relay.accepted×3, message.delta×3, message.completed×3, relay.*×9, message.delivered×3）|
| SHELL_MUTATION | pkill uvicorn/personal_assistant.main 清旧进程，写 /tmp/feat340-gw-config.yaml，写 /tmp/feat340-r6-ws-capture.py + ws2.py，mkdir /tmp/feat340-r6-workspace/Alpha，curl 注册 alexr6 用户，curl 确认节点绑定，curl 创建对话 |
| SENDMESSAGE | 本轮 1 次（本报告写完后向 team-lead 回报） |

**源码单次例外引用**：仅读 design.md §Runbook for Reviewer（获取服务启停命令）——已在上方 READ 桶标注。

## §环境声明

| 服务 | PID | 端口 | 启动时 commit | 启动时间 |
|---|---|---|---|---|
| Agent Kernel | 82553 | :8000 | 0aac561e | 2026-05-12 13:04 |
| IM Service | 82571 | :8011 | 0aac561e | 2026-05-12 13:04 |
| PA Gateway | 83204 | — | 0aac561e | 2026-05-12 13:05 |
| LLM_PROXY | 外部，未动 | :4000 | — | — |

临时文件（遗留 /tmp/）：`feat340-gw-config.yaml`, `feat340-r6-ws-capture.py`, `feat340-r6-ws2.py`, `feat340-r6-ws-events.log`, `feat340-r6-ws2.log`, `feat340-r6-*.png`, `feat340-r6-s0*.png`, `feat340-r6-workspace/`。

IM DB 新增：用户 alexr6（id=fff75c36...），节点 feat340-r6-node（owner=alexr6），对话 de6b02f3...（Chat with Alpha，Alpha 不是 participant）和 2d6393...（Direct with Alpha，alexr6+Alpha 均为 participant）。

---

# Round 7 — 2026-05-12

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## Issues Count

- blocking: 2
- major: 1
- minor: 1

## Top Concern

前端 WS 仍然用 `?user_id=` 参数连接（被 403 拒绝），导致用户面**完全收不到任何实时事件**：消息发送后内容区保持"No messages yet"、没有 streaming bubble、没有 Token Chip。R6-1 与 R6-3 均重现——M16 声称修复但独立验证确认未生效。

## R6 Issues 验证状态

| R6 # | 原描述 | M16 修复声明 | R7 独立验证结果 |
|---|---|---|---|
| R6-1 | 前端 WS 用 `?user_id=` 被 403 | M16 声称已修复（见 M16-fix-streaming/progress.md） | ❌ 仍 fail — 浏览器 console 日志：`WebSocket connection to 'ws://127.0.0.1:8011/im/ws/user?user_id=9d6ec9d2...' failed: 403`，连续出现 |
| R6-2 | `message.created` 从不触发 | M16 声称已修复 | ⚠️ 后端已修复 — reviewer WS 脚本（用 `?token=` 正确连接）捕捉到 `message.created` 事件；但前端因 R6-1 WS 403 看不到该事件，用户面表现仍为"无 agent 占位 bubble" |
| R6-3 | `message.completed` content 拼接用户+agent 文本 | M16 声称已修复 | ❌ 仍 fail — DB 查询显示 message_id `2bba2630`（用户消息）被 `sender=Alpha` 的内容 "4" 再次写入；刷新后 UI 出现两个 Alpha 气泡（content 均为 "4"），用户消息气泡显示正确（未被文字追加），但 DB 中用户消息 id 被 agent 的 completed 事件重复写入 |
| R6-4 | "Open chat ↗" 点击 404 | M16 未声明修复 | ❌ 仍存在 — 点击 Open chat ↗ 停留在 `/settings/agents/Alpha`，底部显示 "404 Not Found" |

## 旅程体验

平台：Chrome headless (gstack-browse) + 真实 IM 服务 port 8011（新启动，commit b8dfe083）+ PA Gateway（feat340-r7-node，alexr7 用户）+ 真实 LLM（kernel:8000 → moonshot）+ WS 帧捕捉脚本 `/tmp/feat340-r7-ws-capture.py`（`?token=` 正确连接）。

### 用户旅程清单

| # | 旅程 | 结果 |
|---|---|---|
| J1 | 打开 http://127.0.0.1:8011/ → 登录 (alexr7) | ✅ 登录页正常渲染，登录跳转 /chat 成功 |
| J2 | Chat workspace 侧栏 + 标签显示 | ✅ All/Agent/Group/Network 标签正常，侧栏 262px 宽，侧栏中 "Direct with Alpha R7" 对话可见 |
| J3 | Settings Agents 侧栏（无 Policies 检查） | ✅ 侧栏仅 Agents/Nodes/Account，无 Policies（R7 已关闭） |
| J4 | Alpha 绑定到节点，绿色 online dot | ✅ Agents 列表 Alpha 显示绿色 dot |
| J5 | 向 Alpha 发消息（输入框 + Enter） | ⚠️ 消息 API POST 成功（WS 脚本捕捉到 message.sent 1709），但 UI 主内容区保持"No messages yet"——WS 403 阻断前端更新 |
| J6 | **浏览器 console 无 WS 403** (R6-1) | ❌ fail — console 日志持续：`ws://127.0.0.1:8011/im/ws/user?user_id=9d6ec9d2...` 403，退避重连 |
| J7 | **Streaming bubble 逐字渐显** | ❌ fail — 前端 WS 完全断开，无实时事件到达，发送后内容区零气泡变化 |
| J8 | **刷新后用户/agent 消息各自独立** (R6-3) | ❌ fail — 刷新后出现两个 Alpha 气泡（均为 "4"）；DB 中用户 message_id 被 agent completed 再次写入，agent 消息出现重复渲染 |
| J9 | **Token Chip** | ❌ fail — 前端无实时事件，Token Chip 不点亮 |
| J10 | message.created 后端发出（WS 脚本验证） | ✅ 后端已正确发出：脚本捕获到 message.created event_id=1712 |
| J11 | "Open chat ↗"（R6-4） | ❌ 仍 fail — 停留在 /settings/agents/Alpha，底部 "404 Not Found" |

### 关键截图

- `/tmp/feat340-r7-01-chat-home.png` — Chat 空态，UI 样式正常
- `/tmp/feat340-r7-02-agents-list.png` — Agents 列表，Alpha 绿色 online
- `/tmp/feat340-r7-03-alpha-detail.png` — Alpha 详情页
- `/tmp/feat340-r7-04-after-openchat.png` — Open chat 404（R6-4 重现）
- `/tmp/feat340-r7-05-conv-open.png` — Direct with Alpha R7 空对话界面
- `/tmp/feat340-r7-06-before-send.png` — 发送前消息框
- `/tmp/feat340-r7-07-t1s-after-send.png` — 发送后 t+1s：侧栏有预览但主区无气泡
- `/tmp/feat340-r7-08-t4s-after-send.png` — 发送后 t+4s：主区仍无气泡
- `/tmp/feat340-r7-09-current-ui.png` — agent 回复后主区仍无变化（WS 断）
- `/tmp/feat340-r7-10-after-reload.png` — 刷新后：用户气泡正确，但 Alpha 出现两个气泡（均为 "4"）
- `/tmp/feat340-r7-11-agents-check.png` — Agents 页正常，无 Policies

### WS 帧捕捉（reviewer 脚本 `?token=` 正确连接）

```
[14:37:25] message.sent        ✅ event_id=1709
[14:37:25] relay.accepted      ✅ event_id=1710
[14:37:27] message.sent        ✅ event_id=1711  (重播)
[14:37:27] message.created     ✅ event_id=1712  (后端已发出)
[14:37:27] message.delta       ✅ event_id=1713
[14:37:27] message.completed   ✅ event_id=1714
[14:37:27] relay.processing    ✅
[14:37:27] relay.report        ✅
[14:37:27] relay.completed     ✅
[14:37:27] message.delivered   ✅
```

**后端事件链完整**。问题在前端：仍用 `?user_id=` 连接，收不到任何事件。

### DB 消息状态（REST API 验证）

```
id=2bba2630 sender=alexr7   content='What is 2+2? Please answer briefly.'  (正确)
id=2079a1c3 sender=Alpha    content='4'                                      (正确 agent 回复)
id=2bba2630 sender=Alpha    content='4'                                      (❌ 用户消息 id 被重写 — R6-3 重现)
```

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| R7-1 (=R6-1) | blocking | 前端 WS 仍用 `?user_id=9d6ec9d2...` 连接，被 403 拒绝；连续退避重连，最大间隔 128s。用户面：发送消息后主内容区永远无气泡、无 streaming、无 Token Chip。 | fix-implementation | M16 声称已修复前端 WS 参数，但 R7 独立验证仍见 `?user_id=` 在 console。需检查 M16 修复是否真正合入，或是否存在多处 WS 构建路径未一并修改。 |
| R7-2 (=R6-3) | blocking | `message.completed` 事件仍然把 agent 的 content 写入用户消息的 message_id；DB 中用户消息 `2bba2630` 被 sender=Alpha 以 content="4" 再次写入，刷新后 Alpha 气泡渲染重复（两个"4"气泡），语义上用户消息与 agent 消息仍共享同一 message_id。 | fix-implementation | M16 声称修复了 R5-2/R6-3，但 DB 查询证伪：用户消息 id 仍被 agent 的 completed 事件覆写。需确保 message.completed 只更新以 agent sender 创建的 placeholder message_id，而非用户消息 id。 |
| R7-3 (=R6-2 partial) | major | 后端 `message.created` 已正确发出（reviewer WS 脚本捕捉到），但用户面永远看不到 agent 占位 bubble，因为前端 WS（R7-1 blocking）完全断开。若 R7-1 修复，此项需重验 UI 渲染逻辑是否正确响应 `message.created`。 | fix-implementation | R6-2 的根因已拆分：后端发送 message.created 已修复（✅）；前端接收路径（WS 403）是 R7-1 阻断；前端收到 message.created 后是否渲染占位 bubble 尚未验证（取决于 R7-1 修复后才能测）。 |
| R7-4 (=R6-4) | minor | "Open chat ↗" 点击停留 `/settings/agents/Alpha`，底部报 "404 Not Found"。 | fix-implementation | Agent 详情页 Open chat 路由逻辑未修复，应跳转到该 agent 的 direct 对话（或先创建再跳转）。 |

## 验收标准覆盖

| 用户故事 | 要求 | R7 结果 |
|---|---|---|
| 用户打开 IM Web 并登录 | 看到登录页，登录后进 Chat | ✅ pass |
| Chat workspace 正常渲染 | 侧栏 + 标签 + 搜索框 | ✅ pass |
| 向 agent 发消息 | 消息送达 API 层 | ✅ API 层通（HTTP 201） |
| **浏览器 console 无 WS 403** | `?token=` 连接，无 403 | ❌ fail（R7-1，仍 `?user_id=` 403） |
| **Streaming bubble 逐字渐显** | 发送后 bubble 字符级递增 | ❌ fail（WS 断，前端无实时） |
| **Agent 占位 bubble 立即出现** | message.created 触发前端渲染 | ❌ fail（R7-1 阻断；后端已发 message.created） |
| **Token Chip 显示 input/output 数字** | 回复完成后显示 token 数 | ❌ fail（前端无实时事件） |
| **刷新后用户/agent 消息各自独立** | 无内容拼接污染 | ❌ fail（R7-2，用户 message_id 被 agent 再写，重复气泡） |
| 群聊 @ 提及 picker | @ 弹出选择框 | inconclusive（沿用 R6，未重测） |
| Settings 侧栏无 Policies | 仅 Agents/Nodes/Account | ✅ pass（R7 已修） |

## 上层文档同步

（延续 R1–R6 结论，无新变化）

- [x] `SPEC.md`：无需更新
- [x] `docs/内核设计SPEC.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：需更新（R1 已标记，待 PR 阶段处理）
- [x] `docs/IM-SPEC.md`：需更新（R1 已标记，待 PR 阶段处理）

## Side Findings

- Side-F8 (in-unit, minor): 刷新后 Alpha 出现两个"4"气泡——根因是 R7-2（message_id 复用），但 UI 渲染逻辑应对重复 id 有去重保护，否则前端容易出现幽灵气泡。
- Side-F1 沿用：8 个 IM integration tests pre-existing failure（baseline）。

## §行动账本

| 桶 | 内容 |
|---|---|
| READ | SKILL.md, design.md §Runbook for Reviewer, acceptance.md R1-R6（继承验证状态），spec.md（验收标准对照） |
| RESTART_SERVICE | Agent Kernel PID=96459 :8000（commit b8dfe083，14:29 启动）；IM Service PID=96484 :8011（commit b8dfe083，14:29 启动）；PA Gateway PID=97067（feat340-r7-node，14:32 启动） |
| BROWSE | goto /bind/confirm（节点绑定）→ /chat（Home）→ /settings/agents（Agents 列表）→ /settings/agents/Alpha（Alpha 详情）→ click Open chat ↗（R6-4 验证）→ /chat/74b3c960...（Direct 对话）→ fill + Enter（发送消息）→ reload（R6-3 验证）→ /settings/agents（冒烟）|
| CAPTURE | 截图 11 张（/tmp/feat340-r7-*.png）；WS 脚本 /tmp/feat340-r7-ws-capture.py（收到 events：message.sent×3, relay.accepted, message.created×1, message.delta, message.completed, relay.processing/report/completed, message.delivered）；DB REST 查询 3 条消息 |
| SHELL_MUTATION | pkill 旧进程；curl 注册 alexr7 / gw-r7 用户；写 /tmp/feat340-gw-r7-config.yaml；mkdir /tmp/feat340-r7-workspace/Alpha；curl 创建对话 74b3c960...；写 /tmp/feat340-r7-ws-capture.py；curl DB 消息查询 |
| SENDMESSAGE | 本轮 1 次（本报告写完后向 team-lead 回报） |

**源码单次例外引用**：仅读 design.md §Runbook for Reviewer（获取服务启停命令）——已在 READ 桶标注。

## §环境声明

| 服务 | PID | 端口 | 启动时 commit | 启动时间 |
|---|---|---|---|---|
| Agent Kernel | 96459 | :8000 | b8dfe083 | 2026-05-12 14:29 |
| IM Service | 96484 | :8011 | b8dfe083 | 2026-05-12 14:29 |
| PA Gateway | 97067 | — | b8dfe083 | 2026-05-12 14:32 |
| LLM_PROXY | 外部，未动 | :4000 | — | — |

临时文件（遗留 /tmp/）：`feat340-gw-r7-config.yaml`，`feat340-r7-ws-capture.py`，`feat340-r7-ws-events.log`，`feat340-r7-*.png`（11 张），`feat340-r7-workspace/`。

IM DB 新增（此轮）：用户 alexr7（id=9d6ec9d2...），用户 gw-r7（id=69cdaec3...），节点 feat340-r7-node（owner=gw-r7），对话 74b3c960...（Direct with Alpha R7，alexr7+Alpha 均为 participant），消息 2bba2630（用户）、2079a1c3（Alpha）。
