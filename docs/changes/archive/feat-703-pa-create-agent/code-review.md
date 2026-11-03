# feat-703 Code Review

## Round 1 — full

- Reviewer: `/root/static_review_703`, independent of implementation.
- Snapshot: `1580df55443b4404a85777b707f147ae36575b33 → 6a588bde10f95b2bf8a408c80287b54595bb67ca`.
- Reviewed at: 2026-11-03 16:57 +08:00.
- Scope: complete 21-file implementation diff; current specs, unit spec/design/delta/milestone; affected shared creation/catalog, ConfigOperations, PA identity/source/lifecycle and native Context consumers.
- Checkout: `codex/feat-703-pa-create-agent`; initially clean. No source/test/design edits, no new services or commits.

## Findings

```json
[
  {
    "file": "apps/im-server/src/agent-creation.ts",
    "line": 185,
    "summary": "[P1] Recheck the initiating PA lifecycle after queue/catalog waits",
    "failure_scenario": "A PA create passes gateway.ts lifecycle admission at revision 1, then waits on the shared per-Agent queue or omitted-Skills capabilities RPC. The owner disables the PA before that wait completes. Lines 185–187 recheck only target node availability and still insert/send a new configuration operation, so a new independent Agent is created after its producer has been stopped. Reproduced with an in-memory DB and held ConfigOperations queue: {status:'created',requests:['agent.create'],created:{agent_id:'new-agent'},paLifecycle:{desired:'disabled',revision:2}}. Pass a trusted pre-submit guard into the shared service and revalidate the initiating PA generation/current authority immediately before accepting a new operation; keep receipt recovery of already accepted operations distinct.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "CRITICAL"
  }
]
```

### R1-C1 evidence and limits

The production ingress guard is `apps/im-server/src/gateway.ts:413-416`; the new handler then crosses `ConfigOperations.serialized` (`control.ts:176-185`) and potentially `gatewayRequest(node.capabilities.resolve)` (`agent-creation.ts:146`) before `ops.create` at line 187. The target owner/online checks do not check the initiating PA. `PersonalAgents.authority` does not check lifecycle; its post-handler recheck also occurs after the effect. The host lifecycle check cannot retract a request already executing inside the separate IM process.

Independent reproduction used existing built HEAD modules, `openDatabase(':memory:')`, the same authenticated account/node/PA fixture facts and a fake applied Gateway configuration receipt. It held `configurationOperations(ctx).serialized('new-agent', () => gate)`, called `requireLifecycle(db,'a',1)` then `ctx.personal.handle(..., 'pa.agent.creation', {lifecycle_revision:1, action:'create', ...})`, changed the PA lifecycle to disabled/revision 2, and released the gate. No configuration operation existed before disable. Observed result:

```json
{"status":"created","requests":["agent.create"],"created":{"agent_id":"new-agent"},"paLifecycle":{"desired":"disabled","revision":2}}
```

This proves the deterministic acceptance/dispatch boundary defect; it is not a real LLM or production-run claim. The same async gap can occur without queue contention when Skills are omitted and the capabilities RPC is in flight. Recommendation is a small producer guard at the actual new-operation boundary, not a new lifecycle state machine or cancellation of an already applied result. Add a regression proving disable during that wait prevents the first `agent.create`, while querying/recovering a previously accepted operation keeps its truthful semantics.

## Coverage

- Shared Web creation/default-Skills/fingerprint/Feature preparation extraction compared with the original route; existing Web operation semantics retained.
- Owner-scoped node catalog, connection/epoch fencing and post-await owner revalidation; target computer independent from PA transport identity.
- Exact host-reserved operation ID association, same-key configuration/node conflicts, rejection/pending/unknown/committed recovery and existing-ID collision.
- Main PA and root-session gating in native ProductBridge and PA product host; original owner-message check rejects observation/other sender/represented message as new evidence.
- One fixed short tool, no dynamic schema changes, on-demand Skill, existing Skill selection and ordinary create approval.
- No DSH private imports, cross-package runtime bypass, second Agent loop, client changes or duplicated apply state engine found.

## Agent Context Review — Mode B

Triggered by new tool/schema/results, on-demand Skill and owner provenance. Consumer: main PA. Covered trusted identity → native fixed tool → ProductBridge → PA host → IM owner/source checks → shared configuration operation; tool/Skill selection and child filtering; loaded guidance, options and status meanings; ordinary history/Skill restoration paths are reused.

The native HTTP fixture in `packages/dsh-integration/tests/personal-security.test.ts:200-243` captures four actual native-runtime HTTP requests. It asserts identical serialized tools/system, a discoverable Skill summary without body in request 1, actual Skill body after load, options fields in request 3 and created result in request 4. This is actual assembly/wire evidence with controlled provider outputs; it does **not** prove real model tool choice, source-ID selection, option agreement or truthful final user wording. The model fixture deliberately has permission skipping; final product evidence must use normal real-model approval.

No separate confirmed Context-interface defect was found. R1-C1 is an execution-authority boundary defect and must be fixed regardless of prompt wording. Final representative model/product journeys were still in progress when this report was written; full verification remains provisional until their report is supplied. No cache-hit-rate claim.

## Validation evidence reused

- Caller-provided versioned run: 72 relevant IM/PA/catalog tests; 50 native PA/context + host + contract tests; build/typecheck; pytest 129 + ruff passed.
- Independently inspected local `.feat703-backend-tests.log`: `vitest run --maxWorkers=4`, 210 files / 1121 tests passed, started 16:48:41, duration 313.09 seconds.
- Independent in-memory lifecycle reproduction above.
- No additional speculative review loop or duplicate broad suite was run.

Verdict: one confirmed blocking finding. Final product acceptance evidence pending separately.

## Round 2 — targeted closure of R1-C1

- review_mode: `closure`
- finding_origin_head / pre_fix_head: `6a588bde10f95b2bf8a408c80287b54595bb67ca`
- validated_at: `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- reviewed delta: `6a588bde10f95b2bf8a408c80287b54595bb67ca..f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`, focused on the new admission callback, associated authority/receipt paths, three regressions and design clarification. R1 full-review coverage remains applicable to unchanged code.
- reviewed at: 2026-11-03 17:06 +08:00.
- focus finding: R1-C1 — **closed**.

The shared service calls synchronous `beforeCreate?.()` at `apps/im-server/src/agent-creation.ts:187`, after the per-Agent queue and any omitted-Skills catalog await and before the first `ops.create`. The callback supplied at `personal-agent.ts:403-406` resolves current server authority, checks the original initiating lifecycle revision and rechecks current access to the original owner message. There is no intervening await before ConfigOperations synchronously authorizes and inserts the operation. This closes the demonstrated late first-acceptance/dispatch gap for disable, binding revocation and source revocation.

An already associated pending/committed/rejected operation takes its existing recovery/result branch before the new callback. A status request without an accepted operation returns `not_started` before calling the shared service. Thus the fix does not turn historical result confirmation into a new creation intention or prevent truthful receipt recovery. The optional callback leaves existing Web creation behavior unchanged.

Validation:
- Independently ran `pnpm exec vitest run apps/im-server/tests/personal-agent-creation.test.ts --maxWorkers=1` on the frozen fix head: **1 file / 9 tests passed**, started 17:05:57, duration 606 ms.
- Three new cases hold the real shared queue, revoke disabled/binding/source authority, then release; each rejects and asserts zero receipt dispatch and zero configuration operation. Existing pending/recreated-service recovery remains green.
- Caller supplied 28 IM creation/config/catalog tests and IM build/typecheck passed; reused without duplicating its broader run.
- Context Mode B delta: no tool/schema/Skill/model-visible result change. The fix enforces the trusted authority at the execution boundary; the prior serialized Context evidence remains applicable.
- Design delta distinguishes transport `unknown` from accepted-operation `pending` and states the effective-authority invariant; it does not silently weaken the original contract.

Surviving code findings in this closure:

```json
[]
```

Verdict: **R1-C1 closed; no remaining confirmed code findings.** Final real-model/product evidence remains pending separately; this code closure does not assert M1 product acceptance.
