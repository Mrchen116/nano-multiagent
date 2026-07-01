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

- Context: Round 2 verifier 发现切换会话时，active conversation heading 已变成新会话，但 reducer 里的 `streamState.messages` 仍属于旧会话；另外 owner-scoped user stream 在 reducer 尚未绑定会话时可能用外会话事件 seed 当前 pane。
- Decision: Workspace render path 新增 `visibleMessages`，只有 `streamState.conversation_id === conversationId` 时才把 reducer messages 传给 `MessagePane`，否则传空数组。共享 user stream 的 chat event dispatch 增加 active conversation guard：只有 `chatEvent.conversation_id === conversationIdRef.current` 才进入 reducer；所有会话的 message event 仍继续触发侧边栏 conversations refresh。
- Rationale: active pane 是一个 conversation-scoped view，不能在会话切换过渡态复用旧 reducer slice；同时 shared user stream 本来就是 owner-scoped，过滤应在 workspace 边界完成，避免把跨会话事件交给当前 conversation reducer 猜测处理。
- Evidence:
  - Tests:
    - Red: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx` failed on the two new regression cases: c2 delayed history still showed `Hi Planner`; c2 shared stream event seeded c1 pane before c1 history.
    - Green: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx` passed: 1 file / 27 tests, with existing React `act(...)`, route, and `--localstorage-file` warnings.
    - `cd src/IM/frontend && npx tsc -b` passed.
  - Entry: Chat workspace active pane now receives an empty message list during conversation switch until matching history or matching stream state is available; same-conversation live events still render through the existing shared stream path.
  - Frontend State Matrix: loading/empty/missing nullable data covered by delayed c2 history and unbound reducer shared stream regressions; desktop default active conversation render remains covered.
  - Browser QA: pending R2 combined true-browser spot check.
  - E2E/Regression: `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx` now covers delayed conversation switch old-message leak and out-of-conversation shared stream pollution before reducer seed.
  - Visual/Interaction: no CSS/layout changes; user-visible difference is that a newly selected conversation shows its empty/loading state instead of previous conversation bubbles.
- Rollback: Revert C2 `371eca4b` and C1 `5315fd38` to restore previous direct `streamState.messages` render and unfiltered shared stream dispatch.
- Commits: C1=`5315fd38`, C2=`371eca4b`, C3=TODO
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
