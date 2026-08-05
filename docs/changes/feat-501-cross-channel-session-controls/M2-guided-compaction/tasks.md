# M2: Guided compaction

## Scope

Implement `/compact` and `/compact <focus>` through the same Gateway pipeline.
Manual compaction must remain an SDK operation, preserve the current session on
failure, and use the inbound replay identity exactly once.

## Testing strategy

- Unit-test exact command parsing, no-binding no-op, focus forwarding, busy
  rejection, and replayed Gateway operations.
- Unit-test strict manual summarization and persisted transcript replay data.
- Run existing SDK, conversation, and compaction integration suites to prove
  automatic compaction keeps its former fallback behavior.

## Progress

- [x] Add focused command, summary, transcript, and coordinator tests.
- [x] Implement and validate M2 focused suites.
- [x] Prove empty/error summaries, mid-commit durable failure, and restart replay
  preserve the pre-compaction context or return the first committed result.
