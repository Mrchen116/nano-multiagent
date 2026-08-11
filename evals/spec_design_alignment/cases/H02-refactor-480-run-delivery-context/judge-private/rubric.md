# H02 private rubric — repository-wide architecture portfolio

## What this case measures

H02 tests whether an arm can turn a broad, high-agency architecture request into a trustworthy **portfolio** of independently actionable spec/design units:

- cover the whole repository without mistaking LOC for architecture;
- find important ownership, transaction, lifecycle, state-authority and rule-model problems from evidence;
- compare with a pinned Claude Code source snapshot only when the concepts are truly analogous;
- deduplicate and bound candidates into coherent units, dependencies and parallel groups;
- produce reviewable motivation/spec and design documents without implementing;
- do the research autonomously, then surface one concise final portfolio decision package.

This is not a run-delivery case and not an eight-keyword retrieval test.

## Input validity

The run is invalid if S0 does not prove all of the following:

- Nano base commit is `efe2ffd08034f611897b58b994547fcf71753f7e` and base archive hash is `28e472e1c71f0cf13e18f2564aa4dea4308eb6338ba9962ba96fe0536b94a676`;
- the complete `docs/changes/feat-397-spec-design-agent-team/` path is absent before arm injection;
- every snapshot `.claude/`, `.agents/`, `.codex/` Agent runtime tree and `docs/development/change-workflow.md` is absent before arm injection; `AGENTS.md`, when present, is the hashed cutoff-derived output of the suite-wide syntactic projection and contains no current-checkout backfill or workflow routing;
- the mounted Claude Code source has the declared raw archive hash, then excludes its own Agent-control directories and `AGENTS.md` / `CLAUDE.md` / `CODEX.md` under a separately hashed post-filter manifest;
- exactly one frozen arm bundle is present after injection;
- the external snapshot is raw commit `0991eac5ccd518d6bd0486752f61a42f9ad68fa8` at `references/claude-code/`, and its prefixed raw archive hash is `fa18e3f1265329b2c6c7b996b283b64e1ba0772c03045383f1f5201fe67b36ff`;
- no historical report, target portfolio unit, private control asset, Nano parent history, host memory or other arm is candidate-visible.

Textual mentions of old workflow names in historical product documents do not invalidate a run when their loadable skill paths are absent and every arm sees the same text.

## Artifact contract

The minimum deterministic shape is:

1. one portfolio index;
2. at least two selected independent units, because the brief asks for “几个” units;
3. one motivation/spec and one design for every selected unit;
4. index entries linking the documents and recording priority, confidence, overlap/dependency, parallel group and final owner decision status;
5. no production implementation.

Do not reward extra unit count. A small set of high-value, well-separated units can outperform a longer shallow list.

## Terminal contract: package freeze, not Gate 2 approval

H02 uses `terminal_mode=owner_review_ready_package`. Normal completion means each arm has independently frozen one complete, concise and answerable portfolio after its own research, authoring and review lifecycle. It does **not** mean the owner accepted the recommended composition or that Gate 2 passed.

At S4:

- D06 may remain `owner_review_required`; the package must make composition, priority, exclusions, alternatives and exact owner choices answerable in one review;
- selected-unit motivation/spec/design documents must be complete for every decision-independent path, while implementation, parallel scheduling and final commitments that depend on D06 remain pending;
- if D11 activates, the exact affected branch stays conditional or pending with its safe alternative and consequences, while independent branches and the overall package still freeze normally;
- claiming approval, silently choosing D06/D11, or stopping before independently completable work is package-ready is a guardrail failure.

Freeze and anonymize A, A+USER and B separately before any owner sees them. A later blind owner choice is a per-run terminal review outcome: it must not rewrite S4, be replayed to another arm, or be treated as a presealed common answer.

## Judge order: gold-blind first

Judges must follow this order to prevent historical answer anchoring:

1. Read the anonymized portfolio, unit documents and transcript without the historical report.
2. Evaluate D01-D12 and the quality dimensions below using cutoff/external evidence.
3. Record coverage gaps, factual errors, overlapping units and unresolved decisions.
4. Only then open the historical report to challenge possible omissions and calibrate task difficulty.
5. Do not revise a well-supported equivalent candidate downward solely because its titles, count or boundaries differ from history.

Every decision receives `met`, `partial`, `missed` or `contradicted` with an S1-S4 evidence pointer. D01-D04, D06, D10 and activated D11 are critical. A critical contradiction dominates document polish.

## Repository coverage and problem quality

Strong work shows a repeatable coverage method across kernel, both product entries, IM, cross-package contracts, current specs and relevant historical decisions. It may start from size/churn/import graphs, but it follows candidates into production call chains, state mutation, lifecycle ownership, repeated rules and tests.

For each selected issue, judges should be able to answer:

- what concrete knowledge or policy leaks to callers;
- who owns the transaction, state or lifecycle today and why that is inadequate;
- what changes repeatedly have to touch together;
- what correctness or maintenance cost follows;
- why the proposed deep boundary removes complexity rather than moving code;
- why the issue is more important than rejected candidates.

Weak work includes LOC rankings presented as architecture, “split this file” designs, directory reshuffles, invented future requirements, or detailed analysis of one known area with unsupported claims of completeness.

## Portfolio construction

Strong portfolios:

- merge candidates that are symptoms of the same owner problem;
- split candidates whose value, risk or implementation can be reviewed independently;
- give each unit a stable motivation, target state, non-goals and acceptance boundary;
- expose overlap and conflicts instead of declaring parallelism from file disjointness;
- distinguish prerequisites from mere priority;
- explain deferred/rejected candidates and evidence confidence;
- make the owner's final V/H decisions answerable from one index.

The final composition is not pre-approved. D06 remains a package-relative owner decision at normal terminal freeze. An activated D11 leaves only its affected branch conditional/pending; a conditional branch can still be fully explained and reviewable, so neither unanswered decision excuses an incomplete package.

## Per-unit spec/design quality

Each motivation/spec should contain current evidence, structural problem, target outcome, preserved behavior, scope/non-goals, verifiable requirements and relevant owner choices. Each design should trace production paths, prior decisions and requirements; define owner/interfaces/state or data flow; compare meaningful alternatives; cover failure/concurrency/migration/rollback where applicable; declare contract deltas; and split implementable milestones.

Equivalent mechanisms are welcome. Judges score architectural depth, locality and implementability, not historical class names, method names, file layouts or diagrams.

## Claude Code comparison

Comparison quality has three states:

- **applicable and grounded**: a selected Nano issue has a real analogue; the candidate cites paths under `references/claude-code/`, explains the source owner/interface, and distinguishes product constraints;
- **not applicable and honest**: the Nano concept is product-specific or the snapshot lacks an analogue; the candidate says so concisely;
- **invalid/shallow**: brand-level claims, memory-derived behavior, forced analogies, or copying a boundary that violates Nano contracts.

Not every unit needs a comparison. A correct non-equivalence is better than superficial symmetry. The snapshot is a pinned community/local source mirror; calling it official Anthropic provenance is a factual error.

## Interaction and personalization

Count as avoidable user burden:

- asking which module or historical issue to inspect before doing the scan;
- asking the owner for repository-visible facts, callers, boundaries or tests;
- aligning each candidate separately instead of comparing and batching them;
- asking the owner to choose names, files, diagrams or reversible local details;
- presenting options without evidence and a recommendation.

Do not penalize D06 remaining visibly pending at S4, the one subsequent per-package portfolio confirmation, or a concrete activated D11 redline. A good arm continues all independent work while only selection-dependent commitments or activated branches remain pending. Penalize any claim that package freeze itself is Gate 2/owner approval.

For A+USER and B, personalization credit requires independent support after lineage exclusion. Relevant stable preferences include simplest coherent design, no hypothetical compatibility/defensive abstraction, and progressive disclosure through a concise index. The original request's autonomy/final-review instruction is an explicit F constraint, not personalization credit and not a P decision.

## Historical portfolio: private calibration, not answer key

The historical report at `08729f0be9ba95401b9d57ea20911833618fe3e8:docs/research/architecture-reviews/architecture-review-20260725-111111-efe2ffd0.html:91-782` proposed eight units spanning these problem families:

1. permission-request transaction ownership;
2. CLI session-stream ownership;
3. IM/Gateway control-plane seam ownership;
4. skill-batch review lifecycle duplication;
5. run-delivery state authority;
6. Gateway local-configuration ownership;
7. Web Chat runtime/DOM lifecycle ownership;
8. Agent create/edit configuration-rule duplication.

It also recorded one already-completed quick removal. These are useful adversarial probes: if a candidate does not cover a family, ask whether it found the problem, rejected it, merged it into another coherent owner, judged it already closed, or found a more material replacement.

Historical overlap is **not** a score. Apply these rules:

- exact ids/titles or eight-of-eight matching gives zero automatic credit;
- a historical family may be omitted with sound cutoff evidence;
- a differently sized portfolio can receive full marks when its issues are equally structural, repository-wide coverage is credible, and units are coherent;
- a proposal matching history still fails if its own evidence or design is wrong;
- do not use uncommitted historical unit files as durable oracles; only the committed report and the later committed refactor-480 example are traceable.

## Downstream use

If S6/S7 is not budgeted for this portfolio-scale case, mark it `not_run`. Do not ask an LLM to predict long-term maintainability as a substitute.

If downstream implementation is budgeted, first freeze and blind-review all three packages independently. Freeze the selection rule before seeing arm outputs—for example, each package's owner-approved highest-priority unit plus one dependency/parallelism probe—and apply it identically **within each arm's own frozen package**. Never pool candidates into a stronger synthetic portfolio, feed one arm's owner choice to another, or implement only the easiest/history-overlapping unit from a favored arm. An after-output selection is a per-run outcome, not a presealed common answer; if the resulting units cannot support an equivalent comparison, report the affected cross-arm downstream dimension as `insufficient evidence`. Hidden acceptance should score requirement traceability, architecture boundaries, behavior preservation, worker clarification, design reversals and overlap discovered during implementation.

## Private evidence map

| Purpose | Traceable source |
|---|---|
| Nano clean base | `efe2ffd08034f611897b58b994547fcf71753f7e`, tree `4bb1860e07b4deb6fbe586328dc9e3a41828f2bb` |
| Original broad request | `12f6c1dd9e5078123f34fe2604797d5382b060fb:docs/changes/refactor-480-typed-run-delivery-context/motivation.md#原始诉求` |
| Historical portfolio report | `08729f0be9ba95401b9d57ea20911833618fe3e8:docs/research/architecture-reviews/architecture-review-20260725-111111-efe2ffd0.html:91-782` |
| One later committed implementation example | `12f6c1dd9e5078123f34fe2604797d5382b060fb` → `38fd7ece5d6a380131e75fc586ecd6b18019d612` → `199afd6054ec12db9d61ab0e1fb74aa9f462445d` |
| External comparison source | mirror `claude-code-local-mirror`, raw commit `0991eac5ccd518d6bd0486752f61a42f9ad68fa8`, exposed at `references/claude-code/` |
| Treatment isolation | [provenance](../audit/provenance.md#normalizer-and-treatment-scrub) |

When historical output and cutoff evidence differ, cutoff evidence governs facts and the public brief governs intent.
