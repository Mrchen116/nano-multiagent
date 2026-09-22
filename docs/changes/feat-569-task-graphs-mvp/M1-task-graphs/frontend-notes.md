# Frontend implementation notes

## Scope and consumers

Implemented in the shared unit worktree on `codex/feat-569-task-graphs`, based on `499774a56`. This subtask owns only `src/IM/frontend/` and this note. IM / PA implementation and real-stack product acceptance remain with the orchestrator.

- `/tasks` offers permission-filtered goals, conversation filtering, submitted name search, and cursor pagination. `/tasks/:graphId?scope=...&node=...` restores a precise scope and selection, and rejects invalid locations without silently changing targets.
- Desktop and mobile shell navigation include Tasks. Each Chat header links to that conversation's goals; count requests use `limit=1` and the agreed additive `total` field.
- The graph consumes the authenticated `view=all` document. Containment defines scopes, dependencies define DAG edges, and derivation defines exploration edges. The scope layout keeps distinct fork/join ports and top lanes for direct cross-column edges, following the corrected P2 prototype. Details list direct prerequisites/successors and derivation separately.
- The desktop layout retains the goal sidebar, graph and node detail. Mobile uses the existing bottom navigation, a goals dialog and a bottom detail drawer; closing a selected detail removes only the node parameter and preserves graph scroll. Zoom and selection survive same-revision rereads. Both nesting directions, explicit choices, dropped directions, long results and leaf empty states are represented.
- Visible pages reread every three seconds, with focus and manual refresh. Transient read failures keep the old graph with an explicit stale warning; 403/404 replace cached task data with unavailable state, including cached list titles. Unknown schema versions are rejected rather than interpreted as version 1.
- Return to chat appends a Markdown task deep link to the home conversation's existing composer snapshot and preserves existing text, mention metadata, attachments and slash state. It does not send, seed-replace a draft, or start an Agent.
- No creation/editing forms or prototype simulation controls were added. All product labels use existing zh/en i18n and palette tokens.

## Test ownership and validation

Existing ownership was located first: `app-shell.test.tsx` protects desktop/mobile navigation; `message-pane-composer-draft.test.tsx` protects draft restoration, mention and attachment state; `chat-workspace.integration.test.tsx` and route/source-navigation tests protect Chat assembly. Those protections are retained. The shell test is extended for the new Tasks destination, and MessagePane takes a presentational `headerActions` slot so existing composer callers do not gain a query dependency.

The new `task-graphs.test.tsx` is the task-domain browser-component seam. Six tests use HTTP-schema fixtures to cover complete direct relationships, nesting/deep links and reread stability, stale-versus-forbidden cache behavior, actual MessagePane draft restoration without send, mobile drawer closure, invalid locations, and filtered/search/paginated empty lists. These are component/API-consumer tests, not real-stack browser or model acceptance.

Validation on 2026-09-22:

- `npm --prefix src/IM/frontend ci`: completed using the lockfile. npm reported 7 dependency advisories; no dependency versions or lockfile were changed by this task.
- `npm --prefix src/IM/frontend test -- task-graphs app-shell message-pane-composer-draft`: **3 files / 25 tests passed**.
- `npm --prefix src/IM/frontend run build`: **passed** (TypeScript and Vite). Vite reports the existing large-bundle advisory; `dist/` is not committed.
- `npm --prefix src/IM/frontend test`: **84 files / 776 tests passed**. The suite emits existing act()/mock stream environment diagnostics, plus asynchronous task-count act() diagnostics in older Chat fixtures; there were no failed tests.
- `git diff --check -- src/IM/frontend`: passed.

## Remaining acceptance boundary

No real services, production instance, browser or model were started by this subtask. P1–P6 desktop 1440×960 / mobile 390×844 screenshot comparison, actual IM ACL changes, live Agent tool updates, static deep-link fallback, and the full S01–S20 journey require the orchestrator's isolated real stack. Automated fixture tests are not presented as that evidence.
