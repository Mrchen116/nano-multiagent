# Code Review: feat-665-general-personal-agent

Current code verdict: **Round 11 minimal post-PR fixture-module review passes at `3a7da0407`**, no surviving findings (`code-review.json=[]`). V-01 stays closed; initial remote CI failure and the pending updated-head rerun are recorded separately.

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

## Round 5 — CR-04 targeted closure

- review_mode: `closure`; finding_origin_head: `085b1b89611c642162e577e30dbdb268cbb7206f`; validated_at: `d2a6f53d2c666e6c06b05c89ece6a377abd1e489`.
- Focus: CR-04 confirmed exact-body reproduction and the modified continuation validation/persistence/idempotency path. Earlier full-review coverage and unrelated closures retained. Historical CR-04 machine-readable finding is preserved in `code-review-r4.json`; latest findings are `[]`.

The existing memory lock now encloses validation against the selected current normalized body and associated prior-body hashes/lengths. A matching exact current/prior body is rejected before `prepareForget` or publishing the erase transaction. Prior tombstones retain only normalized content hash/length; missing historical length fails closed for nonempty summaries with a concrete empty-summary recovery. Safe continuation is persisted by callback only after validation/apply succeeds and before the erasure authority commits. An already-complete replay does not call prepareForget, so it does not leave a new transient handoff.

Independent validation:

- `pnpm exec vitest run packages/dsh-integration/tests/personal-memory.test.ts packages/dsh-integration/tests/personal-memory-context.test.ts packages/dsh-integration/tests/personal-artifacts.test.ts` → **15/15 passed**, `/tmp/pa665-independent-round5.log`, 2026-10-26 20:51 Asia/Shanghai. The modified real native context test supplies current and previous exact bodies: both return isError, current record remains, no pending forget is created. Its subsequent clean summary reaches the rollover with remaining work/private DM, the secret is absent, and the existing restart fence probe remains passing.
- Direct compiled Store reproduction of the exact CR-04 synthetic marker `SYNTHETIC-ERASE-865`, followed by corrected historical-body and missing-length cases, produced:

```json
{"currentBodyRejected":true,"priorBodyRejected":true,"legacyMissingLengthRejected":true,"emptySummaryCompletes":true,"completeReplayDoesNotPrepare":true,"prepareCount":1,"recordCount":0}
```

The callback counter stays zero after each unsafe request; only the valid empty-summary erase prepares it once, and completeForget followed by the same complete replay does not increment it. Temporary synthetic Store data was removed. These direct boundary checks do not claim semantic paraphrase removal or natural model reliability beyond the exact reported defect.

**CR-04: closed.** No new surviving CONFIRMED/PLAUSIBLE finding in the reviewed fix. The existing clean/empty handoff path is retained; no general-purpose semantic erasure layer or speculative edge-case loop was requested.

The independent product report's Round 4 at `085b1b896` closes the original PA-5 mixed-request failure using real correction-before-forget, an empty continuation, a received erasure receipt and later cross-group morning candidates. That is relevant evidence for the original successful mixed-request path; it does not retroactively remove R1/Round 3 failed evidence or settle the still-incomplete full-unit V-01 package. No source, tests, design or runtime configuration was edited by this reviewer.

## Round 6 — child-result reply continuation and preparation/observation guidance

- review_mode: `patch`; Context mode: focused **Implementation Review**.
- requested source range: `e453eb019..42844df8b`; caller's `12d2f3c3c` adds product acceptance evidence only. Included the caller-authorized one-line mode-name closure at `671de6ac4224c3d73e64aae198e3c72a3b74c9b4`.
- Scope: child delegation provenance → current consumed native return → host-only ProductCall → private reply classification; cancellation/restart; preparation guidance/settings names; observe terminal capture; forget callback type narrowing. Report/evidence additions were read for claims and version limits, not treated as product implementation. No unrelated full audit/test rerun.
- Latest findings: `[]`; no surviving CONFIRMED or PLAUSIBLE issue. CR-01–04 closures retained.

| Focus | Independent review and evidence | Conclusion / limit |
|---|---|---|
| Original-request source for a later child result | Successful native spawn stores actual child ID, actual parent session and the original live input IDs in a dedicated durable domain. childReturns requires a message with native agent-message/subagent-settled source actually consumed by the current parent turn, a matching direct continuable child and a non-aborted latest child turn. No model argument supplies the grant. | Scoped continuation of the original private reply, not new authority from child text. |
| Product/IM authority boundary | Bridge injects metadata outside args. PA resolves the original Inbox row and requires owner+participant metadata; IM revalidates ownerMessage/current readable original source. The new classification enters the same private destination flow. External/shared sends retain existing independent review. | Reviewed path does not turn observer content or a child claim into owner authorization. |
| Cancellation/restart/later unrelated turns | Explicit native interrupt removes the stored mapping; aborted turn prevents grant. A real restart preserves origin references for an actually resumed/returning child. Current-turn inputEvidence prevents unrelated later turns from reusing the result. | Independently exercised return/cancel/restart plus later unrelated input. No universal claim about untested native event interleavings. |
| Preparation guidance | Read actual settings, then relevant source coverage; prepare/authorized_action permit useful private preparation from a concrete commitment, response_only does not explore. No external action or responsibility takeover is authorized. This addresses the observed P01 refusal without changing runtime authority. | Design-aligned guidance; actual fixed P01 behavior remains pending. |
| Mode-name interface correction, CR-05 (closed in this round) | Initial text said `delegate`, while settings only accepts/returns response_only/prepare/authorized_action. Caller changed that single value to `authorized_action` at 671de6ac4; compared directly with personal-attention.ts validation. | Confirmed naming inconsistency closed; no real authorized_action-mode behavioral claim. The running earlier P01 prepare-mode sample cannot prove this mode branch. |
| Observation capture | Common idle() checks root and latest visible child turns; observe now additionally waits for five seconds of actual idle/stable root revision, without requiring a public reply. New protocol test covers root then child completion and last revision reset. | Prevents collecting/stopping while known active work remains; does not grade P03 or other real behavior as passed. |
| Forget callback TS narrowing | Capture forgetKey before callback resolves the union type without changing continuation/erase authority semantics. Three affected packages have an explicit successful build log, distinct from earlier JS emitted despite type errors. | Source/runtime boundary retained; build evidence accurately upgraded. |

Independent commands: `pnpm exec vitest run packages/dsh-integration/tests/personal-delivery-evidence.test.ts apps/im-server/tests/personal-attention.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/dsh-integration/tests/personal-context.test.ts` → **35/35 passed**, `/tmp/pa665-independent-round6.log`; `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py` → **12/12 passed in 0.38s**. The native tests use real subprocesses/DSH events and scripted providers; they prove the tested provenance/guard/receipt conditions, not natural model completion. Reused `/tmp/pa665-child-return-build2.log` explicitly shows integration, PA and IM builds Done.

Read the new M1/M2/M3 evidence ledgers, validation.md and acceptance through its latest appended Round 5. They preserve real D08 and P01 failures; no runtime-test success overwrites those. New worker and product evidence narrows V-01, as mapped in verification Round 6. Actual repaired P01/D08 runs and complete 58-case classification/core replay comparison are still being collected. No production action or source/test/design edit by this reviewer; native fixture resources are disposed by their tests.

## Round 7 — finite evaluation fixture/runner review

- review_mode: `patch`; reviewed delta `a5acef430..ee26e367421d45cba0a1b3f5e7b7a20982566849`, limited to eval fixture/runner/protocol and corrected contract wording. The acceptance append is evidence, not product source.
- Verified `git diff --quiet 671de6ac4 ee26e3674 -- apps packages src/IM` is empty. Prior full product/Context review and all finding closures remain applicable; no new product audit or native full-suite rerun.
- Local fetched `origin/main` resolves to `85910853ebe4a7a22c5b761029cf46da2f78cd5a`, the original diff base. No upstream product delta must be incorporated into this bounded review.
- Latest findings: `[]`.

M08 now contains 90 independent opaque 64-hex synthetic values rather than a predictable RULE-n sequence. Independently parsed **90 unique values**, domain IDs 000–089 exactly once, total first-request text **7924 characters** (above the old 3575-character summary capacity). The request explicitly identifies synthetic test data and requires exact retention; it does not feed the model tool parameters or hidden identity. Follow-up still queries 001/045/089, then corrects 045 and rechecks. This removes the old fixture's easy semantic compression; actual storage/recall/prefix behavior still requires the real run and adjudication, not a fixture-size pass.

Runner now enables extra Heartbeat configuration only when the adapter explicitly says so. Independently checked the only such case is **P05**. Other observe cases retain the ordinary Inbox ten-minute batch and do not create an unrelated configuration operation. Existing idle/revision settlement logic is unchanged. The protocol protects P05 opt-in and P03 absence, alongside the existing real-root/child settlement regression.

Independent `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py` → **12 passed in 0.34s**. `python -m tests.e2e.general_personal_agent collect --cases all` → **58 cases, live_actions=0**. These verify evaluation wiring only, not product outcomes. No new Context injection/selection behavior is added to the product by this patch.

Corrected contracts were reconciled separately in verification.md's unique Corrected Delta Reconciliation section. Caller reports an independently passed new D08-r4 and actual P01-r2 persisted private preparation; this finite pass does not re-adjudicate those live artifacts or replace the still-arriving complete evaluation evidence package. Historical D08/P01/M08/P03 limitations and failures remain intact.

Only review reports were edited. Pre-existing untracked `scripts/e2e-up-pa665-temporary.sh` was preserved and not staged; this reviewer did not run it or start any service.

## Round 8 — adjacent owner input retention and P12 relevance fixture

- review_mode: `patch`; Context mode: focused **Implementation Review**.
- Source range: `dfe29d5e5..32255b1ee38d59fc411390f27994c6bd7d990735`, specifically `a4a0f9a55` input-admission fix and `32255b1ee` fixture. No product full audit or full-suite rerun.
- Latest findings `[]`; no surviving CONFIRMED/PLAUSIBLE defect in the reviewed delta.

The observed I02 failure involved two inputs from the same allowed group: an addressed owner request and an adjacent rejected peer request. Recovery formerly used whole-source revokeSource after the peer verdict, deleting the accepted owner input as well. The provided red regression `/tmp/pa665-adjacent-red.log` directly shows `sources=[]` where one owner unread input was expected.

Reviewed fix: `InboxStore.rejectInput` updates consumed only for the exact agent/message identity and closes that message's pending control obligation; it preserves the original inbox payload and relay receipt. Live admission denial and unclassified recovery now use this entry-level operation. Existing true source revocation remains in refreshPersonalSources and retains the whole-source frozen-read/fragment/snapshot removal logic. Rejected unclassified rows cannot be reclassified/woken because both unclassified() and model entries() require consumed=0. This separates a refused peer action from loss of a readable conversation and keeps the owner original/source intact for Context selection.

Independent regression: the new GlobalAgent recovery test accepts owner and peer in the same group, uses a real InboxStore/NodeStore with controlled review/source seams, rejects peer, and observes unread=1, actual owner content present, rejected peer absent and no remaining unclassified input. It proves the deterministic product seam rather than assuming a successful model response.

Independent commands: `pnpm exec vitest run packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/inbox.test.ts packages/personal-assistant/tests/personal-assistant.test.ts` → **80/80 passed**, `/tmp/pa665-independent-round8.log`; `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py` → **12/12 passed in 0.34s**. No unaffected native/all-product suite was repeated.

P12 now has an authentic owner message in the existing observer work group stating responsibility for the upcoming review and concern about feedback preparation before the colleague's review background. It contains no PA address, tool parameters, fabricated identity or delegated external action; runner's settle applies only to owner_pa/shared_group direct requests, so this observer send does not become a direct PA call. It establishes ordinary owner relevance for the existing observe/bounded-source behavior. README is corrected to match the previously reviewed P05-only Heartbeat setup and core-repeat terminology. Old weak-background failures remain historical and cannot be relabelled using the revised fixture.

Actual new I02 rerun is still in progress and not graded here. V-01 remains pending the final actual evaluation package; no waiting/polling occurred. Only review reports were modified; the caller's independently changing acceptance.md and temporary untracked e2e script were preserved unstaged and not executed.

## Round 9 — complete live Inbox fragments and long-run login renewal

- review_mode: `patch`; Context mode: focused **Implementation Review**.
- Source delta: `5e46cf874..06d8041bfcc16870ab3af9a0f8379ffa621c305c`, only policy/sources.ts, its regression and eval runner client refresh. No broader product review or full-suite rerun.
- Latest findings: `[]`; no surviving CONFIRMED/PLAUSIBLE issue in this finite delta.

The real M08 pressure case supplied a 7924-character owner request whose two host pieces were completely read in one actual Inbox result. Old humanInputs discarded every partial-marked message even when the entire original had been consumed, leaving no live source for the completion reply. The supplied red `/tmp/pa665-fragments-red.log` shows an empty HumanInput array despite both observed parts; the new test preserves that original failure as red evidence.

Reviewed source boundary: humanInputs scans only events after the most recent turn/start and only successful tool results whose call ID was registered by the actual live Inbox execution in this process. Fragments are grouped by host target and original message ID, indexed by one-based part number, and emitted only when all host-reported parts are present; text is joined in part order. The host Inbox provides immutable/frozen fragment metadata from 6000-character text slicing. This restores the complete original request, not consent from a lone incomplete piece or a historical body. The existing owner/participant/source access checks after these IDs are unchanged.

Independent `pnpm exec vitest run packages/dsh-integration/tests/approval-sources.test.ts packages/dsh-integration/tests/personal-delivery-evidence.test.ts` → **19/19 passed**, `/tmp/pa665-independent-round9.log`. The new regression covers incomplete first piece, complete same-turn pieces and a cross-turn incomplete pair. Existing source/history and native delivery tests remain green. Protocol: `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py` → **12/12 passed in 0.33s**.

Additionally called compiled ApprovalSources directly with a complete single-page result in reversed part order, a fresh recovered ApprovalSources without live registration, mismatched targets and a split across turns. Actual output:

```json
{"sameTurnCompleteOnePageOrdered":true,"restoredNotGranted":true,"differentSourceNotMerged":true,"crossTurnIncompleteNotGranted":true}
```

EvaluationClient renews authentication at the header-access boundary after five minutes using an ordinary login POST, then updates the token/time before the requested read/write is sent. It contains no response-triggered business retry or replay branch. An independent synthetic HTTP/clock probe accessed headers twice after the refresh threshold: exactly **one `/im/v1/auth/login`**, **zero mutation calls**, both headers used the new token. Credentials remain in the in-memory fixture object; no credential output was captured.

Actual fresh v12 M08/P03/I02/P12 outcomes remain running/awaiting separate evidence. These tested seam fixes do not retroactively pass the earlier M08 response timeout or any preceding scenario. Prior corrected product deltas remain aligned because the change restores original complete-input provenance within the existing turn/source contract. Only reports were changed; caller's dirty acceptance.md and untracked temporary e2e script remain preserved unstaged.

## Round 10 — final evidence closure / retained code and Context conclusions

- Mode: evidence-focused closure; no repeated full source/Context review.
- executed_base / effective_base: `85910853ebe4a7a22c5b761029cf46da2f78cd5a`.
- validated_at / effective_through: `fb792c8d22b5f75d252b58bba4949152a7806380`, including independent product acceptance commit `57fd15853`.
- Verified current fetched origin/main is still the same base. `git diff --quiet 06d8041bf HEAD -- apps packages src/IM tests evals` is empty: later changes only consolidate reports/docs. Thus prior full review, focused code fixes, Context traces and corrected-delta alignment remain valid at this tree.
- Latest findings: `[]`. CR-01–04 and the in-round mode-name correction remain closed; historical reproductions/failures are preserved.

Read final evaluation.md/evaluation-results.json, acceptance through its final Round6 verdict, validation.md and M1/M2/M3 worker evidence. The independent product reviewer now accepts all 15 required Scenario groups using actual representative journeys and the worker-owned native/file/transaction guards; no blocking/major remains. PA-2 is a retained minor first-draft terminology issue, already corrected in the later user revision, and is not a newly inferred code defect.

Independently checked all **58 unique case IDs** and counts **21 passed / 0 current failed / 3 blocked / 34 not_run**. For all 21 passed rows, checked the raw execution_complete status, raw-result hash bound by independent-review, adjudication review hash, and every manifest file's exact bytes: **145 referenced files / 27,615,536 bytes**, **zero hash/status errors**. These manifests include actual model_input, tool_trace and user_result. Read the assertion-level decisions for M08/P03/I02/P12/D08/M01/M02 rather than relying only on passed labels. This integrity check reuses the independent adjudicator's semantic review; it is not a claim that this reviewer reran or regraded every model task.

The previously pending real paths now have scoped final evidence: M08 has 90 independent original values and correction-only 045; actual provider prefix remains bounded. I02 preserves addressed owner work alongside a refused peer and actually delivers the public result. P03 ends with an actual private conflict message and no family disclosure to the work group. P12 and P01 persist usable private preparation with real settings/source checks. D08-r4 ends in an actual complete owner itinerary, not a child acknowledgement. The independent product report additionally records real quiet settings, a 600.105-second background wake, useful private preparation and zero new DM/external messages, then verifies settings restoration.

Core comparison retains three unique nodes per condition for M01/M02/D08, the same gpt-6-astra model/medium effort/no fallback, three valid candidate M01 and M02 passes, D08's original failed/passed/failed candidate series and separately passed repaired r4. Tool/Feature differences are explicitly `comparable:false`; no percentage improvement is asserted. This is repeated observation across recorded builds, not three green repetitions of the final fixed D08 build or a robustness guarantee. Unknown model-call/duplicate/error-memory/blocking-delay metrics stay null/unknown. The 34 not_run and three absent external-account live branches remain exactly that; representative acceptance does not overwrite them.

V-01 pre-PR evidence closure is supported by the combined scope above; details are in verification Round10. No new product tests or services were started. Local wide checks retain their original two timeout outcomes and the successful six-test affected recheck; final source typecheck and later affected builds/tests are explicitly versioned. Archive/current-spec promotion/docs validation and then Ready PR/remote required CI remain the orchestrator's subsequent actions under change-workflow; this review does not predict their result, authorize merge/deploy or claim a release.

## Round 11 — post-PR fixture module extraction / size gate

- review_mode: `patch`; PR: **#414 Ready**.
- reviewed source range: `16cc51fad2cd0e63b7e3a937158a7aed3fca2799..3a7da0407c800a79bbc66623daf2d9ccab0308ed`.
- executed_base / effective_base: `85910853ebe4a7a22c5b761029cf46da2f78cd5a`; validated_at / effective_through: `3a7da0407c800a79bbc66623daf2d9ccab0308ed`.
- Scope: only EvaluationClient/request/validate_manifest extraction into fixture.py, runner/protocol imports and the validation ledger. No product/Prompt/adapter/receipt/adjudication semantic delta and no new model-visible Context change. Prior full/Context and evidence closure conclusions retained.
- Latest findings: `[]`.

The first remote CI run `40341170257` at `16cc51fad` is retained as an actual failed attempt: frontend passed and backend/native/IM 149 files /801 tests passed, while Python's new-file size gate rejected the 432-line runner. This review does not rewrite that attempt as green. The patch moves the existing three definitions to their fixture-owning module and reduces runner to **386 lines**, with fixture.py **56** and protocol **231**, all within the 400-line contract.

Independent AST checks compare each relocated EvaluationClient/request/validate_manifest definition with the old runner and every retained CheckpointRequired/verified_files/Run definition with its predecessor: **all equal with source locations excluded**. Import execution confirms EvaluationClient still directly subclasses the same real `tests.e2e.critical_paths._im_client.IMClient`; runner.EvaluationClient is the exact imported fixture class. Auth renewal, authenticated request behavior, isolation validation and the Run execution body therefore retain their already-reviewed behavior at these boundaries. No fake client is introduced and no action retry/replay is added.

Independent `python -m pytest -q tests/e2e/general_personal_agent/test_protocol.py tests/contract/test_test_naming_and_size_contract.py` → **14 passed in 0.41s**. `python -m tests.e2e.general_personal_agent collect --cases all` → **58 cases /0 live actions**. Reused same-frozen-source full Python **70 passed /44 deselected** (`/tmp/pa665-ci-python-green.log`), docs **271 sources /68 routes** (`/tmp/pa665-ci-docs-green.log`), and caller's full ruff/96-file format result; no duplicate broad/native/model run.

Product, frontend and eval adapter trees are unchanged from the first Ready PR head (`git diff --quiet 16cc51fad HEAD -- apps packages src/IM evals`), so previous code/Context/evaluation/product conclusions and first CI's unaffected passes remain applicable. The extracted module is a behavior-preserving evaluation harness organization change. **Updated-head remote required CI must still execute and be observed**; this static/local gate pass is not a claim that the new remote run is green. Only archived review reports were changed by this reviewer; no model task, live service or product data was created.
