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
