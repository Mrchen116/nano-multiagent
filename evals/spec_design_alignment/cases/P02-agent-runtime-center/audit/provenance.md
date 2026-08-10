# P02 case provenance

This is a prospective pilot. The draft records evidence and unresolved choices; it is not sealed and contains no product answers. Its candidate-side inputs are designed as C0, but the case was visible before the runnable A/B workflow and profile-builder froze, so it is not eligible for a clean-holdout conclusion. Dataset-authoring review evaluates the case construction rather than answering those choices.

## Product clock

- Mode: `prospective_sealed` at case seal; currently draft.
- Cutoff timestamp: pending dataset-authoring review and seal.
- Commit/tree hash: `25dc9c818400ab66c99650316610b73ca5d2060f`, committed `2026-08-06T23:36:17+08:00`; this raw commit object resolves via `git rev-parse 25dc9c818400ab66c99650316610b73ca5d2060f^{commit}`.
- Seal evidence: the brief and private draft were created before any target implementation or historical gold. P02-A18 records that the pinned tree has no runtime-center capability to reuse as an answer.

## Knowledge clock

- Mode: `prospective_sealed` at the same cutoff.
- Included audit authorities: P02-A01 through P02-A18 in `knowledge/authority-map.json`, all checked against the pinned clean tree without semantic additions. The map is owner/judge-only and is not candidate-visible.
- Excluded future material: local dirty files; this case's private judge and audit layers; future code, branches, issues, PRs, owner answers, and conversations that derive an activity-center solution.
- Snapshot hashes: repository commit recorded above; suite-wide scrub manifest, cutoff-source/treatment-neutral `AGENTS.md` projection, post-scrub product tree, and case-file hashes pending seal.
- Collection method: `git show 25dc9c818400ab66c99650316610b73ca5d2060f:<path>`, `git grep ... 25dc9c818400ab66c99650316610b73ca5d2060f -- <paths>`, and `git ls-tree 25dc9c818400ab66c99650316610b73ca5d2060f`. The local dirty worktree was not used as product truth.

## Documentation clock

- Mode: `suite_frozen_latest`; framework/workflow F/W is commit `adb93d33a2ec5443a647dd367eb67557ac72e199`, tree `025b16b8c900c2b40ac23b126f99eda94e280633`.
- The pinned native documentation epoch needs no semantic rewrite. DP1 preserves B product/documentation bytes, removes direct active/retired unit instances plus eight whole archive roots derived by `drop_noncompleted_cross_references_v1`, preserves the remaining B-consistent completed archives, and verifies the three W-owned routing files against W.
- No F product claim, case authority map, private decision, or target-specific hint enters the candidate tree.

## Workflow clock

- Bundle version/hash for A: pending runner freeze.
- Bundle version/hash for A+USER: pending runner freeze.
- Bundle version/hash for B: pending runner freeze.
- Neutral private answer-policy, scripted response bank, semantic matcher, and no-answer refinement-window schedule hashes: pending authoring review; all freeze before any confirmatory arm run.

## User clock

- Base profile version/hash: `docs/changes/feat-397-spec-design-agent-team/user-profile-draft.md`, draft snapshot from 2026-08-05; runtime cross-fitted hash pending.
- Stable-profile evidence-ledger hash: pending seal. D09, D19, and D20 must each trace to pre-P02, cross-case user evidence; an authoring suggestion or the public brief cannot establish a `P`, and any entry without that lineage is removed before freezing.
- Allowed stable preferences: complete but restrained scope; inspect the current system and repair the owning seam; demand real evidence; put facts before conclusions; investigate lookup-answerable facts instead of asking; escalate true value forks and conditional hard red lines; preserve a configured default unless explicitly directed to change it; verify visual product changes in a real browser on desktop and mobile. The brief already fixes readable, non-log presentation, so that preference is not counted as personalization in this case.
- Cross-fit exclusions: every P02-specific activity-center choice, field, state, threshold, action, security policy, IA, retention rule, and owner response listed in `decision-inventory.json`.
- Resulting profile hash: pending runtime materialization as `runtime/candidate-inputs/P02/USER.cross-fitted.md`.
- P-evidence rule: every `P` oracle is supported only by the exact hashed runtime profile. If the cited preference is absent there, the runner fails dataset validation; brief text, repository facts, or an arm recommendation cannot substitute.

The inventory contains 20 decisions: 8 `F`, 3 `P`, 6 `V`, and 3 conditional `H`. Nine entries need a private response only as specified below; the three `P` entries are independently supported by the cross-fitted profile and do not answer any product fork.

## Model/tool clock

- Model/build and inference settings: pending runner freeze.
- Tool/runner image versions: pending runner freeze.
- Permission manifest hash: pending; required permissions deny network, push, host memory, and parent-repository access.

## Five-layer manifest

| Layer | Build input | Transform | Output hash | Candidate visible |
|---|---|---|---|---|
| Product world | complete tree at B and frozen clean-room scrub | remove treatment, active/retired units and eight archive-lineage roots | `afcb5907...` final combined content manifest | yes, post-scrub only |
| Documentation world | native B docs with F/W ownership audit | preserve exact and retain B-consistent completed archive | bound in base-repository receipt | yes |
| Common compatibility | suite-wide N0 derivation table | empty for this case | pending | yes |
| Arm bundle | frozen A, A+USER, or B bundle | arm-specific injection | pending | yes |
| Private controls | authority map, inventory, rubric, provenance, leak signatures | none | pending | no |

## Normalizer

- Identity/version: `n0-byte-copy-v1`; this case has no registered derivation, so its common layer is empty.
- Suite-wide preprocessing applies the frozen clean-room scrub before N0: remove treatment roots, direct active units and `docs/changes/retired/**`; independently derive `drop_noncompleted_cross_references_v1`, remove eight matching archive roots, and preserve product-owned skills plus the remaining B-consistent archives; verify W-owned routing bytes and the absence of the `feat-397` path/text atom. `source-roots.json` and the formal recipe freeze the source/tree and resulting manifests.
- Scrub boundary: this denylist, replacement bytes, and implementation hash are suite-wide controls fixed without reading a case brief, authority map, decision inventory, oracle, or arm. The scrub removes evaluation treatment exposure; it is not N0 and is not target-derived semantic normalization.
- Inputs visible to N0: only the post-scrub pinned product tree and its verified content manifest. The authority map and scrub control manifest are not normalizer inputs.
- Evidence that task/arm/private answers were hidden: candidate documentation comes only from the registered B-preserving DP1 result and W-owned routing closure; it contains no target task, oracle language, host path or test credential. Candidate export excludes `case.json`, `knowledge`, `judge-private`, and `audit`.
- Transformation audit: after the suite-wide scrub, N0 exports product content without rewriting, filtering, path hints, or map-driven prioritization. The Agent must independently research the remaining repository; authority-map paths and line ranges exist only for owner/judge audit.

## Lineage audit

- Candidate contamination level: `C0` candidate-side; treatment-authoring status is `pre_treatment_freeze_visible`, so the result class is prospective pilot.
- Frozen workflow/profile-builder/profile lineage-manifest refs and hashes remain pending; completing them prevents target-derived bytes from entering the run but cannot retroactively make this pilot author-blind.
- Workflow-derived candidate exposure: none until frozen bundles are injected per arm; no bundle may include P02 atoms or oracle language.
- Profile-derived candidate exposure: generic stable preferences only, cross-fitted to remove all P02 lineages.
- Common/normalizer-derived candidate exposure: the same task-blind treatment scrub plus N0 identity export for every case and arm; the private authority map cannot select or highlight files.
- Private oracle lineage: `prospective_pre_output`; the case-specific inventory/rubric may derive from this sealed brief and pinned facts, but must be frozen before any arm output and never enter generic judge calibration, few-shot, or candidate input.
- Answer-derived exposure: the blinded response bank remains withheld until that run's initial and refined packages are frozen; only a decision actually surfaced in the refined package can receive its matching pre-sealed response. The bank is never part of the workspace, profile, refinement signal, or another case.
- USER-learning exposure: any post-answer profile candidate and micro-delta live in an isolated secondary-probe namespace. They never alter P02 arm bundles, P01 inputs, the baseline cross-fitted profile, or the primary verdict.

## Neutral private answer policy

- After dataset-authoring review, the owner completes a blinded answer-setting pass using the public brief, pinned evidence, inventory, and a fixed response form, but sees no arm identity, transcript, recommendation, spec, design, or score.
- Before confirmatory runs, that pass freezes one response for every `V` item and one response for each possible activated `H` gate. False `H` predicates receive no owner interruption and use `inactive_safe_behavior`.
- Each confirmatory run starts with the bank withheld. At the fixed initial checkpoint, the runner freezes the complete initial question/decision package and its transcript, call, token, and time counters.
- Every arm then receives the same task-blind continue/refine instruction and the same no-answer call, token, and wall-time window. The runner provides no substantive owner signal; when the window closes, it freezes the complete refined package and counters before any answer is released.
- Only after both packages are immutable does the frozen semantic matcher map actual owner questions in the refined package to inventory decisions. For each matched `V`, and each matched `H` whose `activation_predicate` is true, the runner replays the same pre-sealed semantic response to every arm even if wording or packet batching differs.
- The runner never volunteers an answer for a decision the arm did not actually surface. A missed `V`, or a true-predicate `H` that was not surfaced, remains an omission for judging; a false-predicate `H` uses `inactive_safe_behavior` and creates no interruption.
- The policy, response bank, option provenance, package hashes, refinement-window counters, and matcher results remain private. Exploratory runs cannot update them; any post-seal correction invalidates all affected arm runs rather than adapting an answer or window to one workflow.

## Snapshot generation

- Archive command/recipe: extract the exact pinned tree into a staging area; apply the frozen suite-wide treatment scrub there; verify the deleted-path set, cutoff-source/treatment-neutral `AGENTS.md` hashes, and post-scrub product-tree manifest; copy that post-scrub tree into a fresh root; add only the empty common output and exactly one selected frozen arm bundle; inject the exact public brief body as the initial user message rather than a workspace file; then initialize and commit the isolated repository.
- Fresh-root commit hash: recorded in the arm-A receipt. It is not expected to equal the source commit; equivalence is proved by the B source, clean-room scrub, DP1/W entries and final content manifest.
- Remote check: `origin/main` was resolved to the pinned commit before evidence collection; repeat immediately before sealing without advancing the case clock.
- Candidate export allowlist: the post-scrub pinned product tree, the empty common output, and exactly one arm bundle; the public brief body is sent as the initial user message and is not exported as a file.
- Scrub verification: before arm injection the product tree must contain no declared scrub root or undeclared outer `SKILL.md` directory; after injection every `.claude/**` byte must belong to the selected arm/shared-helper dependency closure. Repository-root `AGENTS.md` must equal the frozen cutoff projection and must not equal an imported current-checkout document.
- Leak scan result: pending seal and run over the complete fresh-root allowlist after arm injection.

## Source facts and limits

| Authority | Pinned location | Directly supports | Does not support |
|---|---|---|---|
| P02-A01 | `agent-detail-page.tsx:1244-1273,1390-1607` | current default, query, shell, tabs, overview/session placeholders | target IA or activity semantics |
| P02-A02 | `agent-detail-page.test.tsx:184-206` | executable placeholder/tab behavior | future activity behavior |
| P02-A03 | `im-agent-config-api.ts:163-167` | current detail state has config/capabilities/node only | an activity projection |
| P02-A04 | `agent-status-ws-consumer.ts:16-82` | current status/channel cache updates and recovery | run/task lifecycle streaming |
| P02-A05 | `runs/origin.py:6-14` | four current origins | display grouping or permissions |
| P02-A06 | `runs/registry.py:43-85` | Run status and record fields | central IM queryability |
| P02-A07 | `background_tasks/models.py:10-59` | separate task lifecycle and record fields | common activity semantics |
| P02-A08 | `heartbeat-cron.md:14-41` | scheduled-mechanism distinctions and cron history requirements | a unified UI feed |
| P02-A09 | `kernel/runs.md:191-240` | cancel/interrupt, permission wait, liveness, close behavior | owner-approved UI actions or stuck threshold |
| P02-A10 | `IM/domain/models.py:206-228` | raw ToolCall storage | safe broad disclosure |
| P02-A11 | `IM/api/routes/messages.py:89-108` | raw ToolCall history payload | cross-context authorization |
| P02-A12 | `im/tool-timeline.md:43-75` | human summaries and parameter/result timing in chat | activity-center redaction policy |
| P02-A13 | `im/agents-nodes.md:161-179` | desktop navigation and mobile/loading/error constraints | density or drill-down choice |
| P02-A14 | `im/agents-nodes.md:222-240` | JWT owner scope, replay, and resync | new activity event schema |
| P02-A15 | `test_kernel_sdk_behavior_contract.py:144-179` | idempotent run cancel | actions for other source types |
| P02-A16 | `test_background_tasks.py:75-154,215-255` | task transitions, partial result, kill and terminal idempotency | UI retry/resume semantics |
| P02-A17 | `test_status_broadcast_e2e.py:115-155` | executable cross-owner event isolation | shared/group visibility policy |
| P02-A18 | pinned Agent-detail/API/current-spec routes | absence of committed unified activity capability | any preferred aggregation design |

## Direct observations, synthesis, and value judgments

- **Direct observation:** the current page deliberately leaves overview and sessions as placeholders; current detail data is configuration/node state, not activity.
- **Direct observation:** run origins cover the requested source classes, but RunRecord, BackgroundTaskRecord, and cron history have different state and ownership contracts.
- **Direct observation:** raw ToolCall data exists and current chat already values human summaries, while no current source grants a broader activity view permission to disclose raw details.
- **Synthesis:** a projection seam is required to join source-specific records without moving execution authority. The evidence does not choose pull versus push, persistence duration, endpoint shape, or event format.
- **Synthesis:** no-output duration alone cannot define stuck because liveness and permission waiting intentionally represent alive-but-quiet work.
- **Value judgment pending owner:** IA, activity grain, state/stuck semantics, freshness, density, and retention are unconditional product forks. New mutating actions, broader audiences, and raw-sensitive projection are conditional hard-red-line gates only if a proposal activates their predicates.

## Private response bank required before confirmatory runs

Unconditional product choices:

- D10: information architecture and default landing.
- D11: activity grain, grouping, and parent/child relationships.
- D12: normalized states and stuck/freshness evidence.
- D13: offline, partial, stale, resync, and refresh policy.
- D14: desktop/mobile density and drill-down.
- D15: history horizon, retention, and pagination.

Conditional hard-red-line gates; no owner question is needed when the arm keeps the recorded safe baseline:

- D16: activated only if the surface adds a new or materially broader mutating action instead of remaining read-only or reusing an evidenced safe action.
- D17: activated only if the surface broadens its audience or cross-context detail access beyond owner-only plus existing source authorization.
- D18: activated only if the surface projects raw-sensitive content or adds broader drill-down instead of safe allowlisted summaries and existing-context inspection.

All nine items remain `owner_review_required` during authoring because the neutral response bank has not been sealed and no arm predicate outcome has been observed. For H items, that status means “private owner response replayed if activated,” while a false predicate uses `inactive_safe_behavior` without interruption. Arm recommendations never become answers.
