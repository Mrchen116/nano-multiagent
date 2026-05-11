# feat-340-M5 — Progress

## Design 修订记录

- 2026-05-11: M5 退出标准追加 "agent status pill 由 `agent.status_changed` WS 实时反映"(决策 11 / M10 立项时同步追加,见 design.md changelog)。
  M5 消费侧需在 list / detail 接 ws reducer + React Query cache patch;M10 producer 并行进行,M5 收尾阶段(R5 status-broadcast 消费)用单测 fixture 模拟事件断言 cache 更新。

## Roadpoints 状态

- R1 list page rewrite — DONE
- R2 detail page four-card rewrite — TODO
- R3 create page three-card rewrite — TODO
- R4 i18n zh translations + UI 切换断言 — DOING(R1 已落地 agents 部分 zh,详情/新建页 zh 在 R2/R3 继续追加;R4 收尾做端到端切换断言)
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
- Commits: C1=d81b1790, C2=bd7c49a0, C3=<this>
- Next: R2 详情页四卡重写
