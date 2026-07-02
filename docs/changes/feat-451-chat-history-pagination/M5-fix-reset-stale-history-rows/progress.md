# feat-451-M5 — Progress

## Baseline

- Context: 新 worker 接 Round 4 code-review confirmed correctness issue。unit 分支已有 M1-M4 合并和 Round 4 verifier/reviewer pass；M5 只修 reset stale row correctness，不扩大到测试文件拆分。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `64561477eedbe35673c5558c9b532c6e7d562cce`.
  - Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-451-M5` from `origin/unit/feat-451`.
  - Initial narrow baseline failed before executing tests because the new worktree had no `node_modules` (`vitest: command not found`).
  - After `cd src/IM/frontend && npm ci`, baseline passed: `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` = 2 files / 106 tests, with existing React `act(...)`, `--localstorage-file`, and route warnings.

## R1 — Reset 收敛并保留 pending live rows

- Context: Round 4 code review confirmed that M4's reset merge preserved every same-conversation row from old reducer state. That kept the live-before-history race fixed, but also kept rows the backend intentionally stopped returning, including synthetic `:relay:` mirror messages suppressed once a real agent row exists.
- Decision:
  - Added an integration regression where initial REST history contains a synthetic `turn-1:relay:relay-dup-1` row, then a same-conversation event triggers a messages refetch whose REST response returns the real agent row and omits the synthetic mirror. The active pane must remove the mirror.
  - Changed `streamReducer` reset semantics to converge to the REST response by default. It still merges existing metadata for IDs returned by REST, but it only carries missing existing rows across reset when their IDs are explicitly listed in `preserveMessageIds`.
  - Added `pendingLiveMessageIdsRef` at the workspace boundary. Same-conversation `message.created` rows accepted while the active messages query is fetching are marked as pending live rows and may survive the next history reset, preserving M4's live-before-history fix without keeping arbitrary stale history rows.
- Rationale:
  - REST history is the authority for which persisted history rows should currently be visible; frontend reset should not outvote backend suppression/dedup rules.
  - M4's race requires preserving only rows that arrived through the live stream during the active history request window. Making that set explicit separates transient live rows from old rows that the server has deliberately removed from history.
  - External-conversation events are still filtered before dispatch, and synthetic `:relay:` live `message.created` IDs are still ignored by `applyWsEvent`, so the new preservation path does not reopen cross-conversation pollution or relay-mirror insertion.
- Evidence:
  - Tests:
    - C1 red: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx -t "removes a same-conversation relay mirror"` failed because the old synthetic relay mirror remained visible after refreshed history returned the real agent row.
    - Targeted green: `cd src/IM/frontend && npx vitest run src/features/chat/v2/chat-workspace.integration.test.tsx -t 'removes a same-conversation relay mirror|keeps an active conversation live message|ignores shared stream chat events'` passed: 3 tests.
    - Required targeted suite: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed: 2 files / 107 tests.
    - Full frontend: `cd src/IM/frontend && npm run test` passed: 63 files / 592 tests.
    - Typecheck: `cd src/IM/frontend && npx tsc -b` passed.
    - Final after rebase on `origin/unit/feat-451`: targeted suite passed (2 files / 107 tests), full frontend passed (63 files / 592 tests), and `npx tsc -b` passed.
  - Entry:
    - `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
    - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`
  - Frontend State Matrix:
    - default: refreshed REST history prunes suppressed same-conversation relay mirror rows.
    - loading/empty: existing c2 delayed-history regression confirms c2 live row appears while history is pending and survives empty history reset.
    - missing/nullable data: external events remain filtered; reset accepts an empty explicit preservation set.
    - desktop/mobile: real browser spot check opened the chat pane through Vite/IM; no layout/styling changes.
  - Browser QA:
    - Isolated services: IM `127.0.0.1:51740`, Vite `127.0.0.1:51741`, DB `.feat451-m5-im.sqlite3`.
    - Seeded user `feat451m5`, conversation `004942b8fae04dd59f604163c8feeabc`, and message `M5 browser history convergence check` through the real IM HTTP API.
    - Browser: Playwright + Chromium, route `http://127.0.0.1:51741/chat/004942b8fae04dd59f604163c8feeabc`; active pane rendered heading `M5 Browser Check` and one `.chat-bubble` containing the seeded message.
    - Console/network: one Vite-origin user-stream websocket proxy warning (`ECONNREFUSED 127.0.0.1:8021`) and one Google Fonts abort were observed; IM HTTP history/conversations/nodes/agents requests returned 200 and the active pane rendered correctly.
    - Cleanup: stopped IM/Vite exec sessions and removed local token/DB/log/PID/screenshot artifacts.
  - E2E/Regression:
    - New regression: `removes a same-conversation relay mirror when the refreshed history suppresses it`.
    - M4 retained: `keeps an active conversation live message that arrives before the switched conversation history resolves`.
    - External isolation retained: `ignores shared stream chat events for other conversations before the active conversation history seeds the reducer`.
  - Visual/Interaction:
    - No visual or interaction surface changed. Browser spot check verified the chat pane still renders via the real route; screenshot was temporary evidence and removed after recording.
- Rollback: Revert `73d87215` to restore the previous reset merge behavior and `42aa6cd4` to remove the new regression test; `88aa1f77` and the final docs commit are documentation-only.
- Commits:
  - `88aa1f77 docs(feat-451/M5): plan reset stale history fix`
  - `42aa6cd4 test(feat-451/M5/R1): cover stale relay mirror reset`
  - `73d87215 fix(feat-451/M5/R1): prune stale reset rows`
- Next: COMPLETE. Ready to merge into `unit/feat-451` and clean milestone worktree/branch.
