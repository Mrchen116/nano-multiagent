# M1 runtime and Gateway implementation record

## Scope

This branch implements the feat-514 Agent SDK/provider and Personal Assistant
Gateway half of M1. It intentionally excludes the IM package, Web frontend, and
production configuration.

## Delivered

- Parsed the per-model absent/fixed/selectable reasoning schema and projected
  only its safe public descriptor.
- Added `reasoning_effort` to Agent config and complete session runtime identity,
  persistence, fork, reconfigure, and normal LLM requests. Hook/approval requests
  retain their independent request shape.
- Merged registered static model request bodies in both provider clients, then
  rendered dynamic Anthropic `output_config.effort` or OpenAI-compatible
  `reasoning_effort` with request-time precedence.
- Added durable Gateway create/apply write-ahead receipts, expected-previous CAS,
  idempotent workspace/config/live convergence, operation status recovery, and
  WebSocket RPC dispatch for create/apply/status.
- Kept the cross-package operation fingerprint aligned with the IM owner: SHA-256
  over canonical JSON for the Gateway-owned Agent fields, with canonicalized
  `heartbeat_json` and no description, secret, or provider request body.

## Verification

- 298 focused unit, contract, and integration tests passed, including both
  provider packet shapes, runtime round trips, config schema/projection, create
  and apply recovery at all four persistent boundaries, operation replay/CAS,
  and WebSocket create/apply/status handling.
- `ruff check src tests`, repository `scripts/docs-check`, and
  `git diff --check` passed before the implementation commit.
