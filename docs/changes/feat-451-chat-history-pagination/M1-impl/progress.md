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
- Commits: C1=`c689b124`, C2=`452d9f2f`, C3=TODO
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
- Commits: C1=`767ce6fe`, C2=`30809ad4`, C3=TODO
- Next: R3

## R3 — 消息菜单、移动端 fork 与真实浏览器验收

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: TODO
- Next: Milestone integration
