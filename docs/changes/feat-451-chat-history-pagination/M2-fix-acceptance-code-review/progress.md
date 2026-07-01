# feat-451-M2 — Progress

## Baseline

- Context: 新 worker 接 round 1 fix milestone；unit 分支已有 M1、verification pass、acceptance fail 和 M2 design 行。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `dcbeb1636f9547663b3d23ba0062820b86c0e59e`.
  - `cd src/IM/frontend && npm run test`: initial run failed because worktree had no `node_modules` (`vitest: command not found`); after `npm ci`, baseline passed: 63 files / 575 tests, with existing React `act(...)` and `--localstorage-file` warnings.
  - `cd src/IM/frontend && npx tsc -b`: passed.
- Root-cause notes before implementation:
  - Realtime blocking: current page has two separate user stream paths. `openChatStream` opens a raw socket once from `useAuthStore.getState()` and does not share the existing resume/ping/reconnect machinery in `attachUserConversationStream`; tests seed auth before render, masking real browser timing and recovery. The correct architecture for open-chat bubbles is to consume the same shared user stream and filter current conversation events.
  - Mobile menu major: long-press opens menu from `touchstart` timer, but document `mousedown` outside handling and lack of touch/pointer ownership make release/tap fragile in real mobile browsers; no regression currently exercises release before selecting. Copy failure is explicitly fire-and-forget and closes the menu.

## R1 — 实时消息与历史分页状态正确性

- Context: 修复 reviewer blocking 的同会话新消息不可见问题，以及 code review confirmed 的 history anchor 泄漏、同 cursor 重复请求、metadata unknown 误显 no-more 三项 correctness bug。
- Decision: 当前聊天气泡不再开启独立 `openChatStream`；改为复用 `attachUserConversationStream` 的 owner-scoped 用户流，把 `message.*` / tool / thinking / permission 事件转换为 `WsEvent` 后交给同一个 reducer。历史分页改为三态 `hasMoreHistory`（unknown / true / false），并用同步 `historyRequestRef` guard 同一会话同 cursor 的并发请求；会话切换时同步 reset loading / cursor / request / MessagePane anchor refs。
- Rationale: 共享用户流已经承载侧边栏刷新、resync、node/agent status，且具备真实浏览器需要的 owner token 生命周期；会话内气泡沿用该通道可消除双 socket 分叉。历史分页的 bug 都源于仅靠 async React state 表达“正在请求”和把 unknown 折叠为 false，必须用同步 ref 和明确 unknown 状态建模。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed: 2 files / 95 tests. New red→green coverage includes shared user stream same-conversation append, duplicate older-history guard, conversation-switch unknown metadata, MessagePane anchor reset, and MessagePane unknown metadata no-more suppression.
  - Entry: `ChatWorkspacePageV2` now consumes live message events through shared user stream; `MessagePane` receives `hasMoreHistory` as boolean/null.
  - Frontend State Matrix: loading/empty/missing nullable data covered by targeted component/integration tests; desktop/mobile scroll-follow still covered by existing MessagePane tests.
  - Browser QA: pending R2 C3 combined true-browser run for reviewer blocking/major scenarios.
  - E2E/Regression: `cd src/IM/frontend && npx tsc -b` passed.
  - Visual/Interaction: no visual asset changes; scroll behavior regressions covered by MessagePane tests for off-bottom no disturb and bottom follow.
- Rollback: Revert `0e831b65` and C1 test commit `2d32b995` if the shared stream conversion causes live event regressions; this restores the previous independent `openChatStream` path and previous history state semantics.
- Commits: C1=`2d32b995`, C2=`0e831b65`, C3=`70e281f5`
- Next: R2

## R2 — 移动菜单、Copy 失败反馈、桌面 Enter 与浏览器验收

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
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: Milestone integration
