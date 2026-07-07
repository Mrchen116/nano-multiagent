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

## R2 — Kernel event observer extraction

- Context: `main.py` still owned the kernel event delivery branch for running placeholders, assistant deltas, tool/permission states, abnormal reconcile, external visible mirror, and heartbeat lazy direct delivery. M2 requires this behavior to live in `runtime_delivery`.
- Decision: Moved ack extraction, bubble rolling, and `_build_kernel_event_observer()` into `personal_assistant.gateway.runtime_delivery.observer`. `main.py` now imports the observer builder and compatibility aliases only; the new observer accepts `RunDeliveryContextStore` and internally consumes its legacy view during the transition. Added owner-direct tests that drive `HEARTBEAT_OK` silence and real-content ack backfill through the new module.
- Rationale: Mechanical movement keeps IM/EventBridge frame semantics unchanged while removing the largest runtime delivery branch from the composition root. The typed-store adapter lets R2 prove owner direct semantics without rewriting every existing observer assertion at once.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/unit/personal_assistant/test_steer_bubble_roll.py` -> 51 passed, 2 warnings. `ruff check src/personal_assistant/gateway/runtime_delivery src/personal_assistant/main.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py` -> All checks passed.
  - Entry: FK-enforced heartbeat IM delivery tests route `turn_start{to_user_id}` through the real IM `GatewayHandler`; external visible delivery tests cover Feishu main-path mirror when IM is absent.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: `test_owner_direct_context_store_suppresses_heartbeat_ok` and `test_owner_direct_context_store_ack_backfills_and_continues_delta` cover owner lazy-direct silence and ack backfill through `runtime_delivery.observer`.
  - Visual/Interaction: N/A.
- Rollback: Revert `67bbb7da` and `fe6871d8`.
- Commits: C1=`fe6871d8`, C2=`67bbb7da`, C3=pending.
- Next: R3 background/session delivery extraction and build wiring.

## R3 — Background/session delivery extraction and build wiring

- Context: After R2, `main.py` still owned background/control visible replies, session-event IM system notifications, reply-context delivery helpers, and the bare runtime context store in `build_runtime()`.
- Decision: Moved background/control reply sender, session-event callback, and reply-context helper functions into `personal_assistant.gateway.runtime_delivery.background`. `build_runtime()` now creates `run_delivery_contexts = RunDeliveryContextStore()` and wires lifecycle/observer through the typed store; heartbeat/cron streaming helpers receive `run_delivery_contexts.legacy_contexts` only at their still-dict-shaped boundary.
- Rationale: Background/control replies follow the same external-vs-shadow-vs-IM delivery rules as runtime events, so they belong with runtime delivery instead of composition root. Keeping legacy dict exposure at heartbeat/cron helper boundaries keeps behavior stable while satisfying the composition-root wiring split.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/unit/personal_assistant/test_steer_bubble_roll.py` -> 52 passed, 2 warnings. `ruff check src/personal_assistant/gateway/runtime_delivery src/personal_assistant/main.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py` -> All checks passed.
  - Entry: External visible delivery tests cover Feishu control/background text to external + shadow IM, IM shadow text staying internal, and session-event notification to shadow IM only.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: `test_build_runtime_wires_typed_delivery_context_store` guards the composition-root wiring; existing external visible tests now import `runtime_delivery.background` directly.
  - Visual/Interaction: N/A.
- Rollback: Revert `e81589ea` and `e4f05c3e`.
- Commits: C1=`e4f05c3e`, C2=`e81589ea`, C3=pending.
- Next: R4 gates and live-critical verification.
