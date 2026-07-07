# refactor-454-M4 — Progress

## Baseline

- Context: M4 starts from `origin/unit/refactor-454` at `6e5e409c`, after M3 closed relay lifecycle ownership and typed-store fresh accepted receipt but verifier round-2 still found observer typed-store ownership open.
- Decision: Re-run the full M4/M3 gate before editing, then add typed-store behavioral regressions before changing observer/context.
- Rationale: The blocker is an architecture/behavior state-owner gap hidden behind green compatibility tests. A green baseline prevents mixing pre-existing failures with M4 changes, and red behavior tests prove the typed state itself is currently stale.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 117 passed, 2 warnings.
  - Entry: Gate covers Gateway lifecycle, observer side effects, heartbeat/cron, IM websocket API and main contract; no services started yet.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing unit/integration/contract suite above is the starting safety net.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: plan=`c42514dd`.
- Next: R1 red regressions.

## R1 — Red regressions for typed observer state ownership

- Context: Verifier round-2 found `observer.py` still uses `RunDeliveryContextStore.legacy_contexts` as the runtime owner, so typed `RunDeliveryContext` stays stale after ack/backfill operations.
- Decision: Added behavior regressions in the existing relay lifecycle/observer unit file: typed shadow `turn_start` ack must backfill typed `message_id`; typed owner-direct lazy `turn_start` must backfill typed `conversation_id` / `message_id` / `kernel_message_id` and continue sending delta; typed `roll_bubble()` must update typed `message_id` / `kernel_message_id` and clear rolling state.
- Rationale: These are the exact mutable runtime fields called out by the verifier. The tests drive public observer/roll_bubble behavior instead of only scanning source strings, and keep legacy dict path tests in place as compatibility coverage.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_steer_bubble_roll.py tests/unit/personal_assistant/test_relay_kernel_message_id.py` -> expected red: 3 failed, 36 passed, 2 warnings. Failures were `test_typed_context_store_holds_turn_start_ack_message_id`, `test_typed_owner_direct_lazy_turn_start_backfills_context_and_sends_delta`, and `test_roll_bubble_updates_typed_context_runtime_state`; all failed because typed context/store lacks runtime backfill fields/API.
  - Entry: N/A for red tests; this step proves the production observer state owner gap.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Permanent regressions added in `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`.
  - Visual/Interaction: N/A.
- Rollback: Revert R1 test commit.
- Commits: C1=<pending>.
- Next: R2 typed store implementation.
