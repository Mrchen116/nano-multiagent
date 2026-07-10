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
- Commits: C1=`562334ae`, C2=`f39e47f6`, C3=`6a073b5c`.
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
- Commits: C1=`fe6871d8`, C2=`67bbb7da`, C3=`7515bccc`.
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
- Commits: C1=`e4f05c3e`, C2=`e81589ea`, C3=`43d54334`.
- Next: R4 gates and live-critical verification.

## R4 — Gates and live-critical verification

- Context: R4 is the milestone closeout gate. During takeover, the pending diff also exposed a private runtime protocol metadata leak into persisted/public `ReplyContext` metadata when typed runtime facts were attached to inbound messages.
- Decision: Keep `RuntimeProtocolFacts` private to the Gateway runtime boundary by stripping the private metadata key when building `ReplyContext` and when serializing a binding to SQLite. Verified the live-critical subset with repo `.venv` first on `PATH`, because the e2e shell scripts use `python3` fallback snippets that otherwise hit the macOS system interpreter without PyYAML. The final unit branch gate exposed one stale attachment test that still expected `WebRelayAdapter.accept_relay()` to return the callback `InboundMessage`; the M1 contract is now `InboundEnvelope`, so the test was updated to assert `inbound.message is received[0]`.
- Rationale: Runtime protocol facts carry delivery internals for typed handoff; persisted session reply contexts should retain only public channel metadata. The live-critical evidence must use true IM + Gateway processes and must state caveats instead of converting missing external credentials or known xfail paths into false green evidence.
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_persistent_session_binding_store.py` -> 18 passed. `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check src/personal_assistant/gateway/runtime_protocol.py src/personal_assistant/gateway/session_keys.py tests/unit/personal_assistant/test_persistent_session_binding_store.py` -> All checks passed. `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py` -> 112 passed, 2 warnings. `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_web_relay_adapter_attachments.py` -> 13 passed. `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` in `unit/refactor-454` -> 3325 passed, 2 skipped, 22 deselected, 16 warnings.
  - Entry: `env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/refactor-454-M2/src python -m pytest tests/e2e/critical_paths/test_tool_call_reply_critical_path.py tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py tests/e2e/critical_paths/test_cron_push_critical_path.py -ra` -> 3 passed in 56.92s. This covers Web IM trigger through real IM/Gateway to `message.completed`, Gateway restart session continuity, and cron owner-direct push back to the IM direct conversation.
  - Entry: `env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/refactor-454-M2/src python -m pytest tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py -ra` -> 1 passed in 22.10s. This covers IM restart/reconnect and Gateway-starts-before-IM recovery to node online.
  - Entry caveat: `env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/refactor-454-M2/src python -m pytest tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py -ra --timeout=240` -> 1 xfailed in 185.65s, matching the repository's tracked heartbeat active-bubble product bug #126. This is not claimed as green evidence.
  - Entry caveat: Feishu/Lark true-platform journeys were not run because this isolated stack has no verified Feishu/Lark channel credentials; no fake inbound was used.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A; this milestone does not change the frontend client surface. The Web IM evidence above uses the same HTTP/WS backend entrypoints and observes protocol-visible completed messages.
  - E2E/Regression: `test_build_reply_context_strips_private_runtime_protocol_metadata` and `test_bind_strips_existing_private_runtime_protocol_metadata` are permanent regressions for private runtime metadata not leaking into public/persisted reply contexts.
  - Visual/Interaction: N/A.
- Rollback: Revert `671b47b8` and `19e65dcf` for the metadata fix; revert R1/R2/R3 commits listed above for the runtime delivery extraction.
- Commits: C1=`19e65dcf`, C2=`671b47b8`, C3=`8afb80d5`, unit-gate-fix=`b184159e`.
- Next: M2 complete; push `unit/refactor-454`, release the unit lock, then remove the milestone worktree/branch.
