# feat-451-M1 — Progress

## Baseline

- Context: M1 开始前按 worker 流程确认现有前端基线。
- Evidence:
  - `cd src/IM/frontend && npm run test`: 63 files / 560 tests passed，存在既有 React `act(...)` warning 与 `--localstorage-file` warning。
  - `cd src/IM/frontend && npx tsc -b`: passed。

## R1 — 历史分页与阅读位置保持

- Context: 初始 chat v2 只取最近一页消息，MessagePane 在 `messages` 任意变化时无条件滚到底部，导致无法通过向上滚动看到更早历史。
- Decision: 在 workspace 内维护 50 条分页 cursor/loading/hasMore 状态，首屏显式 `limit=50, markAsRead=true`，更早页用 `beforeMessageId` 且不 mark read；内联 `streamReducer` 新增 `prepend_history` 合并分支。MessagePane 在 `scrollTop <= (scrollHeight - clientHeight) / 3` 时触发 `onLoadOlder`，顶部显示 loading/no-more 状态，并在 loading 前后通过 `data-message-id` anchor 恢复阅读位置。
- Rationale: 延续 design 的手动 cursor 方案，避免把现有 REST+WS reducer 合并模型迁到 `useInfiniteQuery`。Anchor 用消息 id 而不是高度差作为主路径，能在 bubble 高度变化时更稳定；高度差仅保留为 anchor 不存在时的 fallback。实现中发现 prepend 恢复后同一轮 `messages` effect 会再次滚底，根因是自动滚底 effect 没区分“历史 prepend 后的恢复”与“普通新消息”，因此增加一次性 skip 标记跳过该轮旧自动滚底。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-api.test.ts src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` → 3 files / 94 tests passed. `cd src/IM/frontend && npx tsc -b` → passed.
  - Entry: Component/integration entry covered `/chat/:conversationId` render path with fake WS + real React Query fetch calls; full browser entry deferred to R3 milestone QA after all UI pieces land.
  - Frontend State Matrix: loading and no-more history indicators covered; default message list and empty state covered by existing tests; mobile/desktop viewport visual checks deferred to R3 browser QA.
  - Browser QA: Deferred to R3 after R2/R3 interactions land, so one browser session can cover pagination + composer + menu together.
  - E2E/Regression: Added regression coverage in `chat-api.test.ts`, `chat-workspace.integration.test.tsx`, and `message-pane.test.tsx`. Red state before C2: 4 failures for missing load trigger, anchor restoration, top history status, and older-page fetch.
  - Visual/Interaction: Top loading/no-more CSS and i18n landed; screenshot evidence deferred to R3 browser QA.
- Rollback: Revert `452d9f2f` after `c689b124` to remove R1 implementation while keeping red tests, or revert both R1 commits to restore pre-R1 behavior.
- Commits: C1=`c689b124`, C2=`452d9f2f`, C3=`e8eae8d3`
- Next: R2

## R2 — 智能滚底与 composer 输入行为

- Context: R1 解决历史 prepend 后，剩余体验问题是旧 `messages` effect 仍把普通新消息无条件滚底；移动端 Enter 被旧的 `!isMobile` 条件排除；移动端 composer 固定 1 行。
- Decision: MessagePane 维护 near-bottom 状态、last message id、刚发送消息 force-bottom 标记。消息变化时仅在初次 hydration、用户已在底部附近、或本地刚发送时滚到底部；用户滚到历史中间时新消息不抢位置。Enter 发送逻辑移除 `!isMobile` 限制，slash picker 打开时仍拦截 Enter 让 picker 接管。Composer rows 按草稿行数增长，移动端 1-4 行、桌面 2-5 行，超过上限后 textarea 内部滚动。
- Rationale: 滚动策略必须区分“用户正在看历史”和“用户正在跟随底部”。near-bottom ref 由真实 scroll 事件维护，避免每次 render 误判；本地发送单独 force-bottom，符合 spec 中“用户自己刚发出消息时应看到最新内容”的口径。Rows 直接来自受控 draft 行数，和现有 mention mirror 同步，不引入新依赖。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx` → 1 file / 65 tests passed. `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-api.test.ts src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` → 3 files / 100 tests passed. `cd src/IM/frontend && npx tsc -b` → passed.
  - Entry: Component/integration entry covered real `/chat/:conversationId` React path for send and WS append behavior; full browser entry deferred to R3 combined QA.
  - Frontend State Matrix: default, long content, mobile input, desktop Shift+Enter, bottom/off-bottom scroll states covered by regression tests; browser viewport checks deferred to R3.
  - Browser QA: Deferred to R3 after menu/fork lands.
  - E2E/Regression: Added `message-pane.test.tsx` cases for off-bottom no auto-scroll, near-bottom auto-scroll, mobile Enter send, desktop Shift+Enter newline, slash picker Enter ownership, mobile composer auto-grow. Red state before C2: 3 failures for off-bottom scroll, mobile Enter, mobile rows; slash picker ownership already passed after correcting the expected behavior.
  - Visual/Interaction: CSS max-height/overflow for composer landed; screenshot evidence deferred to R3 browser QA.
- Rollback: Revert `30809ad4` after `767ce6fe` to remove R2 implementation while keeping R2 tests, or revert both R2 commits.
- Commits: C1=`767ce6fe`, C2=`30809ad4`, C3=`6debd8e6`
- Next: R3

## R3 — 消息菜单、移动端 fork 与真实浏览器验收

- Context: R1/R2 已完成历史分页、智能滚底和 composer 输入行为后，剩余缺口是消息级菜单：复制没有统一入口，移动端没有 hover，现有 fork 按钮虽在 DOM 中但移动端不可达。
- Decision: 在 `MessageBubble` 内新增受控菜单状态。桌面端 `contextmenu` 打开菜单并提供 Copy；移动端通过 600ms 长按打开菜单，touch move 超过 10px 取消以避免滚动误触。菜单固定定位并按视口夹取，always 提供 Copy；移动端 direct agent 完成回复且有 `kernel_message_id` 时额外提供 fork。桌面端 hover fork 按钮继续按原 CSS 显示，移动端不渲染 hover fork 按钮，fork 只走长按菜单。
- Rationale: 保持桌面既有 hover fork 交互，最小化用户可见变更；移动端没有 hover，因此将 fork 放入长按菜单才能满足可达性。菜单状态放在每个 bubble 内，避免提升到 MessagePane 造成跨消息复杂状态；Copy 使用 `navigator.clipboard.writeText`，失败时不阻塞菜单关闭，符合轻量操作菜单预期。
- Evidence:
  - Tests: Red before implementation: `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx` → 3 expected failures for missing desktop menu, mobile copy menu, mobile fork menu. After implementation: same command → 1 file / 68 tests passed. Combined targeted check: `npm run test -- src/features/chat/v2/chat-api.test.ts src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` → 3 files / 103 tests passed. `npx tsc -b` → passed.
  - Entry: Browser opened real Vite entry `/chat/c1` with route-level IM fixtures: initial history response 50 messages and `next_before_message_id=h-11`; older-history response 10 messages and `next_before_message_id=null`; real React Router, React Query, MessagePane, CSS, keyboard and clipboard paths were exercised.
  - Frontend State Matrix: default/history list, no-more after older page, desktop right-click menu, desktop hover fork, desktop Shift+Enter, desktop Enter send, mobile Enter send, mobile auto-grow, mobile long-press copy, mobile long-press fork all covered. Error UI remains N/A for this milestone because design did not introduce a history-load error surface.
  - Browser QA: `Vite http://127.0.0.1:50839/chat/c1`; desktop viewport `1366x900` result: older request `GET /im/v1/conversations/c1/messages?limit=50&before_message_id=h-11`, 60 message rows after prepend, right-click Copy wrote `Agent reply 60`, hover fork computed display `flex`, Shift+Enter value `Desktop line\n`, Enter send cleared composer, no console/page errors. Mobile viewport `390x844` result: initial rows `1`, multi-line rows capped at `4`, Enter send cleared composer, long-press Copy wrote `Agent reply 60`, mobile hover fork button count `0`, long-press fork POST payload `{ "fork_message_id": "h-60" }`, no console/page errors. Screenshots were generated during QA under worktree-local `output/playwright/` and not committed; viewport/result evidence above is the retained artifact.
  - E2E/Regression: Added `message-pane.test.tsx` coverage for desktop right-click copy, mobile long-press copy, and mobile long-press fork. Existing `message-pane-fork.test.tsx` remains the desktop hover fork regression suite.
  - Visual/Interaction: Menu styling added in `global.css` as a compact fixed overlay with 8px radius, keyboard focus state, disabled state, and viewport-clamped placement; i18n added `copy` in en/zh.
- Rollback: Revert `c779dab7` after `c8dcfb27` to remove R3 implementation while keeping red tests, or revert both R3 commits. No backend contract changes.
- Commits: C1=`c8dcfb27`, C2=`c779dab7`, C3=this docs update
- Next: Milestone integration

## Final Exit Criteria Evidence

- `[reviewer]` >50 history pagination: Component/integration tests prove first request uses `limit=50, markAsRead=true`, scroll threshold is `scrollTop <= (scrollHeight - clientHeight) / 3`, and older request uses `limit=50&before_message_id=<cursor>`. Browser QA on `/chat/c1` confirmed `before_message_id=h-11` and 60 rendered rows after loading earlier messages.
- `[reviewer]` reading position and no-more behavior: `message-pane.test.tsx` covers anchor restoration after prepend and loading/no-more status rendering; R1 fix added skip of the next auto-scroll after anchor restore to prevent jumping to bottom.
- `[reviewer]` smart bottom behavior: `message-pane.test.tsx` covers no auto-scroll when user is reading history and auto-scroll when user is near bottom; local send uses a force-bottom flag.
- `[reviewer]` composer behavior: `message-pane.test.tsx` covers mobile Enter send/clear, desktop Shift+Enter newline, slash picker Enter ownership, and mobile auto-grow to 4 rows. Browser QA confirmed desktop Shift+Enter retained newline and Enter sent/cleared, plus mobile Enter sent/cleared and rows capped at 4.
- `[reviewer]` message action menu/fork: `message-pane.test.tsx` covers desktop right-click Copy, mobile long-press Copy, mobile long-press fork. Browser QA confirmed desktop Copy clipboard text, desktop hover fork displayed, mobile hover fork not rendered, mobile long-press fork POST payload.
- `[worker]` `cd src/IM/frontend && npm run test`: 63 files / 575 tests passed. Existing warnings observed: React `act(...)`, Vitest `--localstorage-file`, one existing query-data warning in an unrelated agent detail test; no test failures.
- `[worker]` `cd src/IM/frontend && npx tsc -b`: passed.
