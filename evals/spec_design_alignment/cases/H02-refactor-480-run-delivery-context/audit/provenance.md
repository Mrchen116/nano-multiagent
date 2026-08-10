# H02 provenance — repository-wide architecture portfolio

## Reconstruction status

H02 now evaluates the historical request at its true breadth. The candidate-visible brief preserves the original intent recorded later at `12f6c1dd9e5078123f34fe2604797d5382b060fb:docs/changes/refactor-480-typed-run-delivery-context/motivation.md#原始诉求`:

- scan the whole repository for important architecture problems and “giant” code;
- compare against Claude Code source only where a genuinely analogous concept exists;
- turn the selected problems into several independent change units with motivation/spec and design;
- work autonomously during research and authoring, then give the owner one final portfolio confirmation before implementation and parallel scheduling.

The wording is a candidate input, not target leakage. The only treatment-neutral clarifications added are the deliverable shape (portfolio index plus per-unit documents and the scheduling view implied by later parallel implementation), that implementation is out of scope, that comparisons require pinned source evidence, and that the runner-injected arm bundle replaces scrubbed historical skill implementations. Architecture-quality lenses, historical diagnoses, target boundaries and negative-selection criteria remain private judge material.

The previous narrow run-delivery reconstruction is retired. No module, candidate, unit count, diagnosis, class, DTO, event matrix or target file list is preselected in the public brief.

## Terminal-mode reconstruction

The historical request delegated autonomous investigation and document authoring, but reserved the final portfolio choice for the owner after seeing the proposed units. H02 therefore declares `terminal_mode=owner_review_ready_package`, not `gate2_complete`.

For every arm, the reproducible terminal artifact is its own frozen, complete and answerable portfolio package after natural author/reviewer convergence. D06 remains a package-relative `V + owner_review_required` decision at that point: no historically preferred composition and no cross-arm common answer is prefilled. Normal completion keeps portfolio selection, priority/exclusion commitments, implementation and parallel scheduling pending without claiming owner or Gate 2 approval.

If a candidate activates D11, the package must fully explain the redline, safe alternative and consequences, then leave only the affected branch conditional or pending. This does not block the independent units or the portfolio as a whole from reaching package freeze. The three S4 packages are frozen and anonymized separately before blind owner review; an after-output owner choice belongs only to that run and cannot be merged into, replayed to or used to repair another arm.

## Product clock

- Nano cutoff commit: `efe2ffd08034f611897b58b994547fcf71753f7e`.
- Nano cutoff tree: `4bb1860e07b4deb6fbe586328dc9e3a41828f2bb`.
- Base archive SHA-256: `28e472e1c71f0cf13e18f2564aa4dea4308eb6338ba9962ba96fe0536b94a676`, produced by `git archive --format=tar efe2ffd08034f611897b58b994547fcf71753f7e`.
- Commit timestamp: `2026-07-25T10:54:42+08:00`.
- This is the exact `Full commit` recorded by the historical architecture-review output generated at `2026-07-25 11:11:11 CST`.

The historical review records that its working tree was dirty with 1 tracked modification and 58 untracked paths. Those dirty paths include the output lineage and are not reconstructible from the commit. The candidate world therefore starts only from the clean archive above, then applies the suite-wide treatment scrub below. It never imports the historical dirty tree.

## Knowledge clock

Candidate-visible repository knowledge is the scrubbed Nano cutoff plus the pinned external source snapshot. It excludes:

- the complete feat-397 unit, including its team research and evaluation material;
- loadable historical spec/design author and reviewer skills that would compete with the arm treatment;
- the historical architecture-review report and all eight target portfolio units;
- later implementation, verification, acceptance, documentation reorganization and target descendants;
- parent checkout metadata, Nano Git history, host memory and every host path except the control plane's read-only materialization of the declared external snapshot.

Historical change records outside the scrubbed feat-397 unit remain product-world evidence. They may mention old workflow names, but the named skill directories are absent and cannot be loaded; all arms see the same text.

## Workflow clock

At S0, all arms use byte-frozen current bundles. The product snapshot contributes no loadable spec/design treatment. The runner injects exactly one bundle for the selected arm after the suite-wide scrub:

- A: current spec/design author and natural review/gate workflow up to an owner-review-ready portfolio package, no USER profile;
- A+USER: byte-identical workflow to A plus the cross-fitted USER profile, with the same package terminal boundary;
- B: the feat-397 team workflow plus the same profile as A+USER, with the same package terminal boundary.

No candidate workspace may contain another arm bundle, a fallback copy of a scrubbed skill, or the control manifests used to assemble the workspace.

## User clock

A receives no profile. A+USER and B receive the same current-cross-fitted profile. The builder removes the 2026-07-25 architecture portfolio, all eight unit lineages, their direct repair descendants, and feat-397-derived examples or conclusions. The public brief itself governs the current interaction: autonomous investigation and authoring, one consolidated final confirmation, and no implementation before that confirmation.

Stable preferences may still be reused when independently supported outside those excluded lineages, such as avoiding hypothetical compatibility/abstraction and leading a large review with a concise decision index. Current brief instructions always win.

## Model/tool clock

At S0, freeze one model build, reasoning setting, tool image, time/token budget and tool permission set for all arms. Network, real push, host memory and parent-repository access stay disabled. The only second repository is the declared read-only external snapshot materialized identically for every arm.

## Normalizer and treatment scrub

The following sequence is suite-wide, deterministic and independent of case answers or arm identity:

1. Export Nano commit `efe2ffd...` with `git archive`.
2. Apply `source-root-treatment-scrub-v1` before any arm bundle: remove the Nano snapshot `.claude/`, `.agents/`, `.codex/`, root `CLAUDE.md` / `CODEX.md`, `cc-hooks-on/off`, feat-397 and `docs/development/change-workflow.md` when present; discover every `SKILL.md` and remove its containing non-product instruction root while preserving the declared product implementation `src/personal_assistant/builtin_skills/**`.
3. Rebuild Nano root `AGENTS.md` only from this cutoff's bytes: retain the preamble before the first `## ` line, then complete level-2 sections headed exactly `架构总览`, `架构红线` or `工作红线`; never retain `## Project overview` or backfill current bytes. Assert all scrub roots, feat-397 atoms and non-selected arm bundles are absent. `source-roots.json` freezes raw/source/projection/removed/post-filter hashes independently of S0 runtime hashes.
4. Materialize the pinned Claude Code raw archive at `references/claude-code/`, verify `fa18e3…`, then run the same root-ownership scrub: remove outer `.claude/`, `.agents/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `cc-hooks-on/off` when present, plus every undeclared `SKILL.md` instruction root. Preserve `src/skills/**` because it is product source being compared, not an outer candidate instruction. Verify the frozen external post-filter manifest before exposure.
5. Apply only epoch-wide N0 route/copy outputs. Do not synthesize a module index, candidate list, hotspot ranking or “relevant files” guide.
6. Inject exactly one selected arm bundle, then record final layer and workspace hashes.

The scrub is experimental treatment isolation, not a semantic rewrite of product code or contracts. Its rule version applies byte-identically to every formal case and three arms whenever paths exist; its output remains clock-specific. It never imports current-checkout `AGENTS.md` wording into this historical world. The feat-397 directory is removed as a whole; keyword filtering individual documents is insufficient. The private authority map therefore does not claim the historical `AGENTS.md` is copied unchanged; the cutoff source and neutral projection hashes live in the S0 treatment manifest.

## External source snapshot

- Mirror id: `claude-code-local-mirror`.
- Control-plane repository: `/Users/czj/Repos/opensource-hub/claude-code`.
- Configured origin: `git@github.com:Mrchen116/CC-baseline.git`.
- Configured upstream: `git@github.com:claude-code-best/claude-code.git`.
- Selected raw commit: `0991eac5ccd518d6bd0486752f61a42f9ad68fa8`.
- Tree: `fb16fd7efeccaa12965404efb2ea47419922ae30`.
- Sole parent: `c98707354da7b68a4c4bb11984a8f0cd7a542673`.
- Committer timestamp: `2026-05-29T19:54:06+08:00`, earlier than the Nano cutoff.
- Local-ref audit: among all commits reachable from the mirror's local refs whose committer timestamp is no later than the Nano cutoff, this is the latest timestamped commit.
- Candidate exposed path: `references/claude-code/`.
- Archive SHA-256: `fa18e3f1265329b2c6c7b996b283b64e1ba0772c03045383f1f5201fe67b36ff`.
- Frozen candidate post-filter files-manifest SHA-256: `d41101e252e85cda8d69d97c43e030898c171981694ade5cb11994433c218321`; validator reproduces it from the raw commit after removing outer Agent controls while preserving declared product source. S0 separately records the concrete extracted-layer and final export hashes.

Materialization recipe, run by the control plane without using the checkout's dirty files:

```bash
git -C /Users/czj/Repos/opensource-hub/claude-code archive \
  --format=tar \
  --prefix=references/claude-code/ \
  0991eac5ccd518d6bd0486752f61a42f9ad68fa8
```

The raw tar bytes must match the recorded SHA-256 before extraction at the candidate workspace root. After extraction, the fixed source-root scrub above must match its S0 post-filter manifest before candidate exposure. The mirror checkout is currently dirty and conflicted, but `git archive <raw-commit>` reads the committed object graph and repeated archive hashing is stable; no working-tree content is copied.

This is a reproducible community/local source mirror selected from the user-designated reference checkout. It is **not** represented as official Anthropic provenance. Candidates may make only source-grounded architectural observations and must cite paths under the exposed snapshot.

## Lineage audit

Chronology:

1. `efe2ffd08034f611897b58b994547fcf71753f7e` — clean Nano baseline at 2026-07-25 10:54:42 +08:00.
2. The broad user request starts the architecture-scan task. The runner injects the exact `public/brief.md` body as the initial user message; the control file itself is not copied into the workspace.
3. `architecture-review-20260725-111111-efe2ffd0.html` — first recoverable target output, generated 2026-07-25 11:11:11 CST from a dirty worktree based on `efe2ffd...`.
4. `08729f0be9ba95401b9d57ea20911833618fe3e8` — first Git commit containing that report, 2026-07-30 23:07:40 +08:00; parent `0daf95f82b9ad216f15486cc1728f31afcf54a6e`.
5. `12f6c1dd9e5078123f34fe2604797d5382b060fb` — first committed approved document set for one portfolio member, refactor-480.
6. `38fd7ece5d6a380131e75fc586ecd6b18019d612` — its first implementation commit; direct parent `12f6c1dd...`.

Ancestry checks confirm `efe2ffd... → 08729f... → 12f6c1dd... → 38fd7ece...`. The clean cutoff is not the direct parent of the first Git report commit because the report existed locally for five days before it was committed. Using `0daf95f...` as cutoff would be chronologically unsafe even though it is the Git parent.

The case is C1: generic current workflow/profile rules can reflect lessons from the historical era, and the broad original request is visible by design, but no target diagnosis or portfolio output is visible. Its treatment-authoring status is `historical_posthoc`, never clean holdout. A target-derived rule/example or any of the eight unit artifacts in an arm/profile makes the run C2. Candidate access to the report, target unit files, private judge, unsanitized feat-397 tree, Nano parent history or another arm makes it C3 and invalid. Before freeze, structured workflow/profile-builder/profile lineage manifests must record every retained rule/statement and explicitly exclude target-derived entries; literal target-name scanning is not sufficient.

## Historical portfolio evidence and scoring boundary

The committed report at `08729f0be9ba95401b9d57ea20911833618fe3e8:docs/research/architecture-reviews/architecture-review-20260725-111111-efe2ffd0.html:91-782` records the historical output: eight proposed independent refactor units plus one already-completed quick removal. Its problem families included transaction ownership, session stream ownership, control-plane seams, review lifecycle, delivery state, local configuration ownership, Web runtime ownership and shared form rules.

That portfolio is private evidence of task difficulty and a source of judge probes, not a fixed answer key:

- exact unit ids, titles, count, wording, boundaries and mechanisms receive no automatic credit;
- missing a historical candidate is not itself a defect if the candidate rejects it with evidence or replaces it with an equally material issue;
- a different number or combination of independently actionable, non-overlapping, high-value units can earn full marks;
- judges must score repository coverage, evidence, structural importance, boundary quality and implementability before consulting historical overlap;
- historical units that remained uncommitted in the dirty worktree are not treated as durable source refs; the committed report is the reproducible portfolio evidence. Refactor-480's later committed documents are only one downstream example, not the portfolio template.

The private judge therefore uses the report to challenge omissions and detect shallow analysis, never to turn H02 into eight keyword matches.
