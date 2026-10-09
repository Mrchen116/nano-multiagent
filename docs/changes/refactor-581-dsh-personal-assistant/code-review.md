# Code Review: refactor-581-dsh-personal-assistant

**Latest: Round 3 closure at `05036c240307fef56adf2ed1aa55e9af241cf58f` — prior findings remain CLOSED; surviving findings `[]`.** The historical full-review result below applies only to its original frozen snapshot. This is code-review approval for the repair scope, not completion of independent product or physical-device acceptance.

Round 1 · full · **Changes required**

Frozen implementation: `4915c44cb7f7b829414a19087877ad9b73d69ea1 → e89179da8956577b288ee374fe791c2ce82d5047`.

The machine-readable result is [code-review.json](code-review.json): **3 CONFIRMED findings**, no PLAUSIBLE findings. The two P1 defects concern execution liveness and the retained client usage schema; the P2 defect concerns public execution readiness after DSH recovery.

## Scope and interpretation

Reviewed the new semantic owners: product contracts; Node configuration, lifecycle, provider and device-binding/migration entrypoints; DSH public profile/RPC/session/preset/event/history/approval/fallback/capability integration; all five independent Feature lifecycles; Workflow host/guest controls, prefix state, catalog and accounting; knowledge maintenance; PA single-thread/global Inbox, session controls, delivery/outbox and channel ownership; Feishu parsing/transport/credentials; native IM identity, configuration operations, media, messages, gateway delivery, Work and task-graph projections; retained Web/Swift consumers; tests, CI and legacy-test disposition. Deleted Python implementation was examined through retained invariants and replacement owners rather than mechanically reviewing retired implementation lines.

Applied the approved migration decisions: stock DSH `0.2.1-alpha.1`, public interfaces, native tool names, native schedules to the parent conversation, no old-chat conversion, and retirement of the old Python kernel/Coding CLI. Canonical spec merge/archive is a later workflow step and is not reported as a source defect. Physical iOS acceptance is owned by the product reviewer, not this code review.

Only the frozen commit was reviewed. Parent-owned uncommitted repairs and documentation updates are excluded and require a precise patch/closure handoff.

## Independent confirmation

1. **Watchdog:** created an isolated native IM server and temporary database, shortened its own timeout to 0.05 seconds/interval to 0.01 seconds, inserted one quiet execution and one pending approval. Both became failed despite the fresh approval wait. The resulting content was `relay idle for 0.05s with no new event`. The actual timeout is 120 seconds. Source confirms no replacement runtime producer for `run_heartbeat`; node connection heartbeat is a different fact. Server and temporary data were removed.
2. **Usage:** transpiled and executed the frozen `presentation.ts` without loading the modified working-tree file. Native input=100/cache=50/output=20 projected `{prompt:150,completion:20,total:170,cache_read:50,cache_total_input:150,context_window:128000}`. The retained client calculation yielded NaN (JSON serializes it as null); accessing `usage.output.toLocaleString()` produced a TypeError.
3. **Readiness:** started a real isolated node with stock DSH and a private empty-agent config, killed only its owned runtime PID 33272, and observed replacement 33287. State still recorded `{ready:true,runtime_pid:33272}` and public status returned `RUNNING pid=33254 ready=true DSH=33272`. CLI stop completed and the private fixture was removed.
4. Independently reran `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest tests/contract/test_runtime_dependency_contract.py -q`: **8 passed**. The worktree-local `.venv` is absent; the shared repository interpreter was used. Other retained integration test results are mapped in [verification.md](verification.md), not represented as independently rerun here.

No source/test/configuration/design edits or shared-tree commit were made by this reviewer.

## Round 2 — precise repair closure

Mode: `closure`. Finding origin and patch base: `e89179da8956577b288ee374fe791c2ce82d5047`; validated implementation: `3014fe8cd76df81f34fb756eaebefe205b4051ad`. Reviewed the initial `bbbaee580` repair delta plus the explicitly supplied `bbbaee580..3014fe8cd` partial-usage repair and direct callers/consumers, without reopening the full branch. The six-area design/response-metrics delta is committed in the latter snapshot and reconciled separately by verifier.

| Original focus | Closure | Evidence |
|---|---|---|
| P1 watchdog / C1 | CLOSED | Runtime emits `session.liveness` every 15 seconds only for an actual running bound native Agent; PA forwards only that session's sending deliveries with a real bubble ID. Existing IM heartbeat events refresh the watchdog. Independent native-profile quiet-model test and actual-process IM approval/heartbeat/heartbeat-loss test passed. Permission waits follow the same liveness contract; there is no permanent exemption for a dead owner. |
| P1 token schema / W1 | CLOSED | `presentation.ts` emits `context_used/output/cache_read_tokens/cache_total_input_tokens`; Work and Feishu consumers use those fields. Web/Swift retain unknown counters rather than invent zero. Independent product projection/store/fallback regressions and all seven TokenChip tests passed. Parent retained actual token-usage HTTP/WS critical-path evidence applies to this repair. |
| P2 stale readiness/PID / W2 | CLOSED | Supervisor loss, failed initialization and shutdown call `onUnavailable`; lifecycle clears readiness and runtime PID. Successful initialization plus product recovery updates the actual replacement PID. Independent real SIGKILL lifecycle regression observed unavailable then ready with the replacement PID and public status. |

Also reviewed the bounded accompanying repairs: center capability endpoints consume the nested `capabilities` response envelope; Workflow read returns lossless JSON, failed native children retain diagnostics, and tool instructions clarify inherited effort. The native Workflow real-tool `read` regression passed. These repairs restore the existing contract and introduced no surviving maintainer-worthy finding in the reviewed scope.

Independent command: `pnpm exec vitest run apps/node/tests/lifecycle.test.ts apps/im-server/tests/e2e/server.test.ts packages/dsh-integration/tests/runtime-profile.test.ts packages/dsh-integration/tests/workflow-native.test.ts packages/personal-assistant/tests/single-thread.test.ts packages/personal-assistant/tests/model-fallback.test.ts packages/personal-assistant/tests/store.test.ts` → **7 files / 16 tests passed (19.65s)**. Frontend focused command `pnpm exec vitest run src/features/chat/components/token-chip.test.tsx` → **1 file / 7 tests passed (577ms)**. Tests used their existing isolated fixtures and completed cleanup. No code edits or commit were made by this reviewer.

Latest machine-readable findings are [code-review.json](code-review.json): `[]`. Historical findings remain available in the committed Round 1 report/JSON at `bbbaee580` and the narrative above.

The precise `3014fe8cd` addition also closes persisted partial-usage display: optional `context_used/output` fields cannot produce NaN or an expansion TypeError; absent counters render `—` and unsupported percentages are suppressed. This uses the canonical field names without aliases for the former erroneous payload. Independently reran the updated TokenChip file: **8 tests passed**. The 16 backend checks above remain applicable because this addition changes only three frontend files and the two reviewed unit documents.

## Round 3 — native Cron product projection

Mode: `closure` with accompanying narrow patch review. Retained implementation baseline: `3014fe8cd76df81f34fb756eaebefe205b4051ad`; latest frozen source/docs snapshot: `05036c240307fef56adf2ed1aa55e9af241cf58f`. The source addition in `7690ae4ae` maps native catalog `title/prompt/status` into existing Web/Swift jobs fields `name/instruction/enabled`, preserves session identity for deletion, and forwards `result.deleted === true` rather than the truthiness of a native response object. Reviewed the unchanged IM `/cron/jobs` routes and actual client consumers. **No new surviving code finding; JSON remains `[]`.**

Independently executed `pnpm exec vitest run packages/dsh-integration/tests/cron.test.ts`: **1 file / 2 tests passed (6.21s)**, including the real native catalog-to-product jobs view and existing Agent isolation/cold-recovery cases. Parent's build/typecheck results are retained. Product reviewer owns actual Web list/delete confirmation and its acceptance report; a passing runtime regression does not substitute for that UI observation.

Also inspected the eight-area corrected delta and two parent-owned precise documentation corrections after the frozen commit: routing prose now uses unified approval liveness; Cron capability prose uses `schedule_create` and still restricts other `schedule_*` tools to the allowlist. The accompanying two Cron subtitle strings describe the already approved original-conversation context behavior and add no execution semantics. Canonical preparation remains a local plan, not completed merge/archive. Reports only were edited; no commit or implementation edit was made by this reviewer.
