# H03 provenance — cross-channel session controls

This provenance separates the historical product world from current workflow/profile clocks. The case remains `draft` until all runtime hashes and owner review are complete.

## Product clock

- Mode: `historical_pre_target`.
- World cutoff commit: `ef52bbb16592fcd98c785136084dd47d78552ff7` (`2026-08-05T12:09:59+08:00`), tree `08c7429c55d9672d5a1d7d49bda85c53843e55e3`.
- First target trace: `781f65956d637552fb47cdfad648a0caa54084e1`, commit timestamp `2026-08-05T12:20:40+08:00`, whose sole parent is the world cutoff. It introduces the target docs and implementation in one commit. The author timestamp is earlier than the parent, so graph ancestry and committer time—not author-wall-clock sorting—define the cutoff.
- `git grep` at the cutoff finds no target id outside the pre-existing evaluation-method unit. Parent equality, tree hash and path additions were verified with `git show`, `git diff-tree` and `git rev-parse`.

## Knowledge clock

- Mode: `historical_cutoff`, same tree as product clock.
- Included authorities are hashed in `knowledge/authority-map.json`: Gateway routing/external contracts, kernel context persistence, inbound/coordinator/binder/queue/shadow code, public compact API and earlier stop/compaction/shadow decisions.
- The public brief preserves the original requests recorded in the post-cutoff spec: Feishu lacks new-session/manual-compaction controls, both internal IM and Feishu must be considered, and the agent should independently finish spec/design for one later owner review. Later product answers about visible history, focused compact, FIFO, groups and persistence are excluded.
- The historical request mentioned competitor research, but no competitor source tree or report was sealed. Host references and network are forbidden; the map records this evidence as absent, and the brief explicitly tells candidates to state that limit rather than fabricate or treat competitor claims as a deliverable.
- Excluded future material includes every target spec/design/delta/milestone/implementation/test/verification/acceptance artifact, PR `#242`, later FIFO reservation and group-reset fixes, current canonical session-control specs and host memory.
- Private oracle references pin held-out documents to `25dc9c818400ab66c99650316610b73ca5d2060f` and use `#Lx-Ly` ranges that can be resolved mechanically. These references remain judge-only and are not candidate authorities.

## Documentation clock

- Mode: `suite_frozen_latest`; framework/workflow F/W is commit `adb93d33a2ec5443a647dd367eb67557ac72e199`, tree `025b16b8c900c2b40ac23b126f99eda94e280633`.
- H03 is in the native documentation epoch. DP1 preserves B product/documentation bytes exactly; only the three W-owned routing files are checked against W, with `AGENTS.md` replaced because its B bytes differ and the other two preserved because they are byte-identical.
- The clean-room scrub removes direct active units and `docs/changes/retired/**`, plus eight whole archive roots derived by `drop_noncompleted_cross_references_v1`, while preserving the remaining B-consistent completed archives. No current product claim is imported from F, and no `feat-397` path/text atom survives.

## Workflow clock

- Mode: `current_frozen`.
- At this cutoff the selected current author skill contents are effectively compatible; nonetheless the runner removes/replaces historical workflow-owned paths so each arm receives exactly its frozen bundle.
- Literal scans of current selected author/reviewer packages found no target id or target-specific visibility/FIFO symbols. Generic lessons from the same development era justify C1 disclosure.
- A/A+USER/B bundle hashes: `TBD at S0`; A and A+USER workflow bytes must be identical.

## User clock

- Mode: `current_cross_fitted` for A+USER/B, none for A.
- Exclude the target unit, its acceptance, the later compact-FIFO reservation fix, group reset behavior, listener-harness work, canonical-spec merge and any profile statement supported only by those sources.
- No explicit target citation was found in the current draft profile, but source-level leave-one-lineage-out remains mandatory.
- Resulting profile hash shared by A+USER/B: `TBD at S0`.

## Model/tool clock

- Mode: `current_frozen`; model/build, reasoning, tools, runner image and permission manifest: `TBD at S0`.
- Network, real channels, host browser/session state and production side effects are disabled during spec/design runs. Real-channel checks, if S6 is authorized, use a separately isolated fixed acceptance harness and never feed observations back into only one arm.

## Five-layer manifest

| Layer | Build input | Transform | Output hash | Candidate visible |
|---|---|---|---|---|
| Product world | Git tree `08c7429c...` | `git archive`; scrub treatment, active/retired units and eight archive-lineage roots | `c322a409...` final combined content manifest | yes |
| Documentation world | native B documents plus F-compatible framework ownership | preserve exact; W owns routing paths | bound in base-repository receipt | yes |
| Common compatibility | suite-wide N0 derivation table | empty for this case | TBD | yes |
| Arm bundle | frozen A/A+USER/B | one workflow; profile by arm | TBD per arm | yes |
| Private controls | inventory, rubric and audit | no transform | TBD at seal | no |

## Normalizer

- Identity/version: task-blind epoch N0 normalizer, `TBD at S0`.
- The cutoff already exposes all current documentation entry paths; no case-specific path alias or format conversion is necessary.
- Inputs are raw archive paths and suite routing rules only. Brief, title, target lineage, decisions, held-out fixes and arm identity are hidden.
- It may not create a command list, select session-control files, summarize the queue/visibility problem or backfill later canonical specs.
- Raw-versus-DP1 documentation sensitivity is `N/A`: the registered DP1 operation for native H03 is byte-preserving, so raw B and DP1 product/documentation file bytes are identical. The `AGENTS.md` delta is an explicit Workflow@W overlay, not a DP1 semantic rewrite.

## Lineage audit

- Candidate contamination level: `C1 generic lineage exposure`; this is not a holdout.
- Treatment-authoring status: `historical_posthoc`; frozen workflow/profile-builder/profile lineage manifests must cover retained rules/statements and exclude target-derived entries before run.
- Product/knowledge world is the direct graph parent of first target trace and contains only legitimate pre-existing `/stop`, compact, binding, queue and shadow facts.
- Current canonical docs/code and host memory carry exact post-target answers but are excluded. A hit/access is C3 and invalidates the run.
- Current profile is leave-one-lineage-out; any retained target decision changes the declaration to C2.
- Private oracle lineage: `historical_target_derived_private`; judge material is confined to the private layer, admits equivalent solutions, is frozen before outputs and is never used as generic judge calibration or few-shot.

## Snapshot generation

1. `git archive --format=tar ef52bbb16592fcd98c785136084dd47d78552ff7` into a new temporary directory.
2. Apply the frozen clean-room scrub: remove treatment roots, direct active change-unit roots and `docs/changes/retired/**`; independently derive and remove eight matching archive unit roots under `drop_noncompleted_cross_references_v1`; preserve the remaining B-consistent archives and product-owned built-in skills. Install the W-owned routing files with the recipe's exact replace/preserve assertions.
3. Inject exactly one frozen arm bundle. Add no semantic compatibility content.
4. Create a single-root local Git repository with no remote, alternates, parent history or worktree metadata.
5. Verify archive/tree/file hashes, layer manifests, empty remote, candidate allowlist and private leak signatures before S0.

Pre/post-scrub manifests, fresh-root commit, hashes and scan result: `TBD at S0`. Candidate export allows only the scrubbed historical product world, the empty N0 compatibility output and the selected arm bundle. The runner injects the exact `public/brief.md` body as the initial user message without copying that control file into the workspace. It excludes `case.json`, the entire `knowledge/` directory (including the runner/audit-only authority map), `judge-private/` and `audit/`. Candidates see the cutoff product evidence but no snapshot-bundled treatment workflow, and must discover relevant authorities themselves.
