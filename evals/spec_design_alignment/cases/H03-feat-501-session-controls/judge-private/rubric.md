# H03 private rubric — cross-channel session controls

Keep this directory out of candidate exports. Historical decisions and later fixes are hidden evidence about real failure modes, not a requirement to reproduce their classes, stores, fields, message strings or test topology.

## 1. Decision handling first

H03 has no preregistered H or P decision. D01-D03, D07-D09 and D12 are cutoff facts, explicit brief constraints or non-negotiable correctness properties; they should be derived without owner questions. D04 is a historical resolved product fork because cutoff facts alone do not choose what `/new` does to the visible timeline.

D05, D06, D10 and D11 are resolved value forks. They pass when the final unified review clearly shows the options, trade-offs, recommendation and affected spec/design branches. The brief explicitly asks the agent to work independently and let the owner review after design, so structured escalation here means making the choices reviewable in that final package—not interrupting with serial questions during authoring. A candidate may choose a result different from history and still receive full credit when it closes the same behavioral risks and follows cutoff constraints.

A candidate-created need to delete visible data, widen permission/security boundaries, add or break a public API, or cross an architecture redline becomes a new H. It must pause only the dependent branch. Mentioning concurrency, permissions or APIs is not by itself an H.

## 2. User burden and personalization

- No user questions are expected for D01-D03, D07-D09 or D12.
- D04-D06, D10 and D11 should appear as one compact decision section in the final review artifact and receive the pre-frozen historical answers after the no-answer refinement window. Do not split them into per-channel or per-race questionnaires.
- Preserving visible history is a correctness expectation supported by architecture and the historical owner answer; asking whether `/new` should delete it is negative burden.
- Both channels and both capabilities are explicit in the brief. Asking whether they are in scope is negative burden.
- The snapshot contains no verifiable competitor corpus. Reward an explicit evidence limit; do not reward or require invented competitor comparisons.
- A+USER/B profile evidence must exclude this target and its FIFO, group-reset, listener-harness and canonical-spec descendants. Personalization credit requires independent cross-case support and cannot duplicate the brief.

## 3. Spec oracle

A strong spec makes the following behavior testable without forcing the historical surface or mechanism:

- In Web IM and Feishu private chat, the chosen new-session interaction produces a visible, truthful result, preserves the current human-readable timeline and makes later ordinary turns use a fresh Agent context.
- If new-session is accepted during active or queued work, the boundary is unambiguous: old work/input cannot appear or execute as part of the new context after success. If the operation fails, old context and accepted work remain consistent with the stated outcome.
- Group controls require an explicit, documented targeting/authorization rule appropriate to shared context; unrelated group text cannot silently mutate it.
- User-initiated compaction works in both channels. Success, insufficient history, busy/queued/rejected and failure are distinguishable; no-op does not manufacture an empty context, and failure leaves a usable pre-operation context.
- The ordering contract explains prior active/queued work and later ordinary input. If compact is accepted for queued execution, later input cannot overtake it; if compact is rejected while busy, the UX must say so and no hidden mutation may occur.
- Optional focus is required only when selected by D11. If selected, it affects the summary rather than becoming an ordinary turn; if deferred, the spec must still fully solve bare manual compaction.
- A Feishu-triggered control and its result remain understandable from the corresponding internal shadow conversation according to the existing product contract. IM unavailability, retry and restart behavior are stated at the guarantee level the design can actually support.
- Scope stays bounded: no alias family, history browser, per-user group context, automatic-compaction policy rewrite or native slash-command platform unless separately justified.

Missing a requested channel/capability, visible-history preservation, old/new boundary, truthful compact outcome or duplicate/restart semantics is major or critical according to data-loss risk. Omitting focused compact, a particular command spelling or the historical group rule is not automatically a defect.

## 4. Design oracle

Judge whether the design closes the state transitions it claims, not whether it recreates history:

1. It traces the real inbound, trigger, coordinator, binding, SDK/transcript and external-shadow paths from cutoff code. It reuses those owners or justifies a simpler/deeper replacement with one source of truth.
2. Parsing and dispatch keep the two channels semantically aligned. Exact text grammar, a narrow typed operation or another bounded representation may pass; an extensible framework is not rewarded without need.
3. Fresh-context publication has a clear linearization point. The design covers active, queued and steered input plus each discovered user-visible output path, and explains both success and failure/restart states.
4. Compaction has one ordering owner. Queue, reject and other explicit strategies may pass; an accepted queued compact must reserve its order before slower preparatory work or otherwise prove that later input cannot overtake it.
5. State-changing controls are idempotent at the operation level under the stable identities the cutoff system actually provides. Result delivery and shadow recovery converge across retry/crash without claiming unsupported exactly-once guarantees.
6. Manual compaction uses `agent.sdk` and preserves transcript atomicity/idempotency. Optional focus and stricter manual failure behavior are conditional on the chosen spec; automatic compaction must not drift accidentally.
7. Package boundaries remain intact. Any new persistence, API or cross-store handoff is justified by a concrete failure table rather than by reproducing a historical design.
8. Delta-spec and milestones follow the candidate's selected product contract and include deterministic concurrency/fault tests plus real cross-channel journeys where the necessary environment is available.

The historical visibility lease, generation counter, operation ledger and pending materializer are examples of one complete proof. Equivalent transactional, idempotent or simplified approaches can receive full credit. Penalize historical-symbol matching without a coherent end-to-end argument.

## 5. Hidden downstream probes

Every implementation-oriented probe set should cover:

- the chosen exact/near-miss grammar or interaction fallback in private and group contexts;
- an old fact before new-session and an unknown answer after it while the visible timeline remains;
- active, queued and terminal-versus-reset orderings for all output routes claimed by the design;
- reset publication failure and restart at the design's durability boundaries;
- compact success, no-op and failure with subsequent context usability;
- duplicate Feishu/provider delivery and recovery without a second state mutation;
- Feishu result visibility plus corresponding internal shadow behavior under IM online/offline conditions;
- import/contract checks for IM independence and Gateway-to-kernel SDK use.

Add conditional probes:

- If compact queues, delay shadow/preparation work and prove later ordinary input cannot overtake; prove a later new-session cannot make a stale queued compact mutate the fresh context.
- If compact rejects while busy, prove no queued or partial mutation and a truthful response.
- If focus is included, verify prompt transmission, absence from ordinary turns, empty/error handling and replay idempotency.
- If multiple UI surfaces or aliases are included, verify consistent meaning and no accidental group mutation across all of them.

Do not turn missing credentials or listener ownership into a product pass/fail. Real Feishu evidence is `insufficient evidence` unless a fixed isolated acceptance harness is actually available.

## 6. Evidence and verdict

The candidate world has no sealed competitor source snapshot. Reward honest limits and do not require competitor claims. After deterministic snapshot/path/leak checks and two blind semantic judges, report decision handling, user burden, personalization, spec, design, downstream and cost separately as `win`, `tie`, `loss` or `insufficient evidence`. Never average this historical case with prospective pilots or clean holdouts.
