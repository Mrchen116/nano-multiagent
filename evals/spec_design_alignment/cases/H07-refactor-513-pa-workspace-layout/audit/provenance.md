# H07 provenance — refactor-513 product workspace layout

## Product clock

- Safe cutoff `B`: `d96b7c4ea5196186588443b3ae88f61955bd41e5`, tree `4376bfb0e7dae418e70479dd458d204636547930`.
- The first target trace is its child `adb93d33a2ec5443a647dd367eb67557ac72e199` (`docs(refactor-513): define product workspace layout`). B predates the motivation, design and implementation.
- Candidate product claims come only from B. Merge `ff27a30b4ab3759213ec148ae46f0a6a6d23a12a` is private held-out evidence.

## Knowledge clock

- Mode: `historical_cutoff`; candidates receive the complete scrubbed B repository with its mixed legacy `.nano`, `.nano-assistant`, PA and CLI behavior.
- No migration result, production machine state, target document or later current code is exposed.
- Private authority mapping audits the cross-package owners without narrowing candidate discovery.

## Documentation clock

- Mode: `suite_frozen_latest`; F is the target-authored commit `adb93d33a2ec5443a647dd367eb67557ac72e199`, tree `025b16b8c900c2b40ac23b126f99eda94e280633`.
- This clock coincidence is safe only for framework/workflow-owned bytes: the entire target unit is scrubbed and no post-B product claim is projected. B's current specs and product docs remain exact.

## Workflow clock

- Mode: `current_frozen`; W equals F.
- Historical workflow roots are removed, then exactly one A, A+USER or B bundle is installed. The terminal is one motivation/spec plus Gate-2-complete design/delta/milestone package; no code or migration executes.

## User clock

- Mode: `current_cross_fitted` for A+USER/B and none for A.
- Exclude refactor-513, namespace/layout conclusions, per-turn scope, migration dispositions, JWT procedure, PR 253, fleet execution and target review/acceptance descendants.
- Stable cross-case preferences cannot pre-answer D01-D08.

## Model/tool clock

- Mode: `current_frozen`; exact run identity, reasoning, permissions and budget are sealed later.
- Network, production hosts/configuration, host memory, parent history, real migration, push and external side effects are disabled.

## Five-layer manifest

| Layer | Input | Transform | Candidate visible |
|---|---|---|---|
| Product world | B tree `4376bfb0...` | exact archive plus suite scrub | yes |
| Documentation world | ProductClaims@B + framework ownership at F | preserve B claims; inject only W-owned workflow paths | yes |
| Common compatibility | native-spec N0 epoch | empty | yes |
| Arm bundle | frozen A/A+USER/B | one workflow, profile by arm | yes |
| Private controls | inventory, rubric, provenance, owner policy | none | no |

## Normalizer

- Suite N0 adds no file-placement table, migration matrix, security hint, target alias or selected-module guide.
- The full B repository provides the ambiguity this refactor must resolve; private controls never influence source selection.

## Lineage audit

- C1 historical-posthoc. Only the two earliest owner observations are public; eighteen clarifications, target documents, multi-round design review, code, one-time fleet migration and acceptance remain private or excluded.
- Because F/W is the first target-doc commit, validator assertions must prove the whole target path and its text atoms are absent after injection. Workflow assets at the same commit are allowed only through the suite-owned fixed list and hashes.
- A retained target decision raises contamination to C2; any access to target documents, later code, production state, raw session, host memory, private judge or parent Git history is C3 and invalidates the run.

## Snapshot generation

1. Archive B and verify commit/tree/source-root hashes.
2. Remove treatment roots, direct active/retired units and B-derived inconsistent archive roots as whole units; preserve B-consistent archive history and product Skills.
3. Inject the fixed arm A workflow assets only; assert refactor-513, feat-397 and private-control atoms are absent in paths and text.
4. Create one canonical parentless `main` commit and compare it to the stable receipt.

The exact public brief becomes the first user message. No private case asset or historical answer enters the candidate repository.
