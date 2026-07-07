# refactor-454-M2 — Progress

## Baseline

- Context: M2 begins from `origin/unit/refactor-454` at `113b4332`, after M1 landed the IM/Gateway protocol boundary, `InboundEnvelope` runtime facts, and workspace local-wins resolver.
- Decision: Run the exact seven-file gate from the派发包 before writing red tests.
- Rationale: Runtime delivery touches live-critical Gateway/IM behavior; a green baseline is required before attributing any later failure to this milestone.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py` -> 106 passed, 2 warnings.
  - Entry: Existing unit/integration gate includes Gateway websocket API and FK-enforced heartbeat IM delivery paths; no long-running live stack started yet.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing regression suite above is the starting safety net.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: planning commit pending.
- Next: R1 typed run delivery context and lifecycle.

## R1 — Typed run delivery context and lifecycle

- Context: M2 needs `RunDeliveryTarget(shadow|owner_direct|none)` before the observer can be moved out of `main.py`. The existing lifecycle callback seeded a raw `dict[str, str]`, which made owner proactive runs and external shadow delivery look like the same shape.
- Decision: Added `personal_assistant.gateway.runtime_delivery.context` with `RunDeliveryTarget`, `OwnerDirectTarget`, `RunDeliveryContext`, and `RunDeliveryContextStore`. Relay accepted lifecycle can now seed typed context while exposing a legacy dict view for the still-unmoved observer; completed/failed/cancelled discard removes both typed and legacy entries. Existing dict callers remain compatible until R2/R3 move the observer and wiring.
- Rationale: The store gives R2 a typed owner for run context without forcing a risky all-at-once observer rewrite. The explicit `owner_direct` variant keeps heartbeat/cron lazy direct delivery separate from `ShadowConversationRef`, matching design decision 3.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> 22 passed, 2 warnings. `ruff check src/personal_assistant/gateway/runtime_delivery src/personal_assistant/main.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> All checks passed.
  - Entry: Unit-level Gateway lifecycle callback entry exercised receipt/report compatibility plus new typed seed/cleanup behavior.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: `test_run_delivery_target_distinguishes_shadow_owner_direct_and_none`, `test_relay_lifecycle_seeds_typed_owner_direct_context_and_legacy_view`, and `test_relay_lifecycle_cleanup_removes_typed_and_legacy_context` are permanent regressions.
  - Visual/Interaction: N/A.
- Rollback: Revert `f39e47f6` and `562334ae`.
- Commits: C1=`562334ae`, C2=`f39e47f6`, C3=pending.
- Next: R2 kernel event observer extraction and owner lazy-direct regression.
