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
