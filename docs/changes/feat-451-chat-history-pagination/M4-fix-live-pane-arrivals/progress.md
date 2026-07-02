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

- Context: Round 3 reviewer blocking showed same-conversation live arrival could update the sidebar preview while the active pane stayed stale. Round 3 verifier W1 showed c1 -> c2 switching could drop a c2 live event if it arrived before c2 history reset bound the reducer.
- Decision:
  - `chat-workspace-page.tsx` now binds the stream reducer to the newly selected `conversationId` immediately with an empty reset, so active-conversation live events during history loading are accepted instead of being dropped by the previous conversation scope.
  - History reset now merges already accepted same-conversation stream messages with the REST history response and sorts the result, preserving live messages that arrived before the history response.
  - Shared user stream metadata events (`message.sent`, `message.created`, `relay.completed`) invalidate the active messages query when their `conversation_id` matches the current pane, so REST-created `message.sent` arrivals refresh the open pane as well as the sidebar.
- Rationale:
  - `message.sent` from the IM REST create-message path carries enough metadata to refresh conversation previews but not enough content to build an active-pane message directly, so the pane must refetch active messages for the same conversation.
  - The reducer must be scoped to the route's active conversation before the first history response, otherwise the verifier W1 race is decided by stale reducer state.
  - Keeping same-conversation stream rows across a later history reset avoids trading one race for another; external conversation rows remain rejected by `applyWsEvent` and by the active conversation guard.
- Evidence:
  - Tests:
    - C1 red: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx` failed only the two new regressions:
      - `refreshes the active pane when a same-conversation message.sent event updates the sidebar preview`
      - `keeps an active conversation live message that arrives before the switched conversation history resolves`
    - C2 green: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx` passed: 1 file / 29 tests.
    - Targeted regression: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed: 2 files / 106 tests.
    - Full frontend: `cd src/IM/frontend && npm run test` passed: 63 files / 591 tests.
    - Typecheck: `cd src/IM/frontend && npx tsc -b` passed.
  - Entry:
    - `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
    - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`
  - Frontend State Matrix:
    - default: same-conversation `message.sent` refreshes active pane and sidebar.
    - loading/empty: c2 history delayed while c2 `message.created` arrives first; active pane shows c2 live row and never leaks c1 rows.
    - missing/nullable data: reducer null/mismatch scope remains guarded.
    - desktop/mobile: real browser evidence covered desktop live-arrival scroll states and mobile pane visibility.
  - Browser QA:
    - Isolated services: IM `127.0.0.1:55293`, Vite `127.0.0.1:55294`, DB `.feat451-m4-im.sqlite3`, seeded one user conversation with 75 historical messages.
    - Browser: Playwright + system Chrome, route `http://127.0.0.1:55294/chat/adada716e93e4d31842625487a66f9f9`.
    - Off-bottom live arrival: posted `M4 live off-bottom 1782956483445`; active pane and `.chat-sidebar` both showed the text. Scroll metrics stayed off-bottom: before `{scrollTop: 2505, bottomDistance: 260}`, after `{scrollTop: 2505, bottomDistance: 328}`.
    - Bottom live arrival: posted `M4 live bottom 1782956483658`; active pane and `.chat-sidebar` both showed the text. Scroll metrics followed bottom: before `{bottomDistance: 0}`, after `{bottomDistance: 0}`.
    - Mobile spot check: viewport `390x844` reopened the same chat and active pane showed `M4 live bottom 1782956483658`; metrics `{scrollTop: 2720, bottomDistance: 0}`.
    - Network/console: no non-font request failures. Console contained Vite debug lines and transient user-stream WebSocket handshake/reconnect warnings during page load/reload; the live-arrival assertions still passed through the shared stream/refetch path.
    - Cleanup: stopped `.feat451-m4-im.pid` / `.feat451-m4-vite.pid`, closed the PTY service session, and removed local token/DB/log/env files.
  - E2E/Regression:
    - Kept M3 protections covered by existing integration tests: no old conversation rows before switched history returns, external stream events do not enter active pane, send failure and history-anchor behavior remain covered by the targeted suite.
  - Visual/Interaction:
    - No layout/styling files changed. Browser checks focused on active pane visibility and bottom/off-bottom scroll behavior.
- Rollback: Revert commits `5307e6ac` and `c5549ad0` to remove the code/test changes; `5e40d55b` and the final docs commit are documentation-only.
- Commits:
  - `5e40d55b docs(feat-451/M4): plan live pane arrival fix`
  - `c5549ad0 test(feat-451/M4/R1): cover live pane arrival regressions`
  - `5307e6ac fix(feat-451/M4/R1): keep active pane live arrivals`
- Next: Re-run final validation after rebasing on `origin/unit/feat-451`, then merge `milestone/feat-451-M4` into `unit/feat-451`.
