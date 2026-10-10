# Code Review: refactor-581-dsh-personal-assistant

**Latest: Round 9 documentation/scope closure through `10ffd634bc75bac11cd9a18d655c95e0925aeea4` — prior source findings remain CLOSED; surviving findings `[]`.** Approval applies to the user's adjusted delivery scope. Physical iPhone UI remains unverified and explicitly deferred by the user; it is not recorded as passed.

| Metadata | Value |
|---|---|
| validated_at | `10ffd634bc75bac11cd9a18d655c95e0925aeea4` |
| executed_base | `4915c44cb7f7b829414a19087877ad9b73d69ea1` |
| effective_base | `4915c44cb7f7b829414a19087877ad9b73d69ea1` |
| effective_through | `10ffd634bc75bac11cd9a18d655c95e0925aeea4` |
| last implementation freeze | `88d49182b0cccfc2937bdc0a337dfe436f76be9d` |

Executed base identifies the original full-review range; runtime tests and product journeys retain the precise snapshots documented in their rounds. The documentation-only extension through the effective head does not claim those journeys were rerun there. `origin/main` remains the same base; no incoming implementation delta was found.

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

## Round 4 — capability catalog and native Skill preflight

Mode: `closure` with narrow patch review. Baseline: `7cf584b9a` (the previous `05036c240` source plus the inspected documentation corrections); frozen implementation: `34164e5e241b55bd674ffa0d7aedef4e83e2eb1f`. Reviewed the exact nine-file delta and direct capability, Feature, native Schedule and Web distillation consumers. The previous three findings stay CLOSED. **No new surviving maintainer-worthy finding; JSON remains `[]`.**

| Repair focus | Closure | Independent evidence |
|---|---|---|
| F6: Schedule candidates missing from Node/Agent catalogs | CLOSED at implementation/regression level | Node catalog and prompt-preview requests now use separate runtime RPCs. Catalog creates a fresh random preview Agent with all five Feature candidates and its own native Schedule service; prompt preview retains the requested selections. Actual Agent configuration is not changed. Capability/Cron regression files passed. |
| Temporary native owner isolation and cleanup | VERIFIED | Preview has a unique preset/session and hashed Schedule storage realm. Cleanup disposes the Agent and preset, then its native Schedule fiber, domain/JSON/storage fibers, and only the temporary owner's data directory. A real isolated RuntimeClient probe ran three disabled-Agent catalogs and one disabled-Agent prompt preview: catalog included schedule tools; the actual disabled Agent still had none; the separate enabled Agent retained all six native schedule tools; the exact Schedule-directory set was unchanged (1 before, 1 after). Runtime and private fixture were cleaned up. |
| F7: Web Generate Skill preflight still checked retired tool name | CLOSED at implementation/regression level | Preflight and accompanying instructions now require native `skill`; both enabled/disabled preflight cases use that name. The complete Web workspace integration file passed. Actual UI acceptance remains with the product reviewer. |

Independent commands: `pnpm exec vitest run packages/dsh-integration/tests/capabilities.test.ts packages/dsh-integration/tests/cron.test.ts` → **2 files / 4 tests passed (5.77s)**; frontend `pnpm exec vitest run src/features/chat/chat-workspace.integration.test.tsx` → **1 file / 54 tests passed (5.05s)**. The real-runtime probe also checked unchanged actual session capabilities after the repeated disposable catalog/preview calls, rather than inferring isolation from catalog contents alone. The patch continues to use public stock native Schedule/storage services; it adds no alternative scheduler or actual Feature-permission enablement.

No source/test/configuration/design edits or commit were made. Final independent product journeys and physical iPhone UI evidence remain an open acceptance gate; signed build/install does not close it.

## Round 5 — Skill usage response envelope

Mode: `closure` with narrow patch review. Frozen delta: `34164e5e241b55bd674ffa0d7aedef4e83e2eb1f → 0ddf25b8b42a7e2062a6cdc950f8411380cdef48`. F8 is CLOSED at implementation/regression level: the public Skill usage route now reads the Node RPC's existing `usage` member, matching `apps/node/src/main.ts` and the Web `SkillsUsageResponse` consumer. Identity/profile authorization and response fields remain unchanged. This restores actual usage rows/counts instead of taking the defaults from the outer response envelope. **No surviving finding; JSON remains `[]`.**

Independently ran `pnpm exec vitest run apps/im-server/tests/e2e/control-work.test.ts` → **1 file / 3 tests passed (4.29s)**. The new regression exercises actual HTTP and Gateway WS correlation, returns a nonempty archived Skill with `use_count: 20`, nonzero heatmap/health, and checks the entire public response. Parent reports the product reviewer also observed public API/Web rows and counts after restarting the isolated IM; final acceptance evidence remains owned by that reviewer. Earlier review and corrected-delta conclusions are retained. No implementation edit or commit was made.

## Round 6 — single-thread public sends and S04 boundary

Mode: `closure` with focused patch review. Frozen delta: `0ddf25b8b42a7e2062a6cdc950f8411380cdef48 → 0ca89aee67474d5014f92b04ebf24ace1307bd61` (five files). F9 is CLOSED at implementation/regression level. Shared product `send_message` and `conversations` now mount for single-thread Agents too; Inbox and global work/source instructions remain global-only. The native `agent_id/message` branch continues to invoke the captured native sender, while `target/text` uses the existing product bridge and identity checks. `target: current` resolves to the single-thread binding's actual conversation.

For an explicit send to that same internal Web group, the product owner obtains durable native events, refreshes input/turn evidence, then checks newer non-context-only NodeStore inputs before synchronous dispatch admission. Other conversations/channels retain their existing rules. A withheld publication remains keyed to the original call: after the correction's new native turn sends a revised message, retrying the old call still returns its held result. Global reconciliation and publication facts are retained unchanged. Reviewed direct store, automatic reply and product bridge consumers; **no new surviving finding, JSON remains `[]`**.

Independent command: `pnpm exec vitest run packages/dsh-integration/tests/communication-native.test.ts packages/personal-assistant/tests/global-agent.test.ts` → **2 files / 4 tests passed (1.08s)**. Parent's retained full-backend log `/tmp/refactor581-send-full.log` reports **50 files / 118 tests passed (20.89s)**; build/typecheck are parent-reported. The controlled-model RuntimeClient regression proves native tool dispatch into the product bridge; the NodeStore regression proves same-group correction hold/new-turn send/old-call replay. Actual S04 acceptance remains with the independent product reviewer, and physical-phone evidence remains open. No source/test/configuration/design edits or commit were made.

## Round 7 — single-thread IM conversation query admission

Mode: `closure` with focused patch review. Frozen two-file delta: `0ca89aee67474d5014f92b04ebf24ace1307bd61 → 38d6e5206bae3af38daca384c9e7d40303fe08ae`. Actual product revalidation found the downstream IM query still required a global Work journal session for single-thread calls, preventing their `target: current` send from reaching its correction check. This repair closes that concrete F9 path at implementation/regression level without changing the Round 6 native dispatch/NodeStore evidence.

`Work.query` first requires a non-stale Agent on the authenticated connection's Node. Global mode still requires that Agent's `global_main` session on that Node. Single-thread mode no longer requires a journal row it does not own. Every action still derives the accessible conversation set from the querying Agent's messaging identity: info/read reject targets outside that set, describe filters to it, and list/cursor projection uses it. **No surviving finding; JSON remains `[]`.**

Independently ran `pnpm exec vitest run apps/im-server/tests/e2e/control-work.test.ts` → **1 file / 3 tests passed (4.26s)**. The actual HTTP/WS fixture now confirms single-thread info for its own conversation succeeds and a different global Agent's private conversation returns `target_not_accessible`; retained global query and Skill-usage coverage also passes. Parent reports IM build passed. Actual S04 remains product-reviewer-owned; physical-phone evidence remains open. Only reports were edited, without implementation changes or commit.

## Round 8 — first proactive fallback notice routing

Mode: `closure` with focused patch review. Frozen four-file delta: `38d6e5206bae3af38daca384c9e7d40303fe08ae → 88d49182b0cccfc2937bdc0a337dfe436f76be9d`. F10 is CLOSED: model notices now follow the existing body-delivery rule for an unmaterialized owner conversation, sending `to_user_id` and adopting the real conversation returned by IM before later notices/body. Existing conversation bindings use their formal target. This removes the invalid virtual `owner:<id>` target from first-Heartbeat fallback without changing model selection or authorization. **No surviving finding; JSON remains `[]`.**

The parameterized regression covers both ordinary chat and owner-first Heartbeat, checking first owner-directed creation, subsequent formal conversation targeting, notice/body order and usage. The Python E2E helper now preserves the existing fallback/effort/Skill-selection fields while updating configuration. The IM test title accurately separates suspended-user revocation from a different owner's gateway disconnect; it registers the close listener before closing and polls for server-side identity expiration. Product authentication code is unchanged.

Independent command: `pnpm exec vitest run packages/personal-assistant/tests/model-fallback.test.ts apps/im-server/tests/e2e/server.test.ts` → **2 files / 6 tests passed (6.17s)**. Also inspected `.dsh-runtime/final-heartbeat-fallback-evidence.json`: one primary HTTP401 request, configured live `deepseek:deepseek-v4-flash` backup, three Agent messages (failure, switch, `HB_BACKUP_581` completed) in the same real conversation, with no preceding human message in that first-Heartbeat evidence. Parent reports **50 files / 119 tests passed (20.51s)** and build/typecheck passed. The product reviewer independently accepted S25 and records 30/33 passed; only S01/S17/S31 physical iPhone evidence remains inconclusive because the host Mac is locked. No implementation edit or commit was made.

## Round 9 — canonical promotion and authorized physical deferral

Mode: `closure`, documentation and scope only. Reviewed `88d49182b..c10650095` promotion plus the explicitly handed `c10650095..10ffd634b` Gateway-index correction. No product source, tests, dependency lockfile or CI workflow changed in that range. The eight promoted canonical files contain all **28** corrected delta Requirement bodies, identical after delta-marker removal and relative-link adjustment. README/SPEC/development/operations and retired Python Kernel/Coding CLI routing now describe Node + public stock DSH ownership. The one identified stale index description (`agent.sdk` in-process execution and independent Cron scope) is CLOSED by `10ffd634b`.

The user's exact physical-iPhone deferral is recorded in motivation's delivery-scope section and pending-decisions Q25. The independent product report retains **30 pass / 3 authorized-deferred** for only the physical portions of S01/S17/S31. Web and iPhone share IM HTTP/WS contracts, while Swift UI behavior remains unverified. This scope adjustment does not claim 33 passes, remove iOS automatic test/archive CI, or authorize production deployment. No new source finding; [code-review.json](code-review.json) remains `[]`.

No runtime matrix or full suite was rerun for documentation-only changes. Parent reports post-promotion docs-check **251 sources / 64 routes passed**, retained Python **51 passed / 31 deselected**, and iOS automatic test/archive still running. Archive/path-only handling and final CI results remain parent workflow work. Only the two assigned reports were edited; findings JSON was checked, and no implementation changes or commit were made.
