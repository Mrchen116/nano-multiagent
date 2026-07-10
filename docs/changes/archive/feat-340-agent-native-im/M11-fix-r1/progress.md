# M11-fix-r1 Progress

## R1 — 补 Chat CSS 规则（chat-* 类名）

- Context: M4 实施时只写了组件 className，没在 global.css 里对应补 CSS 规则。82 处 chat-* class 在 global.css 里 0 条匹配。Chat workspace 整页渲染为无样式纯 block 流。
- Decision: 在 `styles/global.css` 末尾追加所有 chat-* 类的 CSS 规则，覆盖全部 82 个 class 名，遵循 design 决策 6（Tailwind v4 token + global.css 规则）。
- Rationale: 不改组件 className，只补 CSS，改动最小且不破坏现有测试。
- Evidence:
  - Tests: `npm test -- --run` → 52 files, 236 tests, all pass
  - Entry: CSS 规则补齐后 vitest 组件渲染测试全绿，chat-workspace-page.tsx 的类名断言正常
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R2

---

## R2 — im-chat-api requestJson → authFetch

- Context: `im-chat-api.ts:612 requestJson` 调用裸 `fetch()` 不带 Bearer，导致 Chat workspace 所有 GET（/im/v1/agents /im/v1/nodes /im/v1/conversations /im/v1/messages /im/v1/uploads 等）全部 401。
- Decision: 在 `im-chat-api.ts` 顶部 import `authFetch`，把 `requestJson` / `requestUpload` / `deleteConversation` / `leaveConversation` 里的 `fetch(withBase(...))` 全部换为 `authFetch(withBase(...))`。authFetch 内部已有 Bearer 注入 + 透明 refresh 逻辑。
- Rationale: authFetch 对 `http://...` 路径不双重 withBase，对相对路径也正常处理，无双重前缀风险。
- Evidence:
  - Tests: `im-chat-api.test.ts > requestJson Authorization` → 新增断言 `Authorization: Bearer test-bearer-token` 通过
  - Tests: `npm test -- --run` → 52 files, 236 tests, all pass
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R3

---

## R3 — WS query param: access_token → token

- Context: 前端 `chat-stream.ts:21,25` 用 `access_token=` 传 token，后端 `app.py:342` 读 `token=`，握手 1008。所有实时事件用户收不到。
- Decision: 修改 `chat-stream.ts` 中 `resolveWsUrl` 函数，`searchParams.set("access_token", ...)` 改为 `searchParams.set("token", ...)`，SSR fallback 同步修改。
- Rationale: 后端命名 `token` 与 design 决策 1 描述（"query 参数 token="）吻合；单边改前端即可，后端代码不需动。
- Evidence:
  - Tests: `chat-stream.test.ts > 'opens a WebSocket...?token='` → 通过，含 `not.toContain("access_token=")`
  - Tests: `npm test -- --run` → all pass
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R4

---

## R4 — SPA fallback: /login /register /me

- Context: `IM/app.py` 只注册了 `/`, `/chat/*`, `/settings/*`, `/bind/confirm`。直链或刷新 `/login`, `/register`, `/me` 返回 FastAPI 404 raw JSON，SPA 路由失败。
- Decision: 在 `_install_frontend_entrypoints` 函数末尾追加 3 条 `@app.get` 路由（`/login`, `/register`, `/me`），全部调用 `frontend_entry_response(request)`，服务 SPA shell。
- Rationale: 3 条显式路由比通配 `/{path:path}` 更安全，不会意外吃掉 `/im/*` 或 `/assets/*` 请求。
- Evidence:
  - Tests: `test_create_app_serves_spa_shell_on_login_register_me_routes` → 200 + shell HTML
  - Tests: `pytest tests/im_service/ --ignore=...` → 199 passed（+1 新测试）
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R5

---

## R5 — i18n: Settings 侧栏硬编码字符串

- Context: `settings-page-shell.tsx` 侧栏 navItems 使用硬编码英文字符串 "Agents" / "Nodes" / "Policies" / "Account"，中文模式下保持英文，spec "全 UI EN/中" 不满足。
- Decision: 添加 `settings.nav.{agents,nodes,account}` i18n key 到 `en.json` 和 `zh.json`，更新 `settings-page-shell.tsx` 使用 `useTranslation` + `t()` 渲染 navItems 标签。
- Rationale: 与 design 决策 2（react-i18next + JSON 文案）一致。"Policies" 链接同步在 R7 删除，故无需为它添加 i18n key。
- Evidence:
  - Tests: `settings-shell-mobile.test.tsx` / `settings-scroll-layout.test.tsx` → pass，无新 i18n 相关失败
  - Tests: `npm test -- --run` → all pass
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R6

---

## R6 — tsc fix: account-page.test.tsx fixture 类型

- Context: `account-page.test.tsx:126:9` tsc 报错：`stored` 推断类型 `{ ..., default_entry_node_id: string }` 与 PATCH payload `string | null` 不兼容。
- Decision: 用 `Omit<..., "default_entry_node_id"> & { default_entry_node_id: string | null }` 类型别名显式标注 `stored` 变量，让 TypeScript 接受可空赋值。
- Rationale: `meBody()` 返回类型保持不变；只在测试用例局部引入宽松类型，最小侵入。
- Evidence:
  - `node_modules/.bin/tsc -b` → 0 errors
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: R7

---

## R7 — 删除 Settings 侧栏 Policies 链接

- Context: `settings-page-shell.tsx` 侧栏有 "Policies" 链接，spec/design 未提及此页，属未立项功能，会误导用户。
- Decision: 从 navItems 数组删除 `{ to: "/settings/policies", label: "Policies" }` 条目。`/settings/policies` 路由和 `PoliciesPage` 组件保留（Router 配置里存在）但不在导航栏暴露。同步删除 `settings-scroll-layout.test.tsx` 里对 `/settings/policies` 的测试行（测试本意是验证侧栏导航，Policies 不在导航就不需要这行）。
- Rationale: 不删路由组件，方便将来独立 unit 立项后重新加回入口；只隐藏导航入口。
- Evidence:
  - Tests: `settings-scroll-layout.test.tsx` → pass（已删除 `/settings/policies` 行）
  - Tests: `npm test -- --run` → all pass
- Rollback: revert C2 commit
- Commits: C1=410def3b, C2=f7a57e3c, C3=TBD
- Next: milestone 完成，集成到 unit 分支
