# refactor-489-M16 — Progress

## Baseline

- Claim: 清理前 M16 foundation Vitest 可稳定运行，后续删除/合并能与同一范围直接对照。
- Baseline: `milestone/refactor-489-M16` from `origin/unit/refactor-489@90415c3d1`。
- Method: 在 `src/IM/frontend/` 对不属于 M14/M15 的 19 个 tracked `*.test.{ts,tsx}` 运行 Vitest；worktree 的临时未跟踪 `node_modules` 链接到主仓已安装的同版本 frontend dependencies，收尾时删除。
- Result: PASS；`19 test files / 105 tests passed in 2.91s`。
- Locator: `src/IM/frontend/src/` foundation tests、`src/IM/frontend/tests/vite-proxy-config.test.ts` 与本 milestone `tasks.md` 处置表。
- Limit: Vitest/jsdom + fake WebSocket/Notification/fetch；不证明真实浏览器视觉、真实 IM 服务或外部网络。既存输出含 router 测试未隔离全局 stream 导致的 `/im/v1/sync` invalid-URL console error，以及 Node `--localstorage-file` warnings；基线仍绿，前者在 R1 从测试 harness 隔离，后者记录但不扩张产品范围。

## R1 — 删除静态扫描与 app/me 伪视觉重复

- 状态: DONE
- Context: foundation 基线含 `.gitignore`/`index.html` raw-text 扫描，App 与 AppShell 对 nav/banner 的重复，以及 Me/AppShell 对 prototype 流水号、CSS class、emoji、chevron、圆角和颜色的 jsdom 断言；router 还反射 `RouteObject/Navigate` 内部形状并因未隔离全局 user stream 在绿测中输出真实 fetch URL error。
- Decision: 删除两份 raw-text 测试；App 只保留全局 notification coordinator 和 identity-scoped cache；AppShell 保留 desktop/mobile 导航、退出与 unread sum；Me 保留身份/入口、语言与退出；root route 改为实际 MemoryRouter 从 `/` 进入 chat workspace，并把 router fixture 更新为 current `Conversation` shape、隔离与路由无关的全局 stream。
- Rationale: 构建与用户操作才是分发/路由/导航的有效 seam；HTML/`.gitignore` 字符串、React element 类型和 Tailwind class 不能证明真实视觉。路由测试仍应直接证明页面可达，但不应附带真实网络副作用或旧 API fixture。
- Evidence:
  - Tests: App/router/AppShell/Me 定向 `4 files / 13 tests passed in 1.63s`；current fixture 修正后 router `4 passed` 且不再输出 `/im/v1/sync` invalid-URL error；完整 M16 从 `19 files / 105 tests` 收敛为 `17 files / 88 tests passed in 2.95s`。
  - Entry: Testing Library 仍从 authenticated root 打开 chat workspace，执行 desktop/mobile nav、UserMenu/Me 退出、语言切换并观察 localStorage/router/auth state；零产品源修改。
  - Frontend State Matrix: default、empty unauthenticated、mobile、desktop 与 unread 代表性状态仍由保留的 App/router/shell/Me tests 覆盖。
  - Browser QA: N/A（测试资产重构，无 UI/product delta）。
  - E2E/Regression: 永久 regression 为收敛后的 DOM interaction/state Vitest；本 R 不新增浏览器 E2E。
  - Visual/Interaction: N/A；删除的 class/text scan 不能作为真实视觉证据，且无样式改动。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复 raw-text 与 prototype/CSS 断言，不影响产品源码或数据。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 收敛 auth freshness/store lifecycle 与 notification/i18n 同 seam 重复。

## R2 — 收敛 auth 与 notification 状态保护

- 状态: TODO

## R3 — 收敛 realtime 并完成配置门禁

- 状态: TODO

## Promotion Candidates

None.
