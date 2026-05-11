# feat-340-M3: frontend-shell-i18n-auth — Tasks

> 对齐: ../design.md (M3 行 + 决策 1/2/6/10 + 风险 1)

## 目标

把 IM 前端从"硬码 owner-1001 + 浅色暖米色 + 无 i18n + 无登录"重塑成"暗顶栏 shell + 移动底栏 + JWT 登录注册 refresh + EN/中 i18n + oklch/IBM Plex 设计 token"。这个 milestone 是 M4-M7 的运行壳:能登录就够,EN 文案先全覆盖,zh 可逐步补齐。

## 退出标准

- [ ] 未登录访问任何路径 → 跳转 `/login`
- [ ] 在 `/login` 输入 username/password → 调 `POST /im/v1/auth/login` → 成功后 access/refresh token 持久化、跳回首页
- [ ] `/register` 同理
- [ ] 401 response → 自动用 refresh_token 调 refresh → 失败跳 `/login`
- [ ] 已登录 shell:48px 暗色顶栏(Logo + Chat/Agents tab + UserMenu);移动 (<768px) 退化为状态栏 + 底部三 tab
- [ ] UserMenu / Me 页可切换 EN/中,localStorage 持久化,刷新仍生效
- [ ] 移动 `/me` 聚合页:Account / Nodes / Language / Sign out
- [ ] 全 `owner-1001` / `resolveCurrentUserId` 在前端被删除,改用 auth store 的 user
- [ ] `styles/global.css` 重写为 oklch + IBM Plex + Tailwind v4 `@theme` token
- [ ] vitest 全绿;现有功能性测试通过 (auth gate / mock 注入下其余页面照常工作)

## 测试策略

- 真实入口测试 = vitest + RTL,渲染 Router、用 mock fetch 模拟 `/im/v1/auth/*` 端点,断言登录流程、token 持久化、shell 渲染、i18n 切换、UserMenu 行为。
- 既有 24 个测试文件不允许在结束时变红;凡是默认入口路径变成 `/login` 而原测试假设直接进 `/chat` 的,用 helper(`renderWithAuth`)注入 mock token 后渲染目标路由。
- 不写新 snapshot 测试(决策 6),写行为测试(getByRole / accessible name)。
- 暗顶栏 + 移动底栏的"存在性"用 `getByRole("banner")` / `getByRole("navigation", { name: "mobile" })` 而不是 class 名断言。

## Roadpoints

### R1 — Auth store + fetch 封装 + login/register API

- 写 `features/auth/auth-api.ts`:`login`/`register`/`refresh`/`logoutApi`/`fetchMe` 直接调 `/im/v1/auth/*`
- 写 `features/auth/auth-store.ts`:Zustand store 含 `accessToken / refreshToken / user / status`,持久化到 localStorage(单 key `im_auth_v1`)
- 写 `features/auth/auth-fetch.ts`:全局 `authFetch(path, init)` wrapper:自动注入 `Authorization: Bearer <access>`;401 → 调 refresh → 重试一次 → 仍失败则清 store + emit `auth:expired`
- 测试:`auth-store.test.ts`(set/clear/persist round-trip)、`auth-fetch.test.ts`(注入 header、401 触发 refresh、refresh 失败清空)
- 状态:DONE

### R2 — i18n (en/zh) + LanguageProvider

- 引入 `react-i18next` + `i18next` 依赖
- 写 `i18n/en.json` + `i18n/zh.json`:覆盖本 milestone 文案 key (auth/shell/me 页),其它页面 key 占位、由 M4-M7 worker 增量补
- 写 `i18n/index.ts`:初始化 i18next、`useLanguage()` hook 返回 `{ lang, setLang }`(localStorage `im_lang` + 同步 `users.locale` 可选,后端调用留给 Account 页)
- 测试:`i18n.test.ts` 验证默认 EN、`setLang("zh")` 后 t() 返回 zh 串、localStorage 持久化、刷新后载入
- 状态:TODO

### R3 — Login + Register + auth-gate 路由守卫

- 写 `features/auth/login-page.tsx` + `register-page.tsx`:基础表单,错误内联展示(toast 留给 M4)
- 写 `features/auth/require-auth.tsx`:guard 组件,未登录 → `<Navigate to="/login" replace />`
- 改 `app/router.tsx`:增 `/login` `/register` 公开路由 + 其余路由包 `<RequireAuth>`
- 测试:`auth-gate.test.tsx` 验证未登录访问 `/chat` 跳 `/login`;`login-page.test.tsx` 验证表单提交、loading、错误状态、成功跳转
- 状态:TODO

### R4 — Design token 重写 + AppShell(顶栏/底栏/UserMenu)

- 改 `styles/global.css`:替换字体/调色板为 IBM Plex + oklch,暗顶栏色 `oklch(0.19 0.012 240)`,accent `oklch(0.52 0.14 180)`,Tailwind v4 `@theme` 暴露 token。保留 `im-card` 等旧 class 作为透传(语义重映射到新 token),让 M4-M7 重写前 UI 不至于完全崩
- 写 `app/shell/app-shell.tsx`:替换 `app/App.tsx` 现有 header,变成 48px 暗顶栏(Logo + Chat/Agents tab + UserMenu)+ 移动断点底栏(Chat/Agents/Me)
- 写 `app/shell/user-menu.tsx`:头像 dropdown,包含 New Agent / Account / Language / Sign out
- 测试:`app-shell.test.tsx` 验证桌面 banner + tabs + UserMenu 存在;移动断点(`useIsMobile` mock)下底栏出现、顶栏退化
- 状态:TODO

### R5 — Me 聚合页 + i18n 切换实际生效 + 移除 hardcoded owner-1001

- 写 `features/me/me-page.tsx`:Account / Nodes / Language toggle / Sign out 入口列表
- 删除 `features/settings/im-settings-api.ts` 的 `listUsers` / `resolveCurrentUserId`,改用 auth store 的 `user.id` 直接拼 `/im/v1/me`(无 query param,后端从 token 解 owner)
- 删除 `features/settings/mock-settings-api.ts` 中 `user_id: "owner-1001"` 等硬码引用,统一从测试 fixture 注入
- 改 `features/chat/im-chat-api.ts` 里 `selfUserId` 的获取方式:从 auth-store `getState().user.id` 取,不再从 `/im/v1/users` 兜底
- 测试:`me-page.test.tsx`(EN/中 切换实际改变文案)、回归 account/settings 旧测试在新 mock 注入下仍通过
- 状态:TODO
