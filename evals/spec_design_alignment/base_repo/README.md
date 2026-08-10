# Evaluation base repository materializer

`materialize.py` builds the formal arm-A candidate repository for each registered case. The method is `counterfactual-latest-base-v1`:

```text
Code@B + ProductClaims@B + DocsFramework@F + Workflow@W
```

Every recipe freezes six clocks and five layers. Product/knowledge stay at the case baseline `B`; documentation uses the suite-frozen framework `F` without importing post-B product claims; workflow-owned files and skills come from `W`; arm A has no user profile. A+USER and B are deliberately not materialized until their profile/team bundles freeze.

## Formal recipes

| Case | Product baseline B | Documentation projection | Workflow ownership |
|---|---|---|---|
| H01 | `088b2f8b...` | DP1 moves exact B `docs/SPEC_GUIDE.md` to `docs/specs/CONTRIBUTING.md`, rewrites only two B index links, and generates framework navigation | composed `AGENTS.md` keeps B architecture red lines and adds W routing; the change index is the hash-bound W framework/lifecycle slice through `## 唯一定位`, not a whole-file F copy |
| H02 | `e9a2a02b...` | native epoch, preserve exact | `AGENTS.md`, change index and workflow file must be byte-identical to W |
| H03 | `ef52bbb1...` | native epoch, preserve exact | replace `AGENTS.md`; preserve the other two W-owned files exactly |
| H04 | `a51d9915...` | native epoch, preserve exact | preserve the three W-owned files exactly |
| H05 | `f54e008b...` | native epoch, preserve exact | preserve the three W-owned files exactly |
| H07 | `d96b7c4e...` | native epoch, preserve exact | preserve the three W-owned files exactly |
| P01 | `25dc9c81...` | native epoch, preserve exact | preserve the three W-owned files exactly |
| P02 | `25dc9c81...` | native epoch, preserve exact | preserve the three W-owned files exactly |

The formal registry is the eight JSON files in [recipes](recipes/). Each recipe binds its source commit/tree, F/W commit/tree, every projected or arm blob hash, required/forbidden output facts, complete content-manifest hash, and the canonical Git envelope. H06 is intentionally absent because the owner rejected bugfix-520 for the formal suite.

## Clean-room policy

The materializer exports the complete B tree, then:

1. removes outer treatment roots and undeclared `SKILL.md` roots while retaining product-owned skills;
2. removes every direct pre-existing change-unit root and `docs/changes/retired/**`;
3. derives B's direct active/retired unit-id set, scans every completed archive unit for references to that set, and removes each match as one whole root under `drop_noncompleted_cross_references_v1`; only the remaining B-consistent completed history is preserved;
4. records every archive disposition and lets the shared validator independently recompute the exact root/id list from B, without a case name, target keyword list or partial-file rewrite;
5. applies any epoch-wide, preregistered `drop_proposed_control` list before projection; H01 uses this task-blind rule for the obsolete root control records and proposal documents inherited from its legacy epoch;
6. retains the latest lifecycle/framework index at `docs/changes/README.md` through its W-owned recipe entry; H01 keeps only the hash-bound framework slice and excludes F-only evidence/migration claims whose link targets do not exist in that B world;
7. applies DP1 and one explicit arm closure;
8. rejects target atoms, forbidden paths, content-hash drift, unresolved declared links, collisions, symlinks and non-canonical paths; every formal recipe forbids the `docs/changes/feat-397-spec-design-agent-team` path and the `feat-397` path/text atom;
9. creates one parentless neutral `main` commit (`Repository Bootstrap <repository@invalid>`, `initial repository`) and reduces `.git` to the validator's byte-canonical HEAD/config/index/ref/loose-object closure.

`AGENTS.md`, `docs/changes/README.md`, and `docs/development/change-workflow.md` are not common F whole-file copies. Their routing is arm-owned. H01 is composed because its B product architecture rules and W workflow routing come from different clocks. H02/H03/H04/H05/H07/P01/P02 use their native documentation epoch and preserve their W-owned index bytes exactly; the H01 slice rule does not rewrite them.

## One-case usage

All output parents must exist. Output, manifest and receipt paths must be new; the tool never overwrites a non-empty destination.

```bash
work_dir="$(mktemp -d)"
mkdir -p "$work_dir/out"
.venv/bin/python \
  evals/spec_design_alignment/base_repo/materialize.py \
  --recipe evals/spec_design_alignment/base_repo/recipes/H02-feat-510-A.json \
  --repository . \
  --output "$work_dir/out/repository" \
  --manifest "$work_dir/out/content-manifest.json" \
  --receipt "$work_dir/out/receipt.json"
```

The receipt records B archive identity, whole-root archive-lineage disposition, scrub hashes/counts, the eight-root `feat-397` absence assertion, DP1/W entries, output manifest, and canonical root commit/tree. It stays outside the candidate repository.

## Validation and seal state

```bash
.venv/bin/pytest -q \
  evals/spec_design_alignment/base_repo/tests
.venv/bin/python \
  evals/spec_design_alignment/validate_dataset.py
.venv/bin/python \
  evals/spec_design_alignment/validate_dataset.py \
  --verify-base-repositories
```

The full replay materializes all eight formal roots and passes each directly to the shared fresh-root validator. Stable evidence is summarized in [base-repository-A.md](../receipts/base-repository-A.md); temporary output paths are intentionally absent.

The suite is not sealable yet. This command must fail until all arm inputs freeze:

```bash
.venv/bin/python \
  evals/spec_design_alignment/validate_dataset.py \
  --require-sealable
```

Current blockers are `frozen_cross_fitted_profile` for A+USER, and both `executable_agent_team_bundle` plus `frozen_cross_fitted_profile` for B. Arm A is `ready_materializable`; that does not imply the three-arm suite is ready or sealed.

## Extending the suite

For a new case, first record the owner disposition and reserve an id; rejected candidates stay in diagnostics and their ids are not silently reused. For an accepted historical case, pin the parent of the first target trace as B, prove its commit/tree and source-root receipt, preserve B product claims, derive the complete archive-reference closure from B without target keywords, choose an existing documentation epoch or add a reviewed DP1 transform, list the fixed W-owned workflow closure, author answer-free public input plus private semantic truth, freeze the expected content manifest after a pilot materialization, bind the case in dataset/treatment/seal/receipt/validator/tests, then rerun structural and all-root validation. Do not copy a current docs tree, target unit or active change unit as a shortcut.

When a later extension changes the formal case set, update all set-valued contracts together: `dataset.json`, both suite schemas, treatment bindings, seal case assets and run policy, source roots, recipe registry hash, stable receipt, validator/test registries, protocol counts and owner-review navigation. The validator treats any partial extension as an error.
