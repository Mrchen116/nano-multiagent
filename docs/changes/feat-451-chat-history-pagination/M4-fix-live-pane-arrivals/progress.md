# feat-451-M4 — Progress

## Baseline

- Context: 新 worker 接 round 3 acceptance blocking / verifier W1 fix milestone；unit 分支已有 M1、M2、M3 和 round 3 verification/acceptance 记录。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `072058ddaa291a645131f84b86da3d7de7cf998b`.
  - Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-451-M4` from `origin/unit/feat-451`.
  - Initial narrow baseline failed before executing tests because the new worktree had no `node_modules` (`vitest: command not found`).
  - After `cd src/IM/frontend && npm ci`, baseline passed: `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` = 2 files / 104 tests, with existing React `act(...)`, `--localstorage-file`, and route warnings.
- Systematic debugging notes:
  - Round 3 symptom: sidebar preview updated after same-conversation live messages, but active pane did not show them; browser console showed user-stream WebSocket handshake failures.
  - Current workspace only drives active pane from the shared user stream. If that event path drops/misses a message, conversations refetch can still update sidebar preview, while the reducer-backed pane remains stale.
  - M3 also left a transition window: c1 -> c2 allows c2 event through the active-conversation guard, but the reducer can still be scoped to c1 and drop it before c2 history resolves.
  - Root fix belongs at the chat workspace active-conversation state boundary: bind the reducer to the newly selected conversation immediately, and make history reset preserve same-conversation live messages already accepted during the loading window.

## R1 — Active conversation live event 不丢

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
- Next: TODO
