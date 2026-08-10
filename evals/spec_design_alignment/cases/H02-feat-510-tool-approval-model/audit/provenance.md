# H02 provenance — PA unified tool approval model

This provenance separates the raw historical request, the private historical owner answers, the pre-target product world and the held-out implementation oracle. The case remains `draft` until runtime manifests, the frozen owner-answer policy and owner review are complete.

## Request reconstruction

- Historical thread: `019fd65b-1d09-7852-993f-5a4e562930a2`.
- Host audit source: `/Users/czj/.codex/sessions/2026/08/06/rollout-2026-08-06T17-15-23-019fd65b-1d09-7852-993f-5a4e562930a2.jsonl`; this file is control-plane evidence and is never copied into a candidate workspace.
- The first raw user message is JSONL line 9 at `2026-08-06T09:16:25.132Z`. `public/brief.md` is byte-for-byte its text after removing only the terminal newline.
- The brief adds no title, PA boundary, field name, omission rule, failure rule, lifecycle, architecture hint, deterministic sequence or instruction derived from the later target.
- Later questions and owner replies are retained only as the private historical answer source below. Target-writing messages, tool output and later implementation requests are not candidate input.

## Product clock

- Mode: `historical_pre_target`.
- Safe world cutoff: `e9a2a02b48a651bdd1cb871c7a1a27c0f0c1c0d6`, commit timestamp `2026-08-06T15:29:40+08:00`, tree `64ee09dd5aae44f36fff9325835c7c45dc088b5c`, before the owner request.
- Deterministic base archive SHA-256: `2fd34f6d0cccd213b8d1963b0c6e102f54ef0696ca20cbdfe4b9f3cdbb280923`, produced by `git archive --format=tar e9a2a02b48a651bdd1cb871c7a1a27c0f0c1c0d6`.
- First committed target trace: `d7600ca913b040250e68acc46ba170093b46bbe7` at `2026-08-06T17:35:35+08:00`, adding the target spec. Its direct parent is `8abcd4ca0ea797126f6cb73d90e25cbd03fa218f`, not the selected cutoff.
- The intervening `1e20b25f76fc455e380bb766961447575deed47a` and `8abcd4ca0ea797126f6cb73d90e25cbd03fa218f` belong to unrelated bugfix-509 documentation. The more conservative `e9a2a02b...` cutoff is intentional: it is the last declared safe main state before the request and excludes every commit made during the request/design window, even unrelated ones.
- `git ls-tree` and `git grep` at the cutoff find no feat-510 path, target id, unified approval-model field or target phrase outside the later-private evidence. The field/helper/test paths introduced by the target are absent.

## Knowledge clock

- Mode: `historical_cutoff`, same Git tree as the product clock.
- Candidate-visible evidence is the scrubbed cutoff repository. `knowledge/authority-map.json` hashes the PA LLM configuration and persistence owner, Gateway composition, PA product-to-SDK seam, public kernel construction, auto gate, hook-model call, provider runtime, run origins, architecture and canonical pre-target contracts.
- Candidates may discover that both classifier stages omit a model, `HookModelCall` already accepts one, runtime resolves an explicit model through its registered provider, and PA owns a process-level LLM catalog. The normalizer supplies no answer-bearing summary of those facts.
- Excluded future material includes the complete feat-510 unit, Q1-Q6 answers, implementation/helper/fixture/tests, PR 248, verification and acceptance reports, target canonical merges, later code, current checkout state and host memory.
- No Claude Code, competitor or other external source snapshot is needed or exposed. The task is fully grounded in the Nano cutoff.
- Private held-out references pin the final archive/implementation tree to merge commit `b17a2e09ebfb13e8bf81cb088d4a6bd2345b01c9`. They are judge-only and admit equivalent behavior and architecture.

## Documentation clock

- Mode: `suite_frozen_latest`; framework/workflow F/W is commit `adb93d33a2ec5443a647dd367eb67557ac72e199`, tree `025b16b8c900c2b40ac23b126f99eda94e280633`.
- The native documentation epoch at B already has the required framework paths. DP1 therefore resolves to `preserve_exact`: candidate-visible product/documentation bytes stay at B, while the three workflow-routing paths are verified byte-identical to W.
- Every direct active unit and `docs/changes/retired/**` is removed. `drop_noncompleted_cross_references_v1` removes nine whole archive roots that reference B-noncompleted units; the remaining completed archives stay available as history, and neither the feat-510 target unit nor any `feat-397` path/text atom survives.

## Owner-answer record

The runtime `owner-answer-policy` must use `creation_mode=historical_owner_record`, bind the frozen decision-inventory hash and cover exactly resolved V decisions D01-D06. Each answer below is expressed as a semantic product constraint rather than historical option numbering or target implementation names. Replay remains `only_if_run_raises_equivalent_decision`.

### D01 PA-only scope

- Historical question/reply: JSONL lines 83-90.
- Owner answer: configuration applies to PA. The kernel may generically support explicit selection and reuse of the current Agent/run model; Coding CLI is not changed by this PA requirement.

### D02 Omission behavior

- Historical question/reply: JSONL lines 102-109.
- Owner answer: when PA omits the setting, automatic classification keeps reusing each triggering Agent/run model.

### D03 Invalid configuration

- Historical question/reply: JSONL lines 120-127.
- Owner answer: an explicitly selected model not registered in the PA model catalog is a startup error, not a silent fallback.

### D04 Classifier only

- Historical question/reply: JSONL lines 138-145.
- Owner answer: only automatic permission classification uses the selected model; normal Agent requests and post-tool continuation retain the run model.

### D05 No cross-model fallback

- Historical question/reply: JSONL lines 156-163.
- Owner answer: the chosen classifier model is a hard choice. Runtime failure does not retry classification with the Agent, default or another model; existing same-model retry and permission-failure handling remain.

### D06 Restart lifecycle

- Historical question/reply: JSONL lines 174-181.
- Owner answer: configuration changes become effective after Gateway restart, with no new field-specific hot reload.

At S0, integration must materialize `runtime/H02/private/owner-answer-policy.json`, use the six reconstruction references above as `source_refs`, compute its response-bank hash and replace the case's pending policy hash. No answer is injected before an arm independently raises the mapped decision.

## Held-out target lineage

Chronology and evidentiary role:

1. `d7600ca913b040250e68acc46ba170093b46bbe7` — committed spec after all six owner decisions.
2. `eaaed4c3ec91c5359044ca6b47d3834e8388063f` — design, delta-specs and independent design-review history; final review closes at 0 critical / 0 warning.
3. `89197f46323803d413a012f83418d5dad03049ce` — initial implementation and deterministic critical-path fixture.
4. `7f0d4be1e3d2adf992dd80413a4bed587cbf5ff8` — closes verification gaps for distinct provider clients and the real `background_task` origin.
5. `b17a2e09ebfb13e8bf81cb088d4a6bd2345b01c9` — merged PR 248 tree containing the archived unit, final implementation, verification and acceptance.

The production delta through `7f0d4be1e...` is a bounded vertical change: PA config/composition/product, public SDK build, one auto-gate call path and one kernel-scoped helper. The private oracle uses its behavior and failure probes, not its helper module, key, field spelling or registry bridge as mandatory topology.

## Workflow clock

- Mode: `current_frozen`.
- The runner removes snapshot workflow-owned roots and injects exactly one frozen A, A+USER or B bundle. A and A+USER workflow bytes must be identical.
- Literal scans of the currently selected workflow packages found no feat-510 id or exact target field/helper. Generic same-era lessons still justify C1 disclosure.
- A single-unit run freezes the owner-answered spec at S2 and the naturally reviewed Gate-2-complete design/delta/milestone package at S4. It must not implement code during the authoring run.

## User clock

- Mode: `current_cross_fitted` for A+USER/B and none for A.
- The profile builder must exclude feat-510, its six decisions, PR 248, exact field/helper, provider-routing and run-origin corrections, deterministic sequences, verification/acceptance, canonical merges and memory statements supported only by that lineage.
- Stable preferences may remain only with independent cross-case evidence. They cannot pre-answer D01-D06 or introduce target symbols.
- A+USER and B receive the same frozen leave-one-lineage-out profile; resulting hash: `TBD at S0`.

## Model/tool clock

- Mode: `current_frozen`; model build, reasoning, tool image, permission manifest and budgets: `TBD at S0`.
- Network, real channels, host memory, parent history, production credentials, push and external side effects are disabled.
- This case needs no browser or external account. Any later S6 implementation uses deterministic local recording clients/fixtures shared identically across arms.

## Five-layer manifest

| Layer | Build input | Transform | Output hash | Candidate visible |
|---|---|---|---|---|
| Product world | Git tree `64ee09dd...` | `git archive`; suite-wide treatment scrub; remove active/retired units and nine archive-lineage roots | `f79a953b...` final combined content manifest | yes |
| Documentation world | native B documentation framework, checked against F/W-owned routing paths | preserve exact; keep B-consistent completed archive | bound in base-repository receipt | yes |
| Common compatibility | suite-wide N0 derivation | empty for this case | TBD | yes |
| Arm bundle | frozen A/A+USER/B | one workflow; profile by arm | TBD per arm | yes |
| Private controls | inventory, rubric, owner policy and audit | no candidate transform | TBD at seal | no |

## Normalizer

- Identity/version: task-blind epoch N0 normalizer, `TBD at S0`.
- The cutoff already exposes current repository paths needed for discovery. No case-specific alias, selected-file guide, model-routing summary or compatibility document is added.
- Inputs are archive paths and suite routing rules only. Brief, target lineage, owner answers, decisions, held-out symbols and arm identity stay hidden.

## Lineage audit

- Candidate contamination level: `C1 generic lineage exposure`; this is historical-posthoc, not a clean holdout.
- The product and knowledge world predates the raw request and every target trace. It contains only legitimate pre-existing PA configuration, hook-model, provider-routing and run-origin facts.
- Treatment/profile lineage manifests must exclude every target-derived rule, example or statement listed above. A retained exact target decision changes the declaration to C2; access to target documents, raw session, host memory, current code, private judge or parent history is C3 and invalidates the run.
- Private oracle lineage is `historical_target_derived_private`. Judge material is frozen before outputs, never enters candidate inputs or generic calibration and accepts semantically equivalent designs.
- The original one-line request is intentional candidate input, not leakage. Historical owner answers are not public and are replayed only by the fixed policy after an arm raises the equivalent decision.

## Snapshot generation

1. `git archive --format=tar e9a2a02b48a651bdd1cb871c7a1a27c0f0c1c0d6` into a new temporary directory and verify tree/file/archive hashes.
2. Apply the frozen clean-room scrub: remove treatment roots, all direct active change-unit roots and `docs/changes/retired/**`; independently derive `drop_noncompleted_cross_references_v1`, remove its nine matching archive unit roots, and preserve the remaining B-consistent archive history. Verify `AGENTS.md`, `docs/changes/README.md`, and `docs/development/change-workflow.md` are byte-identical to Workflow@W before keeping them.
3. Add no external source root or semantic compatibility content. Inject exactly one frozen arm bundle and the allowed profile for that arm.
4. Create a single-root local Git repository with no remote, alternates, parent history, worktree metadata or host path.
5. Verify source and layer manifests, the fresh-root envelope, candidate allowlist and private leak signatures before S0.

The runner injects the exact `public/brief.md` bytes as the initial user message without copying the control file. Candidate export excludes `case.json`, `knowledge/`, `judge-private/` and `audit/`; the raw historical session and all runtime-private owner material remain outside the product snapshot.
