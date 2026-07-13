# refactor-460-M1 — Progress

## 启动基线

- Context: M1 是 live-critical 前端 runtime 重构，必须先证明当前分支可测且不把既有失败混入实现。
- Evidence:
  - `npm run test`: 64 files / 618 tests passed。
  - `npm run build`: passed。
  - 当前 unit/local/remote 同步于 `d9e478063251c2a27a129dd816b1677873c15401`。

## R1 — Auth session freshness coordinator

- Context: WebSocket 重连不能依赖其他页面碰巧触发 HTTP 401；同时 refresh 结果不能覆盖已切换账号。
- Decision: 新增 `ensureFreshSession()`，按 JWT `exp` 的 30 秒窗口判定 freshness；与 `authFetch` 共用 module-level refresh promise，并按 `{userId, refreshToken}` 提交或丢弃结果。
- Rationale: auth module 是 access/refresh token 失效语义的唯一 owner；runtime 只消费 `ready/retry/signed_out`，不读取 refresh token。
- Evidence:
  - Tests: `npm run test -- src/features/auth/auth-session.test.ts src/features/auth/auth-fetch.test.ts`，2 files / 13 tests passed。
  - Entry: `authFetch` 真实公开 wrapper 的 401 重放测试与 `ensureFreshSession` 并发测试共用一次 refresh；浏览器 WebSocket 入口在 R3 真栈验证。
  - Frontend State Matrix: fresh、near-expiry、expired、network/5xx、refresh 401、A→B account switch 已覆盖。
  - Browser QA: R3 统一执行。
  - E2E/Regression: `src/features/auth/auth-session.test.ts` 覆盖 observable readiness contract；`auth-fetch.test.ts` 保持既有 HTTP 入口回归。
  - Visual/Interaction: N/A（无 UI/视觉变化）。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `5a5adaec` 恢复原 authFetch 私有 refresh 路径；C1 保留契约红测。
- Commits: C1=`519d6ec7`, C2=`5a5adaec`, C3=本提交。
- Next: R2 实现唯一 user-stream lifecycle。

## R2 — 单一 user-stream lifecycle

- Context: legacy Chat 与 desktop notifier 分别持有 socket，且 token、cursor、reconnect、resync 语义不一致。
- Decision: 在 `src/realtime/user-stream` 建立 transport-neutral runtime 与 production adapter；外部只暴露 `subscribeUserStream({onEvent,onRecovery})`，内部注入 session/socket/cursor/scheduler/sync ports。
- Rationale: 单一 lifecycle owner 隐藏 token、generation、resume、ping、backoff、cursor 与 sync，领域消费者只解释 raw event。
- Evidence:
  - Tests: `npm run test -- src/realtime/user-stream/user-stream.test.ts src/features/auth/auth-session.test.ts src/features/auth/auth-fetch.test.ts`，3 files / 21 tests passed。
  - Entry: production adapter 连接真实 `/im/ws/user`、发送 `resume`/`ping` 并用 authenticated `/im/v1/sync`；R3 在真浏览器签收。
  - Frontend State Matrix: first connect、retry/signed_out、reconnect、token/user generation、status 无 cursor、resync、last unsubscribe 已覆盖。
  - Browser QA: R3 统一执行。
  - E2E/Regression: `src/realtime/user-stream/user-stream.test.ts` 从公开 subscribe interface 驱动 fake socket/storage/session，覆盖单 socket、多 subscriber、bounded backoff、recovery 与 stale callback。
  - Visual/Interaction: N/A（无 UI/视觉变化）。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `e5c10806` 删除新 runtime；C1 保留 lifecycle 红测。
- Commits: C1=`f4c2f7d5`, C2=`e5c10806`, C3=本提交。
- Next: R3 迁移所有生产消费者、删除旧 stream、补 cache/ownership contract 并真栈签收。

## R3 — 消费者迁移与真栈签收

- 状态：DOING
