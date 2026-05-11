# feat-340-M5 — Progress

## Design 修订记录

- 2026-05-11: M5 退出标准追加 "agent status pill 由 `agent.status_changed` WS 实时反映"(决策 11 / M10 立项时同步追加,见 design.md changelog)。
  M5 消费侧需在 list / detail 接 ws reducer + React Query cache patch;M10 producer 并行进行,M5 收尾阶段(R5 status-broadcast 消费)用单测 fixture 模拟事件断言 cache 更新。

## Roadpoints 状态

- R1 list page rewrite — DONE
- R2 detail page four-card rewrite — DONE
- R3 create page three-card rewrite — TODO
- R4 i18n zh translations + UI 切换断言 — DOING(R1/R2 已落地 agents 部分 zh,新建页 zh 在 R3 继续追加;R4 收尾做端到端切换断言)
- R5 status-broadcast 消费(WS reducer + React Query cache patch) — TODO(新增 roadpoint,见上方 design 修订)

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
- Commits: C1=fdc6bb03, C2=733bd8d8, C3=<this>
- Next: R3 新建页三卡重写
