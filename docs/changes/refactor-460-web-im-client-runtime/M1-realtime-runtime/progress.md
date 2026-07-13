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

- 状态：DONE
- Context: 五类生产消费者原本分散持有 legacy/v2 stream 或依赖旧 cache；收尾必须同时证明唯一连接 owner、账号隔离与真实恢复旅程。
- Decision: Chat、toast、desktop notifier、Nodes、Agents 统一订阅 `subscribeUserStream()`；AppProviders 按 user id 清 QueryClient；删除 legacy stream 与 `v2/chat-stream.ts`；用 ownership contract 阻止第二 owner 回流。
- Rationale: transport lifecycle 只由 runtime 管理，领域 subscriber 只负责 mapper/reducer/cache 决策；token refresh 与 account switch 采用不同 cache 语义。
- Scope expansion: 真浏览器暴露测试 helper 的 opaque `test-token` 会强制走 refresh，并在并发页面测试中制造无关 401。经 orchestrator 批准，将 `render-router.tsx` 的共享 token 改为结构合法、长期有效的 test JWT，并同步一处精确 Authorization 断言；未扩大生产范围。
- Evidence:
  - Tests: `npm run test`，65 files / 630 tests passed；`npm run build` passed；`pytest -q tests/contract/test_im_frontend_user_stream_ownership.py`，2 passed。
  - Entry: contract 证明生产源码只有 runtime 构造 `/im/ws/user` WebSocket；legacy/v2 stream 实现和测试已删除。
  - Frontend State Matrix: 当前会话、后台会话 toast、desktop notification gates、Node/Agent status、token refresh、logout/account switch、desktop/mobile 均有 regression 或真浏览器证据。
  - Browser QA: `evidence/live-browser-report.md`；真实 Gateway/LLM 回复、expired access + valid refresh、Gateway offline/online、浏览器 offline/online、应用内 toast、移动端、A→B 隔离均通过。
  - E2E/Regression: 稳态仅一个 browser user-stream；refresh 401→200 重放后仍收到新事件；未观察历史通知重放。
  - Known unrelated issue: IM 共享 SQLite 连接偶发 500 后重试成功，已登记 #191，不在前端 M1 内修复。
  - Visual/Interaction: N/A（无设计变化；仅回归既有 UI）。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `aa0227bd` 恢复消费者旧路径；R1/R2 runtime 可独立保留，C1 契约测试用于暴露回退缺口。
- Commits: C1=`90bb0a27`, C2=`aa0227bd`, C3=本提交。
- Next: M1 合入 `unit/refactor-460` 后由 orchestrator 进入 reviewer/verifier gate，再决定是否启动 M2。
