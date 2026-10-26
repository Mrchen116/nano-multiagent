# Code Review: feat-665-general-personal-agent

Current code verdict: **Round 4 patch review requires a fix at `085b1b896`**: one CONFIRMED / WARNING finding (CR-04). Earlier full-review findings and closures remain historical; V-01 evidence collection remains pending.

## Snapshot and verdict

- review_mode: `full`; independent implementation reviewer; Context mode: **Implementation Review**.
- executed_base: `85910853e`; validated_at: `783ff080f4a110780d78473e95d0bc391c64c50f`.
- Reviewed the complete unit range, including the preceding memory, attention, artifact and eval commits, rather than only the last integration commit (83 files; 6323 insertions / 202 deletions).
- Initial checkout: `codex/feat-665-general-pa`, clean, HEAD matches validated_at. No source/test/config/design mutations, production operations or new services by this reviewer.
- Verdict: **changes required**. Three surviving findings, all `CONFIRMED / WARNING` (P2); no PLAUSIBLE findings. Historical machine-readable results: [code-review-r1.json](code-review-r1.json).

## Coverage

Read AGENTS.md, docs map, architecture, current Gateway/IM PA and Task contracts, applicable capability rules, testing and Context engineering/observation guidance, the unit spec/design/design-review/deployment-prompt and four delta specs. Traced the changed implementation across:

1. Memory source authority → record transaction/revision/idempotency/tombstone → bounded projection/search/get → root and maintenance injection → next safe boundary/forget rollover → child invalidation, notes/history fences and cold-state persistence. Non-PA file semantics and maintenance read-version guards were included.
2. Source queries/independent cursors → fresh coverage receipts/watermarks → private attention/settings/budget → trusted live-input, Schedule and Task reply classification → native and external owner delivery receipts → published interactive revision/feedback idempotency. The ordinary owner-private path is included.
3. Task schema/canonical revisions → native catalog/input acceptance → persistent execution reference → per-Task running suppression/correction/withdrawal → real interrupt/drain. Minimal task/observer tool/configuration scopes, handoff files, source/private tool guards and disabled selections were included.
4. Real workspace bytes → publish_artifact → existing authenticated upload → media idempotency/hash/version → protected IM resource link → existing reviewed external-copy path. Default custom_prompt, 12 domain Skills, Feature dependencies and existing user configuration preservation were inspected.
5. The 58 scenario catalog/adapters, actual-result classification, checkpoint receipts, evidence capture, independent adjudication and baseline comparison protocol were inspected. `collect --cases all` independently resolves 58 cases and performs zero live actions.

No new architecture boundary violation was found. Independently ran `python -m pytest -q tests/contract/test_runtime_dependency_contract.py tests/e2e/general_personal_agent/test_protocol.py`: **24 passed in 0.69s**.

## Context evidence and limits

Source review includes the combined System Prompt/tool/Skill rules and runtime assembly/refresh/guard chain. Reused actual native-subprocess evidence supplied with the frozen version: `/tmp/pa665-memory10.log` (memory/forget/notes/history/restart), `/tmp/pa665-native-test3.log` (Task native binding/coordinator/withdrawal), `/tmp/pa665-observer-test2.log` (task/observer delivery scope), `/tmp/pa665-context-test7.log` (independently selected tools and real snooze Schedule), `/tmp/pa665-schedule-test.log` (creation provenance and actual wake across restart). These use scripted `llm/stream` providers. They prove native dispatch/assembly and guards at their tested seams; they do **not** prove final serialized provider wire input or independent model choices.

At report capture, nine `/tmp/pa665-runs-v2/*/results/result.json` files existed, covering baseline/candidate M01/M02 and D08. They report `execution_complete=true`, `status=not_run`, `diagnostic=evidence_needs_review`, and no adjacent `adjudicated-result.json`. Real model journeys are useful raw evidence, not accepted behavior results. No independent provider-input adjudication or browser journey was supplied to this review. Remaining milestone evidence is separately recorded in [verification.md](verification.md), rather than invented as code defects.

## Independent reproductions

All data below is synthetic. Built modules from the frozen version were called directly; temporary workspaces were removed, in-memory SQLite closed. The snippets below describe the exact public calls and outputs and are sufficient to repeat them without modifying repository tests.

### R1 / CR-01 — fresh owner correction A → B → A

Construct `PersonalMemoryStore` with a fresh workspace and `{ownerId:'owner',agentId:'pa',bindingId:'binding'}`. Call `execute(upsert)` three times, using distinct verified owner sources `fresh-owner-1/2/3`, distinct keys, `kind=preference`, `subject_ref=owner`, `certainty=confirmed`:

| Call | Content | Existing identity |
|---|---|---|
| 1 | I prefer trains | New record |
| 2 | I prefer flights | Call 1 record ID, expected_revision=1 |
| 3 | I prefer trains | Same ID, expected_revision=2 |

Actual call 3: `Memory source/content was forgotten or superseded; replay refused`. Current search still returns `I prefer flights`. No forget action or stale source is involved. The unconditional hash check at `personal-memory.ts:236` rejects a legitimate new owner correction.

### R2 / CR-02 — identical body, independent subjects

In a fresh Store, upsert two records with content `Does not eat seafood`: subject `owner` citing verified `source-owner`, and subject `partner` citing verified `source-partner`. Forget only the first record ID at revision 1 with key `forget-owner`.

Actual current search: `remaining=[]`. The independent partner record is removed and tombstoned by `personal-memory.ts:253`, which treats same body as the same fact regardless of subject/domain/applicability. Expected remaining subject is `partner`.

### R3 / CR-03 — same feedback, next turn

Use compiled `PersonalAttention` with real `node:sqlite` `DatabaseSync(':memory:')`. Persist a first `pa_attention_mutations` row with canonical payload:

```json
{"action":"snooze","id":"item-1","expected_revision":1,"idempotency_key":"same-logical-feedback","owner_instruction_id":"owner-message","snoozed_until":"2026-10-27T00:00:00.000Z","exploration_batch_id":"root:10"}
```

Persist its result as `{id:'item-1',revision:2,schedule_status:'pending'}`. Replay `command` for the same binding and exact business arguments, changing only host field `exploration_batch_id` to `root:20`. Actual error: `attention_idempotency_conflict`.

This is the payload the integration deterministically generates at `personal-context.ts:26` after a new native turn. At `personal-attention.ts:135-139`, host batch metadata participates in the full canonical payload. In the real snooze chain the first business commit precedes Schedule creation, so a failed Schedule leaves the persisted pending row but the next turn cannot retry it with the advertised stable key. Keep host budget metadata outside business retry identity, while retaining budget accounting.

## Stopping point

Relevant code paths and confirmed reproductions are covered. No speculative review loop or source repair was performed. Fix these three mechanisms and request patch/closure review of the resulting delta. Final real-model, browser and milestone evidence can be supplied separately; it must remain version-bound.

## Round 2 — closure of CR-01 / CR-02 / CR-03

- review_mode: `closure`; finding_origin_head: `783ff080f4a110780d78473e95d0bc391c64c50f`; validated_at: `860eb4ecbfee8982dafa2a7c50afe5ab3b30fd65`.
- Scope: only the three reported mechanisms and their associated regression tests; no speculative expansion. The rest of R1 full review is retained because the fix delta changes only scoped tombstones, attention payload identity and corresponding tests.
- Independently ran `pnpm exec vitest run packages/dsh-integration/tests/personal-memory.test.ts apps/im-server/tests/personal-attention.test.ts`: **22/22 passed**; log `/tmp/pa665-independent-closure.log` (2026-10-26 19:49 Asia/Shanghai).

| Finding | Fix and independent evidence | Outcome |
|---|---|---|
| CR-01 | Superseded protection now checks matching subject/domain/applicability scope and old sources, while a fresh source at current revision can restore the earlier value. Regression rejects stale source, then accepts fresh A→B→A with revision=3. | closed |
| CR-02 | Tombstones now retain a scope hash; duplicate removal matches scope as well as content. Regression preserves partner and distinct-applicability same-text facts, and subsequently updates the partner record. Existing same-fact duplicate/previous-version erasure still passes. | closed |
| CR-03 | `exploration_batch_id` is removed from canonical mutation identity but remains available to count first creations against the batch. Regression replays the same pending snooze and key with a different host turn batch, receives the original pending result, then completes its Schedule receipt. | closed |

Final findings: `[]`. Closure does not establish real provider-wire input, browser journeys or the incomplete milestone evidence. No source/tests/design were modified by the reviewer.

## Round 3 — focused patch after real acceptance findings

- review_mode: `patch`; executed_base: `4d5ef9c9c`; validated_at: `d41425170f0f1226ce51b71d77072cee040bd9d3`.
- Scope: five-file delta for direct-reply attention publication identity, cold PA catalog registration order, and evaluation settlement. R1 full coverage and R2 closures remain applicable outside this delta. No source, test, config or design edits by the reviewer. Caller-owned untracked `acceptance.md` was read for the original failed journey and preserved unstaged.
- Findings: `[]`; no surviving CONFIRMED or PLAUSIBLE defect in the reviewed patch. This is source/seam verification, not the pending actual Web regression verdict.

| Focus | Reviewed mechanism and evidence | Result / limit |
|---|---|---|
| Real attention-card dismiss failure | `deliveryCheck` now resolves/validates an optional item/revision before reply classification and retains item identity in direct_request, Schedule and Task branches. The existing prepare → Messaging publication → saved message/item revision → feedback path can therefore recover the clicked item. Test now runs both exploratory and direct-request publication, including cross-key duplicate click and stale-card rejection. | Independently passed. R1's real failure remains historical evidence; repaired Web click journey still pending. |
| First catalog on fresh empty runtime | Built-in personal registration is before optional workspace extension HMR wait. Independently exercised the updated real native test: `initialize(agents=[])` → first `configuration.catalog` must contain personal_sources/context/attention/publish_artifact → apply → actual chosen-tool calls and native snooze Schedule. Existing selection assertions remain. | Independently passed; catalog fix does not imply every workspace plugin or actual model's discovery is verified. |
| D08 capture truncated at acknowledgement | Runner checks latest turn (`limit=1`, Work API orders seq DESC) for every visible child and rejects settlement while status is running/waiting_permission. Root revision changes reset the five-second stability window. | Deterministic probe below passes; no replacement of pending D08 actual run/adjudication. |

Independent commands: `pnpm exec vitest run apps/im-server/tests/personal-attention.test.ts packages/dsh-integration/tests/personal-context.test.ts` → **11 passed** (`/tmp/pa665-independent-round3.log`); `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py` → **11 passed in 0.35s**.

Additionally invoked the real `Run.settle` function with a synthetic client and patched clock/read-only get seam (no source mutation): root idle + acknowledgement from t=0, child running until t=3, waiting_permission until t=5, then completed; root revision changes at t=7. It returns only at **t=12**, after 13 actual child-view reads, respecting both child completion and the reset stability window. A second probe keeps the child running despite an acknowledgement and gets **TimeoutError at t=4**, never a false settled return. This verifies harness control flow; it is not real product/LLM evidence.

Provider capture note: the caller reports shared proxy logging became unavailable at 19:46. Capturing the actual serialized HTTP body at the isolated Node outbound boundary is a valid next observation seam when collected with version/model/session/role provenance; this review does not count a proposed capture as observed provider input, upstream receipt or successful model consumption.

## Round 4 — focused source/forget/recovery delta

- review_mode: `patch`; Context mode: focused **Implementation Review**.
- executed_base: `d41425170f0f1226ce51b71d77072cee040bd9d3`; validated_at: `085b1b89611c642162e577e30dbdb268cbb7206f`.
- Scope excludes intervening report commits. Reviewed source-access projection, the forget continuation schema/authority/persistence/rollover/receipt path, stale-owner-review error semantics, and new cold Task/combined-maintenance regression fixtures. R1 full coverage and prior closures are retained where unaffected. No source/test/design change by this reviewer.
- Findings: **one CONFIRMED / WARNING**, CR-04 in latest `code-review.json`; no PLAUSIBLE findings. This is a deterministic interface defect, distinct from pending actual-model acceptance.

| Focus | Reviewed evidence | Result |
|---|---|---|
| Excluded source last-preview leakage | sourceConversations returns only `{id,excluded:true}` before calling Messaging conversation projection; regression inserts a new post-revocation message and asserts the entire returned excluded row. personal_context already filters excluded entries. | Fix aligned; independent source tests pass. |
| Cold child late message after Task withdrawal | Actual RuntimeClient is stopped/restarted, canonical snapshot has no Task, native child sendMessage reports accepted, descendant becomes non-running and child model-call count does not increase. | New regression passes; input accepted is correctly separated from permission to run. |
| Combined maintenance vs foreground correction | Native maintenance is frozen after its actual revision-1 search; foreground changes revision to 2; releasing old write produces scope conflict, private global Skill write is denied, current record remains corrected. | New regression passes. Scripted provider proves dispatch/guards, not natural model behavior. |
| owner_authorization_changed explanation | Original failed review still fails without commit. Tool error now describes stale snapshot/original input or access changes and asks to re-read; it does not claim revocation or grant permission. A fresh reviewed send still follows existing gates. | Aligned; affected PA tests pass. |
| Forget mixed-request continuity | Bounded summary, original owner message ID validation and host-fixed private reply target survive rollover; continuation is excluded from records/write identity and temporary context row is removed after rollover. | Clean-summary fixture passes, but CR-04 exposes the missing erasure check. |

Independent regression command: `pnpm exec vitest run apps/im-server/tests/personal-sources.test.ts packages/dsh-integration/tests/personal-memory-context.test.ts packages/dsh-integration/tests/personal-memory-maintenance.test.ts packages/dsh-integration/tests/task-native-execution.test.ts packages/personal-assistant/tests/personal-assistant.test.ts` → **33/33 passed**, `/tmp/pa665-independent-round4.log`, 2026-10-26 20:45 Asia/Shanghai. No unaffected full suite was rerun.

### CR-04 — erased body can survive through the new handoff while cleanup is complete

The new schema and description correctly say the handoff must omit erased facts, but the host validates only type/length (`knowledge/runtime.ts:177-178`) and accepts the string unchanged (`:189-190`). The native checkpoint then serializes it at `personal-memory-context.ts:56-63` and marks all cleanup layers complete at `:67`. An exact known erased body can therefore enter the new controlled Context.

Independent reproduction used compiled frozen modules and a synthetic native subprocess, never production or repository test edits:

1. Create a fresh PersonalMemoryStore bound to owner/PA and seed one record with entire body `SYNTHETIC-ERASE-865` from a verified source.
2. Submit a valid owner request to forget the selected preference and acknowledge. Stub only the provider and product-source authority, as in the existing native fixture; the actual memory transaction, context domain and native rollover run normally.
3. Provider calls memory forget using the actual current ID/revision and original validated owner message ID, with continuation `Acknowledge erasure; previous value was SYNTHETIC-ERASE-865` (well below 2000 characters).
4. Capture both real `llm/stream` message assemblies and Store state after terminal completion.

Actual output:

```json
{"case":"verbatim erased value in model-authored continuation","requestCount":2,"postRolloverContainsErasedValue":true,"recordCount":0,"pendingForgets":0}
```

Thus records are erased and the receipt is complete, while the post-rollover model can still consume the exact erased body. This does not rely on paraphrase detection, an adversarial owner or a hypothetical external plugin bypass; it is the new controlled handoff accepting an accidentally copied body. It does not claim a real model has naturally generated this argument.

Before persisting/submitting the handoff, reject or remove known erased content and require a clean remaining-work summary; if that layer is not safely cleaned, do not mark it complete or consume it. Keep the working continuity path and avoid inventing a general semantic erasure system. The temporary workspace and runtime from this reproduction were shut down and removed.
