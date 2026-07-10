# bugfix-441-M3 — Progress

## Baseline

- Sync Gate: `unit/bugfix-441` and `origin/unit/bugfix-441` both at `57ac8bbe7aa13daebe2b7b545ba3103bb4255ceb`.
- Worktree: created `/Users/czj/Repos/nano-multiagent/.worktrees/bugfix-441-M3` from `origin/unit/bugfix-441` on branch `milestone/bugfix-441-M3`.
- Context read: `incident.md`, `design.md` M3 row, M2 `tasks.md` / `progress.md`, `design-review.md` findings, `docs/TESTING_GUIDE.md`, `AGENTS.md`, `CLAUDE.md`, `LOGBOOK.md`, existing renderer/tests.
- Baseline tests: first run failed because this fresh worktree lacked frontend dependencies (`vitest: command not found`); ran `npm install` in `src/IM/frontend` to restore local test tooling. Baseline `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx` -> 65 passed.

## R1 — failed start-detail rendering

- Context: M2 correctly preserved start-side `output` / `detail` / `emoji` when abnormal reconcile emits a synthetic failed tool completion. The frontend collapse row already sees top-level `call.status=failed`, but bespoke expanded cards only received `isRunning`; failed + start-side detail therefore fell through to completed rendering and showed `✓` / `completed` even though the row was red.
- Decision: Keep the existing parameter rendering path, but rename the card gate to `isResultPending`. `running` is always pending; `failed` is pending only when the known bespoke detail lacks terminal/result fields. Terminal failed details such as agent `{status,error}` and `success:false` memory/skill failures still render their existing failure bodies.
- Rationale: The root cause is at the renderer boundary, where `ToolCall.status` was not passed into card semantics beyond running. Treating failed parameter-only detail like running preserves the interrupted tool parameters without inventing fake error content, while terminal detail detection avoids regressing legitimate failed result cards.
- Evidence:
  - Tests: C1 red `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx` -> 4 failed / 65 passed. Failures showed exactly the bug: failed agent rendered `.chat-tool-detail-agent-result` with `✓ sub-agent completed`; failed memory/skill/task_stop rendered `✓` success heads.
  - Tests: C2 green `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx` -> 69 passed.
  - Tests: narrow final `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` -> 2 files passed, 87 tests passed. Existing React `act(...)` warnings in the approval-gate block remain as pre-existing test noise.
  - Build: `npm run build` -> passed (`tsc -b && vite build`), with existing Vite dynamic import/chunk-size warnings.
  - Entry: `ToolCallsPanel` expanded-body tests exercise the real React component with `ToolCall` payloads shaped like the IM frontend receives after Gateway/IM relay.
  - Frontend State Matrix: failed-with-start-detail covered for agent/memory/skill_manage/task_stop; running gate covered by existing running tests; completed success covered by existing memory/skill success tests; reducer completion replacement covered by `chat-stream-reducer.test.ts`.
  - Browser QA: Started Vite on `127.0.0.1:57858` with a temporary `bugfix-441-m3-qa.html` fixture that rendered real `ToolCallsPanel` failed start-detail examples. Playwright opened the page, expanded all four rows, asserted parameters visible and no `✓` / completed markers, checked no console error/warning and no failed/4xx requests, then captured `src/IM/frontend/output/playwright/bugfix-441-M3-failed-detail.png`. The temporary fixture was deleted before commit.
  - E2E/Regression: Permanent regression coverage is in `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx` under `ToolCallsPanel · failed calls with start-side detail`.
  - Visual/Interaction: Browser snapshot showed red failed rows; expanded agent row displayed only `Dispatch prompt` + prompt text. Script verified memory action/target/content, skill action/name, and task_id remained visible without success markers.
- Rollback: Revert `63fb97ee` to remove implementation, and revert `28bd5733` to remove failed start-detail regression tests.
- Commits: C1=`28bd5733`, C2=`63fb97ee`, C3=this docs commit
- Next: Rebase on `origin/unit/bugfix-441`, rerun narrow vitest, merge into `unit/bugfix-441`, push, and clean milestone worktree/branch.
