# Verification Report: feat-703-pa-create-agent

> Validation snapshot: `1580df55443b4404a85777b707f147ae36575b33 → 6a588bde10f95b2bf8a408c80287b54595bb67ca`

## Round 1 metadata

- verification_mode: `full`
- reviewer: `/root/static_review_703`, independent static code reviewer + verifier
- review_round: 1
- validated_at: `6a588bde10f95b2bf8a408c80287b54595bb67ca`
- executed_base: `1580df55443b4404a85777b707f147ae36575b33`
- report status: provisional, final product report pending
- requires_full_verification: false (this is the full verification itself)

## Summary

| Dimension | Result |
|---|---|
| Completeness | Implementation present for all four spec requirements; M1 exit evidence incomplete pending real product report |
| Correctness | One confirmed lifecycle-boundary defect; remaining reviewed deterministic paths align |
| Coherence | Shared operation/catalog and identity design followed; first-operation lifecycle boundary needs correction |

## Completeness

M1 is the sole milestone. IM shared creation/catalog, PA request association, native tool, Skill, protocol and regressions are implemented. Final end-to-end product acceptance is still running; implementation presence is not milestone completion.

Prototype / reference: N/A. No client UI change or new reference contract.

## Correctness

| Requirement / scenario | Implementation | Tests/evidence | Status |
|---|---|---|---|
| Explicit owner request; ordinary discussion, observation, child and ordinary Agent boundaries | `personal-agent.ts:141-145,280-283`; PA root gates; Skill lines 12-20 | IM source/owner tests, host child/non-PA tests, native catalog contrast; real discussion self-check reported by caller | Deterministic identity aligned; semantic discussion/withdrawal behavior awaits product evidence |
| Persistent Agent, discoverable, chat/configurable, truthful links | `personal-agent-creation.ts:87-93`; shared `createAgent` + existing configuration commit | IM actual durable profile/user/conversation + links checks | Implemented; final real-model full journey pending |
| Ask about real options; default PA computer; explicit alternative owned computer | `personal-agent-creation.ts:40-56`; `personal-assistant.ts:115-123`; Skill lines 14-16 | Real catalog test; separate owned-node success; foreign/offline reject | Deterministic aligned; live agreement wording pending |
| Low-frequency guidance and fixed tool | `personal-security.ts:209-213`; `capabilities.ts`; bundled Skill | Four actual serialized HTTP requests in native fixture; tools/system stable and body loaded on demand | Mechanism proven; real tool choice still pending |
| Same-key pending/unknown/restart recovery; conflict/rejection truth | `personal-agent-creation.ts:58-99`; `agent-creation.ts:124-138`; reserved operation ID in `control.ts` | Lost ACK + recreated PersonalAgents recovery uses one operation; key conflict, existing ID, rejection and unknown tests | Aligned at tested seams |
| Current producer execution authority at actual new-operation boundary | `gateway.ts:413-416` versus `agent-creation.ts:123,146,185-187` | Independent held-queue reproduction in `code-review.md` R1-C1 | **CRITICAL: queued creation survives PA disable** |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| One fixed short schema + one on-demand Skill | Yes | Native tool registration, fixedTools + existing Skill selection; serialized-request fixture |
| Existing creation/catalog semantics shared with Web | Yes | `control-routes.ts:149-157,187-191` delegates shared module; extraction checked against base |
| Host identity separated from model target | Yes | `personal-assistant.ts:117-119`; `PersonalAssistant.request` overwrites transport identity from host; owned second-node test |
| Original owner provenance + main PA only | Yes at admission | Existing `ownerMessage`, root ProductBridge + GlobalAgent gates; lifecycle after wait is the separate defect |
| Request → exact operation; no second apply state machine | Yes | `pa_agent_creations` key/unique operation; caller-reserved ID; ConfigOperations remains authoritative |
| New writes obey lifecycle/management boundary | No | R1-C1: asynchronous wait is not followed by producer generation guard |
| Context proof and representative real behavior separately recorded | Partially | Native fixture proves assembly; real product acceptance report not yet received |

### Prototype / Reference Contract

N/A.

## Evidence and limits

Reused applicable caller-provided test runs: 72 narrow IM/PA/catalog tests, 50 native PA/context + PA host/contract tests, build/typecheck, pytest 129 and ruff passed. Independently read `.feat703-backend-tests.log`: 210 test files / 1121 tests passed. These are regression evidence, not substitutes for missing model behavior.

Mode B Context checks were performed by this same code reviewer and reused here. See `code-review.md` for surfaces, final serialized request evidence and its controlled-provider limitation. No actual provider cache-hit claim. Caller reports the final daily stack uses Astra PA/medium with Codex automatic approval and no permission skip; ordinary discussion did not create, and explicit request produced actual options. Confirmation, final successful creation and independent scenario report were still in progress at this snapshot.

## Issues

### CRITICAL (1)

- **R1-C1 — New operation can be accepted after its PA is disabled.** `apps/im-server/src/agent-creation.ts:185-187` checks target availability after waiting, but not the initiating PA lifecycle/current authority. Deterministically reproduced: lifecycle admission revision 1 → shared queue wait → disable producer revision 2 → release → `agent.create`, durable new Agent, returned `created`. This violates current execution authority and allows a newly created independent Agent beyond PA shutdown. Revalidate a trusted producer guard at the first configuration-operation acceptance/dispatch point, and add a focused wait/disable regression. Keep receipt/status recovery of already accepted work distinct. Evidence: `code-review.md`, R1-C1.

### WARNING (1, evidence gap; not a confirmed product defect)

- **R1-E1 — M1 final real-model/product evidence incomplete.** `design.md:79,104,110` requires representative real chat agreement, long-lived created Agent/use links, non-creation discussion/withdrawal, explicit-node/offline/conflict/unconfirmed-result outcomes, ordinary approval and independent product journeys. The four-request native fixture proves assembly only. Supply the final product reviewer report with version/configuration/locators; reconcile it here before declaring M1/pass. This is still running, not an asserted product failure.

### SUGGESTION (0)

None.

Verdict: **not pass** — one critical defect and one provisional evidence gap. No source, test, config or design changes; no reviewer-started services to clean.

## Round 2 — targeted closure of R1-C1 / current static result

- verification_mode: `targeted-closure`
- review_round: 2
- executed_base / fix_delta_range: `6a588bde10f95b2bf8a408c80287b54595bb67ca..f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- validated_at: `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- focus_issues: R1-C1 and its associated new-operation authority invariant; R1-E1 evidence status carried forward.
- requires_full_verification: false
- prior report: Round 1 above; full static review remains applicable to unchanged implementation.
- report status: **static implementation aligned; final product evidence provisional**.

| Issue / invariant | Closure evidence | Result |
|---|---|---|
| R1-C1: first operation accepted only while initiating PA generation/binding/source are valid | `agent-creation.ts:187-189` invokes synchronous guard after all preparation waits; `personal-agent.ts:403-406` checks current authority, original lifecycle revision and original owner source | **closed** |
| Already accepted operation keeps existing receipt/result recovery | `agent-creation.ts:125-134` exits through own operation recovery/result before new guard; `personal-agent-creation.ts:80-86` returns not_started for unaccepted status | aligned |
| Existing Web creation and one authoritative apply state machine remain intact | Guard is optional and only PA first-create supplies it; existing `ConfigOperations.create` remains the insertion/apply owner | aligned |
| New regression protection | Independently reran actual IM creation suite: 9/9 passed; queued disabled/binding/source cases assert no dispatch and no configuration operation; prior loss/restart recovery remains green | covered |
| Design clarification preserves contract | Unknown transport versus accepted pending split and effective-authority clarification match implementation; no new tool/Skill surface or weakened permission contract | aligned |
| R1-E1: final independent real-model/product evidence | Final fix-head stack is being rebuilt/reviewed; report not yet supplied | **pending; evidence gap, not asserted product defect** |

The new guard executes synchronously immediately before configuration-operation creation, so a lifecycle/source change during queue or omitted-Skills catalog waiting is observed. The fix does not rely on prompt changes and does not introduce another state engine. No new implementation/spec/design mismatch or architecture violation found in the targeted delta. Agent Context Mode B checks from code-review Round 2 are reused; unchanged serialized tool/Skill evidence from R1 remains applicable.

Independent command on frozen fix HEAD: `pnpm exec vitest run apps/im-server/tests/personal-agent-creation.test.ts --maxWorkers=1` → 1 file / 9 passed, 2026-11-03 17:05:57 +08:00, duration 606 ms. Caller reports 28 IM creation/config/catalog tests and IM build/typecheck passed.

### Current issue totals (supersede R1 totals)

- CRITICAL: **0** — R1-C1 closed.
- WARNING: **1 provisional evidence item** — R1-E1 remains until final product report is reconciled.
- SUGGESTION: **0**.

Current verdict: **static closure passed; overall verification remains provisional pending final product evidence**. No source/test/design edits or commits; no reviewer-started services.
