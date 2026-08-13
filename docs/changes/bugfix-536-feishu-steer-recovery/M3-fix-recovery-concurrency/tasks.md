# bugfix-536-M3: recovery successor closure race

> Align: `../incident.md`, approved `../design.md`, `../design-review.md`, and the
> three approved delta-specs. This targeted fix changes no public contract.

## Goal

Close the failed-adopted-successor race reported after M2. A normal message
accepted immediately before failed-successor cleanup must either enter a valid
re-handoff or receive one terminal lifecycle; it must never be removed from the
follower ledger without settlement.

## Exit criteria

- [ ] Linearize the unconsumed-suffix decision and terminal successor close under
  the session transition owner.
- [ ] Preserve re-handoff when an unconsumed suffix already exists; preserve
  normal same-run steering and explicit control/shutdown fences.
- [ ] Add a deterministic regression that holds dispatch preparation inside the
  transition lock, accepts a concurrent follower, and proves exactly-one
  terminal lifecycle, released busy state, and a following normal reply.
- [ ] Run focused recovery tests, the M1/M2 aggregate, static/doc checks, and a
  relevant isolated Gateway/Web IM public-path smoke.

## Plan

| Step | Status | Evidence |
|---|---|---|
| R1 — establish baseline and lock ownership | done | `progress.md` R1 |
| R2 — implement owner-level atomic closure and regression | doing | pending |
| R3 — validate, integrate, and clean isolated runtime/worktree | todo | pending |
