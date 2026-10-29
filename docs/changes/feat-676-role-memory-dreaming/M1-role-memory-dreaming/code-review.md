# Code review: feat-676

> **2026-10-29 设计 R8 实施重开：下列旧版本结论是历史证据。** 前台单写、连续原文、child 两阶段提炼、共享历史回查与输入协议迁移已经改变，相关旧门禁不再覆盖当前实现；本轮新报告完成前不能按旧 pass 交付。未受影响的 UI/旧模式等只可按具体证据继承。

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


## Round 6 — PR #428 bounded guidance cleanup

- Review mode: **patch**, independent change-code-review with Agent Context Implementation Review **Mode B**. Frozen range: `8fef02de95451334567c5d7c1f4c2edb7ed8fa8f..d572ad78bc216fd9347bf6922e5c42171c22afba`; HEAD matched the candidate and the checkout was clean at review start.
- Scope is the four-file wording delta only: `features/skill-creation.ts`, `knowledge/document-memory.ts`, packaged `nano-memory/SKILL.md` and packaged `skill-creator/SKILL.md`. The user's requested cleanup removes redundant permission reminders, retired background-Skill explanations, Codex migration commentary and the memory/scheduler aside. No execution logic, tool schema, selection, scheduling, source eligibility, identity/recovery or file-write behavior changes. Prior unrelated review coverage is retained.

### Context combination and retained operation guidance

- `document-memory.ts:44` still distinguishes saved understanding from authorization, Task state and live permissions, identifies the ordinary memory file tools and routes organization to `nano-memory`. Adjacent guidance retains the fixed owner library, role, full relevant-page reads, current corrections, entry synchronization, checkpoint/version semantics and concrete unavailable-tool feedback. Removing the generic permissions reminder does not remove the actual missing-tool signal.
- `skill-creation.ts:9` retains the creator discovery instruction, evidence threshold, in-place read-before-edit workflow, user deferral/acknowledgement constraint, task/Memory distinction and selected writable scope. The creator body retains `skill_manage` list/create/patch/edit/resource operations, unavailable-tool handling, successful-write receipts and partial-result reporting (`skill-creator/SKILL.md:124-173`). Its opening user-intent/scope guidance remains coherent with those operations. Neither deleting the background explanation nor deleting migration commentary creates a new background workflow or a dependency on Codex helpers.
- `nano-memory/SKILL.md:33-47` retains identity/source/disclosure boundaries, backlog versus eligibility semantics, complete-read/checkpoint/generation steps, explicit exclusion and cleanup, and Dreaming's staging-only/private-finish/no-Skill-publication instruction. The deleted scheduler aside was not the operational entry for Task or pause/cancel control. The assembled short guide still explicitly separates memory from Task state; this delta introduces no contrary instruction.

### Direct delivery evidence and limits

Independently inspected `/tmp/feat676-prompt-cleanup/probe.mjs`, `result.json` and all three JSONL records in `/tmp/feat676-prompt-cleanup/runtime/requests.jsonl`. The probe uses the real built integration `RuntimeClient` and locked DSH, session `prompt-cleanup`, expert agent `probe`, revision `1`, isolated `/tmp` workspace, Dreaming disabled and selected `read/skill`; an `llm/stream` interceptor supplies deterministic skill calls instead of a real provider response.

- Records 1–3, `messages[2].content[0].text`: new document-memory guidance, fixed owner/role and concrete `Unavailable tools: write, edit, memory_maintenance` are present. `messages[0].content[0].text` retains current Skill-creation guidance.
- Record 2 and record 3, `messages[5].content[0].text`: the actual `skill` result contains the current creator body, including unavailable-tool handling and write/partial-result receipts. Record 3, `messages[7].content[0].text`: the second real `skill` result contains current `nano-memory`, including checkpoint and staging/finish instructions. Thus loading is checked beyond the asset files or a preview.
- Independently checked all three records for every removed sentence/fragment in this four-file diff; none appears. The effective tools remain `get_context_remaining/history/new_context/notes/read/skill`; the capture does not claim write capability merely because guidance names file operations.
- This is native assembled delivery at the **pre-adapter `llm/stream` boundary**, with controlled responses. It does not establish provider-wire serialization, autonomous Skill selection, real-model understanding or successful writes. Pure wording cleanup does not require a new model-understanding experiment; prior applicable runtime/product evidence retains its original limits.

Reused caller-provided validation at the candidate: `pnpm --filter @nano/dsh-integration build` and `pnpm exec vitest run packages/dsh-integration/tests/cron.test.ts packages/dsh-integration/tests/capabilities.test.ts packages/dsh-integration/tests/dreaming-runtime.test.ts`, exit 0, **3 files / 9 tests passed**, 10.98 seconds, started 2026-10-29 10:45:21 Beijing time. These stdout results were supplied by the caller without a saved log; they are not an independent reviewer rerun. No wording-match test, service run or full suite was added.

Surviving findings:

```json
[]
```

Round 6 code-review verdict: **pass**. No confirmed or plausible actionable defect in the bounded delta. Round 5's 842-test aggregate and `acceptance.md` Round 3's actual native trajectory/cold-read reacceptance remain applicable to their unchanged implementation; its minor T1 recovery-prompt observation remains a separate non-blocking side finding. This round does not replace those journeys or alter their evidence.


## Round 7 — R8 full implementation review (2026-10-29)

This is the current R8 review. Earlier passes above describe older protocols and do not certify this candidate.

- `review_mode`: full; independent change-code-review with Agent Context Review Mode B.
- `validated_at`: `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`.
- `executed_base` / `effective_base`: `80db8b9a6`; `effective_through`: `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`.
- Approved design baseline: `452e26373` (R8); the candidate also retains the native-identity repair supplement and historical-capability delta sections. These were checked, rather than silently treating the old acceptance as current.
- Scope: the entire implementation increment, including foreground read-only enforcement; frozen root/child sources; original-message continuation; extraction/cache/replacement/no-signal; consolidation/staging/receipts/recovery; public shared history and bounded IM access; protocol migration; prompt provenance; retained configuration, Skill and UI contracts. No implementation, test, design or production change was made by this reviewer. Concurrent caller edits to implementation-r8.md are outside this report's fixed candidate.

**Verdict: changes requested.** Two CONFIRMED product defects; one CONFIRMED low-priority documentation issue. No PLAUSIBLE finding is being promoted to a confirmed product failure.

### Findings (current JSON)

```json
[
  {
    "file": "packages/dsh-integration/src/knowledge/dreaming.ts",
    "line": 351,
    "summary": "[P2] Retain staging while a completed run still needs Git compensation",
    "failure_scenario": "A run saves its Markdown but receives saved=true/versionRecorded=false. After eight days offline, recover() deletes its staging because state is completed. execute() still selects that same run for version compensation (line 141), and apply() rereads staging (line 297), now raising ENOENT before new source work can start. This loses the recovery material and repeatedly blocks future maintenance; the already-saved body remains intact.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "WARNING",
    "recommendation": "Exclude runs with outstanding version-recording receipts from retention cleanup, or make compensation independent of retained staging. Keep the existing recovery seam and cover expiration followed by successful compensation/new work.",
    "evidence": "dreaming.ts:139-150,290-300,349-355; independent built-candidate recover() reproduction /tmp/feat676-static-r8-repro.json: recovery.staging_retained=false, requires_version_compensation=true, next_apply_read=ENOENT. The reproduction invokes the real recovery method with a minimal domain fixture and temporary actual files; no production incident is claimed."
  },
  {
    "file": "packages/dsh-integration/src/knowledge/memory-sources.ts",
    "line": 63,
    "summary": "[P2] Preserve the Inbox source envelope when expanding original messages",
    "failure_scenario": "A PA Inbox read returns target/name/conversation_type/delivery/channel around messages. renderMaterial() emits only the outer event metadata and body.messages, dropping that source envelope. prepare() sends batch.text directly to consolidation, and child renderNative() uses the same expansion. Oversized-message materialSegments() also drops the envelope from each continuation. The model receives the words/author but loses whether they came from an observer source and the original historical conversation context. A preceding tool call may retain a target, but it cannot recover the missing historical delivery/name/type fields.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "WARNING",
    "surface": "Global original-material input, child extraction input and long-message continuation",
    "expected": "Preserve actual author, chat, time, message identity and participant/observer provenance through readable projection, extraction and consolidation (design section 4.4; Agent Context Engineering sections 3 and Messages/Inbox).",
    "observed": "Inbox.read places those fields only on its result envelope (packages/personal-assistant/src/inbox.ts:287-288). renderMaterial() omits every body field except messages; materialSegments() copies record/message metadata without the body envelope. A synthetic envelope with target=conversation-unique and delivery=observer becomes just the event metadata, sender, id and text.",
    "impact": "Durable summaries and role memory cannot reliably preserve historical observation scope and audience applicability from the supplied source. This confirms an interface information loss; it does not claim that a real model has already disclosed information or certainly misattributed it.",
    "recommendation": "Carry the non-messages source envelope into the readable result and each long-message segment; preserve message-specific overrides. Extend the existing source-projection seam to check the actual rendered text/continuation with a realistic PA Inbox envelope.",
    "evidence": "memory-sources.ts:56-84,236,313,347-350; dreaming.ts:250-264, dreaming-agent.ts:130-133; inbox.ts:274-290; /tmp/feat676-static-r8-repro.json: context.preserves_target=false and context.preserves_delivery=false. This is deterministic serialization evidence. Native request delivery is separately captured in /tmp/feat676-static-r8-context/requests.jsonl records 3-4; that probe uses direct synthetic input, so it is not a live observer-case reproduction."
  },
  {
    "file": "docs/changes/feat-676-role-memory-dreaming/spec.md",
    "line": 156,
    "summary": "[P3] Restore implementation links relative to the active unit",
    "failure_scenario": "The three packages links on lines 156-157 use ../../../../ from docs/changes/feat-676-role-memory-dreaming. They resolve outside nano-multiagent and all three targets are absent; readers cannot follow the cited implementation. ../../../ is the active-unit depth, while four levels is appropriate only under archive.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "severity": "SUGGESTION",
    "evidence": "Candidate diff from design baseline 452e26373 changes those three links. Path.resolve()/exists() confirms the targets point to /Users/czj/.codex/worktrees/unit-feat-676/packages/... and do not exist. docs-check passes because its maintained-source scope does not cover these active-unit links."
  }
]
```

### Context delivery and consumption evidence

The affected consumers are foreground root/ordinary child, first-level task extractor, and the single consolidator. Review followed source ownership/qualification → readable input → prompt/tool assembly → cache/generation invalidation → staging/application → root refresh and maintenance recovery. Extraction and consolidation retain distinct duties; all new DSH imports are public declared package imports, and PA/IM use product-contracts rather than DSH.

- Candidate code and `dreaming-task-runtime.test.ts` preserve inherited provenance, replacement/no-signal and real native notes/new_context/source_history handling; the fixture's model returns are controlled. Reused `/tmp/feat676-native-no-signal.log`, `/tmp/feat676-cycle.log`, `/tmp/feat676-history3.log` and the 307-test expanded run as applicable deterministic evidence, not real-model understanding.
- Independent native pre-adapter capture: `/tmp/feat676-static-r8-context/requests.jsonl`, with structural locator `/tmp/feat676-static-r8-context/summary.json`. Records 1/2/5 are root requests with formal-memory read-only guidance; record 3 is `dreaming-bc606e0e-5c33-45b0-8a02-6d8abe68415b` with the actual role prompt, qualified Global input, source directory, `source_history`, own `history/notes/new_context/get_context_remaining` and `finish`. It has no Inbox, messaging, business task, scheduling, shell or Skill publication tool. Record 4 contains the actual finish result in the next maintenance request. The source directory supplies the otherwise-required session IDs. This is a native-runtime fixture with controlled llm/stream output, before provider adaptation; it proves assembled delivery and result presence, not autonomous tool choice or provider-wire behavior.
- Source-history/IM return schemas, identity binding, generation checks, cursor scope, Unicode and cutoff filtering were followed in `dreaming-history.ts`, `memory-source-view.ts`, `global-agent.ts` and `work.ts`. The ordinary history API remains the shared package's archived-current-session view; source_history uses public `createHistoryView` for qualified business snapshots. No implementation copy or private import was found.
- The Codex fixed originals, extraction/consolidation adaptation diff, Muse content-dimension mapping and packaged license/provenance were compared with the final prompt. This establishes source/adaptation coherence; it does not establish real-model preference generalization, audience handling or reflective behavior.

Independent checks: source/history narrow regression **14/14 passed**, `/tmp/feat676-static-r8-narrow.log`; docs-check using `PYTHON=.venv/bin/python` **passed**, `/tmp/feat676-static-r8-docs.log`. The initial system-Python invocation lacked yaml and is an environment failure, not a product finding. `git diff --check` finds only copied Muse original trailing spaces, retained as source fidelity and not reported as a defect.

### Limits and stopping point

The two defects above are directly reproducible at their lowest relevant seam. Real provider request serialization, autonomous source/IM recovery choices, the S21-S30 journeys, affected S05-S07/S13-S20 behavior and the current full CI remain caller/product-review work. implementation-r8.md's preliminary real-model self-check is not independent R8 acceptance. Old UI/legacy/Skill evidence may only be retained for unchanged behavior; it cannot close changed source or single-writer behavior. Scope is sufficiently covered for this full static review; after fixes, review the actual fix delta and these named conditions rather than repeat the entire branch.


## Round 8 — R8 finding closure at eff2d4684 (2026-10-29)

- `review_mode`: closure; `validated_at`: `eff2d4684cc396824ae65943f485a9ba66175111`.
- `finding_origin_head`: `6205cc5794ad6efab00cd144b61e3b2f9eefa09d`; actual fix delta: `b8069b23892d035e67aa0695ae150a9a864e4265..eff2d4684cc396824ae65943f485a9ba66175111` (b8069b238 adds reports only).
- Retained effective implementation coverage: `80db8b9a6..eff2d4684cc396824ae65943f485a9ba66175111`, using Round 7 full review plus this bounded closure. No full review was repeated.
- Focus: F-R8-1, F-R8-2 and D-R8-1; also inspect the actual delta's Web/iOS explanatory strings, test update and implementation/source-reference documentation. Only these two reports were changed by the reviewer.

**Code-review verdict: pass for this closure; surviving findings: `[]`.** This closes the named implementation/documentation findings, not current product acceptance or provider-model behavior.

| Focus finding | Disposition | Direct closure evidence |
| --- | --- | --- |
| F-R8-1 — outstanding Git compensation loses staging after retention | **closed, CONFIRMED** | dreaming.ts:351-354 calculates pendingVersion and retains a completed plan with outstanding saved/unversioned receipts. The existing recovery seam now creates a real .git/index.lock, saves the body while version recording fails, removes the lock, ages the run eight days and uses recover/start to complete version recording; a subsequent aged recovery cleans staging and start reports no increment. The reviewer independently ran this candidate test with Node 24.22.1, not just a mocked Git call. Retired plans remain ineligible for replay under the pre-existing apply admission. |
| F-R8-2 — Inbox envelope lost in readable input and long-message segments | **closed, CONFIRMED Context interface repair** | memory-sources.ts:62-63 emits non-messages envelope as Conversation data; 78-81 attaches that same envelope to each original-message continuation. Message-level sender/id/content remain distinct and preserve their own overrides. Shared renderNative/Global paths continue to use this renderer. Existing Unicode source test now verifies each message page's target/name/observer/type/channel in actual batch.text, and a direct-envelope test verifies the short form. Independent built-candidate rendering contains target, observer, group, web and m1; the 20-test run includes both protections. This proves the formerly lost information is delivered by the projection; no autonomous-model interpretation is inferred. |
| D-R8-1 — active-unit packages links | **closed, CONFIRMED** | spec.md:156-157 restores ../../../packages; the reviewer resolved all three implementation references and confirmed each exists inside the checkout. |

Independent narrow rerun: `PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec vitest run packages/dsh-integration/tests/dreaming-recovery.test.ts packages/dsh-integration/tests/memory-sources.test.ts`, **2 files / 20 tests passed**, `/tmp/feat676-static-closure-eff2d.log`. Reused owner evidence: `/tmp/feat676-review-red.log` records the original 3 failing / 17 passing conditions; `/tmp/feat676-review-node24.log` records **5 files / 26 passed**, and `/tmp/feat676-review-build-node24.log` records the integration build. Scope and assertions were inspected; no broader repeat was needed.

The English/Chinese Web help and iOS help now say that turning off Dreaming preserves reading existing memory and permits explicit manual organization. This matches the sole-writer contract and removes the earlier implication that foreground writes still occur. The delta changes strings only; `/tmp/feat676-review-ui.log` records **28 UI tests passed** and `/tmp/feat676-review-ui-build.log` records the Web build. True-page/prototype R6 acceptance remains the product reviewer's responsibility. No new Context-facing runtime behavior was introduced by these UI strings.

The appended implementation evidence records the owner's fixed-Codex source-mechanism inspection and Nano adaptations; this reviewer did not repeat that whole upstream investigation. The corrected source locator was independently checked at `8fdf6472955749a731fd9e4b8ffc218e8e80c51d`: phase1_output.rs and rollout_input.rs exist, while stage_one.rs does not. Original prompt/body review from Round 7 remains effective. `git diff --check b8069b238..eff2d4684` passes.

Agent Context Review Mode B here is a targeted closure of the deterministic provenance projection failure. Round 7's actual native pre-adapter root/consolidator request evidence remains scoped to that original capture; it is not relabeled as a new eff2d4684 provider-wire or observer-model run. Current real-model source query, own-context restoration, audience-sensitive consumption and full product acceptance remain open pending the in-flight independent report. No new confirmed or plausible finding survives this fix delta.


## Round 9 — final R8 evidence closure (2026-10-29)

- `review_mode`: closure / evidence delta; `validated_at`: `5432c125ad33ec163515dc25acd663da972b3796`.
- `executed_base`: `5ef3bbf960c053629a51830cfc03aa19389a5530`; `effective_base`: `80db8b9a6`; `effective_through`: `5432c125ad33ec163515dc25acd663da972b3796`.
- Reviewed product-code snapshot remains `eff2d4684cc396824ae65943f485a9ba66175111`. The later increment is the independent acceptance report, one S29 test and evidence documentation; c08c3a653 imports main@082e72ec4's bugfix-678 design/incident documents only. Direct diff confirms no later product-source/UI/native/contract implementation change. Previous full and fix-closure coverage is retained; no full review was repeated.

**Final code-review verdict: pass; surviving findings: `[]`.** F-R8-1/F-R8-2/D-R8-1 remain closed. The verifier's V-R8-1 evidence gap can now close on the bounded evidence below. Acceptance retains historical non-blocking T1; it is neither reproduced nor claimed fixed here.

### Reviewed evidence delta and Context scope

`acceptance.md` Round 4 at 5432c125a independently reconciles **30 unique S01-S30 rows**, with genuine-model, controlled-native and retained-evidence boundaries. Its actual product verdict is **pass-with-issues, 0 blocking / 0 major / 0 new minor**. The report explicitly supersedes obsolete foreground-memory-write acceptance rather than inheriting it into the sole-writer design.

For the material Context gap, the reviewer inspected `/tmp/feat676-r8-product/s27-source-history-proof.json`, the corresponding actual adapter request `68981408217c48c39483d4b8bdd5ecd4-request.json` in `/tmp/feat676-live-evidence/`, saved memory, native host-receipt text and run snapshots. Initial material contains only characters 0–8200 of the 15,299-character original message, and neither K-47 nor K-74. The actual model calls source_history search then same-root/initial-window item 24 read at offset 12500; the next actual requests contain the returned appendix. Saved project text distinguishes allowed K-47 from K-74 evidence, records candidate B as failing, and qualifies no deployment/no authorization as the supplied record's status rather than an independent audit. The host records 2/2 saved and versioned. The four completed runs share cycle 93043ffd-1a4d-4365-9a27-0b26df788021; the final run reaches the frozen root through=69 and no longer reports a remaining source range. This is genuine model selection and actual persistence, not the earlier controlled finish fixture. The capture is outbound adapter wire to the local transparent proxy; it does not prove the shared LLM_PROXY's final upstream transformation.

The new `apps/im-server/tests/e2e/memory-conversation-production-chain.test.ts` is a different appropriate seam: real IM child process/HTTP-created records, actual device binding and authenticated WS, real GlobalAgent/NodeStore/InboxStore and memory.conversations relay route. Inspection confirms assertions for search pagination, read original message ID, info/current metadata, no changes to pa_source_reads/pa_source_events/Inbox/journal, unsupported join rejection and old-cursor rejection after withdrawal. The caller/runtime is controlled; the test does not claim a model autonomously chose conversations or exercise the daily Node. Owner `/tmp/feat676-im-process.log` and independent product `/tmp/feat676-r8-product/s29-process.log` each record **1/1 pass**; `/tmp/feat676-r8-product/s29-mechanism.log` adds **2/2** narrow tests. These trustworthy runs were reused without a third identical run. No new finding was found in the test or cleanup/identity wiring.

S28/summary replacement/no_signal and selected failure boundaries retain their controlled native depth; they are not relabeled autonomous-model behavior. S01's nonempty persistent Global cross-chat answer proves scope/correction handling using available original exchanges and links, not a new empty-context memory-only recall experiment. The expert's actual document read and subsequent correct answer supply the separate document-consumption observation. Product report locators preserve failures and preparation-vs-save distinctions rather than treating every response as completion.

Four active delta files are byte-for-byte unchanged since eff2d4684 and still align with the approved target and reviewed implementation. Their canonical requirement destinations exist; all seven Gateway and two IM MODIFIED requirement identities resolve. They may now be reconciled into canonical specs by requirement identity (replace existing earlier-version clauses, do not append duplicate ADDED headings) and archived as pure documentation. This report does not perform or certify a not-yet-created canonical/archive suffix; the caller must record the exact retention delta. The new iOS Simulator build evidence ends BUILD SUCCEEDED; it establishes compilation, not iOS visual acceptance. Local full-suite evidence remains scoped to its recorded versions plus targeted final deltas; no remote CI/merge/deployment result is asserted.
