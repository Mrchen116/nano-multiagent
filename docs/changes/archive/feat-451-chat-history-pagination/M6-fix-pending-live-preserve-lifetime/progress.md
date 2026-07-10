# feat-451-M6 — Progress

## Baseline

- Context: 新 worker 接 Round 5 focused code-review finding。unit 分支已有 M1-M5 合并、Round 5 verifier/reviewer pass，以及新 M6 design 行；M6 只修 pending live preserve 生命周期，不扩大到 payload shape validation、测试拆分或 broad refactor。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `465f0e8d56bd0a480bb78c25cd0c08586cb90312`.
  - Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-451-M6` from `origin/unit/feat-451`.
  - Initial narrow baseline failed before executing tests because the new worktree had no `node_modules` (`vitest: command not found`).
  - After `cd src/IM/frontend && npm ci`, baseline passed: `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` = 2 files / 107 tests, with existing React `act(...)`, `--localstorage-file`, and route warnings.

## R1 — Pending live preserve 一次性生命周期

- Context: Round 5 focused code-review confirmed M5 still left pending live ids in `pendingLiveMessageIdsRef` unless REST history later returned that id. A same-conversation live row that raced with one messages fetch could therefore be preserved by every later reset even when server history continued omitting it.
- Decision: In `chat-workspace-page.tsx`, each reset snapshots `pendingLiveMessageIdsRef.current` into `preserveMessageIds`, dispatches the reset, then clears the pending set. The live row receives exactly one grace reset; future resets can converge active pane rows to REST history.
- Rationale: The pending set models a race window between a live event and the immediately following active messages response. Clearing the set after that reset keeps M4's live-before-history preservation while avoiding permanent immunity for rows the server never returns or later suppresses.
- Evidence:
  - C1 red: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx -t "clears pending live preserve ids after one history reset"` failed before the fix because `live row gets one reset grace` remained in the active pane after the second REST history reset omitted it.
  - Targeted regression: `cd src/IM/frontend && npx vitest run src/features/chat/v2/chat-workspace.integration.test.tsx -t 'clears pending live preserve ids after one history reset|removes a same-conversation relay mirror|renders a same-conversation message.created event|ignores shared stream chat events|keeps an active conversation live message'` passed: 1 file / 5 tests. This covers M6 one-reset cleanup, M5 relay mirror pruning, M4 live-before-history preservation, same-conversation live render, and external conversation isolation.
  - Required narrow: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed: 2 files / 108 tests. Existing warnings only: `--localstorage-file`, React `act(...)`, and route no-match for `/settings/agents/a-planner`.
  - Full frontend regression: `cd src/IM/frontend && npm run test` passed: 63 files / 593 tests. Existing warnings only: `--localstorage-file`, React `act(...)`, and route no-match.
  - Typecheck: `cd src/IM/frontend && npx tsc -b` passed.
  - Frontend State Matrix: default/loading/missing-data reset paths are covered by the new integration regression; mobile/desktop/browser visual states are N/A because M6 changes no layout, styles, controls, or viewport behavior.
  - Browser QA: N/A for this milestone; no visual or manual interaction behavior changed beyond reducer/reset state covered by integration tests.
  - E2E/Regression: No standalone e2e added; persistent regression is the active pane integration test that exercises the IM chat route, mocked REST history, and shared event stream.
  - Visual/Interaction: N/A; active pane rendering path is still exercised by Vitest/RTL assertions.
- Rollback: Revert `c801a4dc` and `ae25db04` together to restore the prior pending id lifetime and remove the M6 regression. Do not keep the test without the implementation; it intentionally fails on the old behavior.
- Commits: C1=`ae25db04`, C2=`c801a4dc`, C3=current docs commit (`docs(feat-451/M6): record pending live reset evidence`; see git log for final hash)
- Next: Rebase against latest `origin/unit/feat-451`, rerun required checks, merge milestone branch into `unit/feat-451`, push, then clean the milestone worktree and branch.
