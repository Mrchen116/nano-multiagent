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
- Rollback: Revert `50285e1b`.
- Commits: C1=`50285e1b`.
- Next: R2 typed store implementation.

## R2 — Make typed store the observer state surface

- Context: `observer.py` previously converted typed stores into `legacy_contexts` at entry and every ack/backfill path mutated that dict. Typed `RunDeliveryContext` only held seed-time facts, so future typed readers could observe stale `message_id`, resolved `conversation_id`, `kernel_message_id`, rolling and external mirror markers.
- Decision: Made `RunDeliveryContext` own mutable runtime fields and added `RunDeliveryContextStore.runtime_view()` plus typed update/backfill helpers. The runtime view is dict-shaped for the existing observer code, but writes through to typed context and regenerates the legacy projection. `build_kernel_event_observer()` and `roll_bubble()` now fetch per-run runtime views from the original store; nested ack/roll closures also write back through the store instead of closing over a legacy map.
- Rationale: This closes the semantic owner gap while keeping the large observer change small and behavior-preserving. Legacy dict inputs still use the old dict path, and `legacy_contexts` remains a compatibility projection for heartbeat/cron explicit boundaries and existing tests.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_steer_bubble_roll.py tests/unit/personal_assistant/test_relay_kernel_message_id.py` -> 39 passed, 2 warnings.
  - Entry: Unit observer/lifecycle tests drive the Gateway observer entry points and `roll_bubble()` directly; no service process needed for this internal state owner fix.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: R1 regressions now pass and legacy dict path tests still pass.
  - Visual/Interaction: N/A.
- Rollback: Revert `8651c0d9` after reverting `50285e1b` if the regression tests are no longer wanted.
- Commits: C2=`8651c0d9`.
- Next: R3 gate and documentation.

## R3 — Gate, documentation, integration evidence

- Context: M4 touches the observer state owner behind existing user-visible delivery behavior; final evidence must prove both the new regressions and the broader M3/M4 gate remain green.
- Decision: Ran touched-file lint and the full requested M4/M3 gate. Did not run `pytest -m "not e2e"` because touched code stayed within `runtime_delivery/context.py`, `runtime_delivery/observer.py`, the existing observer/lifecycle tests, and milestone docs.
- Rationale: The requested gate covers lifecycle, external visible delivery, IM resilience, heartbeat/cron, IM gateway handler/websocket integration and main contract. No frontend frame shape or user entry changed.
- Evidence:
  - Tests:
    - `ruff check src/personal_assistant/gateway/runtime_delivery/context.py src/personal_assistant/gateway/runtime_delivery/observer.py src/personal_assistant/gateway/runtime_delivery/lifecycle.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_steer_bubble_roll.py tests/unit/personal_assistant/test_relay_kernel_message_id.py tests/contract/test_personal_assistant_main_contract.py` -> All checks passed.
    - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 120 passed, 2 warnings.
  - Entry: The full gate includes IM websocket integration and Gateway observer/lifecycle behavior. No additional live Feishu/Lark entry was run because this worker environment still has no credentialed true-platform channel.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Permanent regressions live in `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`; no one-shot e2e artifact was produced.
  - Visual/Interaction: N/A.
- Rollback: Revert docs commit, `8651c0d9`, and `50285e1b`.
- Commits: C3=<this docs commit>.
- Next: Rebase, merge milestone branch into `unit/refactor-454`, push, then clean worker worktree.

## Caveats

- Feishu/Lark true-platform journeys were not run. No credentialed Feishu/Lark channel was available in this worker environment, and no fake inbound was used.

## R4 — Production heartbeat/cron typed-store wiring gap

- Context: Main-session review after M4 found a production-only gap not covered by the M4 worker gate. `build_runtime()` created the observer with `RunDeliveryContextStore`, but heartbeat/cron still passed `run_delivery_contexts.legacy_contexts` into `_stream_run_to_completion()`. That meant owner-direct heartbeat/cron runs could be seeded into the legacy projection while the typed observer read the typed store and found no run.
- Decision: Keep observer typed ownership intact and move heartbeat/cron stream seeding onto the same typed store. `_stream_run_to_completion()` now accepts `RunDeliveryContextStore`, seeds an owner-direct typed context, and returns the discard-before snapshot as a legacy-shaped dict for existing silent-tick callers. Legacy dict input remains supported for narrow compatibility tests.
- Rationale: Reverting observer to legacy would reopen the verifier round-2 blocker. The root cause is production wiring using two state surfaces; the fix is to make heartbeat/cron use the same typed store as observer.
- Evidence:
  - Red tests before fix: `pytest tests/unit/personal_assistant/test_heartbeat_im_delivery.py::test_stream_run_to_completion_seeds_typed_store_seen_by_observer tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_build_runtime_wires_typed_delivery_context_store` -> expected red: 2 failed. Failures proved typed store could not be seeded by `_stream_run_to_completion()` and `build_runtime()` still passed `.legacy_contexts`.
  - After fix: same command -> 2 passed, 2 warnings.
  - Touched-file lint: `ruff check src/personal_assistant/main.py src/personal_assistant/gateway/runtime_delivery/context.py src/personal_assistant/gateway/runtime_delivery/observer.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> All checks passed.
  - Full M4/M3 gate: `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 121 passed, 2 warnings.
  - Full non-e2e regression: `pytest -m "not e2e"` -> 3332 passed, 2 skipped, 22 deselected, 16 warnings.
- Rollback: Revert the main-session fix commit after `1d1cec26` if this production wiring change needs to be backed out.
