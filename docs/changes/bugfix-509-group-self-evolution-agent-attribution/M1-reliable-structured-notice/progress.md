# M1 progress

## Context

- Branch/worktree: `unit/bugfix-509` at latest `origin/main`, isolated under `.worktrees/unit-bugfix-509`.
- Design contract: stable in-process `session_id + sequence`, awaited business ACK, IM profile/node/membership trust, nullable Message sidecar, first-insert `message.created`, exact fork copy.

## Baseline evidence

- Claim: affected Python seams are green before implementation.
  - Baseline: `d7600ca91`.
  - Method: focused pytest across Gateway callback/delivery and IM identity/schema/message/fork/handler/API.
  - Result: PASS, 94 tests; 3 pre-existing dependency deprecation warnings.
  - Limit: no new behavior existed yet; real processes/browser not covered.
- Claim: affected Web IM seams and production build are green before implementation.
  - Baseline: `d7600ca91`.
  - Method: reducer + MessagePane tests, then `npm run build`.
  - Result: PASS, 119 tests and build; pre-existing React `act()` and chunk-size warnings.
  - Limit: no real backend/browser journey.

## Decisions / deviations

- The structured Gateway handler assertion was added beside the existing system-message frame test in `test_background_session_events.py`, not the initially listed IM handler file. This keeps both structured and legacy frame behavior at the same public seam; the contract is unchanged.
- The command runner reaped detached child processes after the startup shell exited. For evidence collection only, the same repository scripts were hosted in named tmux sessions; service configuration and product code were unchanged.

## Evidence / commits

- Red: focused tests failed on the absent callback identity, structured frame, Message sidecar, schema column, API projection and fork copy.
- Green: 111 focused Gateway/IM tests passed with 3 pre-existing dependency deprecation warnings.
- Real stack: IM `64502`, frontend `64635`, Gateway node `wt-unit-bugfix-509-51646`, isolated agents `e2e` and `e2e-peer`.
- A real group turn produced exactly two persisted notices with distinct source snapshots (`E2E Agent`, `E2E Peer Agent`) and stable idempotency keys. Browser reload retained a count of 2 with no duplicate.
- A real direct turn produced skills-only and skills+memory notices. Forking the direct conversation copied the earlier notice snapshot exactly.
- Detailed journey, conversation IDs and screenshots: [`../evidence/README.md`](../evidence/README.md).
