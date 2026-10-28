# M1 implementation evidence

- Base: origin/main ff326c351d104447028f4b185740ab6d6be55de6.
- Implementation: ff9a2a39f; Node 24.22.1, pnpm 11.7.0.
- Baseline: original two owner suites 15 passed. New assertions against old implementation failed on graph `updated_by: Agent (a)` instead of human and done exploration scope timestamp remaining before dissolution. An earlier red run independently exposed persisted wait metadata. Local logs: `/tmp/task-closure-red.log` (final red), `/tmp/task-closure-baseline.log`.
- Green: `pnpm exec vitest run apps/im-server/tests/task-execution.test.ts apps/im-server/tests/e2e/conversation-tasks.test.ts apps/im-server/tests/task-collaboration.test.ts`: 3 files / 21 tests passed; `/tmp/task-closure-green.log`.
- `pnpm --filter @nano/im-server typecheck`: passed on identical product code (before last test-only assertions).

## Test ownership

- rewrite-merge existing task-execution dissolution test: genuine Messaging + TaskGraphService + SQLite, valid isolated Schedule inspection response. Verifies waiting/resume cleanup, user attribution, 101-node graph, exact unchanged done/closed stored nodes, completed graph revision, JSON/SQL audit consistency, no new task messages/receipts/activity, and post-COMMIT invalidation reread.
- Add same-owner failure/empty-group cases: SQLite trigger fails second graph after first update; all durable snapshots unchanged and no execution/membership publish. Empty group still dissolves without task messages/invalidation.
- Extend existing conversation-tasks E2E: real IM child process and HTTP/WS. Non-creator denied, done exploration scope selected candidate cleared with correct audit, result/reason retained, task history read-only, no new messages. WS `task_graph.command/get` serializes human actor/closed record through real Gateway route.
- Keep task-collaboration tests: distinct collaborative permission and notice risks. No new test files; no private-method/file-layout assertions.

## Context evidence and limits

Observed actual serialized WS task_graph.result on real IM: closed child carries `updated_by_actor.type=user`, `id=alice`; graph revision=3 and conversation.can_write=false. Integration renderer at packages/dsh-integration/src/features/task-graphs.ts uses JSON.stringify(result), unchanged; Web uses updated_by, iOS prefers updated_by_actor. No provider request or model semantic behavior was executed/claimed; no prompt or tool schema changed. Schedule inspection is controlled test evidence, not a claim that a production Schedule was canceled.

## Integration scope

Initial local main included unrelated a89b778/a34af8473 documentation commits absent from origin/main. Replayed only this unit's three design commits onto ff326c351; source review remains available through `git show a34af8473:docs/research/architecture-reviews/architecture-review-20261028-102827-a89b778.html` and local `/tmp/refactor-673-source-review.html`. No unrelated local documentation is bundled in this PR. Design Gate retained: target source, task specs and renderer unchanged by main integration. Shared-file integration points are the dissolution method in messaging.ts and the new TaskGraphService method; no Row/ImContext or canonicalJson changes.

## Local CI on 7a77516c0

- `pnpm build`, `pnpm typecheck`, `pnpm check:ios-runtime`: passed.
- `pnpm exec vitest run --maxWorkers=2`: 143 files / 774 tests passed in 424.89s (`/tmp/task-closure-tests-bounded.log`).
- `npm test --prefix src/IM/frontend -- --maxWorkers=1`: 108 files / 1029 tests passed (`/tmp/task-closure-frontend-bounded.log`).
- `npm audit --prefix src/IM/frontend --audit-level=critical`: exit 0; existing dependencies report 11 noncritical vulnerabilities (4 low / 2 moderate / 5 high), no dependency changes in this unit.
- Shared `.venv/bin/python -m pytest -m 'not e2e' -q`: 100 passed / 28 deselected. `ruff check .` and `ruff format --check .`: passed (91 files).
- `./scripts/docs-check` with shared venv Python: passed, 286 maintained Markdown sources / 68 required routes. Initial system Python lacked yaml; reran using repository's documented shared venv.
- Initial unrestricted parallel backend/frontend runs overlapped other worktrees' native tests and this worktree's builds, producing unrelated timing failures. Stopped only this worktree's test trees, removed four verified orphan test DSH children, then reran unchanged full suites at bounded concurrency; all passed. No test timeout/config/product changes used to pass.
- `./scripts/e2e-up.sh --profile daily`: ready using this build and independent worktree config/database/ports; independent product reviewer owns the acceptance report. No package publication occurred.

## Gate integration and final sync

- Design Gate: Approved, 0 CRITICAL / 0 WARNING, originally executed_base a34af8473 and validated_at be46c6e62; retained after replay onto ff326c351 because relevant task sources/specs/consumers are unchanged and the design artifacts were replayed verbatim.
- Code review / verification / corrected-delta: 7a77516c0, executed_base ff326c351; findings [], full consistency pass, corrected-delta aligned.
- Independent product acceptance: 7a77516c0, executed_base ff326c351; full pass, 0 issues. See acceptance.md for real HTTP/WS journey and synthetic historical precondition limits.
- Final fetch after all independent gates: origin/main remains ff326c351d104447028f4b185740ab6d6be55de6. effective_base is that SHA; effective_through is the final delivery head recorded in PR. Post-gate changes only consolidate evidence, merge the independently verified delta verbatim, and archive this unit. No product/test changes invalidate any gate; retain all three conclusions.
- Canonical task-graphs spec receives the reviewed Requirement delta; no corrected delta change after independent review, no new gate round needed.
