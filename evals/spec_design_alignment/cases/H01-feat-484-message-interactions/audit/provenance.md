# H01 provenance — Web IM message content interactions

This file records repository observations separately from evaluation judgments. The case remains `draft` until bundle/profile/model hashes and a generated snapshot are owner-reviewed.

## Product clock

- Mode: `historical_pre_target`.
- World cutoff commit: `088b2f8b1b5327745d2f489ad131015904d5ae0d` (`2026-07-27T08:22:23+08:00`), tree `e80e045164ed91cc13197dfab5dc2a04e55569ad`.
- First target trace: `2eb7103913d857e15c2e3ff8fda804aae9d66d11` (`2026-07-27T15:57:56+08:00`), whose sole parent is the world cutoff. That commit first adds the target spec.
- Verification commands used: `git show -s --format='%H %P %aI %cI %s' <commit>`, `git rev-parse 2eb710391^`, `git log --all -S'feat-484'`, and path-scoped `git grep` at the cutoff.
- Target-name grep outside the pre-existing evaluation-method unit found no target trace at cutoff. The evaluation-method unit itself is removed for every case as described below.

## Knowledge clock

- Mode: `historical_cutoff`, same Git tree as the product clock.
- Included authorities are listed with cutoff hashes in `knowledge/authority-map.json`. The important product pre-state is the then-current Web IM contract, which already promised a custom right-click/long-press message menu, plus the real message bubble, styles and tests.
- The public brief is reconstructed from the original-request block first recorded in the post-cutoff spec. It retains the two reported observations, the request for a candidate list followed by one final design, and the commercial/no-overdesign instruction. Desktop/mobile surfaces, companion features, acceptance scenarios and implementation vocabulary are not backfilled from the later solution.
- The original request referenced a temporary local screenshot. The file cannot be recovered and no substitute image is synthesized; the authority map records an absence marker.
- Excluded future material includes every target spec/design/prototype/milestone/verification/acceptance/implementation commit, PR `#222`, the resulting canonical Web IM contract, and all direct interaction fixes.
- Private oracle references pin held-out documents to `25dc9c818400ab66c99650316610b73ca5d2060f` and use `#Lx-Ly` ranges that can be resolved mechanically. These references are judge-only and are never mounted into the candidate workspace.
- Current checkout files, parent Git history, host memory and LLM logs are never mounted into the candidate workspace.

## Documentation clock

- Mode: `suite_frozen_latest`; framework F is commit `adb93d33a2ec5443a647dd367eb67557ac72e199`, tree `025b16b8c900c2b40ac23b126f99eda94e280633`, shared with Workflow@W.
- The base repository follows `Code@B + ProductClaims@B + DocsFramework@F + Workflow@W` at projection `DP1-counterfactual-latest-v1`. F contributes only document framework/navigation; product claims remain bound to the H01 cutoff.
- H01 moves the exact B bytes `docs/SPEC_GUIDE.md` to `docs/specs/CONTRIBUTING.md` and transforms B `docs/specs/README.md` only by replacing the two `../SPEC_GUIDE.md` links with `CONTRIBUTING.md`. It does not copy the F current-spec tree.
- Clean-room projection removes every direct active unit and `docs/changes/retired/**`, then applies task-blind `drop_noncompleted_cross_references_v1` to whole archive roots before preserving the remaining B-consistent history. Its preregistered legacy-epoch `drop_proposed_control` list also removes the obsolete root `ROADMAP`/`TASKS`/`PROGRESS`/`LOGBOOK`/`ACCEPTANCE` controls and the three proposal-document paths as one task-blind class, not by target relevance.
- `AGENTS.md`, `docs/changes/README.md`, and `docs/development/change-workflow.md` are Workflow@W-owned/composed paths. The H01 composed `AGENTS.md` keeps B architecture red lines and adds only W routing. The change index retains the hash-bound F framework/lifecycle bytes through `## 唯一定位`, excluding the later F-only evidence/migration sections and their unresolved B-world links.

## Workflow clock

- Mode: `current_frozen` at S0; A and A+USER receive the byte-identical frozen current spec/design workflow, while B receives the frozen team workflow.
- The historical repository's embedded change skills are not an arm input. Runner setup replaces/removes workflow-owned skill paths before installing exactly one arm bundle, so B cannot also discover A's author workflow by accident.
- Bundle version/hash for A: `TBD at S0`.
- Bundle version/hash for A+USER: `TBD at S0`; workflow bytes must match A.
- Bundle version/hash for B: `TBD at S0`.

## User clock

- Mode: `current_cross_fitted` for A+USER and B; A receives no profile.
- The current draft profile explicitly cites this lineage for the “IM正文阅读和信息价值优先” preference. That evidence line, the target unit, its fixes, acceptance, canonical merge and any profile conclusion supported only by them must be removed.
- Independently supported preferences may remain, including avoiding overdesign and preferring commercial-quality UI, provided the builder records their non-target sources.
- A+USER and B must receive byte-identical output and access API. Base/resulting profile hash: `TBD at S0`.

## Model/tool clock

- Mode: `current_frozen`.
- Model build, reasoning settings, tool versions, sandbox image and permission-manifest hash: `TBD at S0`.
- Network, remote MCP, package download, host browser state, real push and external side effects are disabled for all arms.

## Five-layer manifest

| Layer | Build input | Transform | Output hash | Candidate visible |
|---|---|---|---|---|
| Product world | Git tree `e80e0451...` | `git archive`; remove treatment roots, legacy proposed-control paths, pre-existing active/retired units and three B-noncompleted-reference archive roots | `8cc1ef93...` final combined content manifest | yes |
| Documentation world | F framework plus B product documents | DP1 exact move, two-link rewrite, generated navigation | bound in base-repository receipt | yes |
| Common compatibility | suite-wide N0 derivation table | empty; the SPEC_GUIDE move belongs to DP1 | `4f53cda1...` | yes |
| Arm bundle | frozen A, A+USER or B manifest | install one workflow; profile only where specified | TBD per arm | yes |
| Private controls | inventory, rubric, provenance, leak signatures | no transform | TBD at seal | no |

## Normalizer

- Identity/version: task-blind epoch N0 normalizer, `TBD at S0`.
- Inputs visible: only raw archive paths plus the suite-wide routing table. It must not see this case title, brief, inventory, held-out unit or arm identity.
- N0 has no file derivation for H01. The `docs/SPEC_GUIDE.md → docs/specs/CONTRIBUTING.md` move is owned and audited by DP1, not common compatibility.
- The case-only `docs/changes/readme.md → docs/changes/README.md` spelling alias is deliberately not materialized because it collides on the default case-insensitive macOS filesystem.
- No summaries, selected-module hints, facts, priorities or new current spec are added. This case is preregistered for raw-versus-N0 sensitivity.

## Lineage audit

- Candidate contamination level: `C1 generic lineage exposure`; historical regression only.
- Treatment-authoring status: `historical_posthoc`; the target predates the current treatment, so this case is never a clean holdout.
- Frozen workflow/profile-builder/profile lineage-manifest refs and hashes: `TBD before authoring/treatment freeze`; each target-derived rule or profile statement must be recorded as excluded rather than accepted by literal target-name scan alone.
- Workflow: current skills have evolved since the cutoff, but a literal scan of the selected current author/reviewer packages found no target id or target-specific symbol. Generic review and workflow lessons may still come from the same era.
- Profile: direct target evidence is known and must be leave-one-lineage-out. If the final profile or arm examples retain any target-derived decision, reclassify to C2 before running.
- Current canonical docs/code and host memory contain direct answers but are outside every candidate layer. Any access is C3 and invalidates the run.
- Private oracle lineage: `historical_target_derived_private`; this rubric uses held-out history only inside the excluded private layer, admits equivalent solutions, and is frozen before arm output. Target material is not used as generic judge calibration or few-shot.

## Snapshot generation

1. `git archive --format=tar 088b2f8b1b5327745d2f489ad131015904d5ae0d` into a new temporary directory.
2. Apply `source-root-treatment-scrub-v1` from the frozen suite manifest: remove the snapshot `.claude/`, `.agents/`, `.codex/`, root `CLAUDE.md` / `CODEX.md`, `cc-hooks-on/off`, feat-397 and `docs/development/change-workflow.md` when present; derive and remove every whole archive root selected by `drop_noncompleted_cross_references_v1`; apply the H01 legacy-epoch `drop_proposed_control` list as one task-blind class; discover every `SKILL.md` and remove its containing non-product instruction root. Preserve the declared product implementation `src/personal_assistant/builtin_skills/**`. Project root `AGENTS.md` is rebuilt only from this cutoff's bytes: preamble before the first `## ` line plus complete level-2 sections whose heading is exactly `架构总览`, `架构红线` or `工作红线`; `## Project overview` is excluded and current bytes are never backfilled. `source-roots.json` freezes the raw/source/projection/removed/post-filter hashes for this cutoff.
3. Apply the frozen DP1 documentation projection, then inject exactly one arm bundle. The formal materialization currently selects ready arm A; A+USER and B remain blocked until their profile/team inputs freeze.
4. Initialize a new repository with one root commit. Do not configure remotes, alternates or parent-worktree metadata.
5. Verify historical tree/file hashes, layer manifests, `git remote -v` empty, candidate allowlist, and zero leak-signature hits before S0.

The formal arm-A recipe replay records content manifest `8cc1ef93...`, root commit `8d22680d...`, root tree `340d117b...`, three removed archive-lineage roots, ten removed proposed-control roots, and passed materializer assertions; the stable receipt remains outside candidate input. Its whole-root/path/text assertions leave no `feat-397` atom. Run-specific A+USER/B bundle hashes remain `TBD at S0`. Candidate export allows only the scrubbed historical world, the empty task-blind N0 layer and the selected arm bundle. The runner injects the exact `public/brief.md` body as the initial user message without copying that control file into the workspace. It excludes `case.json`, the entire `knowledge/` directory (including the runner/audit-only authority map), `judge-private/` and `audit/`. Candidates see all cutoff product evidence but no built-in treatment workflow, and must discover relevant authorities themselves.
