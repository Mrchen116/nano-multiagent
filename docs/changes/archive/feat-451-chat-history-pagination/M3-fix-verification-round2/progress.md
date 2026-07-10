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
- Commits: C1=`5315fd38`, C2=`371eca4b`, C3=`0e9f5ea3`
- Next: R2

## R2 — 滚动状态 correctness 与门禁验收

- Context: Code review confirmed two remaining scroll-state correctness risks: a local send request could leave `forceScrollToBottomRef` set when `onSend` fails or no local message is appended, and `restoreHistoryAnchor()` changed `scrollTop` without recomputing `nearBottomRef`, so the next live arrival could use stale bottom-follow state.
- Decision: `MessagePane` now accepts `selfUserId` from `ChatWorkspacePageV2` and only honors a force-scroll request when the last message changed and that last message is authored by the logged-in user. Synchronous `onSend` exceptions and `sendError` clear the flag, and every message-change pass clears the flag after evaluating it. `restoreHistoryAnchor()` now calls `updateNearBottom()` after moving the scroll position.
- Rationale: The send-scroll override is only valid for the optimistic/local user append caused by the send action; external arrivals after a failed/no-op send must fall back to the normal near-bottom policy. Recomputing near-bottom immediately after anchor restore keeps the live-arrival policy aligned with the actual DOM scroll position instead of a pre-prepend value.
- Evidence:
  - Tests:
    - `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx` passed before the R2 fix commit: 1 file / 77 tests, with existing React `act(...)` and `--localstorage-file` warnings.
    - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed at final verification: 2 files / 104 tests, with existing React `act(...)`, route, and `--localstorage-file` warnings.
    - `cd src/IM/frontend && npm run test` passed at final verification: 63 files / 589 tests, with existing React `act(...)`, localstorage, route, and query warning noise.
    - `cd src/IM/frontend && npx tsc -b` passed.
  - Entry: Chat workspace now passes `selfUserId` into `MessagePane`; local send append still forces bottom follow, while send failure/no append and external arrivals use the normal near-bottom gate.
  - Frontend State Matrix: error/submitting covered by send no-append and sendError/exception cleanup paths; default/loading/empty/missing nullable data covered by R1 delayed switch and shared-stream guard; desktop/mobile viewport covered by browser spot check.
  - Browser QA:
    - Predecessor artifacts existed in the worktree: `.feat451-m3-c1-snapshot.txt` and `.feat451-m3-c1-snapshot-2.txt` showed a real browser at `http://127.0.0.1:49522/chat/c609b21c647540b2917e897c240e910a` with seeded `M3 Planner`, `M3 Research Squad`, and `M3 Delayed Clean` conversations. Those artifacts also recorded unexpanded console warning/error counts, so they were treated as supporting evidence only.
    - Fresh spot check used isolated IM + Vite (`IM_PORT=53024`, `VITE_PORT=53025`) with a temporary SQLite DB and Playwright. Desktop viewport `1280x900`: opened `M3 Planner Spot`, switched to `M3 Research Spot`, verified `M3 c1 history 12` was absent from `.chat-pane-messages`, then switched back and injected a live message while reading history. Scroll position stayed `before=50`, `after=50`. Mobile viewport `390x844`: same chat route opened successfully.
    - Console/network observations from the fresh spot check: no product JS errors and no IM API request failures. Console contained Vite connect logs, React DevTools info, and WebSocket warnings caused by route reload/teardown during the spot check. Failed requests were Google font `woff2` aborts only.
    - The spot check cleaned its IM/Vite processes and temporary files before exit.
  - E2E/Regression: `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx` covers conversation switch old-message isolation and out-of-conversation shared stream filtering; `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx` covers send no-append stale force-scroll, local user append force-scroll, and anchor restore near-bottom recomputation.
  - Visual/Interaction: no CSS/layout changes; user-visible behavior is scoped to preventing cross-conversation messages and preserving the user's scroll position while reading history.
- Rollback: Revert C2 `cf137ead` and C1 `e8d31722` to restore previous force-scroll and anchor restore behavior; R1 rollback remains C2 `371eca4b` and C1 `5315fd38`.
- Commits: C1=`e8d31722`, C2=`cf137ead`, C3=this docs commit
- Next: Final docs commit, push milestone, merge into `unit/feat-451`, push unit branch, clean worktree/branch.

## Final Gate

- Scope check: code/test changes stayed within the M3 design row (`chat-workspace-page.tsx`, `message-pane.tsx`, `chat-workspace.integration.test.tsx`, `message-pane.test.tsx`) plus milestone `tasks.md` / `progress.md`.
- Final evidence:
  - `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx`: passed, 2 files / 104 tests.
  - `npm run test`: passed, 63 files / 589 tests.
  - `npx tsc -b`: passed.
  - Fresh isolated browser spot check: passed; no lingering PID/listening services from the spot check.
- Cleanup:
  - Removed untracked predecessor artifacts after extracting evidence: `.feat451-m3-browser.env`, `.feat451-m3-c1-snapshot.txt`, `.feat451-m3-c1-snapshot-2.txt`.
  - Removed stale dead PID files `.im-feat451-m3.pid` and `.vite-feat451-m3.pid`.
