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
