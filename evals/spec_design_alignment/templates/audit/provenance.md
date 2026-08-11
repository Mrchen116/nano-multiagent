# Case provenance

> Record observations and hashes here; do not infer missing history. Freeze before a confirmatory run.

## Product clock

- Mode:
- Cutoff timestamp:
- Commit/tree hash:
- Evidence for “before first target trace” or prospective seal:

## Knowledge clock

- Mode:
- Included authorities:
- Excluded future material:
- Snapshot hashes:

## Documentation clock

- Framework commit/tree and clock id:
- Product claims bound to Product@B:
- Projection level and receipt hash:
- Clean-room change-unit disposition (`active/retired` removed; B-consistent completed archive preserved):

## Workflow clock

- Bundle version/hash for A:
- Bundle version/hash for A+USER:
- Bundle version/hash for B:

## User clock

- Base profile version/hash:
- Cross-fit exclusions and reasons:
- Resulting profile hash:

## Model/tool clock

- Model/build and inference settings:
- Tool/runner image versions:
- Permission manifest hash:

## Five-layer manifest

| Layer | Build input | Transform | Output hash | Candidate visible |
|---|---|---|---|---|
| Product world |  |  |  | yes |
| Documentation world |  | DP1 projection at F with product claims constrained to B |  | yes |
| Common compatibility |  | suite-locked N0 copy/alias only |  | yes |
| Arm bundle |  |  |  | yes |
| Private controls |  |  |  | no |

## Normalizer

- Identity/version:
- Inputs visible to normalizer:
- Evidence that task/arm/private answers were hidden:
- Transformation audit:

## Lineage audit

- Candidate contamination level (C0-C3):
- Treatment-authoring status (`historical_posthoc`, `pre_treatment_freeze_visible`, or `post_treatment_freeze_blind`):
- Published authoring-freeze receipt ref/hash/commit (clean holdout only):
- First case-assets commit/time/manifest and receipt-to-case-to-HEAD ancestry (clean holdout only):
- A/B workflow and profile-builder lineage-manifest refs/hashes:
- Per-case cross-fitted profile lineage-manifest ref/hash:
- Workflow-derived candidate exposure:
- Profile-derived candidate exposure:
- Common/normalizer-derived candidate exposure:
- Private oracle lineage (`historical_target_derived_private` or `prospective_pre_output`):
- Judge calibration/few-shot exposure:

## Owner-answer protocol

- Pre-run neutral decision-sheet version/hash:
- Pre-run owner-answer-policy version/hash:
- Spec no-answer refinement budget:
- Design no-answer refinement budget:
- Initial/refined package mapping version/hash:
- Blind order/random seed and per-run replay-log location:

## Snapshot generation

- Frozen suite source-root manifest id/hash:
- Source ownership: outer `.claude/.agents/.codex`, root `CLAUDE.md` / `CODEX.md`, `cc-hooks-on/off`, and undeclared `SKILL.md` roots removed; declared product implementation roots preserved:
- Cutoff `AGENTS.md` source/projection hash (preamble before first `## ` plus exact `架构总览` / `架构红线` / `工作红线`; no `## Project overview` or current backfill):
- Archive command/recipe:
- Pre-scrub archive manifest/hash:
- Suite treatment-scrub version/hash:
- Source/composed `AGENTS.md` clocks, hash and workflow ownership:
- Post-scrub product-world manifest/hash:
- Confirm absent: feat-397, snapshot Agent runtime/skills, non-selected arm bundles:
- Fresh-root commit hash:
- Fresh-root Git envelope (byte-canonical HEAD/config/index/ref/raw commit/loose-object closure; HEAD tree equals candidate manifest):
- Candidate export allowlist:
- Confirm excluded: `case.json`, `knowledge/`, `judge-private/`, `audit/`:
- Leak scan result:
- Frozen suite-seal ref/hash, materialized run-plan/control hashes, and run-ledger schema hash:
