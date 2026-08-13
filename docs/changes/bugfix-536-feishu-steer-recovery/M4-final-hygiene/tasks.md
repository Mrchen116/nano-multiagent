# bugfix-536-M4: final hygiene

> Align: existing M1–M3 implementation and Round 3 verifier suggestions. This
> self-contained closeout changes no runtime behavior or public contract.

## Goal

Make the exact CI formatting corrections, refresh stale liveness documentation,
and complete the M3 test-strategy record without expanding the approved unit.

## Exit criteria

- [ ] Repository Ruff formatter is applied only to the two verifier-named files.
- [ ] `liveness.py` describes all four await-bound windows and lists
  `compaction` among `liveness_ticker` source examples.
- [ ] M3 tasks record the lowest concurrency-test owner and non-duplicate
  disposition of existing recovery tests.
- [ ] Required formatter/lint/focused-test/docs/diff checks pass.

## Plan

| Step | Status | Evidence |
|---|---|---|
| R1 — establish scope and baseline formatter drift | done | `progress.md` R1 |
| R2 — apply mechanical formatting and documentation hygiene | doing | pending |
| R3 — run gates, integrate, and clean worker resources | todo | pending |
