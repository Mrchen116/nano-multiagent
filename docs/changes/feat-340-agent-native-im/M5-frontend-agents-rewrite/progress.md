# feat-340-M5 — Progress

## Design 修订记录

- 2026-05-11: M5 退出标准追加 "agent status pill 由 `agent.status_changed` WS 实时反映"(决策 11 / M10 立项时同步追加,见 design.md changelog)。
  M5 消费侧需在 list / detail 接 ws reducer + React Query cache patch;M10 producer 并行进行,M5 收尾阶段(R5 status-broadcast 消费)用单测 fixture 模拟事件断言 cache 更新。

## Roadpoints 状态

- R1 list page rewrite — DONE
- R2 detail page four-card rewrite — DONE
- R3 create page three-card rewrite — DONE
- R4 i18n zh translations + UI 切换断言 — DONE
- R5 status-broadcast 消费(WS reducer + React Query cache patch) — DONE

---

### R1 — list page rewrite (desktop sidebar + mobile)

- Context: 既有 `agents-list-page.tsx` 是浅色 Workspace 表格 + "Open chat" 按钮;原型要求改成 240px 暗色侧栏 + agent 行(头像 + display_name + agent_id + 状态点),移动端占满 + 描述可见;顶部 `+ New` 跳 `/settings/nodes`(让用户先选节点)。
- Decision:
  - 重写 `agents-list-page.tsx`:`useIsMobile()` 切桌面/移动两套布局,共用同一 `AgentRow` 组件;状态点由 `nodes[].status` 派生(无 node_id 视为 offline)。
  - `im-agent-config-api.ts` 全部 fetch 切到 `authFetch`(透明加 Authorization Bearer 头) — 一处改动覆盖该模块 8 个 endpoint。
  - i18n 新增 `agents.*` namespace key(title / newButton / loadError / retry / empty.title / empty.body / openNodes 等),en + zh 两套同步加。
  - 全局样式 `styles/global.css` 新增 `.im-agents-list` / `.im-agent-row` 等 token-based 类(暗色侧栏 240px + 圆形头像 + 状态点),与原型对齐。
  - 列表 `<Link>` 直接用 `to` 属性 → DOM `href="/settings/agents/<id>"`,测试用 `getByRole("link", { name })` 断言,无需 navigateMock。
  - `settings-scroll-layout.test.tsx` 之前 hardcode "Loading agents..." 文案;新布局没有该文案,改成断言 `[data-testid="agents-list"]` 出现即可,保留布局 class 校验不变。
- Rationale:
  - 用 `useIsMobile()` + 共享 `AgentRow` 避免桌面/移动重复实现;靠 `is-mobile` modifier class 在 CSS 切样式,行为一致、字段一致。
  - `authFetch` 透明注入 Authorization,api 层完全不关心 token 来源,符合 M3 已落定的 auth 边界。
  - 数据派生(`statusOf`)而非新增字段,避免 schema 改动 — 当前后端 `AgentSummary` 暂无 status 列,完全靠 owning node 推断,M10 之后会通过 WS `agent.status_changed` 实时 patch react-query cache(R5)。
  - empty/error state 都给一个可点击 CTA / Retry 按钮,确保失败可恢复(测试覆盖 503 → Retry → 200)。
- Evidence:
  - Tests: `npm run test -- --run agents-list-page.test.tsx` → 6/6 通过(桌面侧栏 + 移动 + 空态 + 错误重试 + Authorization Bearer + i18n 中文切换)
  - Full suite: `npm run test -- --run` → **31 test files / 175 tests** 全绿
  - Entry: 列表页是真实路由 `/settings/agents` 入口,测试通过 `renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] })` 走完整 router + QueryClient + auth store + global fetch 链路,等同于浏览器加载该页面。
- Rollback: `git reset --hard d81b1790`(R1 C1 测试已存在)
- Commits: C1=d81b1790, C2=bd7c49a0, C3=732586dd
- Next: R2 详情页四卡重写

### R2 — detail page four-card rewrite

- Context: 旧详情页(498 行)用 `im-section-card`/`im-subtle-card` 浅色 Workspace 风格,顶部用 `<h2 className="im-title">Agent settings</h2>`,无明显的 panel-header 状态 pill,Save toast 是 "Saved" 文案。原型要求改成 `im-agent-panel` + `im-agent-panel-header`(sticky 头,头像 + display_name + agent_id+node + 实时 status pill + Open chat ↗ + Save) + `im-agent-panel-body` 四张 `im-agent-card`(Identity / Behavior / Access&Model / Workspace&Runtime) + `im-agent-footer`(dirty/saved/error 状态语 + Discard + Save)。Workspace 卡片仅详情,新建页不显示。
- Decision:
  - 重写整页:`<form data-testid="agent-detail" className="im-agent-panel">` 容器,sticky `<header className="im-agent-panel-header">` 内 status pill 用 `<span data-testid="agent-detail-status-pill" className="im-agent-panel-status-chip ${online}">`,4 张 `<section className="im-agent-card">`,统一用 `im-agent-field` 包字段,系统提示词改 `im-agent-textarea`(monospace 风格)。
  - i18n 端到端切到 `t("agents.detail.*")` / `t("agents.form.*")`,所有写死英文文案被替换为 key — 副产品是 R4 已为详情页落地,只剩端到端断言。
  - footer 状态文案改用 5 档:noChanges / unsavedChanges("● 有未保存改动") / saving / saved("✓ Saved") / error;Save 按钮文案 `Save`(原型) — 测试改用 `name: /^Save$/` 严格匹配。
  - Save 成功后 `setSaved(true)` 1800ms 自动清除,符合原型 "✓ Saved" 2s 短提示。
  - Workspace 卡用 disabled `<input>` 暴露 workspace_root / profile_version("v{{version}}") / owning_node / last_updated 四只字段,disabled 输入框天然 read-only 且测试可用 `getByLabelText` 精确取值,避免依赖 split 文本节点。
  - Discard 按钮:`detailQuery.data.config` 回滚 draft + 清 touched + 清错误。dirty 才 enable。
  - Open direct chat 按钮挪到 header,文案改 i18n `agents.detail.openChat`("Open chat ↗"/"打开聊天 ↗")。
- Rationale:
  - 用 `data-testid` 锚定 panel + status-pill — R5 需要订阅 WS 事件后断言这两个节点的可见 class 变化,测试可定向到具体 DOM。
  - 整页迁到 i18n 一次性把 R4 "详情页 zh 同步"的工作并掉,避免 R4 阶段再回头改详情。
  - 把 profile_version / workspace_root 收进 disabled `<input>`,而非散落在 `<dl>` 里 — `getByLabelText` 取 value 比 `getByText` 更稳健、不依赖文本拼接、对 i18n 友好(英文/中文文案都不会影响 label-to-input 关系)。
  - 5 档 footer status 把"全部已保存"和"无改动"统一为 noChanges,让 dirty/saved/error 状态可视化对齐(`im-agent-footer-status.dirty/.saved/.error`)。
- Evidence:
  - Tests: `npm run test -- --run agent-edit agent-detail-page` → 4/4 通过(加载+四卡渲染+status pill 在线+ "✓ Saved" + profile_version 输入框 v13 + 必填校验 + 409 冲突保留 v12 + 跳直聊)
  - Full suite: `npm run test -- --run` → **32 test files / 179 tests** 全绿
  - Entry: `agent-edit.test.tsx` 用 `renderRouter` 跑真实路由 `/settings/agents/agent-core-1`,走完整 router + QueryClient + fetchMock(/im/v1/nodes、/im/v1/agents/:id/capabilities、:id/config GET/PATCH) — 等同浏览器加载详情。
- Rollback: `git reset --hard fdc6bb03`(R2 C1 测试已存在)
- Commits: C1=fdc6bb03, C2=733bd8d8, C3=8d2e2d5b
- Next: R3 新建页三卡重写

### R3 — create page three-card rewrite

- Context: 旧新建页 505 行有 5 张 `im-section-card`(Owning node + Identity + Behavior + Access & Model + Workspace),Save 后留在原页显示成功 CTA + 手动跳直聊。原型与 design 规定:新建页只显示 3 张卡(Identity 含 Owning Node、Behavior、Access & Model),没有 Workspace 卡,Save 成功直接跳详情(`/settings/agents/<new-id>`),Cancel 回列表(`/settings/agents`)。
- Decision:
  - 整页重写为 `<form data-testid="agent-create" className="im-agent-panel">`,Header 上是 `agents.create.title`("新建 Agent")+ node 状态 pill,3 张 `<section className="im-agent-card">`(身份/行为/访问与模型),`im-agent-footer` 内 Cancel `<Link to="/settings/agents">` + Create `<button type="submit">`。
  - Workspace 卡片**整体删除**,`workspace_root` 在 `normalizeDraft` 里强制为 `null`(后端按节点 managed default 分配工作区路径) — payload 里固定送 `workspace_root: null`,无 UI 控件露出。
  - 删除原"成功后留页 + Open direct chat" 逻辑;`onSuccess` 直接 `navigate(`/settings/agents/${created.agent_id}`)`,符合 design"一次性引导用户进入正式编辑面板"。
  - 全文 i18n,`agents.form.*` / `agents.create.*` key 全量接管;label 加 `*` 标记必填(`Agent ID *`/`Display Name *`/`System Prompt *`/`Owning Node *`)— 测试用 `/^Agent ID/` 等 prefix 正则匹配 `getByLabelText`,稳健应对 i18n 文案差异。
  - 同步修复 `src/app/router.test.tsx` 一处 obsoleted 断言:旧文案 "Create Agent on" → 新文案 "New agent",error fallback 文案 "Could not load this node." → "Could not load agents.";仍允许 error/normal 两条路径之一通过,符合 router smoke 测试意图。
- Rationale:
  - 移除 Workspace 字段而非"保留但 hide" — design 决策明确"Workspace 是 owning node 的 runtime 属性,新建期间用户无能力填一个有效的本地路径",留 UI 只会诱导出错的输入。强制 `workspace_root: null` 让后端走 managed default,与旧"用户填空白则用 default"行为等价但 UI 更干净。
  - Save → navigate 而非留页:原型希望"一次创建 → 立刻进入完整编辑面板",避免双步骤(成功 CTA → 手动点 Open chat 跳)— 详情页本身已含 Open chat 按钮,留页只是冗余。
  - Cancel 用 `<Link>` 而非 navigate(-1):新建页可能从 Nodes/Agents/UserMenu 三入口进入,后退路径不确定;直接回 `/settings/agents` 与列表→ + New → 列表 的产品心智模型一致。
  - Label 带 `*` 走 i18n 而非纯 CSS pseudo-element — 测试时能直接看到 required 标记,屏幕阅读器也能朗读,a11y 友好。
- Evidence:
  - Tests: `npm run test -- --run agent-create` → 4/4 通过(三卡渲染 + 无 Workspace + Save 跳 `/settings/agents/agent-new` + 必填校验 + 409 错误 + Cancel 链接 `/settings/agents`)
  - Full suite: `npm run test -- --run` → **32 test files / 180 tests** 全绿(含修复后的 router smoke test)
  - Entry: 通过 `/settings/nodes/node-1/agents/new` 真实路由进入新建页,fetchMock 模拟节点 capabilities + listNodes,断言 createNodeAgent 真请求载荷 + navigate 真调用。
- Rollback: `git reset --hard 373dee82`(R3 C1 测试已存在)
- Commits: C1=373dee82, C2=26c5f96c, C3=<this>
- Next: R4 i18n end-to-end switch 断言

### R4 — i18n zh translations + UI 切换断言

- Context: R1 已落地列表 i18n;R2 已把详情页所有英文文案搬到 `t("agents.detail.*")` / `t("agents.form.*")`;R3 已把新建页文案搬到同 namespace 下;`agents.*` 在 en.json/zh.json 中已完整对齐(190+ keys)。R4 只剩一个事:用一个独立的端到端测试文件,在 `setLanguage("zh")` 后跑真实路由,断言关键中文文案出现在屏幕上。
- Decision:
  - 新建 `agents-i18n-switch.test.tsx`,beforeEach 调 `setLanguage("zh")`,afterEach 还原到 `setLanguage("en")`,三个 case:(a) 列表 zh — 断言"还没有 Agent" / "前往节点" / "Agents" 标题;(b) 详情 zh — 断言"身份/行为/访问与模型/工作区与运行时"四卡标题 + "打开聊天" + "保存";(c) 新建 zh — 断言"新建 Agent" 标题 + 三卡 + "取消" + "创建 Agent",并 `queryByRole("heading", { name: /工作区/ })` 不存在 — 双重锁定"新建页无 Workspace"。
  - 由于 R2/R3 已经把页面整体 i18n 化,本 R 不需要改 production 代码,只新增测试 — 这是"R 的边界"实际划在 R2/R3,R4 收口断言。tasks.md 已标 R4 DOING 的"R1/R2 已落地详情/新建 zh,R4 主要做端到端切换断言",与最终落地一致。
- Rationale:
  - 不退而求其次写"假端到端"(setLanguage 后只测一个组件):用 `renderRouter({ routes: appRoutes, initialEntries: [...] })` + 真 fetchMock 跑完整路由 + Settings 外壳,确保 i18n 真的从 lookup 一直传到屏幕。三页都验证、不留盲区。
  - afterEach 还原为 en,避免污染后续测试(其他用例默认走 en 文案断言)。
- Evidence:
  - Tests: `npm run test -- --run agents-i18n-switch` → 3/3 通过(列表 / 详情 / 新建 全部 zh 文案断言通过)
  - Full suite: `npm run test -- --run` → **33 test files / 183 tests** 全绿
  - Entry: 三个测试都走真实路由 `/settings/agents` / `/settings/agents/agent-zh-1` / `/settings/nodes/node-1/agents/new`,等同于浏览器切到中文后访问这三个路径。
- Rollback: `git reset --hard a44544c5`(R4 C1 测试已存在)
- Commits: C1=a44544c5(测试文件即落地;R2/R3 已完成实现侧),C3=48da8121
- Next: R5 status-broadcast WS reducer 消费

### R5 — status-broadcast WS reducer 消费

- Context: M10 producer 在并行落地,M5 消费侧需要在 list / detail 订阅 WS hub 的 `agent.status_changed` 事件,把事件 patch 进 react-query cache 让 status pill 实时刷新。design 决策 11 与 M5/M10 退出标准都列了这一点。
- Decision:
  - 新建 `src/features/settings/agents/agent-status-ws-consumer.ts`,导出两个 API:
    - `applyAgentStatusEvent(client, event)` 纯函数 — 把 `agent.status_changed` 事件 patch 进 `["settings","agents"]` 列表 cache 和 `["settings","agents",agentId,"detail-state"]` 详情 cache。设计成纯函数,让单测可以脱开真实 WS 喂事件断言 cache 变化。
    - `useAgentStatusBroadcastConsumer()` hook — 包 `attachUserConversationStream(selfUserId, onEvent)`,自动绑/解 subscriber。selfUserId 取 `useAuthStore(s => s.user?.id)`,未登录直接 noop。
  - 列表的 `statusOf` 改成"优先取 agent.node_status,缺则回退到 nodes 表的 status" — 让 WS patch 后 AgentSummary.node_status 的覆盖能立刻反映在 row 状态点。详情已经直接读 draft.node_status,patch 之后 useEffect 同步到 draft,UI 自动跟随。
  - `agents-list-page.tsx` / `agent-detail-page.tsx` 顶部各加一行 `useAgentStatusBroadcastConsumer()`。
  - **不依赖 M10 真实推送** — 单测用 fixture 模拟事件直接灌进 `applyAgentStatusEvent`,断言 cache 内容变化;M10 producer 合并后由 reviewer 走 e2e 联调。
- Rationale:
  - 把"事件 → cache patch"做成纯函数而非把逻辑塞进 hook,让单测脱开 hooks API + WebSocket runtime,断言点更稳定也更快(整套 4 个 case 2ms 完成)。
  - 列表的 `statusOf` 用"agent.node_status 优先 + nodes 表回退"的两段策略,而非直接覆盖 nodes 状态:nodes 表上的 status 是 `node.status_changed` 事件的目标(node-level),agents 表上的 node_status 是 `agent.status_changed` 事件的目标(agent-level,可能因 agent 进程崩溃而独立于 node);两者语义不同,不要交叉污染。
  - hook 用 `useAuthStore(s => s.user?.id ?? null)` 而非自己读 token —— 与 `use-global-message-toast` 用法对齐,登录态变化时 effect 自动重订阅。
- Evidence:
  - Tests: `npm run test -- --run agent-status-ws-consumer` → 4/4 通过(list patch / detail patch / 忽略 node.status_changed + 未知 agent / 拒绝 malformed payload)
  - Full suite: `npm run test -- --run` → **34 test files / 187 tests** 全绿
  - Entry: 单测直接喂 fixture 事件到 `applyAgentStatusEvent`,与 WS 链路上 `parseImStreamEvent → onEvent` 给出来的 `ParsedImStreamEvent` 形状一致;hook 侧用真 `attachUserConversationStream` 接入,M10 上线后无需再改 M5。
- Rollback: `git reset --hard a2dc5e53`(R5 C1 测试已存在)
- Commits: C1=a2dc5e53, C2=687c3aec, C3=<this>
- Next: 本 milestone 已完成,等 orchestrator 派 reviewer 验收
