# Verification Report: feat-627

> R1 / verification_mode: `full`, with `corrected-delta` reconciliation.
>
> Nano validation snapshot: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28 → 31e47aab36782a99c17d709b6496f344892c55a1`.
>
> Plugin validation snapshot: `d74876a90968bd5498b5af0bcc2f327c3131f007 → 7f0a2b78ec530075edd48452c2cf5499548ca99c`.

## Summary

| Dimension | Result |
|---|---|
| Completeness | M1 implementation and static validation covered; mandatory independent real-product evidence pending, so M1 is not yet complete |
| Correctness | All six spec requirements have implementation and relevant automated protection; user-visible long-task outcomes are not certified by those tests |
| Coherence | Follows the approved design, including R5 output-reserve policy and all-Agent default scope |
| Corrected delta | `aligned` at the implementation/contract level; product acceptance remains pending |
| Verdict | **PENDING / not ready for final delivery: 1 CRITICAL completeness issue, 0 WARNING, 0 SUGGESTION; 0 identified implementation defects** |

`requires_full_verification: false`. The current full source review is complete. Closing the outstanding product evidence can reuse these static conclusions if the implementation refs remain unchanged; source fixes require the appropriately scoped revalidation. Both worktrees were clean and at the frozen refs when inspected; this report does not substitute a later report commit for `validated_at`.

## Completeness

- M1 implementation scope is present in both repositories: independent fixed package; native deterministic context engine; four tools; durable Notes/History; model budgets; Nano default migration, lifecycle, selection and approval; plugin guidance and delta. M1 remains **0/1 fully closed** because its reviewer exit criteria are still pending.
- All requirements/scenarios are mapped below. No missing implementation was identified. A real model smoke (`FEAT627_DEFAULT_OK`) proves default dispatch is reachable but does not prove the multi-window product journey.
- Prototype/reference contract: **N/A**. There is no new client interface or visual must-match contract.
- PR creation is the caller's delivery step after the gates, not a circular prerequisite for this pre-PR static report. This reviewer did not create or modify a PR.

## Correctness

Paths beginning `plugin/` below refer to `/Users/czj/Repos/opensource-hub/dsh-agent-context-worktree`; Nano paths are relative to this unit worktree.

| Requirement / Scenario | Implementation evidence | Test / acceptance evidence | Status |
|---|---|---|---|
| Multiple resets continue one task; later correction supersedes an older plan | `plugin/src/index.ts:123`, `plugin/src/index.ts:263`, `plugin/src/checkpoint.ts:16`, `plugin/src/history.ts:78`: no old tail or task summary is automatically restored; explicit references and recovery preserve source | `plugin/tests/engine.spec.ts` observes three useful boundaries in one turn with seven requests and zero summary requests; current state and newly steered input survive. Actual latest-correction/final-answer/side-effect journey is assigned to product reviewer | Implementation covered; mandatory product evidence pending |
| Recover original user constraints and long result details | `plugin/src/history.ts:78`, `plugin/src/history.ts:174`, `plugin/src/history.ts:225`: full tool name/arguments/result payload and Nano/Inbox provenance, archived-only reads, Unicode offsets | `plugin/tests/history.spec.ts` recovers a 23,000-code-point result through its tail and metadata; native public-tool dispatch in `plugin/tests/tools.spec.ts` | Covered at the relevant API seam; real task result pending |
| No saved record / nonexistent historical detail | `plugin/src/notes.ts:99`, `plugin/src/notes.ts:130`, `plugin/src/history.ts:233`, `plugin/src/tools.ts:141`: empty listings and explicit missing-read errors; no other-session fallback | `plugin/tests/notes.spec.ts`, `plugin/tests/history.spec.ts`, `plugin/tests/tools.spec.ts`; truthful model handling is a product observation | API behavior covered; product evidence pending |
| Approaching budget, forced reset and failure visibility | `plugin/src/budget.ts:8`, `plugin/src/index.ts:141`, `plugin/src/index.ts:207`, `plugin/src/index.ts:284`: bootstrap, labeled reserve, pending-input estimate, reminder/fallback per window and bounded overflow recovery | `plugin/tests/reminder-delivery.spec.ts`, `plugin/tests/safety.spec.ts`, `plugin/tests/rollover.spec.ts` prove persistent notice state, repeated hard-cap boundaries, valid pairing and terminal fixed-only overflow | Covered; actual model pressure-reminder path pending |
| Normal restart continues saved work | `plugin/src/notes.ts:64` uses host home + encoded owning Agent/session; `plugin/src/history.ts:36` derives stable boundaries from session events; no separate ID database | Replay and reconstructed fresh-plugin notice-state tests; Nano fork/restart and persisted opt-out tests. No completed true-stack restart-continuation product report yet | Persistence primitives covered; reviewer exit pending |
| Other Agent/workspace records and recovered content do not expand authority | `plugin/src/tools.ts:142`, `plugin/src/tools.ts:246`, `plugin/src/notes.ts:72`: caller-supplied Agent/session/root is absent; `plugin/src/checkpoint.ts:29` and guidance mark recovery as evidence. Existing Nano send/approval paths remain | Cross-session/path traversal tests; Nano `tests/agent-context-default.test.ts` checks business denial and explicit downstream denial with Auto off across nano/codex/dsh rules | Covered at data/authorization seams; actual product isolation observation pending |
| New/existing ordinary, Global, Personal and child Agents default on, including empty business selection | `packages/dsh-integration/src/agent-context.ts:12`, `src/workspace-tools.ts:65`, `src/workspace-tools.ts:125`, `src/capabilities.ts:25`, `src/policy/approval.ts:103`; package dependency and lock fix the published candidate | `packages/dsh-integration/tests/agent-context-default.test.ts`: old/fresh/no-workspace/Global/PA scopes and real native child dispatch; `model-policy.test.ts` proves default zero-summary behavior and explicit opt-out original summary behavior | Covered |
| Explicit disable survives restart and newly created Agents | One-time manifest migration preserves user fields and existing installed/unselected state; set_bundle persists selection; no subsequent default reseed | `agent-context-default.test.ts` restarts the runtime and verifies disabled fresh/peer/old scopes independently | Covered |
| Existing enable/disable/re-enable entry, errors and other workspace isolation | Existing WorkspaceOwner idle barrier, scoped tree disposal, audit diagnostics and fallback remain; default shipped bundle participates in that lifecycle and is disableable, not removable | Retained/updated `workspace-tools.test.ts` validates applied ownership, failure diagnostics, off/on, isolation and restart-required replacement; default tests protect opt-out | Covered; separate product feedback journey pending |

Validation evidence:

1. Independently reran plugin `pnpm test` and `pnpm typecheck` at the frozen plugin ref: **9 files / 22 tests passed; typecheck passed**.
2. Read the final fixed-Release Nano logs: `/tmp/feat627-release-tests.log` — **107 files / 482 tests passed**; `/tmp/feat627-peers.log` — **no peer conflicts**; `/tmp/feat627-python-frozen.log` — **62 passed / 31 deselected**; `/tmp/feat627-docs-frozen.log` — **251 Markdown sources / 67 routes passed**. Reused version-bound owner evidence for frozen-lockfile install, build/typecheck, and unchanged Web **936 passed**. Baseline results are not treated as post-change product acceptance.
3. Independently checked local package SHA-256 `f8a26ca5c6558ef04a2ff2b7d93535993272f80cd05d138029c733aa391e4fb1`; owner records the same verified published download. Nano fixes the Release URL and pnpm integrity. Plugin package peers remain public DSH `0.2.1-alpha.1`; no DSH upgrade is hidden in the change.
4. Independently compared the three prompt fixture originals to Codex `464add49587a7cb6032d5ab04faa8a1585947853`, `models[0].model_messages.token_budget`: all match exactly; the reference model entry is `gpt-6-astra` with both enable flags false. All nine action description bodies were checked against that commit's `tools.rs`. Runtime adapted strings match the approved appendix/golden fixtures.
5. Full Nano `git diff --check` passed. No test-layer, new-file-size, unconditional-skip, duplicate-risk or removed-live-regression issue was found in the affected suites. Existing lifecycle coverage was retained and old summary/tool-list expectations were rewritten for the new public semantics; the original focused summary behavior remains tested after explicit opt-out.

## Coherence

| Design decision | Result | Code evidence |
|---|---|---|
| Independent renamed fork, prebuilt fixed Release, no submodule/kernel fork | Followed | Plugin package metadata/exports/peers and `cordis.patch.yml`; Nano dependency/lock; removed private generated path machinery |
| Full paired native compaction and strict shrinking, no old tail/handoff/Notes body | Followed | `plugin/src/rollover.ts:66`, `plugin/src/rollover.ts:208`, `plugin/src/checkpoint.ts:16` |
| Rebuild current runtime state at the actual pre-step/overflow seam; preserve newly claimed inputs | Followed | `plugin/src/index.ts:123`, `plugin/src/index.ts:207`, `plugin/src/index.ts:292`; first new native request asserted in engine/safety tests |
| Stable session + bracket seq/window and event seq/item IDs; successful ordinary compaction also counts | Followed | `plugin/src/history.ts:36`, `plugin/src/history.ts:78`; replay/boundary tests |
| Four flat native tools, empty-schema new_context, action dispatch | Followed | `plugin/src/tools.ts:29`; tool runtime/discovery tests |
| Session-local Notes, archived-only History, bounded indexes/slices and original provenance | Followed | `plugin/src/notes.ts:64`, `plugin/src/notes.ts:133`, `plugin/src/history.ts:152`, `plugin/src/history.ts:254` |
| Per-window reminder/fallback, policy output reserve for valid uncapped requests, bootstrap before first resolved request | Followed | `plugin/src/budget.ts:8`, `plugin/src/index.ts:141`, `plugin/src/index.ts:233`, `plugin/src/tools.ts:53` |
| All-Agent default with one-time profile migration, persistent disable and no business permission expansion | Followed | Nano `src/agent-context.ts:12`, `src/workspace-tools.ts:65`, `src/capabilities.ts:25`, `src/policy/approval.ts:103`; existing mount/maintenance/fallback path retained |
| Exact prompt baseline and documented minimal adaptations | Followed | `prompt-baseline.md`, `plugin/src/guidance.ts`, tool action descriptions and fixed-source cross-check above |

### Prototype / Reference Contract

N/A — no frontend prototype or visual must-match rows are defined.

## Issues

### CRITICAL

- **V1 — M1's mandatory real-product exit evidence is still pending** (`design.md:164`, `design.md:172`, spec's continuous-task/restart scenarios). The implementation and automated evidence support the primitives, but no completed independent product report yet establishes at least three useful resets during one actual model task, latest correction honored in the delivered answer, long-result tail recovered, exactly one controlled IM side effect, normal same-node/session restart continuation, truthful missing-record handling, and user-visible lifecycle/isolation/failure feedback. The owner explicitly reported the long-task review as ongoing. **Action:** obtain the independent product review with user inputs, actual delivered responses, boundary/model-request evidence, side-effect count, restart identity and cleanup evidence; attach its version-bound conclusion and close this issue if those exits pass. Do not rerun or replace that journey with fixture tests, and do not weaken the spec. This is an outstanding completion gate, not a confirmed implementation defect.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/agent-capabilities.md:5` — all-Agent default and persistent opt-out | Nano `src/agent-context.ts:12`, `src/workspace-tools.ts:65`; fixed runtime dependency, one-time profile seed, native set_bundle | `agent-context-default.test.ts`, `model-policy.test.ts` both default and opt-out cases | aligned |
| `specs/gateway/agent-capabilities.md:17` — continuous task and on-demand original detail recovery | `plugin/src/index.ts`, `src/checkpoint.ts`, `src/history.ts`, `src/tools.ts` implement no-summary transitions and source-preserving recovery | Plugin native multi-window, overflow and long-result tail tests; actual model outcome is the pending V1 gate | aligned at implementation/contract level |
| `specs/gateway/agent-capabilities.md:30` — restart durability, re-enable and unchanged record ownership | Session event replay derives IDs; Notes use owning session namespace; disable retains files/logs; existing scope lifecycle is retained | Plugin replay/isolation tests; Nano restart and off/on tests | aligned |
| `specs/gateway/agent-capabilities.md:43` — business allowlist plus only four internal context tools; Auto off does not block them, downstream deny still wins | Nano `src/capabilities.ts:25`, `src/policy/approval.ts:103`; registration disposal controls removal and no blanket workspace-tool bypass was added | Empty/nonempty business selections, PA/Global/child dispatch under nano/codex/dsh Auto off, explicit deny and business denial; existing capability/cron/lifecycle tests | aligned |

### Uncovered Observable Behavior

None identified in the unit implementation diff. The fixed shipped package's disable-only removal policy follows native shipped-bundle lifecycle semantics; schema/dispatch changes, manual compact's new default and opt-out summary behavior are within the documented default/recovery/lifecycle delta. There is no frontend change. Current specs were not silently rewritten to substitute for this pending active-unit acceptance.

Outcome: **aligned**. This reconciliation certifies that the corrected delta describes the final implementation; it does not close V1 or certify unobserved product outcomes.

## Handoff

```json
{
  "unit_id": "feat-627",
  "review_round": "R1",
  "verification_mode": "full",
  "verdict": "pending_product_evidence",
  "issues": {"critical": 1, "warning": 0, "suggestion": 0},
  "validated_issues": ["V1: mandatory real-product completion evidence pending; no confirmed implementation defect"],
  "implementation_defects": 0,
  "requires_full_verification": false,
  "corrected_delta_outcome": "aligned",
  "report_commit": null,
  "top_concern": "Independent product review must establish the M1 true-stack exits before final delivery"
}
```

Only `verification.md` and `code-review.md` were written. No implementation/runtime/config changes, service startup, commits or pushes were performed; no self-created runtime remains to clean up. The caller owns committing these shared-worktree reports and retaining or updating the outstanding product evidence.
