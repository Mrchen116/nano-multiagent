# refactor-454-M1 — Progress

## Baseline

- Context: M1 begins from `origin/unit/refactor-454` at `c948efe4`; main worktree has unrelated dirty files, so all edits happen only in `/Users/czj/Repos/nano-multiagent/.worktrees/refactor-454-M1`.
- Decision: Run the exact five-file gate from the派发包 before writing red tests.
- Rationale: `change-impl-worker` requires a green baseline before adding tests, otherwise new failures would be ambiguous.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/im_service/integration/test_gateway_websocket_api.py` -> 47 passed, 2 warnings.
  - Entry: Local HTTP/WS integration test file included in baseline; no live long-running service was started.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing integration regression suite above.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: planning commit pending.

## R1 — IM gateway protocol fixture/parser

- Context: IM `GatewayHandler` previously parsed `node.report`, `node.streaming_delta`, and `node.delivery_receipt` directly from raw frame dicts. M1 needs an IM-local protocol boundary plus a fixed contract fixture for relay/streaming/receipt/external identity fields.
- Decision: Added `tests/fixtures/gateway_runtime_protocol.json`, extended `tests/im_service/contract/test_gateway_protocol_contract.py`, and introduced `src/IM/ws/gateway_protocol.py` with typed parser dataclasses. `GatewayHandler` now consumes typed events on report/streaming/receipt paths while keeping EventBridge and RelayService as the owners of persistence and broadcast behavior.
- Rationale: Package-local parser keeps IM independent from `personal_assistant`, matches design decision 1, and makes protocol field expectations reviewable without changing user-visible WS ack/error semantics.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/im_service/contract/test_gateway_protocol_contract.py tests/im_service/integration/test_gateway_websocket_api.py` -> 12 passed.
  - Entry: `tests/im_service/integration/test_gateway_websocket_api.py` drives the real IM Gateway websocket entry for register, relay receipt, report, streaming-adjacent receipt chain, and existing node behavior.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Contract fixture covers `relay.message`, `node.streaming_delta`, `node.delivery_receipt`, and `node.report`; WS integration remained green.
  - Visual/Interaction: N/A.
- Rollback: Revert `e1815d62` and `17913629`.
- Commits: C1=`e1815d62`, C2=`17913629`, C3=pending.
- Next: R2 Gateway relay runtime protocol handoff.

## R2 — Gateway relay runtime protocol handoff

- Context: Web relay inbound facts (`relay_task_id`, IM message id, shadow conversation id, external identity) were previously only available as raw `InboundMessage.metadata`; lifecycle and session helpers re-read those keys directly.
- Decision: Added Gateway-local `runtime_protocol.py`, made `WebRelayAdapter.accept_relay()` return `InboundEnvelope(message, protocol)`, attached typed `RuntimeProtocolFacts` to the normalized `InboundMessage`, and moved session key/group/external/lifecycle reads through runtime protocol helpers. The channel callback still receives `InboundMessage`, so non-relay adapters and existing ChannelRegistry wiring remain unchanged.
- Rationale: This gives runtime delivery a typed source for relay facts without changing the generic channel contract or moving M2 lifecycle extraction into M1. The red lifecycle test proves typed protocol facts override stale raw metadata.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> 29 passed, 2 warnings.
  - Entry: Unit-level runtime boundary tests exercise the Web relay adapter entry and lifecycle callback that feeds IM receipts/reports.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: `test_web_relay_adapter_returns_inbound_envelope_with_runtime_protocol` and `test_relay_lifecycle_reads_delivery_facts_from_runtime_protocol` are permanent regression tests for the protocol handoff.
  - Visual/Interaction: N/A.
- Rollback: Revert `920a01a5` and `4f0dd8b8`.
- Commits: C1=`920a01a5`, C2=`4f0dd8b8`, C3=pending.
- Next: R3 workspace authority local-wins.

## R3 — Gateway workspace authority local-wins

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: TODO
  - Visual/Interaction: N/A.
- Rollback: TODO
- Commits: TODO
- Next: Final gate.

## Final Gate

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: TODO
  - Visual/Interaction: N/A.
- Rollback: TODO
- Commits: TODO
- Next: Merge into unit branch.
