# Code Review — bugfix-660-shared-agent-lifecycle

Final result at `6769c89cb`: full review plus the bounded patch rounds below, surviving findings `[]`. Required Context and independent product evidence are now complete; see final verification Round 4. Earlier evidence limits are preserved as historical snapshots.

## Scope and result

- reviewer: `/root/shared_static_review`, independent of implementation.
- mode: full; executed base `5b09dbe82` (`origin/main` at dispatch), validated implementation `60514ca8f`.
- Reviewed the net `origin/main..6a78d0253` implementation, then the complete fixes `6a78d0253..60514ca8f`. Intermediate rollback/restore commits cancel out and were not treated as final behavior.
- Read `incident.md`, `design.md`, `design-review.md`, lifecycle delta, current service-lifecycle spec, `SPEC.md`, testing and Context Engineering requirements.

Surviving code findings, in the change-code-review JSON format:

```json
[]
```

This is a code-correctness conclusion. Required real provider Context and product milestone evidence are tracked separately in `verification.md`; an empty findings array does not certify those missing checks.

## Confirmed defects closed during review

1. `apps/node/src/main.ts:85`: the initial shared implementation skipped ordinary Knowledge/Workflow consumer registration while `onReady` dereferenced those consumers. This caused startup failure and prevented ordinary delivery. `5ca2abaa4` registers the ordinary consumers and keeps the pre-406 ordinary delivery IDs by leaving `partitionKey` undefined. Inspected all registration/recovery call sites; the owner also reproduced the startup failure in the isolated daily stack before fixing it.
2. `packages/dsh-integration/src/index.ts:754`: a rejected disable Promise was retained forever. A managed Job taking over the 4.5-second wait could settle later, but subsequent retry and enable would still receive the cached rejection. `60514ca8f` drops only rejected work that failed before scope disposal starts. Unknown cleanup after destructive scope disposal remains unconfirmed. The real Job regression in `agent-disable-native.test.ts:90` passes together with the existing cleanup-throw case: `/Users/czj/.codex/reports/bugfix-660/shared-retry.log`, 2 passed, 4 intentionally unselected.

## Coverage

- Node partition and admission routing, session/root lineage, scoped collections and ACKs, approval routing, crash generations, management reads, lifecycle synchronization and per-Agent confirmation.
- Public DSH `AgentHandle` create/resume/dispose ownership, admitted creation coalescing, exact-cut fork with `buildForkSeed`, native Schedule resolution through the same owner, child-first native drain and owner-scoped Bash/PTY cleanup. Checked installed DSH's public SessionController fork implementation and exports; no private import or runtime patch introduced.
- Per-Agent revisions and cold inbox fences, selective persisted model/command/Knowledge/Workflow cancellation, Cron admission/skip-missed behavior, Task gating, late callback/result suppression, preservation of ordinary home and PA binding/epoch homes.
- Deletion of per-Agent migration/control/cold-history infrastructure, corresponding retired tests, retained native trajectory/history/fork protection, topology/spec changes and the two feat-657 correction notices. Web/iOS implementation is unchanged by the net diff.
- Reused the supplied native tests and inspected their assertions and logs. Initial focused failures are not reported as passes: Workflow's transient record issue was corrected and rerun; B's empty-history native compaction correctly reports no replaceable range and its final selective-owner test passes in `shared-cold-owner.log`.

## Agent Context Implementation Review

Mode B applies because product root creation/resume/fork and automatic recovery change the lifetime of model-visible Context.

Source and deterministic native coverage: `owned-sessions.ts:18` mounts the original revision preset inside public factory setup; `index.ts:235` attaches the effective history/configuration/approval/model policy before publishing live Agents; `owned-sessions.ts:53` uses DSH's fork seed builder and retains inherited offsets, cwd, preset and parent identity; `runtime-lifecycle.ts:17` clears a restored inbox only once per persisted disable fence. Schedule inputs and Task reminders carry the correct product Agent revision. Model/Workflow/Knowledge persisted work is filtered by trusted binding or native descendant lineage, rather than by model-supplied owner fields. Existing fork/history and cold-inbox tests exercise preservation across restart; real same-host A/B native tests exercise isolation, including descendants and managed shells.

At this review snapshot no real-provider request/response locator has yet been delivered for post-enable history and preset consumption. Source, previews and stub/native fixtures cannot establish what the real model received or understood. That is an explicit unverified milestone item, not a fabricated Context defect. No new model-required owner parameter, tool schema, Skill or system-prompt wording was introduced by this diff.

## Round 2 — bounded patch and Context evidence closure

- review_mode: patch; range `60514ca8f..f10168318`; retains the complete Round 1 findings/coverage through `60514ca8f`.
- Source delta: exactly `main.ts`, `agent-lifecycle.ts`, and the two parameterized lifecycle cases in `agent-lifecycle.test.ts`. No independent implementation or tests were written by this reviewer.
- Patch findings:

```json
[]
```

The empty-node startup branch starts the ordinary management host only with no configured Agents, so it cannot bypass the populated-node authoritative lifecycle barrier. The existing real CLI start/status/runtime-crash/stop/PID-identity case passes after the fix (`shared-empty-node.log`, 1 pass). This closes the only deterministic failure in the two-worker backend run, whose other 732 tests passed. The final identity-report fix changes reporting, not cleanup evidence: local proof still uses the actual current shared host and prior cleanup evidence, while the disabled center report retains the last execution identity required by `apps/im-server/src/agent-lifecycle.ts:122`. Both cleanup-confirmed and cleanup-unknown cases were RED before the fix (`shared-reconnect-red.log`) and pass with the affected Node+IM lifecycle suite (`shared-reconnect-green.log`, 12 pass). It therefore does not turn an unknown prior cleanup into disabled merely because a new management host started.

### Actual Context and model behavior

Independently read only the three precise upstream provider payloads named by `/Users/czj/.codex/reports/bugfix-660/context-evidence.md`; no unrelated or production logs were searched. The payloads are in `/Users/czj/Repos/LLM_PROXY/logs/raw/openai_codex/`, filenames `2026-10-25_23-25-56_737-upstream-req-anthropic_messages.json`, `2026-10-25_23-26-39_091-upstream-req-anthropic_messages.json`, and `2026-10-25_23-26-49_902-upstream-req-anthropic_messages.json`.

These are actual Responses upstream inputs for `gpt-6.1-sol`, high, root `a943501a-fbf1-4434-960f-53d6b082e7bd`, daily P. Compared complete `input[0]` system objects and complete tool schema arrays, not only names: they are exactly equal before/after dispose/resume, with 24 tools. Read the system's daily-role/workspace and global Inbox/source/delivery rules. The retained `input[8]` Inbox result carries the original synthetic code and `sender.type=user`; `input[9:11]` contains the original `send_message` call and sent receipt. After resume, `input[18]` contains the new human recall question without the code. `context-lifecycle.json` confirms disabled revision 2 / enabled revision 3 on the same shared host; `context-messages.json` confirms the model's remembered-code response was delivered under revision 3. This closes the earlier real Context evidence gap for root create→dispose→resume, preset/history/source preservation and actual consumption.

Limits: this probe does not establish all-model/tool reliability or a real-provider fork/child run. Existing native history/fork and same-host child/Job/PTY tests cover those mechanisms. The bounded Node startup/report patches add no model-visible Context surface. Product acceptance Round 2 remains a separate pending gate at the time of this addition.

## Round 3 — cold stopped Work history patch

- review_mode: patch; range `f10168318..6769c89cb`; previous full/patch conclusions retained.
- Findings:

```json
[]
```

Independent product Round 2 exposed R2-1: offline disable after graceful Node shutdown left a cold P execution displayed Running because the newly started host had no live P Agents and returned empty stop history. The patch collects persisted history only for trusted bindings belonging to the disabled product Agent, skips already captured live roots, observes cold roots through public SessionQuery and existing DescendantReader, and respects inherited offsets and supplied root/child cursors. It reuses durable tool presentations and model projections, then feeds the existing `GlobalAgent.recordStopped` projection without generating inputs or notifications to the model. Inspected `tool-presentation.ts:50` and `global-agent.ts:752` to verify the cold-read-to-Work path and that neither path activates an Agent.

`shared-cold-stop-red.log` records the new native test failing on `history: []`; `shared-cold-stop-green.log` records all 16 affected native disable, PA lifecycle and trajectory tests passing. The new case verifies durable `turn/end` retrieval after restart and that the root creation count remains one. Actual user-visible Work reconciliation is being independently checked in product Round 3; no pass is inferred from the regression fixture alone.

Context impact: read-only projection of already durable history. No change to LLM request assembly, tools, identity, preset, admission or resume behavior; the preceding actual-provider probe remains applicable. No additional real-model task is needed for this non-activating read path.

## Final evidence closure

The completed independent product `regression.md` Round 3 passes at `6769c89cb`, closing both reconnect and cold Work issues. Independently inspected its actual screenshot (`product/r3-disabled-interrupted.png`) and native-history text: all four Agents Disabled, P Idle, old execution Interrupted, earlier Completed turns retained, history readable. This resolves the earlier product evidence limitation. No code changed after Round 3; final code findings remain `[]`. The native ownership fixtures and the separate actual-provider root Context probe retain their explicitly different evidence scopes.
