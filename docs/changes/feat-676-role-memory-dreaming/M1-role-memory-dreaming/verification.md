# Verification Report: feat-676-role-memory-dreaming

> Validation snapshot: `6b4213c20 → be1fec6c9075ffafe402c7387f3cde25546ae95d`

- Round: 1. Mode: full, including corrected-delta reconciliation.
- Independent reviewer; code review and Agent Context Implementation Review reused from `code-review.md`.
- Verdict: **fail / incomplete M1**. Four confirmed implementation warnings and outstanding exit-criterion evidence prevent pass. `requires_full_verification: false`: this was already a full review; subsequent review can target the actual fixes and missing evidence.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All seven W criteria and five R criteria assessed; several only partially evidenced |
| Correctness | Ownership, current-file refresh, mode/tool exclusion and atomic per-file publication present; recovery, budget continuation, checkpoint scope and retired UI tool have defects |
| Coherence | Core package/DSH public-export boundary followed; four deviations described below |

## Evidence snapshot

- `/tmp/feat676-validation.txt` records implementation commands and locators. Runtime/PA aggregate was 425/426 followed by the affected 55/55 rerun (`/tmp/feat676-remaining.log`). Boundary suites: 16/16 (`/tmp/feat676-boundaries6.log`). Native request capture/scheduling/review: 8/8 (`/tmp/feat676-coretests4.log`). These are mechanism/provider-stub evidence, not model comprehension.
- Current-head build: `/tmp/feat676-build-be1fec6c9.log`, installer SHA `be1fec6c9075ffafe402c7387f3cde25546ae95d`. The older all6 log identifies the earlier commit and is not used to assert the final version.
- Caller reports build, typecheck and `check:ios-runtime` passed. `/tmp/feat676-python-ci.log`: 124 passed, 28 deselected. This includes the synthetic offline migration and dependency contract gate, but does not prove a production migration.
- At this review cutoff the caller's root TypeScript CI and native iOS build were still running. `/tmp/feat676-root-ci.log` already contained failures in personal-agent/control/personal-attention/providers/global-inbox-native without a final disposition. `/tmp/feat676-ruff-format.log` reported two files requiring formatting. `/tmp/feat676-docs-check.log` contained a missing-yaml execution failure, not a successful docs check. The caller must attach final commands/results and classify/fix failures before closing W7.
- PA live save/correction message locators are supplied in `/tmp/feat676-validation.txt`; the caller owns ongoing real product acceptance. No product scenario is marked passed solely from that summary.

## Completeness

| M1 exit criterion (`design.md:274`) | Available direct evidence | Status / remaining work |
|---|---|---|
| W1 certified live/cold source, own prefix, pairing, dedup/revision, budgets, crash boundaries | `memory-sources.test.ts:21-79`: second-flush cut, failure, inherited prefix, open calls, fragments, revisions and verified child tool evidence | Partial. Large-unit continuation is broken (F2). No final evidence of persistence restart at the source/cursor boundary or actual same-root multiwindow source export was supplied. Add only the missing meaningful seam coverage. |
| W2 conflicts, Git failure, every apply/cursor crash point; consumed/revoked source while off/restart/sync failure; child next decision | `memory-documents.test.ts:20-94`: body freshness, third version, Git failure, generation restart and lost atomic receipt | Partial. Library-level tests do not exercise Dreaming's full plan/entry/cursor recovery; F1 demonstrates a missed recovery failure. No supplied actual child request after revocation/sync failure or complete consumed-source cleanup evidence. |
| W3 injected timing, no increment, off/pause/resource/modes; creation and no F3/F4/combined | `dreaming-scheduling.test.ts:24-49`, `capabilities.test.ts:191-249`, `knowledge-review.test.ts`, config/PA tests | Substantial partial. Timing/admission, cancellation, legacy Memory-only review and fixed built-in Skill loading across selections covered. Real foreground Skill creation/discovery, no-increment actual provider count and both-direction live mode switching are not established by the cited subset. |
| W4 actual root/child/maintenance request, role/freshness/disabled tools/nonrecursive source; real model use | `memory-runtime.test.ts:6-43`, `dreaming-runtime.test.ts:6-31`; inspected actual adapter output/assembly and Skill provider | Partial. Root+maintenance capture exists, but applicable ordinary child request/refresh and real model scenario coverage remain with the caller. F3 is a deterministic model-facing control defect. |
| W5 Work binding/receipt, quiet success, refresh/recovery | `knowledge.test.ts:84` host receipt/link projection; native trajectory registration `trajectory-runs.ts:145-155`; native maintenance test | Partial. Projection/stub evidence exists. Reopened real authorized Work and no external notification in the full stack need the caller's acceptance evidence. |
| W6 Web1280/390 prototype, failure/pending/effective; native iOS build/shared config | frontend detail/config tests; iOS shared-selection tests/code; caller's current live UI observation | Pending screenshots/real contrast and native build. F4 exposes a retired memory control. Runtime TS compile is distinct from native Swift build. |
| W7 offline copies/repeat/interruption/back-switch; scenario table; build/contracts/docs | `test_role_memory_migration.py` covers 7 persistent-write interruption points, bytes/hash/permissions, preserved tool/Skill selections, progress and both stored mode choices; Python 124 passed and final-head build | Partial. Script reentry is proved, but saved mode choices are not a live runtime exclusivity demonstration. S01-S20 acceptance, final complete CI/native build/format/docs results outstanding. |
| R1-R5 actual product scenarios | Initial PA save/correction locators only; ongoing caller acceptance | Not independently accepted by this verifier. Product reviewer owns the journeys and must record every S01-S20 as passed/failed/blocked/not_run. |

## Correctness

| Requirement / scenarios | Implementation | Direct protection / conclusion |
|---|---|---|
| Role ownership, knowledge entry/details, S01-S04 | `document-memory.ts:35-53,99-112`, `memory-documents.ts:55-75`, bundled nano-memory | Trusted role/fixed owner root and blank initialization present. Behavioral scope/uncertainty remains real-model validation. |
| Immediate save/correction/manual save, S05-S07 | `document-memory.ts:54-94,130-134`, `memory-documents.ts:137-166` | Next-root-request stale-basis capture covered; F3 blocks ordinary scoped checkpoint. Original child behavior not established. |
| Actual outcomes/counterexamples, S08-S09 | `memory-sources.ts:77-133,155-177`, Dreaming prompt `dreaming.ts:214` | Failed call/result survives; assistant self-report labeled; own/inherited separation covered. Real synthesis still unverified. |
| Continuous increments/dedup/observation, S10-S12 | `memory-sources.ts:46-150`, `dreaming.ts:86-101,135-145` | Persistent step prefix and source cut covered; F2 prevents progress for a large unit. Actual cross-window journey pending. |
| Concurrent/partial/restart/Git/budget, S13-S16 | `memory-documents.ts:188-244`, `dreaming.ts:133-178,298-316` | Atomic third-version protection and lost receipt supported. F1 prevents later recovery; per-plan cursor crash coverage incomplete. |
| Controls/quiet work/permissions, S17-S18 | `document-memory.ts:116-156`, `dreaming.ts:109-121,204-291`, `knowledge.ts:51-72` | Status/control/tool result semantics and restricted maintenance present. No acceptance from assistant prose; host receipts projected. Actual Work/no-notification verification pending. |
| Migration/default/legacy/import, S19 | `migrate_role_memory.py`, Node configuration/capabilities, tool selection | Offline preservation/normalization/reentry supported; no automatic semantic import. F4 violates UI invisibility. Natural-language import/live mode exclusivity pending. |
| Source revocation/stop-use, S20 | `global-agent.ts:275-293,398-406,446-450`, `memory-documents.ts:169-188` | Complete authority sync precedes cache revoke; generation/pending suppresses entry and is persisted. Full consumed-source cleanup and child behavior still require evidence; registration alone does not establish cleanup. |

## Coherence

- DSH runtime operations remain in dsh-integration using declared public dependencies/exports; Node/PA retain their bridge boundaries. No runtime fork/private import or second agent loop introduced.
- `document` and `legacy` model tool/prompt paths are exclusive; the old writable root is separate. Existing explicit selections stay restricted. Built-in skill-creator is supplied from the package and cannot be shadowed by a user copy; the actual tool allowlist is not expanded.
- Dreaming starts an empty native handle with explicit input files and six allowed tools, no inherited normal sections/contexts, no model-managed catalog entry; Work uses trusted parent/session registration and host outcome projection.
- The approved design requires recoverable conflicts, bounded continuation, per-page confirmation and no exposed old controls. F1-F4 are implementation deviations, not reasons to change the design to fit the code.
- Migration prompt and actual script agree on stopped-writer requirement, raw backup, independent writable legacy root, new blank entry, explicit frozen baselines, retired setting cleanup and no grant of missing tools. Baselines are operator input; the script does not certify live flush itself, which correctly remains the deployment operator's responsibility. Native live mode switch and conversational import still need acceptance.

### Prototype / Reference Contract

| Contract (`design.md:230-232`) | Milestone | Evidence | Status |
|---|---|---|---|
| Only Dreaming control; no memory/creation switch or skill-creator selector | R5/W6 | Web/iOS filtering and config tests; caller observed legacy memory Tool Allowlist row | F4 warning; screenshots pending |
| Save versus applied/pending/failure, draft retained | R5/W6 | Existing config save architecture retained; affected frontend tests | Real1280/390 save/failure/effective comparison pending |
| Work shows range and partial outcomes | R4/W5 | Host partial summary projection test, restricted runtime receipt | Real authorized Work/reopen evidence pending |

## Issues

### CRITICAL

- **C1 — M1 exit criteria are not yet complete** (`design.md:274`). W1/W2/W4 need the specific missing deterministic boundary coverage above; W5/W6 and R1-R5 require caller-owned actual acceptance evidence. W7 still requires final CI/native iOS/format/docs outcomes. Attach versioned direct evidence and resolve real failures; do not treat this report as product acceptance or silently narrow the milestone.

### WARNING

- **F1** `dreaming.ts:133`: retire/rebase inapplicable partial plans while preserving actual saved receipts and third versions; demonstrate subsequent backlog progress and restart safety.
- **F2** `memory-sources.ts:136`: bounded page/continuation support for oversized units without prematurely advancing the unit cursor; demonstrate that a later item eventually becomes reachable under the same budget.
- **F3** `document-memory.ts:132`: scoped confirmation must reuse valid unchanged versions instead of requiring every unrelated page to be reread on each ordinary edit; demonstrate an edit in a library containing an unrelated unread page and maintain revocation safety.
- **F4** `apps/node/src/capabilities.ts:50`: remove the retired tool from document-mode visible settings/catalog/display while preserving stored choices and ordinary tool permissions; verify the actual settings page.

### SUGGESTION

None. Stop after the confirmed findings and required exit evidence are handled.

## Corrected Delta Reconciliation

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| gateway/agent-capabilities: document memory, immediate edits, scoped consumer refresh | document-memory + memory-documents; current-root request capture | implementation-mismatch (F3); child/model evidence pending |
| gateway/agent-capabilities: persistent bounded Dreaming, conflict/restart/Git progress | source adapter + Dreaming + atomic tests | implementation-mismatch (F1/F2) |
| gateway/agent-capabilities: fixed skill-creator, paused Skill automation, modes/defaults/migration | configuration normalization, native fixed-Skill test, Memory-only legacy review, offline migration tests | aligned at inspected mechanism level; actual creation/mode journeys pending |
| gateway/personal-agent: current source eligibility and derived knowledge invalidation | serialized authority sync, pending/generation, restart test, follow-up instructions | aligned at inspected mechanism level; full S20/child evidence pending |
| im/agents-nodes: only Dreaming UI, no retired control, file-only mode | projections/filtering and config tests | implementation-mismatch (F4) |
| im/agent-work: separate native maintenance, host partial results, quiet success, reopen | trajectory registration and host Work projection | aligned at inspected mechanism level; full-stack Work/no-notification evidence pending |

### Uncovered Observable Behavior

No additional deliberate external behavior change was identified outside the four delta files. The catalog/display residual and checkpoint behavior are implementation deviations already listed. Delta itself is not rewritten to accommodate them.

Outcome: **implementation-mismatch**.

1 critical issue (incomplete exit evidence), 4 warnings. Fix and finish the listed evidence before PR approval.
