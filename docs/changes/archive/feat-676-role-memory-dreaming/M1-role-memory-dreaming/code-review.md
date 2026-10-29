# Code review: feat-676

> Latest review: **Round 5 pass**, patch `c1eea6beb6c2ec4e47cb4bb73b8c6d8b5778a689..e207a51b6e8313083cff05ccebfcca7196b8653d`, native Dreaming trajectory identity/recovery. Surviving findings: `[]`. Unrelated prior coverage is retained; S18 native product reacceptance is separately required. Earlier records below are historical evidence, not the latest verdict.

Original full-review snapshot retained below; Round 5 records its own fixed delta at the end.

- `validated_at`: `5a123bae760d429c84bc2a3f72814009a69836f0`
- `executed_base`: `6b4213c205db04adcebc950fe539a5a759e57391`
- `effective_base`: `6b4213c205db04adcebc950fe539a5a759e57391`
- `effective_through`: `5a123bae760d429c84bc2a3f72814009a69836f0`
- Final fetched origin/main equals effective_base; no unreviewed upstream implementation delta. Later report/canonical/archive-only changes may retain this implementation snapshot when recorded by the caller.

- Mode: full, independent change-code-review; Agent Context Review Mode B included.
- Reviewed snapshot: `6b4213c20..be1fec6c9075ffafe402c7387f3cde25546ae95d`, including `5d5697d46` and `87b333156`; checkout clean at review start.
- Scope: configuration/UI and offline migration; document ownership/freshness/read-write receipts; certified history export; isolated Dreaming prompt/tools/finish; recovery/admission; PA source sync; Work/trajectory projections; affected tests and all four delta files.
- No implementation, test or design edits were made by this reviewer. Product acceptance and the complete local CI run belong to the caller and were still in progress.

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/knowledge/dreaming.ts",
    "line": 133,
    "summary": "[P1] Retire an inapplicable partial plan before admitting another batch",
    "failure_scenario": "A frozen plan becomes partial after a source generation change, or after a human saves a third file version. Every later automatic/manual run selects that same plan before freezing new material; generation validation or the original beforeHash fails again. No branch discards/rebases it, so this owner can never process its backlog again, including after restart.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/dsh-integration/src/knowledge/memory-sources.ts",
    "line": 136,
    "summary": "[P2] Provide bounded continuation for a source unit larger than the input budget",
    "failure_scenario": "The next complete step is larger than maxInputTokens. freeze returns no unit and the unchanged cursor. Every later pass with that configured budget blocks on the same step, permanently starving all later events in that stream. There is no page/continuation path for the large result required by design section 4 and S14.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/dsh-integration/src/knowledge/document-memory.ts",
    "line": 132,
    "summary": "[P2] Reuse verified unchanged pages when checkpointing an ordinary edit",
    "failure_scenario": "An established library has unrelated pages confirmed by its previous basis. A normal task fully reads and updates the relevant page and MEMORY.md, then follows the supplied guide and calls checkpoint. The unconditional loop requires this executing Agent to have fully read every unrelated Markdown file too; it throws the generic original-file-read error and leaves the entry stale. Thus scoped immediate edits require a full-library reread, despite the design's per-page verification and on-demand consumption contract.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "memory_maintenance checkpoint schema/result and document-memory lifecycle",
    "expected": "A relevant edit can establish the new basis using actual reads/writes for changed or invalidated pages while retaining previously verified unchanged versions; source-invalidated pages still require verification.",
    "observed": "control ignores a scoped page set and reader.require is invoked for every current version; the tool/Skill says to confirm actually read/written pages and does not disclose a full-library read requirement.",
    "impact": "Routine remember/correct operations fail checkpoint once the library contains an unrelated unread page; current entry consumption stays suppressed and the model receives an error that does not identify the missing page or the actual all-library condition.",
    "recommendation": "Compare with the confirmed basis and require real read/write evidence only for changed/invalidated versions; keep conservative full verification where eligibility invalidates the entire library. Return the concrete unverified paths when refusing.",
    "severity": "WARNING",
    "evidence": "document-memory.ts:130-134; memory-documents.ts:153-166; nano-memory/SKILL.md:40. Deterministic control-flow evidence; no claim that a real model has already failed this scenario. Existing request-capture test has only the entry and the one page it reads, so does not cover this trigger."
  },
  {
    "file": "apps/node/src/capabilities.ts",
    "line": 50,
    "summary": "[P2] Hide the retired memory tool from document-mode settings",
    "failure_scenario": "In document mode, configuration.catalog temporarily removes the Agent restriction and projectCapabilities publishes every schema, including legacy memory. The caller observed daily-engineering's settings showing the selected memory Tool Allowlist row, although the real model tool view correctly excludes it. This exposes an unusable old-mechanism control contrary to S19's explicit product invisibility requirement.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Direct reproductions

Both reproductions used `node --input-type=module` against the current built `packages/dsh-integration/lib/knowledge/*.js`, synthetic in-memory domain/observation fixtures, no provider and no shared service changes. `build-be1fec6c9.log` identifies the build as the reviewed head.

1. Seed Dreaming's run table with a `partial` plan at generation 1 and the current library with generation 2; provide the normal required tools and call `start(parent, false, request)` twice. Both responses are `accepted=true, runId=stale, state=partial`, with `Source eligibility changed; this frozen run cannot be applied.` The only persisted run remains `stale`; cursor remains -1. The same selection/catch cycle applies to an atomic file conflict (`dreaming.ts:157-159,174-178`). Keep already-saved file receipts when retiring/replanning; never overwrite the third version.
2. Seed one root with a 3,000-character human source at seq 0, a complete step at 1, and a later small useful message/step at 2/3. Freeze twice with `maxInputTokens=500`, applying returned ranges between attempts. Both results are `units=[]`, `start=-1, through=-1, observed=3`, `Next complete unit exceeds the remaining input budget.` Cursor remains -1. Scaling the source to the default budget produces the same branch. Preserve complete-read verification and only advance the unit cursor after all its bounded pages are processed.

The UI finding combines caller-provided live observation with `ToolSelection.catalog()` (`capabilities.ts:40-51`), its mode restriction (`:65`) and the unfiltered Node projection. Filtering the UI candidate/display must not silently rewrite stored legacy tool choices or grant new tools.

## Agent Context coverage and limits

Actual request-capture evidence in `memory-runtime.test.ts` and `dreaming-runtime.test.ts` exercises the native runtime: current-entry invalidation in the next request, JSON document receipts, removed legacy model tool, built-in creation guidance, and the isolated six-tool maintenance set (`read/write/edit/glob/grep/finish`). The isolated assembly strips parent sections/contexts, exposes explicit source inputs, requires complete reads and an explicit finish, and distinguishes staged preparation from host application. `ReviewFiles` checks the actual rendered read result, not merely the internal file value. Source role is derived from trusted config and the fixed owner workspace is shared with descendants.

The review inspected PA source pending/sync before freeze/apply, generation invalidation across restart, exclusion guidance, mode exclusion, atomic native writes, per-file/Git receipts, durable plan/cursor ordering, and ordinary-success Work projection. The live model save/correction locators in `/tmp/feat676-validation.txt` support only the stated PA save/correction observation; they do not prove cross-chat reuse, original-child correction, cross-window Dreaming or all S01-S20.

A candidate concerning unfiltered child `inbox/conversations` results was **REFUTED for the current product path**: a synthetic observation exported such a result, but `GlobalAgent.callAdmitted` rejects those child calls (`global-agent.ts:427`), and the child scope removes the tools (`global-mode.ts`). It is not a surviving finding and is not presented as a reachable disclosure.

Missing M1 evidence is recorded in `verification.md`, separately from these confirmed implementation defects. No extra speculative edge-case review is required after the findings and stated exit criteria are addressed.

## Round 2 — targeted closure

- Frozen implementation: `c80a9337f3e1c6bd485723a093b6931bd0af0939`; fix delta `7c1f71cd4..c80a9337f`.
- Additional evidence-only commit inspected: `671954c74` (`memory-child-runtime.test.ts`), no implementation change. The formerly untracked unfinished test was excluded from the frozen implementation review.
- Reused all applicable Round 1 source, configuration, migration, native request and file-atomicity evidence. No full suite was rerun by this reviewer.

| Finding | Disposition | Fix and direct evidence |
|---|---|---|
| F1 stale partial plan | closed | `dreaming.ts:134-146` compares generation/current hashes, retires the inapplicable run while preserving receipts, and freezes the backlog from current files. `dreaming-recovery.test.ts` covers generation and third-version cases, preserved human bytes/receipts and completed metadata replay without rerunning the model. |
| F2 oversized first unit | closed | `memory-sources.ts` now separates durable continuation hash/offset from the logical complete-step cursor; only the final bounded page advances it. `commitSourceRange` is used both on success and ordered completed-run recovery. The added source test round-trips progress between pages, checks every budget and cursor, reconstructs exact original JSON, then reaches the later correction. |
| F3 whole-library reread | closed | `MemoryDocuments.unverifiedPaths` reuses hashes confirmed under the same generation, and the control requires actual read/write evidence for changed/invalidated paths with explicit missing-path errors. Library test preserves full invalidation on revocation. Updated native `memory-runtime` seeds an unrelated confirmed page that the executing Agent never reads and still completes checkpoint. |
| F4 retired memory UI tool | closed | Node capabilities removes the old schema; Web normalization, selected/missing displays and selector updates hide it while retaining its stored allowlist value; iOS hides its catalog, selected count and saved/missing display without altering stored choices. The Node regression asserts both filtered candidates and preserved Agent selection. |

Actual fix-delta review also covered:

- Required `nanoProduct` injection is declared by KnowledgeRuntime. The native Dreaming test now runs both expert and PA configurations and observes PA-only authoritative source refresh before freeze and apply (two calls), along with real staged file writes and the actual restricted request tools. `/tmp/feat676-pa-dream-test2.log`: 2/2 passed.
- New page metadata and prompt agree that source JSON fragments are incomplete evidence and a logical unit closes only on its final page. Work summary explicitly says page completion and that only the final page advances the source cursor. This is deterministic delivery/progress evidence; it is not a claim of universal model extraction quality from arbitrary fragment boundaries.
- `dreaming.recover()` orders replay by run creation time, so durable page offsets are reapplied in source processing order. Earlier complete-step ranges cannot regress a later cursor.
- Migration script/test changes are formatting only: independent Python AST comparison of `7c1f71cd4` and `c80a9337f` returned unchanged for both files. Other CI fixture updates adopt the new default dependency contract rather than expanding production permissions.
- Evidence-only `memory-child-runtime.test.ts` captures three requests from the same real native fork: initial entry, saved correction plus pending eligibility, then revoked generation/stale basis. `/tmp/feat676-child-context3.log`: 1/1 passed. This establishes delivery to the original child, while actual child judgment remains the product acceptance responsibility.

Reused fix validation: `/tmp/feat676-review-fixes.log` 19/19; `/tmp/feat676-ci-fixture-fixes.log` 47/47; `/tmp/feat676-provider-fix.log` 3/3; PA/expert Dreaming 2/2; Web 1031/1031. Native iOS test and Release archive succeeded. Current-head build/typecheck are caller-reported at c80; the earlier review-build installer log names its precommit parent and is not treated as proof of a different reviewed source version.

Additional closure evidence: `01c5088b7` adds only application-recovery tests; `/tmp/feat676-full-apply-recovery.log` is 5/5. The complete root CI at test-only descendant `b36053016` passes 158 files / 836 tests (`/tmp/feat676-root-ci-final.log`, 305.70 seconds). These commits do not change the frozen c80 implementation.

Surviving findings:

```json
[]
```

No new confirmed or plausible defect was found within this targeted implementation delta. Final M1 evidence/verdict remains in `verification.md`; a clear code review does not itself accept all product journeys.

## Round 3 — actual status/receipt serialization boundary

- Frozen delta: `b36053016..b203c5823239e8c462ac1c88615e0f8ef9769450`; only the two product return-object constructions, the added incomplete-input native test and the previously reviewed legacy delta wording were assessed. Prior c80 implementation conclusions remain valid.
- A real `memory_maintenance status` call in the S14 fixture had exposed an absent expert source snapshot as `sources: undefined`, which the native lossless JSON renderer rejected. `MemoryDocuments.status()` now omits `sources` when absent, without inventing an empty authoritative snapshot. `Dreaming.reviews()` likewise omits nonexistent optional fields while preserving legitimate empty summaries and zero timestamps. Callers already treat the snapshot as optional.
- `/tmp/feat676-incomplete-runtime2.log`: 9/9 passed. Four real native runtime modes cover unread inputs, only the first of multiple complete input files read, missing-path read, and assistant normal stop without finish. Real before/after status tool results are parsed from the subsequent actual root request and their stream positions are identical. The test also verifies failed host receipt, unchanged entry bytes, more than one input unit, and finish/read tool errors where applicable.
- This proves the model receives valid status/failure results and incomplete evidence never advances source progress. These are deterministic provider fixtures, not a claim that a real model has understood every source.
- Final reviewed legacy delta wording matches the historical Skill event, legacy in-flight protection and independent Dreaming context behavior. No spec was rewritten to accept an implementation defect.

Round 3 findings: `[]`. No further implementation review is required without an actual source delta or specific evidence gap.

## Round 4 — observed backlog and readable source delivery

- Frozen delta: `b203c5823..5a123bae760d429c84bc2a3f72814009a69836f0`. Actual product acceptance had exposed absent backlog information (an expert mistook `sourcesPending=false` for empty backlog) and native line truncation of a long single-line source JSON input (an automatic run correctly refused finish). These were specific observed interface failures, not speculative hardening.
- `Dreaming.status()` now calls the existing certified source adapter for a read-only next-batch preview. The adapter copies `seen`, reads rotation without incrementing it, never commits source ranges, and status returns no event bodies. Output labels `scope=next_bounded_batch`, pending/blocked/empty state, processed/eligible/observed ranges and blocked reasons. Source eligibility pending yields `scope=unavailable`, not zero backlog. The actual tool description and nano-memory Skill explain these distinctions.
- `prepare()` pretty-prints each input and losslessly encodes long string values into ordered 200-code-point `source_text_chunks`, keeping native per-line reads below their truncation limit. The prompt describes exact concatenation without separators, offset continuation, the untrusted-data boundary and incomplete logical-unit rules. Read completeness remains enforced by the native result observer and finish checks.
- `/tmp/feat676-readable-tests.log`: 4 files / 13 tests passed. Native PA and expert runs consume a source over 6,000 characters, the actual maintenance requests retain its tail marker without the line-truncated notice, explicit finish/application succeeds, and reviver reconstruction reproduces the original string. Four incomplete-input modes also assert observed pending backlog before/after and unchanged source stream progress.
- Before-fix reproduction logs `/tmp/feat676-readable-red.log` and `/tmp/feat676-backlog-red.log` were checked; the direct success and rendered-request assertions above are the closure evidence. Prior atomic recovery, scheduler and source-pagination evidence remains applicable.

Context scope: status schema/JSON result and Skill guidance, source-file serialization, native read output and maintenance consumption. This establishes deterministic complete delivery and guard behavior. Real-model status interpretation/automatic-run reuse remains the independent product reviewer responsibility.

Round 4 findings: `[]`. No broader implementation delta was introduced or re-reviewed.

Final full-root confirmation at the same frozen 5a123 implementation: `/tmp/feat676-root-ci-5a123.log`, `pnpm exec vitest run --maxWorkers=2`, 159 files / 840 tests passed in 292.03 seconds. This supersedes the earlier 836-plus-delta combination for the final aggregate while retaining its diagnostic history.

## Final disposition

All F1-F4 code findings are closed; the two actual product-interface findings and optional JSON status defect were corrected and reviewed in their bounded deltas. Final surviving code findings: `[]`.

Independent product acceptance is committed at `8b28b00dd` in `acceptance.md`: S01-S20 all pass, no open acceptance issue. The final pending-state requirement is supported by actual operation `d67ed387003b486ea12a54f4e739079f` and the real390 pending/applied screenshots; the verifier independently viewed both. This is distinct from the earlier unproven pause attempt and from ordinary Saving state. No product source changed after validated implementation `5a123bae760d429c84bc2a3f72814009a69836f0`.

Code review verdict: **pass**. The overall verification and final evidence reconciliation are in `verification.md`.

## Round 5 — PR #428 native Dreaming trajectory identity

- Review mode: **patch**, frozen `c1eea6beb6c2ec4e47cb4bb73b8c6d8b5778a689..e207a51b6e8313083cff05ccebfcca7196b8653d`; main baseline `6b4213c205db04adcebc950fe539a5a759e57391`. HEAD matched the candidate and the checkout was clean before review. This round covers the seven-file identity/recovery delta and its affected viewer, persistence and model-context interactions; prior unrelated findings and acceptance coverage retain their scope.
- The observed defect is directly reproduced by `/tmp/feat676-trajectory-red.log`: both expert and PA native `trajectory.prepare/open/next` paths failed with `subagent descriptor is corrupt`. Earlier Work-summary/reopen evidence did not prove that native entry worked. The previous final S18/native-trajectory signoff is superseded for this defect; other prior code-review conclusions remain applicable.
- `dreaming.ts:223-226,296` now records the public DSH one-shot/native descriptor during creation setup. The locked DSH `dsh-agent-loop` implementation (`setupAndPublish` / `appendUnstoredSuffix`, `lib/index.js:1830-1892`) durably appends setup events before publishing and resolving `agents.create`; saving `identityRecorded=true` afterward therefore does not precede the descriptor's persistence barrier. This also refutes a possible setup-buffer/crash ordering concern; it is not a surviving finding.
- `dreaming.ts:340-373` repairs only recorded runs with a child ID and no completed identity marker. It checks the expected child ID, persisted origin, exact parent and zero inherited prefix, appends only if no descriptor exists, uses the valid contiguous event count as the next sequence, flushes before marking the run and releases the public write handle. Existing original events and existing descriptors are retained; missing history is not manufactured. A crash after append but before the run marker is safe to retry because the descriptor-presence check prevents a second append. Recovery does not create/resume an Agent or invoke the model. `KnowledgeRuntime` declares its new persistence dependency and initialization runs recovery before normal Agent preparation.
- All new DSH imports are declared dependencies and public exports within `packages/dsh-integration`. No runtime fork, private import, product-layer DSH dependency or viewer-validation bypass was introduced.

### Agent Context Review — Implementation Review (Mode B)

The trigger is persisted maintenance identity and recovery interacting with the model-visible child directory and the native session history. Reviewed surfaces are the actual maintenance request, hidden session metadata, parent/child lineage and catalog publication. The consumer still receives the restricted Dreaming prompt, explicit frozen-source input and native file/finish tools; a viewer identity does not grant model delegation authority.

- `dreaming-runtime.test.ts:32-60` captures actual `llm/stream` requests from the real locked native runtime with a deterministic provider. The prompt/input tail remains present, the initial tools remain `edit/finish/glob/grep/read/write`, unrelated Skill/authority text is absent, and the descriptor event is absent from model messages. Warm and restarted native trajectory DTOs contain the real Dreaming prompt, finish and host receipt and are equal. `session.descendants` remains empty in both processes.
- `dreaming-recovery.test.ts:95-121` checks original-event byte-equivalent serialization, contiguous appended metadata without a `surfaceOp`, valid public descriptor folding, persisted identity marker, repeat recovery and wrong-parent refusal. This test controls the persistence handle; it proves the recovery decision/append contract, not a production upgrade or native UI journey.
- No tool schema, prompt policy, input serialization, source eligibility or file-application behavior changed. No new real-model understanding experiment is required for this metadata-only fix; these fixture captures establish deterministic delivery and boundaries, not general model comprehension. Actual native UI inspection and an existing historical-run upgrade remain independent product acceptance responsibilities.

### Validation and verdict

- Independent command at the frozen candidate: `pnpm exec vitest run packages/dsh-integration/tests/dreaming-runtime.test.ts packages/dsh-integration/tests/dreaming-recovery.test.ts --maxWorkers=2` — **2 files / 9 tests passed**, 8.64 seconds; `/tmp/feat676-trajectory-independent-review.log`.
- Reused `/tmp/feat676-trajectory-regression.log`: the other four files had **16 passing tests**. Its two recovery-fixture failures are historical failures, superseded by the corrected 9/9 rerun above. `/tmp/feat676-trajectory-green2.log` likewise retains the earlier hard-coded-sequence fixture failure; it is not labeled a full pass. `/tmp/feat676-trajectory-typecheck.log` records the successful package typecheck.
- Final caller-run evidence was independently read: `pnpm exec vitest run --maxWorkers=2` — **159 files / 842 tests passed**, 300.29 seconds (`/tmp/feat676-trajectory-full-ts.log`); dependency contracts **13/13** (`/tmp/feat676-trajectory-dependencies.log`); docs integrity **281 maintained sources / 68 required routes** (`/tmp/feat676-trajectory-docs.log`). These replace the historical 840-test aggregate for this candidate.

Surviving findings:

```json
[]
```

Round 5 code-review verdict: **pass**, no confirmed or plausible actionable defect in the reviewed delta. This conclusion does not replace the required S18 native product reacceptance.
