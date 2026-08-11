# P01 case provenance

This is a prospective pilot. The draft records evidence and unresolved choices; it is not sealed and contains no product answers. Its candidate-side inputs are designed as C0, but the case was visible before the runnable A/B workflow and profile-builder froze, so it is not eligible for a clean-holdout conclusion. Dataset-authoring review evaluates the case construction rather than answering those choices.

## Product clock

- Mode: `prospective_sealed` at case seal; currently draft.
- Cutoff timestamp: pending dataset-authoring review and seal.
- Commit/tree hash: `25dc9c818400ab66c99650316610b73ca5d2060f`, committed `2026-08-06T23:36:17+08:00`; this raw commit object resolves via `git rev-parse 25dc9c818400ab66c99650316610b73ca5d2060f^{commit}`.
- Seal evidence: the brief and private draft were created before any target implementation or historical gold. P01-A17 records that the pinned tree has no migration capability to reuse as an answer.

## Knowledge clock

- Mode: `prospective_sealed` at the same cutoff.
- Included audit authorities: P01-A01 through P01-A17 in `knowledge/authority-map.json`, all checked against the pinned clean tree without semantic additions. The map is owner/judge-only and is not candidate-visible.
- Excluded future material: local dirty files; this case's private judge and audit layers; future code, branches, issues, PRs, owner answers, and conversations that derive a migration solution.
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
- Stable-profile evidence-ledger hash: pending seal. D07 and D16 must each trace to pre-P01, cross-case user evidence; an authoring suggestion or the public brief cannot establish a `P`, and any entry without that lineage is removed before freezing.
- Allowed stable preferences: complete but restrained scope; inspect the current system and fix the owning seam; demand real evidence; put facts before conclusions; investigate lookup-answerable facts instead of asking; escalate true value forks and conditional hard red lines; validate important behavior through an isolated real journey rather than only mocks or documentation.
- Cross-fit exclusions: every P01-specific device, entity, migration answer, algorithm, threshold, data policy, UI placement, and owner response listed in `decision-inventory.json`.
- Resulting profile hash: pending runtime materialization as `runtime/candidate-inputs/P01/USER.cross-fitted.md`.
- P-evidence rule: every `P` oracle is supported only by the exact hashed runtime profile. If the cited preference is absent there, the runner fails dataset validation; brief text, repository facts, or an arm recommendation cannot substitute.

The inventory contains 16 decisions: 7 `F`, 2 `P`, 3 `V`, and 4 conditional `H`. Seven entries need a private response only as specified below; the two `P` entries are independently supported by the cross-fitted profile and do not answer any product fork.

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
- Workflow-derived candidate exposure: none until frozen bundles are injected per arm; no bundle may include P01 atoms or oracle language.
- Profile-derived candidate exposure: generic stable preferences only, cross-fitted to remove all P01 lineages.
- Common/normalizer-derived candidate exposure: the same task-blind treatment scrub plus N0 identity export for every case and arm; the private authority map cannot select or highlight files.
- Private oracle lineage: `prospective_pre_output`; the case-specific inventory/rubric may derive from this sealed brief and pinned facts, but must be frozen before any arm output and never enter generic judge calibration, few-shot, or candidate input.
- Answer-derived exposure: the blinded response bank remains withheld until that run's initial and refined packages are frozen; only a decision actually surfaced in the refined package can receive its matching pre-sealed response. The bank is never part of the workspace, profile, refinement signal, or another case.
- USER-learning exposure: any post-answer profile candidate and micro-delta live in an isolated secondary-probe namespace. They never alter P01 arm bundles, P02 inputs, the baseline cross-fitted profile, or the primary verdict.

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
| P01-A01 | `SPEC.md:24-85,132-160` | IM, per-machine Gateway, in-process Kernel boundaries | migration protocol or UI |
| P01-A02 | `docs/specs/im/agents-nodes.md:146-159` | Agent creation on one bound online node with a workspace | existing migration behavior |
| P01-A03 | `docs/specs/im/agents-nodes.md:181-212` | register seeding and ordinary workspace immutability | whether an explicit migration exception should exist |
| P01-A04 | `docs/specs/im/agents-nodes.md:253-274` | same-owner idempotency and cross-owner rejection | same-owner Agent migration |
| P01-A05 | `docs/specs/gateway/service-lifecycle.md:62-100` | local runtime roots and workspace RPC ownership | a sufficient transfer set |
| P01-A06 | `docs/specs/kernel/context-persistence.md:60-76` | per-workspace JSONL recovery after restart | live in-flight transfer |
| P01-A07 | `docs/specs/gateway/routing-delivery.md:249-275` | persistent session bindings and applied runtime identity | copy versus reconstruction |
| P01-A08 | `src/agent/core/memory/path.py:1-29` | memory path derivation under workspace/product config | all arbitrary workspace content |
| P01-A09 | `docs/specs/kernel/skills.md:117-133` | workspace skills in preview/list/runtime resolution | moving global skills |
| P01-A10 | `docs/specs/gateway/heartbeat-cron.md:14-95` | heartbeat/cron context, history, and missed-run semantics | cancellation authority at cutover |
| P01-A11 | `docs/specs/im/agents-nodes.md:317-399` | node-sealed credentials, desired/actual state, offline and stale-report behavior | cross-node credential transfer |
| P01-A12 | `docs/specs/gateway/external-channels.md:274-337` | encrypted local cache, listener ownership, IM history retention | target decryptability of source ciphertext |
| P01-A13 | `src/IM/application/config_service.py:77-135,169-225` | one-node creation and ordinary-update omissions | future migration API shape |
| P01-A14 | `tests/im_service/integration/test_account_binding_api.py:89-145` | executable tenancy guards | migration behavior |
| P01-A15 | `tests/unit/personal_assistant/test_persistent_session_binding_store.py:253-269` | binding persistence across store reconstruction | portable binding storage |
| P01-A16 | `tests/unit/personal_assistant/test_feishu_worker_runtime.py:181-207` | listener death with owning Gateway | acceptable cutover downtime |
| P01-A17 | pinned Agent/Node routes and current specs | absence of a committed migration path | any preferred new design |

## Direct observations, synthesis, and value judgments

- **Direct observation:** Agent placement, session persistence, workspace memory/skills, heartbeat/cron, session bindings, and channel runtime ownership live in different current owners.
- **Synthesis:** `AgentProfile + directory copy` cannot close the user journey because the direct sources expose durable and runtime state outside either one. This is a cross-source inference, not a quotation.
- **Synthesis:** the public no-dual-active requirement plus asynchronous desired/actual and stale-report behavior requires an authority/fencing invariant. The evidence does not choose token, epoch, lease, or database mechanics.
- **Value judgment pending owner:** product entry, workspace scope/collision policy, and health/downtime/rollback are unconditional product forks. Cancellation, cross-node secret transfer, unverifiable recovery, and destructive cleanup are conditional hard-red-line gates only if a proposal activates their predicates.

## Private response bank required before confirmatory runs

Unconditional product choices:

- D09: migration entry and supervision IA.
- D10: workspace scope, target path, and collision policy.
- D13: target health gates, interruption budget, and rollback trigger.

Conditional hard-red-line gates; no owner question is needed when the arm keeps the recorded safe baseline:

- D11: activated only if cutover would cancel or discard non-idle work instead of waiting or blocking.
- D12: activated only if the design would create cross-node credential transfer/rewrap instead of secure re-entry or established re-authorization.
- D14: activated only if the design would cut over from incomplete, stale, or unverifiable state instead of blocking.
- D15: activated only if the design would automatically delete, irreversibly invalidate, or expire source data instead of fencing and retaining it.

All seven items remain `owner_review_required` during authoring because the neutral response bank has not been sealed and no arm predicate outcome has been observed. For H items, that status means “private owner response replayed if activated,” while a false predicate uses `inactive_safe_behavior` without interruption. Arm recommendations never become answers.
