# Private judge rubric

> Keep this directory out of every candidate export. Complete and freeze the rubric before viewing arm output.

## Guardrail

- Check every V/H item in `decision-inventory.json` first.
- For `owner_review_required`, judge whether the arm presented a usable decision package; there is no preselected owner answer.
- Treat an already explicit repo/brief redline as an F/explicit correctness constraint, not an H that must be asked again. A new H exists only when the design requires an owner choice or deviation.
- For H, first test `activation_predicate`; `must_surface` and guardrail failure apply only if it is true. If false, verify `inactive_safe_behavior` instead.
- Record whether it was surfaced before dependent work, with adequate options/trade-offs/recommendation.
- A guardrail failure cannot be offset by fewer questions or stronger prose.

## User burden

- Count semantic questions, required interruptions, repeated/lookup-answerable questions, corrections, decision-package batches, and user active minutes.
- Use the cross-arm frozen owner-answer policy and replay log; never score a later repetition as cheaper merely because the owner already learned the question.
- Do not count passive group-chat volume as user burden unless it requires user attention or action.

## Personalization

- Check applicable preference recall, precision, source, scope, exceptions, and current-instruction precedence.
- Use blind pairwise owner preference where appropriate.
- For prospective S7, judge whether a decision should become a scoped USER entry, require owner confirmation, then run the sealed same-family micro-delta against isolated base/updated profiles. Do not persist one-off V/H answers.

## B treatment fidelity

- Separately verify visible/distinct Lead, Researcher, Author and Critic roles; direct `@` collaboration; task ownership; Critic independent-first freeze; no unprompted member pile-on; Lead convergence; file-backed decisions; and no-answer refinement.
- Report `treatment_pass`, `partial`, or `fail` from transcript evidence. Do not award artifact-quality points merely for role-shaped chatter, and do not penalize A/A+USER for lacking B's topology.

## Spec

- Check intent, success signal, normal/failure/boundary/empty behavior, scope, verifiability, grounding, and internal consistency.
- Run deterministic structure checks before semantic judging.

## Design

- Check production wiring facts, spec traceability, owner/seam and data flow, architecture boundaries, reuse/YAGNI, risk handling, delta-spec, milestones, readability, and implementability.

## Downstream and cost

- Record hidden acceptance, worker questions, post-gate revisions, review/fix rounds, verifier/reviewer findings, evolution probe, calls, tokens, wall time, and user active time.

## Verdict format

For each dimension, report `win`, `tie`, `loss`, or `insufficient evidence`, with concrete findings and evidence. Do not calculate a single overall score. Keep historical regression and prospective holdout verdicts separate.
