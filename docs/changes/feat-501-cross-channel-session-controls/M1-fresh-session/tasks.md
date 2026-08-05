# M1: Fresh session

## Scope

Implement `/new` through the shared Gateway inbound path.  It must create and
publish a fresh Kernel binding without deleting history, and suppress output
from any superseded run after the success confirmation.

## Testing strategy

- Unit-test exact command parsing and the group mention rule in the shared
  inbound pipeline.
- Unit-test coordinator and binder transitions, duplicate ingress handling,
  queued-work invalidation, and running-output suppression.
- Exercise the existing Web relay and Feishu shadow paths with their focused
  integration tests after the unit tests pass.

## Progress

- [x] Baseline: 118 focused Gateway and compaction tests pass on
  `ed814849c7ccbcc565e0feebef41096dd73935e4`.
- [x] Add focused M1 coverage.
- [x] Implement and validate M1.
- [x] Prove external `/new` outcomes survive a pre-materialization restart and an
  external-channel-ready recovery without depending on IM connectivity.
- [x] Recheck the real Web IM private and MENTION-group journeys.
