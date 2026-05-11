# feat-340-M3 — Progress

## R1 — Auth store + fetch wrapper + auth-api

- Context: M3 必须先有"登录态 + 自动加 Bearer + 401 自动 refresh"的运行壳,否则 M4-M7 跑不起来。
- Decision: Zustand store(`AUTH_STORAGE_KEY = im_auth_v1`)持久化 access/refresh/user 到 localStorage;`auth-api.ts` 包 `/im/v1/auth/{login,register,refresh,logout}`;`authFetch` 单飞 refresh,失败清 store。
- Rationale: 选 Zustand 与项目既有 `state/ui-store.ts` 一致;单飞用 module-scope promise,避免并发请求 401 触发多次 refresh;refresh 失败不抛错而是回原 401,由 RequireAuth 兜底跳 `/login`(决策 1)。
- Evidence:
  - Tests: `npx vitest run src/features/auth/` → 9/9 pass;`npm test` → 全套 157/157 pass(基线 148 + 新增 9)。
  - Entry: 由 R3/R4 串通后通过端到端登录测试覆盖。
- 顺手:`src/test/setup.ts` 加 localStorage in-memory polyfill,因 jsdom 27 + node 25 暴露的 `localStorage` 缺 `getItem`/`setItem`/`clear`(Warning: --localstorage-file)。
- Rollback: 删 `src/IM/frontend/src/features/auth/` 三文件 + revert setup.ts polyfill 段。
- Commits: C1=11d2101, C2=ae61e66, C3=(下一提交)

## R2 — i18n EN/中 framework

- Context: spec Q1 + 验收"i18n EN/中 切换持久化"。M4-M7 都要从 `useTranslation()` 取 key,壳必须先把 instance 跑起来。
- Decision: `i18next` + `react-i18next`,JSON 资源(en.json / zh.json)平铺;`setLanguage()` 同步写 localStorage(key `im_lang`);未知 locale 拒绝。本 milestone 只覆盖 auth / shell / me / common 命名空间,其它由下游 worker 增量补 key。
- Rationale: 决策 2 已锁;`react-i18next` 是社区最广 + 支持 React 19;JSON 平铺方便 grep + diff;按需补 key 避免阻塞下游。
- Evidence: `npx vitest run src/i18n/` → 4/4 pass;`npx tsc -b` 无报错;`npm test` 全套 161/161 pass。
- Rollback: 删 `src/IM/frontend/src/i18n/`,从 package.json 移除 i18next + react-i18next 依赖。
- Commits: C1=d3949ba, C2=(本提交), C3=(下一提交)

## R3 — Login / Register / RequireAuth route guard

- Context: 路由壳必须拦截未登录访问;LoginPage 和 RegisterPage 是用户首次进入应用的入口。
- Decision: 增 `/login` `/register` 公开路由,其余包 `RequireAuth`;RequireAuth 首次 mount 触发 `useAuthStore.hydrate()`,未登录 `Navigate to="/login"` 并把原路径塞 `state.from`,登录成功后回跳。`renderRouter` test helper 默认 seed 一个 `TEST_AUTH_USER`,把"原本默认登录"的隐式假设显式化,既不破坏 24 个旧测试,也允许测 `auth: null` 跳登录的反向用例。
- Rationale: 决策 1(JWT)+ 风险 1(壳必须稳)。把 helper 改一处比改 24 个测试文件成本低 10×;`auth: null` 还能被 R3 自己的 auth-gate test 复用。
- Evidence: `npx vitest run src/features/auth/auth-gate.test.tsx` → 4/4 pass;`npm test` → 165/165 pass;`npx tsc -b` 通过。
- Rollback: 删 login/register/require-auth + me-page,revert router.tsx + render-router.tsx + router.test.tsx 路径查找改动。
- Commits: C1=c409a2f, C2=(本提交), C3=(下一提交)

## R4 — Design tokens (oklch + IBM Plex) + AppShell (topbar/bottombar/UserMenu)

- Context: 整个产品视觉切换 + Chat/Agents 双 tab + UserMenu 下拉 + 移动底栏 都是 M4-M7 的运行壳。
- Decision: `styles/global.css` 重写为 oklch + IBM Plex + Tailwind v4 `@theme` 暴露 token;旧 `im-card/im-input/...` 保留为新 token 的 thin alias(决策 6 风险 3:不要让 M4-M7 启动时旧页面全裂)。`app/shell/{app-shell,user-menu}.tsx` 实装 48px 暗顶栏 + 移动底栏 + 头像菜单。`useIsMobile` 断点从 900 → 768(spec 锁的)。`WorkspaceTabs` 旧组件保留为 orphan,M4-M7 重写各自页面时一并清理。
- Rationale: 决策 6 锁定 token + Tailwind utility,不引入新样式库;为下游 worker 不让"视觉切换 = 大爆炸"。
- Evidence: `npx vitest run src/app/shell/` → 3/3 pass;`npm test` → 168/168 pass;`npx tsc -b` 通过。App.test 老断言改为基于 role,符合决策 6 "behavior > snapshot"。
- 顺手:App.test.tsx 旧 `Tab=Chat|Settings` 断言已过时(新壳是 NavLink "Chat|Agents"),改为 `role=link / role=banner / role=main` 行为测试。
- Rollback: 删 `app/shell/` + 还原 `styles/global.css` 旧版本 + 还原 `app/App.tsx` + 还原 `hooks/use-is-mobile.ts` 断点。
- Commits: C1=57bf264d, C2=(本提交), C3=(下一提交)

## R5 — Me page + remove hardcoded owner-1001 / resolveCurrentUserId

_pending_
