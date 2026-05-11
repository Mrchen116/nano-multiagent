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

_pending_

## R3 — Login / Register / RequireAuth route guard

_pending_

## R4 — Design tokens (oklch + IBM Plex) + AppShell (topbar/bottombar/UserMenu)

_pending_

## R5 — Me page + remove hardcoded owner-1001 / resolveCurrentUserId

_pending_
