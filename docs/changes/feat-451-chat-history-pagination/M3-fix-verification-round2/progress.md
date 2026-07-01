# feat-451-M3 — Progress

## Baseline

- Context: 新 worker 接 round 2 verifier critical fix milestone；unit 分支已有 M1、M2、Round 2 acceptance pass、Round 2 verification critical 和 M3 design 行。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `1ffdbc31e616e99c08c9a8d9226897ffc14b01c8`.
  - Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-451-M3` from `origin/unit/feat-451`.
  - Initial narrow baseline failed before executing tests because the new worktree had no `node_modules` (`vitest: command not found`).
  - After `cd src/IM/frontend && npm ci`, baseline passed: `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` = 2 files / 99 tests, with existing React `act(...)`, route, and `--localstorage-file` warnings.
- Root-cause notes before implementation:
  - Conversation-switch leak: workspace renders `streamState.messages` directly even when `streamState.conversation_id` still belongs to the previous active conversation; new conversation heading can update before new history seeds the reducer.
  - Shared stream pollution: owner-scoped stream carries all conversations, while current dispatch path converts every chat event to `WsEvent`; reducer null state currently ignores created events only indirectly via `applyWsEvent` semantics. Active-conversation filtering belongs before dispatch.
  - Force-scroll leak: `commit()` sets `forceScrollToBottomRef` before `onSend`; if `onSend` throws or causes no append, the flag survives until the next unrelated `messages` change.
  - Anchor restore near-bottom: `restoreHistoryAnchor()` mutates `scrollTop` but does not refresh `nearBottomRef`, so a stale true value can make the next live message follow bottom incorrectly.

## R1 — 会话切换与共享流隔离

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

## R2 — 滚动状态 correctness 与门禁验收

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
- Next: TODO
