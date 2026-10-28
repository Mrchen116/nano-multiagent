# Code review: feat-676

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
